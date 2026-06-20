from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.memory import Memory
from app.services.ollama_service import OllamaService
from app.services.embedding_service import embedding_service
from app.core.config import get_active_model

def compress_category_memories(db: Session, category: str, ollama_service: OllamaService):
    """
    Compresses semantic memories of a given category into a single 'summary' memory.
    """
    if category == "other":
        return

    memories = db.query(Memory).filter(
        Memory.category == category,
        Memory.memory_type == "semantic",
        Memory.is_active == True
    ).all()
    
    # We only compress if there are at least 2 memories
    if len(memories) < 2:
        return
        
    print(f"[COMPRESSION] Triggering compression for category: {category} ({len(memories)} facts)")
    
    prompt = f"Combine the following facts into a single, concise sentence summary about the user's {category} profile:\n"
    for m in memories:
        prompt += f"- {m.content}\n"
        
    prompt += "\nOutput ONLY the summary sentence."
    
    try:
        model_name = get_active_model()
        res = ollama_service.generate(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3}
        )
        summary_text = res.get("message", {}).get("content", "").strip()
        if not summary_text:
            return
            
        summary_content = f"{category.capitalize()} Summary: {summary_text}"
        
        # Check if an old summary exists
        old_summary = db.query(Memory).filter(
            Memory.category == category,
            Memory.memory_type == "summary",
            Memory.is_active == True
        ).first()
        
        if old_summary:
            print(f"[COMPRESSION] Archiving old summary")
            old_summary.is_active = False
            db.add(old_summary)
            
        # Create new summary memory
        summary_vector = embedding_service.embed_text(summary_content)
        new_summary = Memory(
            memory_type="summary",
            content=summary_content,
            category=category,
            importance=10,  # Max importance for summaries
            importance_score=1.0,
            embedding=summary_vector,
            is_active=True,
            last_accessed=datetime.now(timezone.utc)
        )
        db.add(new_summary)
        db.commit()
        print(f"[COMPRESSION] Created new summary: {summary_content}")
        
    except Exception as e:
        print(f"Error compressing memories: {e}")
