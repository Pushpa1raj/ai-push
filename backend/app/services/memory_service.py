from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.memory import ConversationMemory, Memory
from app.services.embedding_service import embedding_service
from app.services.memory_extraction_service import extract_memories
from app.services.ollama_service import OllamaService
from app.services.retrieval_service import cosine_similarity


def process_and_save_memories(
    user_message: str,
    assistant_message: str,
    conversation_id: str,
    ollama_service: OllamaService,
    db: Session,
    model: str = "qwen3:4b",
) -> None:
    """
    Extracts memories using the LLM, checks for duplicates using semantic similarity,
    and stores new episodic and conversational memories into the database.
    If a semantically similar memory exists, updates it instead of creating a duplicate.
    Conversational memories auto-expire after 7 days.
    """
    candidates = extract_memories(user_message, assistant_message, ollama_service, model)

    if not candidates:
        return

    # Fetch existing memories that have embeddings
    existing_memories = db.query(Memory).filter(Memory.embedding != None).all()

    for candidate_obj in candidates:
        m_type = candidate_obj.get("type")
        content = candidate_obj.get("content")
        
        if not m_type or not content:
            continue

        # Drop short meaningless fragments
        if len(content.split()) < 3:
            continue

        # Generate embedding for candidate
        try:
            candidate_vector = embedding_service.embed_text(content)
        except Exception as e:
            print(f"Failed to embed memory candidate: {e}")
            continue

        # Check semantic similarity
        best_match = None
        best_score = 0.0

        for ex_mem in existing_memories:
            if ex_mem.embedding and ex_mem.memory_type == m_type:
                score = cosine_similarity(candidate_vector, ex_mem.embedding)
                if score > best_score:
                    best_score = score
                    best_match = ex_mem

        similarity_threshold = 0.85

        if best_match and best_score >= similarity_threshold:
            # Semantic duplicate found -> Update existing memory
            best_match.content = content
            best_match.embedding = candidate_vector
            
            if m_type == "conversational":
                # Refresh expiration
                best_match.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
                
            db.add(best_match)
        else:
            # No semantic duplicate -> Insert new memory
            expires_at = None
            if m_type == "conversational":
                expires_at = datetime.now(timezone.utc) + timedelta(days=7)
                
            memory = Memory(
                memory_type=m_type,
                content=content,
                importance_score=0.5,
                expires_at=expires_at,
                embedding=candidate_vector
            )
            db.add(memory)
            db.flush()

            conv_mem = ConversationMemory(
                conversation_id=conversation_id, memory_id=memory.id
            )
            db.add(conv_mem)
            
            # Add to local loop cache
            existing_memories.append(memory)

    db.commit()
