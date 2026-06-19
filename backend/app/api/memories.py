from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import MemoryOut, MemoryUpdate
from app.core.database import get_db
from app.models.memory import Memory

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("", response_model=list[MemoryOut])
def list_memories(db: Session = Depends(get_db)) -> list[Memory]:
    return db.query(Memory).order_by(Memory.created_at.desc()).all()


@router.patch("/{memory_id}", response_model=MemoryOut)
def update_memory(
    memory_id: str,
    body: MemoryUpdate,
    db: Session = Depends(get_db),
) -> Memory:
    memory = db.get(Memory, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
        
    memory.content = body.content
    db.commit()
    db.refresh(memory)
    return memory


@router.delete("/{memory_id}", status_code=204)
def delete_memory(
    memory_id: str,
    db: Session = Depends(get_db),
) -> None:
    memory = db.get(Memory, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
        
    db.delete(memory)
    db.commit()
