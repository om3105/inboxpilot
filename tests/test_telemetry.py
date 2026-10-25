"""
tests/test_telemetry.py — Verify Langfuse v4 spans are emitted for agent runs.
"""

import uuid

import pytest
from langfuse import Langfuse
from langgraph.types import Command
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import app.telemetry as telemetry
from agent.graph import build_agent_graph


@pytest.fixture
def exporter(monkeypatch):
    exporter = InMemorySpanExporter()
    client = Langfuse(
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
        host="http://localhost:9",
        span_exporter=exporter,
        tracer_provider=TracerProvider(),
    )
    monkeypatch.setattr(telemetry, "_langfuse_client", client)
    yield exporter
    client.flush()


def test_disabled_without_credentials(monkeypatch):
    monkeypatch.setattr(telemetry, "_langfuse_client", None)
    assert telemetry.get_langfuse() is None


@pytest.mark.asyncio
async def test_passthrough_when_disabled(monkeypatch):
    monkeypatch.setattr(telemetry, "_langfuse_client", None)
    async with telemetry.trace_agent_run(run_id="run_x", input_type="email") as meta:
        assert meta["callbacks"] == []
    assert "duration_ms" in meta


@pytest.mark.asyncio
async def test_process_and_approve_share_one_trace(exporter):
    agent = build_agent_graph()
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    config = {"configurable": {"thread_id": run_id}}
    initial = {
        "run_id": run_id,
        "raw_input": (
            "From: aarav.sharma@acme.dev\nSubject: Casual leave\n\n"
            "Casual leave from 2024-11-04 to 2024-11-05. EMP001."
        ),
        "input_source": "email",
        "tool_trace": [],
    }

    async with telemetry.trace_agent_run(run_id=run_id, input_type="email") as meta:
        await agent.ainvoke(initial, config={**config, "callbacks": meta["callbacks"]})
    async with telemetry.trace_agent_run(run_id=run_id, input_type="resume", stage="approve") as meta:
        await agent.ainvoke(Command(resume={"decision": "approve"}), config={**config, "callbacks": meta["callbacks"]})

    telemetry._langfuse_client.flush()
    spans = exporter.get_finished_spans()
    names = {s.name for s in spans}

    assert {"inboxpilot_process", "inboxpilot_approve"} <= names
    # LangGraph nodes are traced as children via the callback handler
    assert "lookup_records" in names
    assert "execute_update" in names
    # Both stages land in the same deterministic trace
    expected_trace_id = int(Langfuse.create_trace_id(seed=run_id), 16)
    assert {s.context.trace_id for s in spans} == {expected_trace_id}
