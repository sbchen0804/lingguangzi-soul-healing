"""Extract lyric sources into safe, semantic HTML without rewriting wording."""

from __future__ import annotations

import html
from pathlib import Path
import re

from docx import Document
import pdfplumber


_OCR_WARNING = (
    "PDF text extraction found fewer than 20 non-whitespace characters; "
    "OCR review is required."
)


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip("\n")


def _paragraphs(text: str) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []
    return [paragraph for paragraph in normalized.split("\n\n") if paragraph]


def _paragraph_html(paragraphs: list[str]) -> str:
    return "\n".join(
        f"<p>{html.escape(paragraph).replace(chr(10), '<br>')}</p>"
        for paragraph in paragraphs
    )


def _read_docx(path: Path) -> str:
    document = Document(path)
    return "\n\n".join(paragraph.text for paragraph in document.paragraphs)


def _read_pdf(path: Path) -> str:
    with pdfplumber.open(path) as document:
        return "\n\n".join(page.extract_text() or "" for page in document.pages)


def extract_lyrics(path: Path) -> dict:
    """Return normalized paragraphs and escaped HTML for a lyric source."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".txt":
        text = path.read_text(encoding="utf-8")
    elif suffix == ".docx":
        text = _read_docx(path)
    elif suffix == ".pdf":
        text = _read_pdf(path)
        if len(re.sub(r"\s", "", text)) < 20:
            return {
                "status": "requires_ocr",
                "paragraphs": [],
                "html": "",
                "warnings": [_OCR_WARNING],
            }
    else:
        raise ValueError(f"unsupported lyric source format: {suffix or '<none>'}")

    paragraphs = _paragraphs(text)
    return {
        "status": "ok",
        "paragraphs": paragraphs,
        "html": _paragraph_html(paragraphs),
        "warnings": [],
    }
