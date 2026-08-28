import hashlib
import mimetypes
import re
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Document, DocumentStatus
from app.rag.chunking import chunk_sections
from app.rag.embeddings import EmbeddingProvider
from app.rag.loaders import extract_sections
from app.rag.vector_store import LocalVectorStore

ALLOWED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx", ".txt": "txt", ".md": "md", ".markdown": "md"}
ALLOWED_MIME_PREFIXES = {
    "pdf": ("application/pdf",),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"),
    "txt": ("text/plain", "application/octet-stream"),
    "md": ("text/plain", "text/markdown", "application/octet-stream"),
}


class UploadValidationError(ValueError):
    pass


def validate_upload(filename: str, content_type: str | None, data: bytes, max_size_mb: int) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise UploadValidationError("Unsupported file type. Upload PDF, DOCX, TXT, or Markdown.")
    if not data:
        raise UploadValidationError("The uploaded file is empty.")
    if len(data) > max_size_mb * 1024 * 1024:
        raise UploadValidationError(f"File exceeds the {max_size_mb} MB upload limit.")
    file_type = ALLOWED_EXTENSIONS[suffix]
    mime = (content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream").split(";")[0]
    if mime not in ALLOWED_MIME_PREFIXES[file_type]:
        raise UploadValidationError("The declared MIME type does not match an allowed document format.")
    if file_type == "pdf" and not data.startswith(b"%PDF"):
        raise UploadValidationError("The file does not contain a valid PDF signature.")
    if file_type == "docx" and not data.startswith(b"PK"):
        raise UploadValidationError("The file does not contain a valid DOCX signature.")
    return file_type, hashlib.sha256(data).hexdigest()


class DocumentService:
    def __init__(self, settings: Settings, embeddings: EmbeddingProvider, vectors: LocalVectorStore):
        self.settings = settings
        self.embeddings = embeddings
        self.vectors = vectors

    async def upload(self, file: UploadFile, db: Session) -> Document:
        data = await file.read(self.settings.max_upload_size_mb * 1024 * 1024 + 1)
        file_type, digest = validate_upload(
            file.filename or "document", file.content_type, data, self.settings.max_upload_size_mb
        )
        duplicate = db.scalar(select(Document).where(Document.file_hash == digest))
        if duplicate:
            raise UploadValidationError(f"This file is already indexed as '{duplicate.original_filename}'.")
        safe_stem = re.sub(r"[^a-zA-Z0-9._-]", "_", Path(file.filename or "document").stem)[:80] or "document"
        document = Document(
            original_filename=Path(file.filename or "document").name,
            stored_filename="pending",
            file_type=file_type,
            file_size=len(data),
            file_hash=digest,
        )
        db.add(document)
        db.flush()
        document.stored_filename = f"{document.id}_{safe_stem}{Path(file.filename or '').suffix.lower()}"
        path = (self.settings.upload_directory / document.stored_filename).resolve()
        if self.settings.upload_directory.resolve() not in path.parents:
            raise UploadValidationError("Invalid destination path.")
        path.write_bytes(data)
        db.commit()
        try:
            self.index(document, path, db)
        except Exception as exc:
            document.upload_status = DocumentStatus.FAILED
            document.error_message = str(exc)[:500]
            db.commit()
        return document

    def index(self, document: Document, path: Path, db: Session) -> None:
        sections = extract_sections(path, document.file_type)
        chunks = chunk_sections(
            sections, document.id, document.original_filename, self.settings.chunk_size, self.settings.chunk_overlap
        )
        embeddings = self.embeddings.embed([chunk.text for chunk in chunks])
        self.vectors.add(chunks, embeddings)
        document.chunk_count = len(chunks)
        document.upload_status = DocumentStatus.READY
        document.error_message = None
        db.commit()

    def delete(self, document: Document, db: Session) -> None:
        self.vectors.delete_document(document.id)
        path = self.settings.upload_directory / document.stored_filename
        if path.exists():
            path.unlink()
        db.delete(document)
        db.commit()

    def reindex(self, document: Document, db: Session) -> Document:
        document.upload_status = DocumentStatus.PROCESSING
        db.commit()
        try:
            self.index(document, self.settings.upload_directory / document.stored_filename, db)
        except Exception as exc:
            document.upload_status = DocumentStatus.FAILED
            document.error_message = str(exc)[:500]
            db.commit()
        return document
