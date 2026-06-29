import json
import logging
import os
import re
from collections import defaultdict
from typing import List, Dict, Any

import requests
from django.conf import settings
from django.core.files.base import ContentFile

from .candidate_model import Candidate
from .chunker import chunk_resume
from .embedder import store_chunks, search_similar_chunks
from .pii_extractor import extract_pii

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CHROMADB HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_chroma_collection():
    """Return the shared ChromaDB collection instance."""
    import chromadb
    client = chromadb.PersistentClient(path=str(settings.CHROMA_DB_PATH))
    return client.get_or_create_collection(name=settings.CHROMA_COLLECTION_NAME)


def delete_candidate_embeddings(candidate_id: int) -> bool:
    try:
        collection = get_chroma_collection()
        collection.delete(where={"candidate_id": str(candidate_id)})
        logger.info("[RAG] [OK] Embeddings deleted for candidate_id=%d", candidate_id)
        return True
    except Exception as exc:
        logger.warning(
            "[RAG] ChromaDB delete failed for candidate_id=%d: %s",
            candidate_id, exc
        )
        return False


def candidate_already_embedded(source_filename: str) -> bool:
    return Candidate.objects.filter(
        source_filename=source_filename,
        is_embedded=True
    ).exists()


# ═══════════════════════════════════════════════════════════════════════════════
# UPLOAD FLOW
# ═══════════════════════════════════════════════════════════════════════════════

def process_resume_upload(
    text: str,
    source_filename: str,
    sharepoint_filename: str = "",
    file_bytes: bytes = b"",
) -> Candidate:
    
    logger.info("[RAG] Processing upload: %s", source_filename)

    # ── Step 1: Extract PII ───────────────────────────────────────────────────
    pii = extract_pii(text, filename_hint=source_filename)
    logger.info(
        "[RAG] PII — name: %s | email: %s | phone: %s",
        pii["name"], pii["email"], pii["phone"]
    )

    # ── Step 2: Save Candidate to normal DB ───────────────────────────────────
    candidate = Candidate.objects.create(
        full_name               = pii["name"],
        email                   = pii["email"],
        phone                   = pii["phone"],
        source_filename         = source_filename,
        sharepoint_filename     = sharepoint_filename or "",
        is_embedded             = False,
        is_posted_to_sharepoint = False,
    )
    logger.info("[RAG] Candidate saved — id=%d", candidate.id)

    # ── Step 3: Save file to disk ─────────────────────────────────────────────
   
    if file_bytes:
        try:
            save_name = sharepoint_filename or source_filename
            resumes_dir = os.path.join(settings.MEDIA_ROOT, 'resumes')
            os.makedirs(resumes_dir, exist_ok=True)
            disk_path = os.path.join(resumes_dir, save_name)

            with open(disk_path, 'wb') as f:
                f.write(file_bytes)

            # Now assign to the FileField using the relative path
            candidate.resume_file = f'resumes/{save_name}'
            candidate.save(update_fields=['resume_file'])
            logger.info("[RAG] [OK] File saved to disk: %s", disk_path)
        except Exception as file_exc:
            logger.error("[RAG] [FAIL] Failed to save file to disk for candidate_id=%d: %s", candidate.id, file_exc)

    else:
        logger.warning("[RAG] No file_bytes provided for %s", source_filename)

    # ── Step 4: Chunk resume ──────────────────────────────────────────────────
    chunks = chunk_resume(
        text            = text,
        candidate_id    = candidate.id,
        source_filename = source_filename,
    )
    logger.info("[RAG] Chunked into %d sections", len(chunks))

    # ── Step 5: Store in ChromaDB ─────────────────────────────────────────────
    if chunks:
        stored = store_chunks(chunks)
        logger.info("[RAG] %d chunks stored in ChromaDB", stored)
    else:
        logger.warning("[RAG] No chunks for %s", source_filename)

    # ── Step 6: Mark embedded ─────────────────────────────────────────────────
    candidate.is_embedded = True
    candidate.save(update_fields=["is_embedded"])

    logger.info("[RAG] [OK] Upload done — candidate_id=%d", candidate.id)  
    return candidate


# ═══════════════════════════════════════════════════════════════════════════════
# SHAREPOINT POST FLOW
# ═══════════════════════════════════════════════════════════════════════════════

def _post_to_sharepoint(candidate: Candidate, skills: str) -> bool:
   
    from .sharepoint_client import (
        upload_resume,
        update_skillset,
        SharePointConfigError,
        SharePointUploadError,
    )

    sp_filename = candidate.sharepoint_filename or candidate.source_filename

    # ── Try reading from FileField first, then direct disk path ──────────────
    file_bytes = b""

    if candidate.resume_file:
        try:
            with candidate.resume_file.open('rb') as f:
                file_bytes = f.read()
        except Exception as e:
            logger.warning("[RAG/SP] FileField read failed: %s", e)

    if not file_bytes:
        # Fallback: read directly from disk path
        direct_path = os.path.join(settings.MEDIA_ROOT, 'resumes', sp_filename)
        if os.path.exists(direct_path):
            try:
                with open(direct_path, 'rb') as f:
                    file_bytes = f.read()
                logger.info("[RAG/SP] Read file directly from disk: %s", direct_path)
            except Exception as e:
                logger.warning("[RAG/SP] Direct disk read failed: %s", e)

    if not file_bytes:
        logger.warning(
            "[RAG/SP] No file found on disk for candidate_id=%d (%s)",
            candidate.id, sp_filename
        )
        return False

    try:
        # ── Step 1: Upload file to SharePoint ─────────────────────────────────
        upload_resume(sp_filename, file_bytes)
        logger.info("[RAG/SP] [OK] Uploaded to SharePoint: %s", sp_filename)

        # ── Step 2: Push skills into SkillSet column (non-fatal) ──────────────
        if skills:
            update_skillset(sp_filename, file_bytes, skills)

        # ── Step 3: Delete file from disk after successful post ────────────────
        try:
            disk_path = os.path.join(settings.MEDIA_ROOT, 'resumes', sp_filename)
            if os.path.exists(disk_path):
                os.remove(disk_path)
            candidate.resume_file             = None
            candidate.is_posted_to_sharepoint = True
            candidate.save(update_fields=["resume_file", "is_posted_to_sharepoint"])
            logger.info("[RAG/SP] File deleted from disk: %s", disk_path)
        except Exception as del_exc:
            logger.warning("[RAG/SP] Could not delete file from disk: %s", del_exc)

        return True

    except SharePointConfigError as exc:
        logger.warning("[RAG/SP] SharePoint not configured: %s", exc)
        return False
    except SharePointUploadError as exc:
        logger.warning(
            "[RAG/SP] Upload failed for candidate_id=%d: %s", candidate.id, exc
        )
        return False
    except Exception as exc:
        logger.warning(
            "[RAG/SP] Unexpected error for candidate_id=%d: %s", candidate.id, exc
        )
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# SCREENING FLOW
# ═══════════════════════════════════════════════════════════════════════════════

def _build_jd_text(job) -> str:
    parts = [
        f"Job Title: {job.title}",
        f"Description: {job.description or ''}",
        f"Role Summary: {job.role_summary or ''}",
        f"Responsibilities: {job.responsibilities or ''}",
        f"Required Skills: {job.required_skills_desc or ''}",
        f"Preferred Skills: {job.preferred_skills or ''}",
        f"Technologies: {job.technologies or ''}",
        f"Experience Required: {job.experience or ''}",
    ]
    try:
        skill_names = ", ".join(s.name for s in job.skills.all())
        if skill_names:
            parts.append(f"Skills: {skill_names}")
    except Exception:
        pass
    return "\n".join(p for p in parts if p.split(": ", 1)[-1].strip())


def _group_chunks_by_candidate(chunks: List[Dict]) -> Dict[str, List[Dict]]:
    grouped = defaultdict(list)
    for chunk in chunks:
        cid = chunk.get("candidate_id", "unknown")
        grouped[cid].append(chunk)
    return dict(grouped)


def _score_candidate_with_llm(job, candidate: Candidate, chunks: List[Dict]) -> Dict[str, Any]:
    sorted_chunks  = sorted(chunks, key=lambda c: c.get("distance", 1.0))
    resume_context = ""
    for chunk in sorted_chunks[:5]:
        section = chunk.get("section", "").upper()
        text    = chunk.get("text", "")
        resume_context += f"\n[{section}]\n{text}\n"

    prompt = f"""You are an expert HR recruiter. Score how well this candidate matches the job.

JOB TITLE: {job.title}
JOB DESCRIPTION: {job.description or ''}
REQUIRED SKILLS: {job.required_skills_desc or ''}
TECHNOLOGIES: {job.technologies or ''}
EXPERIENCE REQUIRED: {job.experience or ''}

CANDIDATE RESUME (most relevant sections):
{resume_context[:2500]}

Respond in JSON only — no markdown:
{{
  "score": <0-100>,
  "reason": "<2-3 sentence explanation>",
  "skills": "<comma-separated skills found in resume>"
}}"""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type" : "application/json",
            },
            json={
                "model"      : "llama-3.3-70b-versatile",
                "max_tokens" : 400,
                "messages"   : [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw  = resp.json()["choices"][0]["message"]["content"].strip()
        raw  = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)
        skills = re.sub(r'[\[\]"\']', "", (data.get("skills") or "")).strip()
        return {
            "score" : int(data.get("score", 0)),
            "reason": data.get("reason", ""),
            "skills": skills,
        }
    except Exception as exc:
        logger.error("[RAG] LLM error for candidate_id=%d: %s", candidate.id, exc)
        return {"score": 0, "reason": f"Scoring error: {exc}", "skills": ""}


def run_rag_screening(
    job,
    request_user,
    top_k: int = 20,
    score_threshold: int = 80,
) -> Dict[str, Any]:
    """
    Full RAG screening pipeline.
    """
    logger.info(
        "[RAG] Screening — job_id=%d threshold=%d%%",
        job.id, score_threshold
    )

    jd_text        = _build_jd_text(job)
    similar_chunks = search_similar_chunks(jd_text, top_k=top_k)

    logger.info("[RAG] ChromaDB returned %d chunks", len(similar_chunks))

    if not similar_chunks:
        return {
            "job_id"                : job.id,
            "job_title"             : job.title,
            "total_candidates_found": 0,
            "total_above_threshold" : 0,
            "score_threshold"       : score_threshold,
            "results"               : [],
            "message"               : "No resumes in vector database. Upload resumes first.",
        }

    grouped = _group_chunks_by_candidate(similar_chunks)
    logger.info("[RAG] %d unique candidates found", len(grouped))

    results = []

    for candidate_id_str, chunks in grouped.items():
        try:
            candidate = Candidate.objects.get(id=int(candidate_id_str))
        except (Candidate.DoesNotExist, ValueError):
            logger.warning("[RAG] Candidate id=%s not in DB", candidate_id_str)
            continue

        llm_result = _score_candidate_with_llm(job, candidate, chunks)
        score      = llm_result["score"]
        reason     = llm_result["reason"]
        skills     = llm_result["skills"]
        best_chunk = min(chunks, key=lambda c: c.get("distance", 1.0))

        result = {
            "candidate_id"       : candidate.id,
            "candidate_name"     : candidate.full_name,
            "candidate_email"    : candidate.email,
            "candidate_phone"    : candidate.phone,
            "source_filename"    : candidate.source_filename,
            "sharepoint_filename": candidate.sharepoint_filename or "",
            "match_score"        : score,
            "reason"             : reason,
            "skills"             : skills,
            "best_section"       : best_chunk.get("section", ""),
            "chunks_matched"     : len(chunks),
            "above_threshold"    : score >= score_threshold,
            "is_shortlisted"     : False,
            "sp_posted"          : False,
        }
        clean_candidate_name = ' '.join(candidate.full_name.split())
        logger.info(
         "[RAG] candidate_id=%d (%s) -> %d%%",
         candidate.id, clean_candidate_name, score
           )
   

        results.append(result)

    results.sort(key=lambda r: r["match_score"], reverse=True)
    logger.info("[RAG] [OK] Scoring done — total=%d", len(results))

    return {
        "job_id"                : job.id,
        "job_title"             : job.title,
        "total_candidates_found": len(results),
        "total_above_threshold" : len([r for r in results if r["above_threshold"]]),
        "score_threshold"       : score_threshold,
        "results"               : results,
    }