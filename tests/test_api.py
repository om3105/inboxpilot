"""
tests/test_api.py — Integration tests for FastAPI endpoints, authentication, and approval workflow.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import get_settings


@pytest.fixture
def auth_headers():
    settings = get_settings()
    return {"X-Demo-Token": settings.demo_token}


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_samples_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/samples")
        assert resp.status_code == 200
        data = resp.json()
        assert "samples" in data
        assert len(data["samples"]) >= 1


@pytest.mark.asyncio
async def test_process_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/process",
            json={"raw_input": "Test content", "input_source": "text"},
            headers={"X-Demo-Token": "invalid-token"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_process_and_approve_flow(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Submit leave request
        payload = {
            "raw_input": (
                "From: aarav.sharma@acme.dev\n"
                "Subject: Casual leave\n\n"
                "Please approve 2 days leave for EMP001 from 2024-10-24."
            ),
            "input_source": "email",
        }
        res = await ac.post("/process", json=payload, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        run_id = data["run_id"]
        assert data["requires_approval"] is True
        assert data["status"] == "awaiting_approval"

        # 2. Check run status via GET
        assert (await ac.get(f"/runs/{run_id}")).status_code == 401
        get_res = await ac.get(f"/runs/{run_id}", headers=auth_headers)
        assert get_res.status_code == 200
        assert get_res.json()["requires_approval"] is True

        # 3. Approve
        appr_res = await ac.post(f"/runs/{run_id}/approve", headers=auth_headers)
        assert appr_res.status_code == 200
        appr_data = appr_res.json()
        assert appr_data["requires_approval"] is False
        assert appr_data["status"] == "completed"


@pytest.mark.asyncio
async def test_process_and_reject_flow(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "raw_input": (
                "From: priya.patel@acme.dev\n"
                "Subject: Leave request\n\n"
                "Requesting casual leave. EMP002."
            ),
            "input_source": "email",
        }
        res = await ac.post("/process", json=payload, headers=auth_headers)
        assert res.status_code == 200
        run_id = res.json()["run_id"]

        # Reject
        rej_res = await ac.post(
            f"/runs/{run_id}/reject",
            json={"reason": "Project deadline conflict"},
            headers=auth_headers,
        )
        assert rej_res.status_code == 200
        assert rej_res.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_missing_token_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/process", json={"raw_input": "x", "input_source": "text"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_fails_closed_without_configured_token(monkeypatch):
    import app.main as main_module
    from app.config import Settings

    monkeypatch.setattr(main_module, "get_settings", lambda: Settings(demo_token=""))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/process",
            json={"raw_input": "x", "input_source": "text"},
            headers={"X-Demo-Token": ""},
        )
        assert resp.status_code == 503


@pytest.mark.asyncio
async def test_cors_allows_only_configured_origins_without_credentials():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        preflight = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "X-Demo-Token"}
        ok = await ac.options("/process", headers={"Origin": "https://allowed.example", **preflight})
        assert ok.headers.get("access-control-allow-origin") == "https://allowed.example"
        assert "access-control-allow-credentials" not in ok.headers

        bad = await ac.options("/process", headers={"Origin": "https://evil.example", **preflight})
        assert "access-control-allow-origin" not in bad.headers


@pytest.mark.asyncio
async def test_review_outcome_reports_error_reason(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/process",
            json={"raw_input": "From: x@y.com\nSubject: Leave\n\nI want 2 days off. EMP999.", "input_source": "email"},
            headers=auth_headers,
        )
        data = res.json()
        assert data["status"] == "needs_human_review"
        assert "EMP999" in data["error"]


def test_dashboard_has_no_prefilled_token_or_alerts():
    from app.ui import HTML_CONTENT
    assert 'value="change-me' not in HTML_CONTENT
    assert "alert(" not in HTML_CONTENT
    assert 'id="errorBanner"' in HTML_CONTENT
