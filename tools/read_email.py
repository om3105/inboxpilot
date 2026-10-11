"""
tools/read_email.py — Inbound email parser.

Parses .eml formatted email files or plain text raw email messages.
Extracts sender, recipient, subject, date, and clean body text.
"""

from __future__ import annotations

import os
from typing import Any
import mailparser


def read_email(source: str | bytes) -> dict[str, str]:
    """Parse an email from raw text, bytes, or a file path.

    Returns:
        dict containing 'sender', 'subject', 'body', 'date'.
    """
    try:
        raw_content: str | None = None
        if isinstance(source, str):
            if os.path.exists(source):
                with open(source, "r", encoding="utf-8", errors="replace") as f:
                    raw_content = f.read()
            else:
                raw_content = source
        elif isinstance(source, bytes):
            raw_content = source.decode("utf-8", errors="replace")

        if not raw_content or not raw_content.strip():
            raise ValueError("Email source is empty")

        # Try mailparser first
        mail = mailparser.parse_from_string(raw_content)
        
        # Format sender
        sender = ""
        if mail.from_:
            sender = mail.from_[0][1] if isinstance(mail.from_[0], (list, tuple)) else str(mail.from_[0])
        elif "From:" in raw_content:
            for line in raw_content.splitlines():
                if line.lower().startswith("from:"):
                    sender = line.split(":", 1)[1].strip()
                    break

        subject = mail.subject or ""
        if not subject and "Subject:" in raw_content:
            for line in raw_content.splitlines():
                if line.lower().startswith("subject:"):
                    subject = line.split(":", 1)[1].strip()
                    break

        body = mail.body or raw_content

        return {
            "sender": sender.strip(),
            "subject": subject.strip(),
            "body": body.strip(),
            "date": str(mail.date or ""),
        }
    except Exception as exc:
        raise ValueError(f"Failed to parse email: {exc}") from exc
