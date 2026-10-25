"""
tests/test_demo_mode.py — Public demo mode: no token, and the real database is never touched.
"""

import pytest
from httpx import ASGITransport, AsyncClient

import app.database as database
import app.main as main_module
import tools.apply_update as apply_module
import tools.lookup_record as lookup_module
from app.config import Settings
from app.main import app
from app.models import ActionType, ProposedAction
from tools.apply_update import apply_update
from tools.lookup_record import lookup_record

LEAVE = "From: aarav.sharma@acme.dev\nSubject: Leave\n\nCasual leave 2024-11-04 to 2024-11-05. EMP001."


@pytest.fixture
def demo_mode(monkeypatch):
    settings = Settings(demo_public=True, demo_token="", mongodb_uri="mongodb+srv://real-cluster.example")
    for module in (main_module, apply_module, lookup_module):
        monkeypatch.setattr(module, "get_settings", lambda: settings)

    def forbidden():
        raise AssertionError("public demo mode must never touch the real database")
    monkeypatch.setattr(database, "get_database", forbidden)
    return settings


@pytest.mark.asyncio
async def test_config_reports_demo_mode(demo_mode):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/config")).json() == {"demo_public": True}


@pytest.mark.asyncio
async def test_demo_runs_and_approves_without_token(demo_mode):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/process", json={"raw_input": LEAVE, "input_source": "email"})
        assert res.status_code == 200
        run_id = res.json()["run_id"]
        assert res.json()["status"] == "awaiting_approval"

        assert (await ac.get(f"/runs/{run_id}")).status_code == 200
        approved = await ac.post(f"/runs/{run_id}/approve")
        assert approved.status_code == 200
        assert approved.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_demo_writes_go_to_sandbox_only(demo_mode):
    action = ProposedAction(
        action_type=ActionType.DEDUCT_LEAVE,
        collection="employees",
        filter_query={"employee_id": "EMP001"},
        update_payload={"$inc": {"leave_balance.casual": -2}},
        reason="test",
    )
    result = await apply_update(action)
    assert result["mode"] == "local_mock"
    record = await lookup_record("employees", {"employee_id": "EMP001"})
    assert record.record["leave_balance"]["casual"] == 8


@pytest.mark.asyncio
async def test_token_still_required_when_demo_mode_off():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/config")).json() == {"demo_public": False}
        res = await ac.post("/process", json={"raw_input": LEAVE, "input_source": "email"})
        assert res.status_code == 401


def test_demo_mode_keeps_run_state_in_memory(monkeypatch):
    import agent.checkpointer as cp
    from langgraph.checkpoint.memory import MemorySaver

    settings = Settings(demo_public=True, mongodb_uri="mongodb+srv://real-cluster.example")
    monkeypatch.setattr(cp, "get_settings", lambda: settings)
    monkeypatch.setattr(cp, "_checkpointer_instance", None)
    assert isinstance(cp.get_checkpointer(), MemorySaver)
