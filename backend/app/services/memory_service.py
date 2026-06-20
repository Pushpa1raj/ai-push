from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.memory import ConversationMemory, Memory
from app.services.embedding_service import embedding_service
from app.services.memory_extraction_service import extract_memories
from app.services.ollama_service import OllamaService
from app.services.retrieval_service import cosine_similarity
from app.core.config import get_active_model
import string

def normalize_memory_text(text: str) -> str:
    text = text.lower().strip()
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text

def is_summary_artifact(content: str) -> bool:
    summary_patterns = [
        "preference summary:",
        "profile summary:",
        "education summary:",
        "project summary:"
    ]
    norm = content.lower()
    return any(p in norm for p in summary_patterns)
def process_and_save_memories(
    user_message: str,
    conversation_id: str,
    ollama_service: OllamaService,
    db: Session,
) -> None:
    """
    Extracts memories using the LLM, checks for duplicates using semantic similarity,
    and stores new episodic and conversational memories into the database.
    If a semantically similar memory exists, updates it instead of creating a duplicate.
    Conversational memories auto-expire after 7 days.
    """
    candidates = extract_memories(user_message, ollama_service)

    if not candidates:
        return

    # Fetch existing memories that have embeddings
    existing_memories = db.query(Memory).filter(Memory.is_active == True).all()

    categories_touched = []

    for candidate_obj in candidates:
        m_type = candidate_obj.get("type")
        content = candidate_obj.get("content")
        category = candidate_obj.get("category", "other")
        importance = candidate_obj.get("importance", 5)
        
        if not m_type or not content:
            continue
            
        print(f"[MEMORY GUARD] Source: USER_ONLY | Candidate: {content}")

        # Skip low-importance memories
        if importance < 5:
            print(f"[MEMORY PIPELINE] Skipping memory. Reason: importance below threshold (importance={importance}, content={content})")
            continue

        # Drop short meaningless fragments
        if len(content.split()) < 3:
            continue

        if is_summary_artifact(content):
            print(f"[MEMORY PIPELINE] Skipping summary artifact: {content}")
            continue

        norm_content = normalize_memory_text(content)
        
        # Exact Deduplication Check
        exact_match = None
        for ex_mem in existing_memories:
            if normalize_memory_text(ex_mem.content) == norm_content:
                exact_match = ex_mem
                break
                
        if exact_match:
            print(f"[DEDUP] Exact duplicate memory found")
            print(f"[DEDUP] Existing memory updated")
            exact_match.last_accessed = datetime.now(timezone.utc)
            exact_match.importance = min(10, exact_match.importance + 1)
            if m_type == "episodic":
                exact_match.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            db.add(exact_match)
            categories_touched.append(category)
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

        similarity_threshold = 0.85
        is_handled = False

        if best_match and best_score >= similarity_threshold and category == best_match.category:
            # We found a highly similar memory in the same category. Determine if it's a DEDUP or UPDATE.
            prompt = f"Compare these two memory facts about the user:\nFact 1: {best_match.content}\nFact 2: {content}\n\nAre they:\n1. DUPLICATE: They mean the exact same thing.\n2. CONFLICT: Fact 2 replaces Fact 1 with new contradictory information on the same topic (e.g. moved from Kolkata to Bangalore).\n3. DIFFERENT: Completely different facts.\n\nRespond with ONLY ONE WORD: DUPLICATE, CONFLICT, or DIFFERENT."
            
            try:
                model_name = get_active_model()
                classification_res = ollama_service.generate(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    options={"temperature": 0.0}
                )
                relation = classification_res.get("message", {}).get("content", "").strip().upper()
                import re
                relation = re.sub(r'[^\w\s]', '', relation).strip()
            except Exception as e:
                print(f"Error classifying memory relation: {e}")
                relation = "DUPLICATE" if best_score >= 0.90 else "DIFFERENT"
                
            if "CONFLICT" in relation or "UPDATE" in relation:
                print(f"[CONFLICT] Conflict detected")
                print(f"[CONFLICT] Old memory archived")
                print(f"[CONFLICT] New memory activated")
                
                # Mark old memory inactive
                best_match.is_active = False
                db.add(best_match)
                
                # Create the new memory as active
                expires_at = None
                if m_type == "episodic":
                    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
                    
                new_memory = Memory(
                    memory_type=m_type,
                    content=content,
                    category=category,
                    importance=importance,
                    importance_score=0.5,
                    expires_at=expires_at,
                    embedding=candidate_vector,
                    is_active=True
                )
                db.add(new_memory)
                db.flush()
                
                conv_mem = ConversationMemory(
                    conversation_id=conversation_id, memory_id=new_memory.id
                )
                db.add(conv_mem)
                categories_touched.append(category)
                is_handled = True
                
            elif "DUPLICATE" in relation or best_score >= 0.95:
                print(f"[DEDUP] Similar memory found")
                print(f"[MEMORY PIPELINE] Duplicate memory detected. Similarity: {best_score:.2f}")
                print(f"[DEDUP] Existing memory updated")
                
                best_match.importance = min(10, best_match.importance + 1)
                best_match.last_accessed = datetime.now(timezone.utc)
                
                if m_type == "episodic":
                    best_match.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
                db.add(best_match)
                categories_touched.append(category)
                is_handled = True
                
        if not is_handled:
            print(f"[DEDUP] New memory created")
            # No duplicate/update -> Insert new memory
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
            categories_touched.append(category)
            
            # Add to local loop cache
            existing_memories.append(memory)

    try:
        db.commit()
        print("[MEMORY PIPELINE] Database commit successful.")
        
        # Trigger memory compression for each category touched
        from app.services.memory_compression_service import compress_category_memories
        for cat in set(categories_touched):
            compress_category_memories(db, cat, ollama_service)
            
        if categories_touched:
            from app.services.retrieval_service import clear_profile_cache
            clear_profile_cache()
            
    except Exception as e:
        print(f"[MEMORY PIPELINE] Error during database commit: {e}")
        db.rollback()

    # Trigger profile extraction for any semantic memories
    semantic_mems = [m for m in existing_memories if m.memory_type == "semantic"]
    if semantic_mems:
        from app.services.profile_extraction_service import update_profile_from_memories
        update_profile_from_memories(semantic_mems, db, ollama_service)
