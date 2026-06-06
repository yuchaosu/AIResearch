"""Extract plain text from a PDF using PyMuPDF."""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


def extract_text(pdf_path: str | Path, max_chars: int | None = None) -> str:
    text_parts: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text_parts.append(page.get_text("text"))
    text = "\n".join(text_parts).strip()
    if max_chars and len(text) > max_chars:
        # keep the head (intro/method) and tail (results/conclusion)
        head = text[: int(max_chars * 0.7)]
        tail = text[-int(max_chars * 0.3):]
        text = head + "\n\n[...truncated...]\n\n" + tail
    return text
