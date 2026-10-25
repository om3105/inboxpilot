"""
tests/test_mail.py — Real-mailbox support: IMAP poller and sending approved replies.

No network: IMAP and SMTP are replaced with fakes.
"""

from email.message import EmailMessage

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

import scripts.mail_poller as poller
import tools.send_reply as send_module
from app.config import Settings
from app.main import app

LEAVE_BODY = "Hi HR,\n\nI need casual leave from 2024-11-04 to 2024-11-05. My employee ID is EMP001.\n\nThanks,\nAarav"


def make_email(body=LEAVE_BODY, sender="Aarav Sharma <aarav.sharma@acme.dev>", html=False, auto=False) -> bytes:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = "ops@acme.dev"
    msg["Subject"] = "Casual leave"
    msg["Date"] = "Mon, 14 Oct 2024 09:30:00 +0000"
    msg["Message-ID"] = "<abc123@acme.dev>"
    if auto:
        msg["Auto-Submitted"] = "auto-replied"
    if html:
        msg.set_content("<p>" + body.replace("\n", "<br>") + "</p>", subtype="html")
    else:
        msg.set_content(body)
    return msg.as_bytes()


# ── Poller ───────────────────────────────────────────────

def test_parse_plain_and_html():
    plain = poller.parse_message(make_email())
    assert plain["from_address"] == "aarav.sharma@acme.dev"
    assert plain["message_id"] == "<abc123@acme.dev>"
    assert "EMP001" in plain["body"]

    html = poller.parse_message(make_email(html=True))
    assert "<p>" not in html["body"] and "EMP001" in html["body"]


def test_skips_own_mail_and_auto_replies():
    own = poller.parse_message(make_email(sender="ops.bot@gmail.com"))
    assert poller.should_skip(own, "ops.bot@gmail.com") == "sent by this mailbox"
    auto = poller.parse_message(make_email(auto=True))
    assert poller.should_skip(auto, "ops.bot@gmail.com") == "auto-reply"
    normal = poller.parse_message(make_email())
    assert poller.should_skip(normal, "ops.bot@gmail.com") is None


class FakeIMAP:
    def __init__(self, raw_messages):
        self.raw = {str(i + 1).encode(): m for i, m in enumerate(raw_messages)}
        self.seen = set()

    def search(self, charset, criterion):
        return "OK", [b" ".join(k for k in self.raw if k not in self.seen)]

    def fetch(self, num, spec):
        assert "PEEK" in spec  # must not mark read before InboxPilot accepts it
        return "OK", [(b"header", self.raw[num])]

    def store(self, num, op, flag):
        self.seen.add(num)


def _client(status_code):
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(status_code, json={"run_id": "run_x", "status": "awaiting_approval"})
    return httpx.Client(transport=httpx.MockTransport(handler)), sent


def test_poll_marks_read_only_after_success(monkeypatch):
    monkeypatch.setattr(poller, "get_settings", lambda: Settings(mail_username="ops.bot@gmail.com", demo_token="t"))
    imap = FakeIMAP([make_email()])

    client, sent = _client(500)
    assert poller.poll_once(imap, client) == 0
    assert imap.seen == set()  # left unread for retry

    client, sent = _client(200)
    assert poller.poll_once(imap, client) == 1
    assert imap.seen == {b"1"}
    body = sent[0].read().decode()
    assert '"from_address":"aarav.sharma@acme.dev"' in body.replace(" ", "")
    assert sent[0].headers["X-Demo-Token"] == "t"


# ── Sending approved replies ─────────────────────────────

class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout=None):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        pass

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr(send_module.smtplib, "SMTP_SSL", FakeSMTP)
    return FakeSMTP


def _settings(monkeypatch, **kw):
    s = Settings(mail_username="ops.bot@gmail.com", mail_password="app-pass", demo_token="test-demo-token", **kw)
    monkeypatch.setattr(send_module, "get_settings", lambda: s)


SOURCE = {"message_id": "<abc123@acme.dev>", "from_address": "aarav.sharma@acme.dev", "subject": "Casual leave"}


async def _process_and_decide(decision):
    headers = {"X-Demo-Token": "test-demo-token"}
    raw = poller.to_process_request(poller.parse_message(make_email()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        run = (await ac.post("/process", json=raw, headers=headers)).json()
        assert run["status"] == "awaiting_approval"
        inbox = (await ac.get("/inbox", headers=headers)).json()["messages"]
        assert inbox[0]["run_id"] == run["run_id"]
        return (await ac.post(f"/runs/{run['run_id']}/{decision}", headers=headers, json={})).json()


@pytest.mark.asyncio
async def test_approve_sends_threaded_reply(monkeypatch, smtp):
    _settings(monkeypatch, mail_send_replies=True)
    result = await _process_and_decide("approve")
    assert result["status"] == "completed"
    assert result["reply_result"]["sent"] is True
    assert "send_reply" in result["tool_trace"]
    msg = smtp.sent[0]
    assert msg["To"] == "aarav.sharma@acme.dev"
    assert msg["Subject"] == "Re: Casual leave"
    assert msg["In-Reply-To"] == "<abc123@acme.dev>"


@pytest.mark.asyncio
async def test_reject_sends_nothing(monkeypatch, smtp):
    _settings(monkeypatch, mail_send_replies=True)
    result = await _process_and_decide("reject")
    assert result["status"] == "rejected"
    assert smtp.sent == []


@pytest.mark.asyncio
async def test_no_send_when_disabled(monkeypatch, smtp):
    _settings(monkeypatch, mail_send_replies=False)
    result = await _process_and_decide("approve")
    assert result["reply_result"] == {"sent": False, "reason": "MAIL_SEND_REPLIES is off"}
    assert smtp.sent == []


@pytest.mark.asyncio
async def test_never_sends_in_public_demo_mode(monkeypatch, smtp):
    _settings(monkeypatch, mail_send_replies=True, demo_public=True)
    result = await send_module.send_reply({"to": "x@y.com", "subject": "Re: hi", "body": "hello"}, SOURCE)
    assert result == {"sent": False, "reason": "public demo mode never sends email"}
    assert smtp.sent == []
