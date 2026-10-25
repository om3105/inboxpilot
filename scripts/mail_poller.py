"""
scripts/mail_poller.py — Feeds a real mailbox into InboxPilot.

Every MAIL_POLL_SECONDS it reads unread mail from MAIL_FOLDER over IMAP, submits
each message to the InboxPilot API (POST /process) with its sender and
Message-ID, and marks it read once the API has accepted it. The agent then
pauses for approval as usual; open the dashboard to approve or reject. With
MAIL_SEND_REPLIES=true, approving also sends the drafted reply.

Usage:
    python -m scripts.mail_poller          # keep polling
    python -m scripts.mail_poller --once   # check once and exit

Gmail: turn on 2-Step Verification, create an app password
(Google Account → Security → App passwords), and set MAIL_USERNAME and
MAIL_PASSWORD in .env. A dedicated label plus a Gmail filter keeps the agent
away from personal mail (MAIL_FOLDER=ops-inbox).
"""

from __future__ import annotations

import argparse
import email
import email.utils
import imaplib
import logging
import re
import time
from email.message import EmailMessage
from email.policy import default as default_policy
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger("inboxpilot.mail_poller")


def _plain_text(msg: EmailMessage) -> str:
    """Best-effort plain-text body: prefer text/plain, else strip tags from HTML."""
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    text = part.get_content()
    if part.get_content_type() == "text/html":
        text = re.sub(r"<(br|/p|/div)\s*/?>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_message(raw_bytes: bytes) -> dict[str, Any]:
    """Turn raw RFC 822 bytes into the fields InboxPilot needs."""
    msg = email.message_from_bytes(raw_bytes, policy=default_policy)
    from_name, from_address = email.utils.parseaddr(str(msg.get("From", "")))
    return {
        "from_address": from_address,
        "from_name": from_name,
        "to": str(msg.get("To", "")),
        "subject": str(msg.get("Subject", "")),
        "date": str(msg.get("Date", "")),
        "message_id": str(msg.get("Message-ID", "")),
        "auto_submitted": str(msg.get("Auto-Submitted", "no")).lower() != "no",
        "body": _plain_text(msg),
    }


def should_skip(parsed: dict[str, Any], own_address: str) -> str | None:
    """Reason to ignore a message, or None. Prevents reply loops and auto-reply storms."""
    if parsed["from_address"].lower() == own_address.lower():
        return "sent by this mailbox"
    if parsed["auto_submitted"]:
        return "auto-reply"
    if not parsed["body"]:
        return "empty body"
    return None


def to_process_request(parsed: dict[str, Any]) -> dict[str, Any]:
    raw = (
        f"From: {parsed['from_address']}\nTo: {parsed['to']}\nDate: {parsed['date']}\n"
        f"Subject: {parsed['subject']}\n\n{parsed['body']}"
    )
    return {
        "raw_input": raw,
        "input_source": "email",
        "source_message": {
            "message_id": parsed["message_id"],
            "from_address": parsed["from_address"],
            "subject": parsed["subject"],
        },
    }


def poll_once(imap: Any, client: httpx.Client) -> int:
    """Process every unread message in the selected folder. Returns how many were submitted."""
    settings = get_settings()
    headers = {"X-Demo-Token": settings.demo_token} if settings.demo_token else {}
    status, data = imap.search(None, "UNSEEN")
    if status != "OK":
        raise RuntimeError(f"IMAP search failed: {status}")

    submitted = 0
    for num in data[0].split():
        # BODY.PEEK keeps the message unread until InboxPilot has accepted it.
        status, parts = imap.fetch(num, "(BODY.PEEK[])")
        if status != "OK" or not parts or not isinstance(parts[0], tuple):
            logger.warning("Could not fetch message %s", num)
            continue
        parsed = parse_message(parts[0][1])

        reason = should_skip(parsed, settings.mail_username)
        if reason:
            logger.info("Skipping %r (%s)", parsed["subject"], reason)
            imap.store(num, "+FLAGS", "\\Seen")
            continue

        res = client.post(f"{settings.inboxpilot_api_url}/process", json=to_process_request(parsed), headers=headers)
        if res.status_code != 200:
            logger.warning("InboxPilot rejected %r (%s): %s; will retry next poll",
                           parsed["subject"], res.status_code, res.text[:200])
            continue
        run = res.json()
        imap.store(num, "+FLAGS", "\\Seen")
        submitted += 1
        logger.info("%s → %s (%s)", parsed["subject"], run.get("status"), run.get("run_id"))
    return submitted


def main() -> None:
    parser = argparse.ArgumentParser(description="Feed a real mailbox into InboxPilot.")
    parser.add_argument("--once", action="store_true", help="check the mailbox once and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    s = get_settings()
    if not (s.mail_username and s.mail_password):
        raise SystemExit("Set MAIL_USERNAME and MAIL_PASSWORD in .env first (Gmail: use an app password).")

    with httpx.Client(timeout=180) as client:
        while True:
            try:
                with imaplib.IMAP4_SSL(s.mail_imap_host) as imap:
                    imap.login(s.mail_username, s.mail_password)
                    status, _ = imap.select(f'"{s.mail_folder}"')
                    if status != "OK":
                        raise SystemExit(f"Folder {s.mail_folder!r} not found in {s.mail_username}.")
                    n = poll_once(imap, client)
                    logger.info("Checked %s: %d new message(s) sent to InboxPilot", s.mail_folder, n)
            except (imaplib.IMAP4.error, OSError, httpx.HTTPError) as exc:
                logger.warning("Mailbox check failed: %s", exc)
            if args.once:
                return
            time.sleep(s.mail_poll_seconds)


if __name__ == "__main__":
    main()
