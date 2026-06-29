import logging
from typing import List, Dict, Any, Optional

import chromadb
from django.conf import settings
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ── Load embedding model once at module level ─────────────────────────────────
_embedding_model = None
_chroma_client   = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        model_name = getattr(settings, "EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
        logger.info("[Embedder] Loading embedding model: %s", model_name)
        _embedding_model = SentenceTransformer(model_name)
        logger.info("[Embedder] Model loaded  [OK]")
    return _embedding_model


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        db_path = getattr(settings, "CHROMA_DB_PATH", "./chroma_db")
        logger.info("[Embedder] Connecting to ChromaDB at: %s", db_path)
        _chroma_client = chromadb.PersistentClient(path=db_path)
        logger.info("[Embedder] ChromaDB connected [OK]") 
    return _chroma_client


def get_collection():
    client          = get_chroma_client()
    collection_name = getattr(settings, "CHROMA_COLLECTION_NAME", "resume_chunks")
    return client.get_or_create_collection(
        name     = collection_name,
        metadata = {"hnsw:space": "cosine"},
    )


# ── Generate embedding ────────────────────────────────────────────────────────

def embed_text(text: str) -> List[float]:
  
    model  = get_embedding_model()
    vector = model.encode(text, convert_to_numpy=True)
    return vector.tolist()


# ── Store resume chunks in ChromaDB ──────────────────────────────────────────

def store_chunks(chunks: List[Dict]) -> int:
   
    if not chunks:
        logger.warning("[Embedder] No chunks to store.")
        return 0

    collection = get_collection()
    model      = get_embedding_model()

    ids       = []
    documents = []
    metadatas = []

    for chunk in chunks:
        chunk_id = (
            f"candidate_{chunk['candidate_id']}"
            f"__{chunk['section']}"
            f"__{chunk['chunk_index']}"
        )
        ids.append(chunk_id)
        documents.append(chunk["text"])
        metadatas.append({
            "candidate_id"   : str(chunk["candidate_id"]),
            "section"        : chunk["section"],
            "source_filename": chunk["source_filename"],
            "chunk_index"    : str(chunk["chunk_index"]),
        })

    logger.info("[Embedder] Generating embeddings for %d chunks...", len(chunks))
    batch_embeddings = model.encode(
        [c["text"] for c in chunks],
        convert_to_numpy=True,
    )
    embeddings = batch_embeddings.tolist()

    collection.upsert(
        ids        = ids,
        embeddings = embeddings,
        documents  = documents,
        metadatas  = metadatas,
    )

    logger.info("[Embedder] [OK] Stored %d chunks in ChromaDB", len(chunks))
    return len(chunks)


# ── Delete candidate chunks from ChromaDB ────────────────────────────────────

def delete_candidate_chunks(candidate_id: int) -> None:
   
    collection = get_collection()
    collection.delete(
        where={"candidate_id": str(candidate_id)}
    )
    logger.info("[Embedder] Deleted all chunks for candidate_id=%d", candidate_id)


# ── Search ChromaDB with job description ─────────────────────────────────────

def search_similar_chunks(
    job_description_text: str,
    top_k: int = 20,
    section_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    
    collection   = get_collection()
    jd_embedding = embed_text(job_description_text)

    where = {"section": section_filter} if section_filter else None

    query_params = {
        "query_embeddings": [jd_embedding],
        "n_results"       : top_k,
        "include"         : ["documents", "metadatas", "distances"],
    }
    if where:
        query_params["where"] = where

    results = collection.query(**query_params)

    output = []
    if results and results["ids"] and results["ids"][0]:
        for i, chunk_id in enumerate(results["ids"][0]):
            output.append({
                "chunk_id"       : chunk_id,
                "candidate_id"   : results["metadatas"][0][i].get("candidate_id"),
                "section"        : results["metadatas"][0][i].get("section"),
                "source_filename": results["metadatas"][0][i].get("source_filename"),
                "text"           : results["documents"][0][i],
                "distance"       : results["distances"][0][i],
            })

    logger.info("[Embedder] Search returned %d chunks for JD query", len(output))
    return output