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

def retrieve_memories(query: str, db: Session, top_k: int = 5, threshold: float = 0.5) -> list[Memory]:
    """
    Retrieves the most relevant memories for a query.
    Returns episodic memories first, then conversational.
    Filters out expired conversational memories.
    """
    query_vector = embedding_service.embed_text(query)
    now = datetime.now(timezone.utc)

    # In a real app we'd query by conversation ID as well if needed,
    # but the prompt implies global memory search for the user context.
    all_memories = db.query(Memory).filter(Memory.embedding != None).all()

    scored_memories = []
    for mem in all_memories:
        # Filter expired
        if mem.expires_at and mem.expires_at < now:
            continue
            
        if mem.embedding:
            score = cosine_similarity(query_vector, mem.embedding)
            if score >= threshold:
                scored_memories.append((score, mem))

    # Sort logic: primary key = is_episodic (True > False), secondary key = score (descending)
    scored_memories.sort(key=lambda x: (x[1].memory_type == "episodic", x[0]), reverse=True)

    result = [mem for score, mem in scored_memories[:top_k]]
    print(f"[MEMORY PIPELINE] Retrieved {len(result)} memories for query: {query}")
    return result
