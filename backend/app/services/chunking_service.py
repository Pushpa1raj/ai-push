from sqlalchemy.orm import Session

from app.models.document import DocumentChunk
from app.services.embedding_service import embedding_service


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """
    Splits text into chunks of specified size and overlap.
    """
    chunks = []
    start = 0
    text_length = len(text)

    # Prevent infinite loops if chunk_size is too small
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be strictly greater than overlap")

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end].strip()
        
        # Only add non-empty chunks
        if chunk:
            chunks.append(chunk)
            
        if end >= text_length:
            break
            
        start += (chunk_size - overlap)

    return chunks


def process_document_chunks(db: Session, document_id: str, text: str) -> None:
    """
    Chunks the given text, generates embeddings, and stores the resulting DocumentChunk records in the DB.
    """
    chunks = chunk_text(text)

    for i, chunk_content in enumerate(chunks):
        try:
            vector = embedding_service.embed_text(chunk_content)
            is_embedded = True
        except Exception as e:
            print(f"Warning: Failed to generate embedding for chunk {i}: {e}")
            vector = None
            is_embedded = False
            
        chunk_record = DocumentChunk(
            document_id=document_id,
            chunk_index=i,
            content=chunk_content,
            embedding=vector,
            embedding_created=is_embedded
        )
        db.add(chunk_record)

    db.commit()
