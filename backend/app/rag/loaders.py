import re
from pathlib import Path

import fitz
from docx import Document as DocxDocument

from app.rag.types import TextSection


class DocumentExtractionError(ValueError):
    pass


def clean_text(value: str) -> str:
    """Normalize control characters and whitespace while preserving paragraphs."""
    value = value.replace("\x00", "").replace("\r\n", "\n")
    value = re.sub(r"[\t ]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def extract_sections(path: Path, file_type: str) -> list[TextSection]:
    """Extract clean text and page metadata from an allowlisted document."""
    try:
        if file_type == "pdf":
            with fitz.open(str(path)) as document:
                sections = [TextSection(clean_text(page.get_text()), index + 1) for index, page in enumerate(document)]
        elif file_type == "docx":
            document = DocxDocument(str(path))
            sections = [TextSection(clean_text("\n".join(p.text for p in document.paragraphs)))]
        else:
            sections = [TextSection(clean_text(path.read_text(encoding="utf-8", errors="replace")))]
    except Exception as exc:
        raise DocumentExtractionError("The document could not be safely parsed.") from exc
    sections = [section for section in sections if section.text]
    if not sections:
        raise DocumentExtractionError("No readable text was found in the document.")
    return sections
