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
