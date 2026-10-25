"""
tools/send_reply.py — Sends an approved reply from the real mailbox over SMTP.

Only called after a human approves a run, and only when MAIL_SEND_REPLIES is on
and public demo mode is off (otherwise any website visitor could send mail from
the operator's account). Replies are threaded onto the original message.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from app.config import get_settings

logger = logging.getLogger("inboxpilot.tools.send_reply")


def reply_sending_enabled() -> tuple[bool, str]:
    """Return (enabled, reason) for sending replies from the real mailbox."""
    s = get_settings()
    if s.demo_public:
        return False, "public demo mode never sends email"
    if not s.mail_send_replies:
        return False, "MAIL_SEND_REPLIES is off"
    if not (s.mail_username and s.mail_password):
        return False, "MAIL_USERNAME / MAIL_PASSWORD not set"
    return True, ""


def _build_message(draft: dict[str, Any], source: dict[str, Any], sender: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = source.get("from_address") or draft.get("to", "")
    subject = source.get("subject") or draft.get("subject", "")
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    if source.get("message_id"):
        msg["In-Reply-To"] = source["message_id"]
        msg["References"] = source["message_id"]
    msg.set_content(draft.get("body", ""))
    return msg


def _send_blocking(msg: EmailMessage) -> None:
    s = get_settings()
    with smtplib.SMTP_SSL(s.mail_smtp_host, 465, timeout=30) as smtp:
        smtp.login(s.mail_username, s.mail_password)
        smtp.send_message(msg)


async def send_reply(draft: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    """Send the drafted reply to the original sender. Never raises."""
    enabled, reason = reply_sending_enabled()
    if not enabled:
        return {"sent": False, "reason": reason}
    if not draft or not draft.get("body"):
        return {"sent": False, "reason": "no reply was drafted"}
    msg = _build_message(draft, source, get_settings().mail_username)
    try:
        await asyncio.to_thread(_send_blocking, msg)
        logger.info("Sent approved reply to %s", msg["To"])
        return {"sent": True, "to": msg["To"], "subject": msg["Subject"]}
    except Exception as exc:
        logger.warning("Sending reply failed: %s", exc)
        return {"sent": False, "reason": f"SMTP error: {exc}"}
