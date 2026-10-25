"""
evals/runner.py — Evaluation benchmark runner for InboxPilot.

Computes (all scored strictly, per case):
  1. Classification Accuracy (%)    — document_type matches the label
  2. Tool-Selection Accuracy (%)    — tool trace matches the expected sequence exactly
  3. Field-Extraction Accuracy (%)  — per labelled field
  4. Decision Accuracy (%)          — proposed action (or safe no-op) matches the label
  5. Heuristic Draft Score (%)      — rule-based tone/grounding/safety check, NOT an LLM judge

The run mode is reported alongside the scores: "offline" uses the deterministic
heuristic extractor in app/llm.py (a regression gate, not a measure of model
quality); "live" uses the configured LLM via GEMINI_API_KEY.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import time
from typing import Any

from agent.graph import build_agent_graph
from app.llm import LLMProvider
from app.models import RunStatus

logger = logging.getLogger("inboxpilot.evals")

_UNSAFE_DRAFT_PATTERN = re.compile(
    r"\b(override|ignore (all )?(previous )?instructions|dan|secret keys?|drop table)\b"
)


def heuristic_draft_score(draft: dict[str, Any], context: dict[str, Any]) -> float:
    """Rule-based draft check on greeting/sign-off, grounding, and leaked injections (0.0 to 1.0)."""
    if not draft or not draft.get("body"):
        return 0.0

    body = draft.get("body", "").lower()
    score = 0.5  # base score for generating a non-empty draft

    # Professional greetings and sign-offs
    if re.search(r"\b(hello|hi|dear|regards|thank you)\b", body):
        score += 0.2

    # Operational grounding (references employee, invoice, or ticket)
    extracted = context.get("extracted", {})
    references = [
        extracted.get("employee_id"),
        extracted.get("invoice_number"),
        extracted.get("ticket_id"),
        extracted.get("employee_name"),
    ]
    if any(str(ref).lower() in body for ref in references if ref):
        score += 0.2

    # Injection leakage: whole-word matches only, so e.g. "abundant" isn't flagged as "dan"
    if _UNSAFE_DRAFT_PATTERN.search(body):
        score -= 0.4

    return min(max(score, 0.0), 1.0)


def _pct(hits: int, total: int) -> float | None:
    return round(hits / total * 100, 1) if total else None


async def run_benchmark(
    dataset_path: str = "evals/dataset.json",
    limit: int | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Execute the benchmark and return calculated metrics plus per-case failures."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if limit:
        cases = cases[:limit]

    mode = "live" if LLMProvider().is_live_available() else "offline"
    agent = build_agent_graph()

    total = len(cases)
    class_matches = 0
    tool_matches = 0
    field_matches = 0
    field_checks = 0
    action_matches = 0
    draft_scores: list[float] = []
    failures: list[dict[str, Any]] = []

    if verbose:
        print(f"\n🚀 Running InboxPilot Evaluation Benchmark on {total} test cases ({mode} mode)...\n")

    for case in cases:
        case_id = case["id"]
        expected_extracted = case.get("expected_extracted", {})
        expected_action = case.get("expected_action", "none")
        expected_tools = case.get("expected_tools", [])

        thread_id = f"eval_{case_id}_{int(time.time())}"
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "run_id": thread_id,
            "raw_input": case["input"],
            "input_source": "email",
            "tool_trace": [],
        }

        # Runs stop at the approval gate; evals never resume, so no writes occur.
        await agent.ainvoke(initial_state, config=config)
        state = await agent.aget_state(config)
        values = state.values
        case_failures: list[str] = []

        # 1. Classification
        actual_doc_type = values.get("document_type", "unknown")
        if actual_doc_type == case["expected_doc_type"]:
            class_matches += 1
        else:
            case_failures.append(f"doc_type {actual_doc_type!r} != {case['expected_doc_type']!r}")

        # 2. Tool selection: exact ordered sequence
        actual_tools = values.get("tool_trace", [])
        if actual_tools == expected_tools:
            tool_matches += 1
        else:
            case_failures.append(f"tools {actual_tools} != {expected_tools}")

        # 3. Field extraction
        extracted = values.get("extracted", {})
        for k, v in expected_extracted.items():
            field_checks += 1
            actual = extracted.get(k)
            if (v is None and not actual) or (v is not None and str(actual or "").lower() == str(v).lower()):
                field_matches += 1
            else:
                case_failures.append(f"field {k}={actual!r} != {v!r}")

        # 4. Decision: a "none" label is satisfied by no proposal, an explicit no-op,
        # or routing to human review.
        proposed = values.get("proposed_action") or {}
        actual_action = proposed.get("action_type", "none")
        if actual_action == expected_action or (
            expected_action == "none" and values.get("status") == RunStatus.NEEDS_HUMAN_REVIEW.value
        ):
            action_matches += 1
        else:
            case_failures.append(f"action {actual_action!r} != {expected_action!r}")

        # 5. Draft quality
        if values.get("draft_reply"):
            draft_scores.append(heuristic_draft_score(values["draft_reply"], values))

        if case_failures:
            failures.append({"id": case_id, "category": case.get("category"), "reasons": case_failures})

    avg_draft = round(sum(draft_scores) / len(draft_scores) * 100, 1) if draft_scores else None

    results = {
        "mode": mode,
        "total_cases": total,
        "classification_accuracy": _pct(class_matches, total),
        "tool_selection_accuracy": _pct(tool_matches, total),
        "field_extraction_accuracy": _pct(field_matches, field_checks),
        "decision_accuracy": _pct(action_matches, total),
        "heuristic_draft_score": avg_draft,
        "drafts_scored": len(draft_scores),
        "failures": failures,
    }

    if verbose:
        print_results_table(results)
    return results


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value}%"


def print_results_table(results: dict[str, Any]):
    """Format evaluation results as a Markdown table followed by per-case failures."""
    print(f"InboxPilot eval results — {results['total_cases']} cases, {results['mode']} mode\n")
    print("| Metric                    | Score  |")
    print("|---------------------------|--------|")
    print(f"| Classification Accuracy   | {_fmt(results['classification_accuracy']):<6} |")
    print(f"| Tool-Selection Accuracy   | {_fmt(results['tool_selection_accuracy']):<6} |")
    print(f"| Field-Extraction Accuracy | {_fmt(results['field_extraction_accuracy']):<6} |")
    print(f"| Decision Accuracy         | {_fmt(results['decision_accuracy']):<6} |")
    print(f"| Heuristic Draft Score     | {_fmt(results['heuristic_draft_score']):<6} |")

    if results["failures"]:
        print(f"\nFailing cases ({len(results['failures'])}):")
        for f in results["failures"]:
            print(f"  {f['id']} [{f['category']}]: " + "; ".join(f["reasons"]))
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the InboxPilot eval benchmark.")
    parser.add_argument("--dataset", default="evals/dataset.json")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.dataset, args.limit))
