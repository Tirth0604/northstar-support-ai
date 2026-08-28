from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.db.session import get_db
from app.models import Document
from app.schemas import DocumentOut
from app.services.container import services
from app.services.documents import UploadValidationError

router = APIRouter(
    prefix="/admin/knowledge/documents", tags=["admin knowledge"], dependencies=[Depends(require_roles("admin"))]
)


@router.post("/upload", response_model=list[DocumentOut], status_code=status.HTTP_201_CREATED)
async def upload_documents(files: list[UploadFile] = File(...), db: Session = Depends(get_db)) -> list[Document]:
    if not files or len(files) > 20:
        raise HTTPException(status_code=400, detail="Upload between 1 and 20 files per batch.")
    document_service, _ = services()
    created = []
    errors = []
    for file in files:
        try:
            created.append(await document_service.upload(file, db))
        except UploadValidationError as exc:
            errors.append(f"{file.filename}: {exc}")
    if not created:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    return created


@router.get("", response_model=list[DocumentOut])
async def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: str, db: Session = Depends(get_db)) -> Document:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str, db: Session = Depends(get_db)) -> None:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    services()[0].delete(document, db)


@router.post("/{document_id}/reindex", response_model=DocumentOut)
async def reindex_document(document_id: str, db: Session = Depends(get_db)) -> Document:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    return services()[0].reindex(document, db)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_documents(db: Session = Depends(get_db)) -> None:
    document_service, _ = services()
    for document in db.scalars(select(Document)):
        document_service.delete(document, db)
    document_service.vectors.clear()
