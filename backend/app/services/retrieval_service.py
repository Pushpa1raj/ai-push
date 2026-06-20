import math

from sqlalchemy.orm import Session

from app.models.document import DocumentChunk
from app.services.embedding_service import embedding_service


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """
    Computes the cosine similarity between two vectors.
    """
    dot_product = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot_product / (mag1 * mag2)


def retrieve_chunks(query: str, db: Session, top_k: int = 5) -> list[DocumentChunk]:
    """
    Retrieves the most relevant document chunks for a given query
    by comparing cosine similarity of embeddings.
    """
    query_vector = embedding_service.embed_text(query)

    # Note: In-memory scoring for SQLite. For production with PostgreSQL, pgvector is recommended.
    chunks = db.query(DocumentChunk).filter(DocumentChunk.embedding_created == True).all()

    scored_chunks = []
    for chunk in chunks:
        if chunk.embedding is not None:
            score = cosine_similarity(query_vector, chunk.embedding)
            scored_chunks.append((score, chunk))

    # Sort descending by similarity score
    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    # Extract the top chunks
    return [chunk for score, chunk in scored_chunks[:top_k]]

from datetime import datetime, timezone
from app.models.memory import Memory
from app.services.temporal_service import parse_time_reference, get_time_range

def retrieve_memories(query: str, db: Session, top_k: int = 5, threshold: float = 0.5) -> list[Memory]:
    """
    Retrieves the most relevant memories for a query.
    Supports temporal queries (today, yesterday, this week, last week).
    Retrieval order: temporal episodic matches → semantic matches → remaining.
    """
    query_vector = embedding_service.embed_text(query)
    now = datetime.now(timezone.utc)

    # Detect temporal reference
    time_ref = parse_time_reference(query)
    time_range = get_time_range(time_ref) if time_ref != "none" else None

    if time_ref != "none":
        print(f"[TEMPORAL] Query detected: {time_ref}")

    all_memories = db.query(Memory).filter(Memory.embedding != None).all()

    temporal_episodic = []
    semantic_matches = []
    other_matches = []

    for mem in all_memories:
        # Filter expired
        if mem.expires_at and mem.expires_at < now:
            continue

        if not mem.embedding:
            continue

        score = cosine_similarity(query_vector, mem.embedding)

        # Temporal episodic: episodic memories within the time range
        if time_range and mem.memory_type == "episodic" and mem.created_at:
            start, end = time_range
            mem_time = mem.created_at.replace(tzinfo=timezone.utc) if mem.created_at.tzinfo is None else mem.created_at
            if start <= mem_time <= end:
                temporal_episodic.append((score, mem))
                continue

        if score >= threshold:
            if mem.memory_type == "semantic":
                semantic_matches.append((score, mem))
            else:
                other_matches.append((score, mem))

    # Sort each group by score descending
    temporal_episodic.sort(key=lambda x: x[0], reverse=True)
    semantic_matches.sort(key=lambda x: x[0], reverse=True)
    other_matches.sort(key=lambda x: x[0], reverse=True)

    if temporal_episodic:
        print(f"[TEMPORAL] Retrieved {len(temporal_episodic)} episodic memories")

    # Merge: temporal episodic first, then semantic, then rest
    combined = temporal_episodic + semantic_matches + other_matches
    result = [mem for score, mem in combined[:top_k]]
    print(f"[MEMORY PIPELINE] Retrieved {len(result)} memories for query: {query}")
    return result
