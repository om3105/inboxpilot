"""
tools/read_pdf.py — Inbound PDF document parser.

Extracts text content across pages using pdfplumber with error handling.
"""

from __future__ import annotations

import io
import os
import pdfplumber


def read_pdf(source: str | bytes) -> str:
    """Extract all text from a PDF file path or byte buffer.

    Returns:
        Consolidated string content of all pages.
    """
    if isinstance(source, str):
        if not os.path.exists(source):
            raise FileNotFoundError(f"PDF file not found at: {source}")
        stream = source
    elif isinstance(source, bytes):
        if not source:
            raise ValueError("Empty PDF byte stream provided")
        stream = io.BytesIO(source)
    else:
        raise TypeError(f"Expected str or bytes for PDF source, got {type(source)}")

    try:
        extracted_pages: list[str] = []
        with pdfplumber.open(stream) as pdf:
            if not pdf.pages:
                raise ValueError("PDF document contains no pages")
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    extracted_pages.append(page_text.strip())

        full_text = "\n\n".join(extracted_pages).strip()
        if not full_text:
            raise ValueError("PDF was parsed but contained no readable text")
        return full_text
    except Exception as exc:
        raise ValueError(f"Failed to read PDF document: {exc}") from exc
