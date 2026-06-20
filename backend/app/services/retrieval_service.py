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


def retrieve_chunks(query: str, db: Session, top_k: int = 3) -> list[DocumentChunk]:
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
import re

def is_profile_query(query: str) -> bool:
    q = query.lower().strip()
    # Strip punctuation
    q_clean = re.sub(r'[^\w\s]', '', q).strip()
    profile_phrases = [
        "who am i",
        "tell me about me",
        "what do you know about me",
        "describe me",
        "summarize me",
        "summarize my profile",
        "what have you learned about me",
        "who am i based on your memory",
        "what all do you remember about me",
        "what do you remember about me",
        "my profile",
    ]
    return any(p in q_clean for p in profile_phrases)

import string

def normalize_memory_text(text: str) -> str:
    text = text.lower().strip()
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text

def deduplicate_memories(memories: list[Memory]) -> tuple[list[Memory], int]:
    seen = set()
    deduped = []
    for mem in memories:
        norm = normalize_memory_text(mem.content)
        if norm not in seen:
            seen.add(norm)
            deduped.append(mem)
    removed_count = len(memories) - len(deduped)
    return deduped, removed_count

def apply_memory_decay(memories: list[Memory], db: Session):
    now = datetime.now(timezone.utc)
    decay_applied = False
    
    for m in memories:
        if m.importance >= 8:
            continue
        if m.memory_type == "semantic" or m.memory_type == "summary":
            continue
            
        ref_time = m.last_accessed if m.last_accessed else m.created_at
        
        # Ensure we're comparing timezone-aware datetimes
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)
            
        age_days = (now - ref_time).days
        
        # Decay by 1 point for every 7 days of inactivity
        if age_days >= 7 and m.importance > 1:
            decay_amount = age_days // 7
            old_imp = m.importance
            new_imp = max(1, m.importance - decay_amount)
            
            if old_imp != new_imp:
                print(f"[DECAY] Memory importance reduced")
                print(f"[DECAY] Old importance: {old_imp}")
                print(f"[DECAY] New importance: {new_imp}")
                
                m.importance = new_imp
                # Reset the clock so it doesn't decay again tomorrow
                m.last_accessed = now
                db.add(m)
                decay_applied = True
                
    if decay_applied:
        db.commit()
        clear_profile_cache()

PROFILE_CACHE = {
    "summary": None
}

def clear_profile_cache():
    PROFILE_CACHE["summary"] = None

def get_cached_profile_summary(db: Session, top_k: int = 10) -> str:
    if PROFILE_CACHE["summary"] is not None:
        print("[PROFILE CACHE] Using cached profile summary")
        return PROFILE_CACHE["summary"]
    
    print("[PROFILE CACHE] Rebuilding profile summary")
    mems = retrieve_profile_memories(db, top_k=top_k)
    summary = format_profile_block(mems)
    PROFILE_CACHE["summary"] = summary
    return summary

def retrieve_profile_memories(db: Session, top_k: int = 10) -> list[Memory]:
    """
    Retrieves ALL active semantic and summary memories for profile queries.
    Groups by category and sorts by importance descending.
    """
    print("[PROFILE MODE]")
    
    # Retrieve ALL active memories (no limit yet)
    all_memories = db.query(Memory).filter(Memory.is_active == True).all()
    apply_memory_decay(all_memories, db)
    now = datetime.now(timezone.utc)
    
    print(f"[PROFILE MODE] Total active memories in DB: {len(all_memories)}")
    
    valid_mems = []
    for mem in all_memories:
        if mem.expires_at and mem.expires_at < now:
            continue
        valid_mems.append(mem)

    # Log each memory being considered
    for mem in valid_mems:
        print(f"[PROFILE MODE]   type={mem.memory_type} cat={mem.category} imp={mem.importance} content=\"{mem.content[:60]}\"")

    def type_priority(m_type: str) -> int:
        if m_type == "summary": return 3
        if m_type == "semantic": return 2
        return 1

    # Sort: summary > semantic > episodic, then by importance (DESC)
    valid_mems.sort(key=lambda x: (type_priority(x.memory_type), x.importance), reverse=True)
    
    deduped_mems, removed = deduplicate_memories(valid_mems)
    if removed > 0:
        print(f"[DEDUP] Removed {removed} duplicate memories")
        
    result = deduped_mems[:top_k]
    print(f"[PROFILE MODE] Retrieved {len(result)} memories")
    print(f"[PROFILE MODE] Injected {len(result)} unique memories")
    return result

def format_profile_block(memories: list[Memory]) -> str:
    """
    Formats memories into a structured profile summary grouped by category.
    """
    categories = {}
    for mem in memories:
        cat = mem.category or "other"
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(mem)
    
    # Category display order
    cat_order = ["personal", "education", "project", "preference", "goal", "other"]
    cat_labels = {
        "personal": "Personal",
        "education": "Education",
        "project": "Projects",
        "preference": "Preferences",
        "goal": "Goals",
        "other": "Other",
    }
    
    lines = []
    for cat in cat_order:
        if cat not in categories:
            continue
        mems = categories[cat]
        lines.append(f"[{cat_labels.get(cat, cat)}]")
        for m in mems:
            lines.append(f"- {m.content}")
        lines.append("")
    
    # Cap profile block to 15 lines max to prevent context bloat
    if len(lines) > 15:
        print(f"[PROFILE MODE] Trimming profile from {len(lines)} to 15 lines")
        lines = lines[:15]
    
    summary = "\n".join(lines).strip()
    print(f"[PROFILE MODE] Generated profile summary ({len(lines)} lines)")
    return summary

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

    all_memories = db.query(Memory).filter(Memory.embedding != None, Memory.is_active == True).all()
    apply_memory_decay(all_memories, db)

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
    deduped_mems, removed = deduplicate_memories([mem for score, mem in combined])
    if removed > 0:
        print(f"[DEDUP] Removed {removed} duplicate memories")
        
    result = deduped_mems[:top_k]
    print(f"[MEMORY PIPELINE] Retrieved {len(result)} memories for query: {query}")
    return result
