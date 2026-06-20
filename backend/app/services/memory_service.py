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
        category = candidate_obj.get("category", "other")
        importance = candidate_obj.get("importance", 5)
        
        if not m_type or not content:
            continue

        # Skip low-importance memories
        if importance < 5:
            print(f"[MEMORY PIPELINE] Skipping memory. Reason: importance below threshold (importance={importance}, content={content})")
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

        # Check semantic similarity against all existing memories
        best_match = None
        best_score = 0.0

        for ex_mem in existing_memories:
            if ex_mem.embedding:
                score = cosine_similarity(candidate_vector, ex_mem.embedding)
                if score > best_score:
                    best_score = score
                    best_match = ex_mem

        similarity_threshold = 0.90

        if best_match and best_score >= similarity_threshold:
            print(f"[MEMORY PIPELINE] Duplicate memory detected. Similarity: {best_score:.2f}")
            print(f"[MEMORY PIPELINE] Existing memory updated.")
            # Semantic duplicate found -> Update existing memory timestamp and content
            best_match.content = content
            best_match.embedding = candidate_vector
            best_match.category = category
            best_match.importance = importance
            best_match.created_at = datetime.now(timezone.utc)
            
            if m_type == "episodic":
                best_match.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
                
            db.add(best_match)
        else:
            # No duplicate -> Insert new memory
            expires_at = None
            if m_type == "episodic":
                expires_at = datetime.now(timezone.utc) + timedelta(days=30)
                
            memory = Memory(
                memory_type=m_type,
                content=content,
                category=category,
                importance=importance,
                importance_score=0.5,
                expires_at=expires_at,
                embedding=candidate_vector
            )
            db.add(memory)
            db.flush()
            print(f"[MEMORY PIPELINE] Created new memory: {memory.id} - {content}")

            conv_mem = ConversationMemory(
                conversation_id=conversation_id, memory_id=memory.id
            )
            db.add(conv_mem)
            
            # Add to local loop cache
            existing_memories.append(memory)

    try:
        db.commit()
        print("[MEMORY PIPELINE] Database commit successful.")
    except Exception as e:
        print(f"[MEMORY PIPELINE] Error during database commit: {e}")
        db.rollback()
