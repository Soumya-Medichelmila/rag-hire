"""
recruitment/sharepoint_service.py
─────────────────────────────────────────────────────────────────────────────
SharePoint Resume Screening Service for Smart Recruit.

Workflow per file:
  1. Download file bytes from SharePoint
  2. Write to secure temp file
  3. Extract text (pdfplumber / python-docx / OCR fallback)
  4. Call Groq Llama 3.1 → score + skills + reason + candidate name
  5. Save ScreeningResult in Django DB (source = SHAREPOINT)
  6. Call SharePoint update API → write extracted SkillSet back to SharePoint
     (NON-FATAL: if this fails, screening still succeeds, failure is logged)
  7. Delete temp file

Nothing from SharePoint is permanently stored on disk or in DB as binary.
"""

import json
import logging
import os
import re
import tempfile

import requests
from django.conf import settings

from .models import ScreeningResult
from .serializers import ScreeningResultSerializer
from .sharepoint_client import (
    SharePointAPIError,
    SharePointConfigError,
    SharePointUpdateError,
    download_file,
    get_resume_files,
    update_skillset,
)

logger = logging.getLogger(__name__)


# ── Text Extraction ──────────────────────────────────────────────────────────

def _extract_text_pdf(file_path: str) -> str:
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except Exception as exc:
        logger.warning("[SharePoint/PDF] pdfplumber failed for %s: %s", file_path, exc)

    if not text.strip():
        logger.info("[SharePoint/PDF] No text — attempting OCR: %s", file_path)
        text = _extract_text_ocr(file_path)

    return text


def _extract_text_docx(file_path: str) -> str:
    try:
        import docx
        doc = docx.Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as exc:
        logger.warning("[SharePoint/DOCX] python-docx failed for %s: %s", file_path, exc)
        return ""


def _extract_text_ocr(file_path: str) -> str:
    text = ""
    try:
        import pytesseract
        from pdf2image import convert_from_path

        pytesseract.pytesseract.tesseract_cmd = getattr(
            settings, "TESSERACT_CMD",
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        )
        poppler_path = getattr(
            settings, "POPPLER_PATH",
            r"C:\poppler\poppler-26.02.0\Library\bin",
        )
        pages = convert_from_path(file_path, dpi=300, poppler_path=poppler_path)
        for i, page_img in enumerate(pages):
            page_text = pytesseract.image_to_string(page_img, lang="eng")
            text += page_text + "\n"
            logger.debug("[SharePoint/OCR] Page %d → %d chars", i + 1, len(page_text))
    except Exception as exc:
        logger.warning("[SharePoint/OCR] OCR failed for %s: %s", file_path, exc)
    return text


def _extract_text(file_path: str, ext: str) -> str:
    if ext == ".pdf":
        return _extract_text_pdf(file_path)
    if ext == ".docx":
        return _extract_text_docx(file_path)
    return ""


# ── Email Extraction ─────────────────────────────────────────────────────────

def _extract_email(text: str):
    if not text:
        return None
    match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    return match.group(0) if match else None


# ── Groq Scoring + Skills Extraction ─────────────────────────────────────────

def _score_with_llm(job, candidate_display_name: str, text: str) -> dict:
    """
    Send resume text + job description to Groq Llama 3.3.

    Returns:
    {
        "score":          int (0-100),
        "reason":         str,
        "candidate_name": str,
        "skills":         str  ← NEW: comma-separated skills for SharePoint
    }
    """
    prompt = f"""You are an expert HR recruiter. Analyze this resume against the job.

JOB TITLE: {job.title}
JOB DESCRIPTION: {job.description}

RESUME TEXT:
{text[:3000]}

Extract:
1. How well the resume matches the job (score 0-100)
2. A 2-3 sentence explanation
3. The candidate's full name (if visible)
4. All technical and professional skills mentioned in the resume (comma-separated)

Respond in JSON only — no markdown, no explanation:
{{
  "score": <0-100>,
  "reason": "<2-3 sentence explanation>",
  "name": "<candidate full name or empty string>",
  "skills": "<comma-separated list of skills, e.g. Python, Django, REST API, PostgreSQL>"
}}"""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       "llama-3.3-70b-versatile",
                "max_tokens":  400,
                "messages":    [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw  = resp.json()["choices"][0]["message"]["content"].strip()
        raw  = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)

        skills = (data.get("skills") or "").strip()
        # Sanitise — remove any stray quotes or brackets
        skills = re.sub(r'[\[\]"\']', "", skills).strip()

        return {
            "score":          int(data.get("score", 0)),
            "reason":         data.get("reason", ""),
            "candidate_name": (data.get("name") or "").strip() or candidate_display_name,
            "skills":         skills,
        }

    except Exception as exc:
        logger.error(
            "[SharePoint/LLM] Scoring error for '%s': %s",
            candidate_display_name, exc
        )
        return {
            "score":          0,
            "reason":         f"Screening error: {exc}",
            "candidate_name": candidate_display_name,
            "skills":         "",
        }


# ── SharePoint SkillSet Update (non-fatal) ────────────────────────────────────

def _push_skillset_to_sharepoint(
    file_name: str,
    file_bytes: bytes,
    skills: str,
) -> bool:
    """
    Push extracted skills back to SharePoint SkillSet column.

    NON-FATAL: any failure is logged but does NOT stop the screening pipeline.

    Args:
        file_name:  Original SharePoint filename
        file_bytes: Raw bytes of the file (already downloaded)
        skills:     Comma-separated skills string from AI

    Returns:
        True if update succeeded, False otherwise.
    """
    if not skills:
        logger.info(
            "[SharePoint/Update] No skills extracted for '%s' — skipping update",
            file_name
        )
        return False

    try:
        success = update_skillset(file_name, file_bytes, skills)
        if success:
            logger.info(
                "[SharePoint/Update] ✅ SkillSet pushed for '%s': %s",
                file_name, skills
            )
        else:
            logger.warning(
                "[SharePoint/Update] ⚠ SkillSet update failed for '%s' after retries",
                file_name
            )
        return success

    except SharePointConfigError as exc:
        logger.error(
            "[SharePoint/Update] Config error for '%s': %s",
            file_name, exc
        )
        return False
    except Exception as exc:
        logger.error(
            "[SharePoint/Update] Unexpected error for '%s': %s",
            file_name, exc
        )
        return False


# ── Per-File Processing ───────────────────────────────────────────────────────

def _process_single_file(file_name: str, job, request_user) -> dict | None:
    """
    Full pipeline for one SharePoint resume file:
      download → temp file → extract text → LLM score+skills
      → save DB result → push SkillSet to SharePoint → cleanup temp file

    Returns serialized ScreeningResult dict, or None on hard failure.
    """
    ext          = os.path.splitext(file_name)[1].lower()
    raw_name     = os.path.splitext(file_name)[0]
    display_name = re.sub(r"[_\-]+", " ", raw_name).title()

    # ── Skip if already screened for this job + filename ─────────────────────
    existing = ScreeningResult.objects.filter(
        job_opening=job,
        source_filename=file_name,
        resume_source="SHAREPOINT",
    ).first()
    if existing:
        logger.info("[SharePoint] Already screened: %s — reusing result.", file_name)
        return ScreeningResultSerializer(existing).data

    # ── Download from SharePoint ──────────────────────────────────────────────
    try:
        file_bytes = download_file(file_name)
    except SharePointAPIError as exc:
        logger.error("[SharePoint] Download failed for '%s': %s", file_name, exc)
        return None

    # ── Write to temp file, process, save ────────────────────────────────────
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        logger.debug("[SharePoint] Temp file written: %s", tmp_path)

        # Extract text
        text  = _extract_text(tmp_path, ext)
        email = _extract_email(text)

        # AI scoring + skill extraction
        llm = _score_with_llm(job, display_name, text)

        # Save to Django DB
        sr = ScreeningResult.objects.create(
            job_opening     = job,
            source_filename = file_name,
            resume_source   = "SHAREPOINT",
            candidate_name  = llm["candidate_name"],
            candidate_email = email,
            match_score     = llm["score"],
            reason          = llm["reason"],
            screened_by     = request_user,
        )
        logger.info(
            "[SharePoint] ✅ Screened '%s' → %s (%d%%) | Skills: %s",
            file_name, llm["candidate_name"], llm["score"],
            llm["skills"][:80] if llm["skills"] else "none"
        )

        # Push SkillSet back to SharePoint — NON-FATAL
        skillset_updated = _push_skillset_to_sharepoint(
            file_name  = file_name,
            file_bytes = file_bytes,
            skills     = llm["skills"],
        )

        # Return serialized result + extra metadata
        result = ScreeningResultSerializer(sr).data
        result["skills"]           = llm["skills"]
        result["skillset_updated"] = skillset_updated
        return result

    finally:
        # Always delete temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                logger.debug("[SharePoint] Temp file deleted: %s", tmp_path)
            except OSError as exc:
                logger.warning(
                    "[SharePoint] Could not delete temp file %s: %s",
                    tmp_path, exc
                )


# ── Public Entry Point ────────────────────────────────────────────────────────

def run_sharepoint_screening(job, request_user) -> dict:
    """
    Orchestrates end-to-end SharePoint screening for a given job.

    Returns:
    {
        "job_id":             int,
        "job_title":          str,
        "folder":             str,
        "total":              int,
        "skipped":            int,
        "failed":             int,
        "skillset_updated":   int,   ← how many SharePoint SkillSet updates succeeded
        "skillset_failed":    int,   ← how many SharePoint SkillSet updates failed
        "results":            list
    }
    """
    logger.info("[SharePoint] Starting screening — job_id=%d", job.id)

    resume_files = get_resume_files()

    if not resume_files:
        logger.info("[SharePoint] No resume files found at root.")
        return {
            "job_id":           job.id,
            "job_title":        job.title,
            "folder":           "SharePoint Root",
            "total":            0,
            "skipped":          0,
            "failed":           0,
            "skillset_updated": 0,
            "skillset_failed":  0,
            "results":          [],
        }

    results          = []
    failed           = 0
    skillset_updated = 0
    skillset_failed  = 0

    for file_name in resume_files:
        result = _process_single_file(file_name, job, request_user)

        if result is None:
            failed += 1
            continue

        # Track SkillSet update stats
        if result.get("skillset_updated"):
            skillset_updated += 1
        else:
            skillset_failed += 1

        results.append(result)

    # Sort by score descending
    results.sort(key=lambda r: r.get("match_score", 0), reverse=True)

    logger.info(
        "[SharePoint] Done — screened=%d failed=%d skillset_updated=%d skillset_failed=%d",
        len(results), failed, skillset_updated, skillset_failed,
    )

    return {
        "job_id":           job.id,
        "job_title":        job.title,
        "folder":           "SharePoint Root",
        "total":            len(results),
        "skipped":          0,
        "failed":           failed,
        "skillset_updated": skillset_updated,
        "skillset_failed":  skillset_failed,
        "results":          results,
    }