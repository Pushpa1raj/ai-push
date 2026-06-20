import sys
import os
import string

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.memory import Memory

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
    
def main():
    db = SessionLocal()
    
    # 1. Delete summaries
    all_mems = db.query(Memory).all()
    summary_mems = [m for m in all_mems if is_summary_artifact(m.content)]
    for m in summary_mems:
        db.delete(m)
        
    print(f"Deleted {len(summary_mems)} summary memories.")
    db.commit()
    
    # 2. Find duplicates
    all_mems = db.query(Memory).all()
    by_content = {}
    for m in all_mems:
        norm = normalize_memory_text(m.content)
        if norm not in by_content:
            by_content[norm] = []
        by_content[norm].append(m)
        
    deleted_count = 0
    for norm, mems in by_content.items():
        if len(mems) > 1:
            # Keep highest importance, then oldest
            mems.sort(key=lambda x: (x.importance, -x.created_at.timestamp() if x.created_at else 0), reverse=True)
            keep = mems[0]
            for dup in mems[1:]:
                db.delete(dup)
                deleted_count += 1
                
    print(f"Deleted {deleted_count} duplicate memories.")
    db.commit()
    db.close()
    
if __name__ == "__main__":
    main()
