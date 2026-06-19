import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.schemas import DocumentOut
from app.core.database import get_db
from app.models.document import Document
from app.services.chunking_service import process_document_chunks
from app.services.extraction_service import extract_text_from_pdf

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = Path("data/uploads")


@router.post("/upload", response_model=DocumentOut, status_code=201)
def upload_document(
    file: UploadFile,
    db: Session = Depends(get_db),
) -> Document:
    allowed_extensions = {".pdf", ".txt", ".md"}
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )
        
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    doc_id = str(uuid.uuid4())
    safe_filename = os.path.basename(filename)
    stored_filename = f"{doc_id}{ext}"
    file_path = UPLOAD_DIR / stored_filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    file_size = os.path.getsize(file_path)
    
    document = Document(
        id=doc_id,
        filename=safe_filename,
        file_type=ext[1:],
        file_size=file_size
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Process synchronously
    if ext == ".pdf":
        text = extract_text_from_pdf(file_path)
    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
            
    process_document_chunks(db, doc_id, text)
    db.refresh(document) # Refresh to load chunk_count
    
    return document


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    return db.query(Document).order_by(Document.created_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
) -> Document:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
) -> None:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    file_path = UPLOAD_DIR / f"{document.id}.{document.file_type}"
    if file_path.exists():
        file_path.unlink()
        
    db.delete(document)
    db.commit()
