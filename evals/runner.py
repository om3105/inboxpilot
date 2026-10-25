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
import enum
import json
import logging
import os
import re
import time
from typing import Any

from agent.graph import build_agent_graph
from app.llm import FALLBACK_COUNTS, LLMProvider
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


# State keys needed to score a case; cached so live runs can resume across days.
_CACHED_KEYS = ("document_type", "tool_trace", "extracted", "proposed_action", "status", "draft_reply")


def _jsonable(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=lambda o: o.value if isinstance(o, enum.Enum) else str(o)))


def _load_cache(path: str | None) -> dict[str, Any]:
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(path: str, cache: dict[str, Any]) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1)
    os.replace(tmp, path)


def _pct(hits: int, total: int) -> float | None:
    return round(hits / total * 100, 1) if total else None


async def run_benchmark(
    dataset_path: str = "evals/dataset.json",
    limit: int | None = None,
    verbose: bool = True,
    cache_path: str | None = None,
) -> dict[str, Any]:
    """Execute the benchmark and return calculated metrics plus per-case failures.

    With ``cache_path``, each completed case's state is saved and reused on the
    next run. In live mode the run stops at the first case whose LLM call fell
    back to the heuristic (e.g. daily quota exhausted) without scoring or caching
    it, so a rate-limited key can finish the benchmark over several runs.
    """
    with open(dataset_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if limit:
        cases = cases[:limit]

    provider = LLMProvider()
    mode = "live" if provider.is_live_available() else "offline"
    cache_key = f"{mode}:{provider.model_name}:{'live_drafts' if provider.live_drafts else 'template_drafts'}"
    cache = _load_cache(cache_path)
    case_cache: dict[str, Any] = cache.setdefault(cache_key, {})
    for k in FALLBACK_COUNTS:
        FALLBACK_COUNTS[k] = 0
    agent = build_agent_graph()

    dataset_size = len(cases)
    total = 0
    cached_hits = 0
    stopped_early = False
    class_matches = 0
    tool_matches = 0
    field_matches = 0
    field_checks = 0
    action_matches = 0
    draft_scores: list[float] = []
    failures: list[dict[str, Any]] = []

    if verbose:
        print(f"\n🚀 Running InboxPilot Evaluation Benchmark on {dataset_size} test cases ({mode} mode, {cache_key})...\n")

    for case in cases:
        case_id = case["id"]
        expected_extracted = case.get("expected_extracted", {})
        expected_action = case.get("expected_action", "none")
        expected_tools = case.get("expected_tools", [])

        if case_id in case_cache:
            values = case_cache[case_id]
            cached_hits += 1
        else:
            thread_id = f"eval_{case_id}_{int(time.time())}"
            config = {"configurable": {"thread_id": thread_id}}

            initial_state = {
                "run_id": thread_id,
                "raw_input": case["input"],
                "input_source": "email",
                "tool_trace": [],
            }

            fallbacks_before = sum(FALLBACK_COUNTS.values())
            # Runs stop at the approval gate; evals never resume, so no writes occur.
            await agent.ainvoke(initial_state, config=config)
            state = await agent.aget_state(config)
            values = _jsonable({k: state.values.get(k) for k in _CACHED_KEYS if k in state.values})

            if mode == "live" and sum(FALLBACK_COUNTS.values()) > fallbacks_before:
                stopped_early = True
                if verbose:
                    print(f"⏸  {case_id}: live LLM call failed (quota or outage); stopping. "
                          "Rerun later to resume from this case.")
                break
            if cache_path:
                case_cache[case_id] = values
                _save_cache(cache_path, cache)

        total += 1
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
        "model": provider.model_name if mode == "live" else None,
        "total_cases": total,
        "dataset_size": dataset_size,
        "complete": total == dataset_size,
        "cached_cases": cached_hits,
        "classification_accuracy": _pct(class_matches, total),
        "tool_selection_accuracy": _pct(tool_matches, total),
        "field_extraction_accuracy": _pct(field_matches, field_checks),
        "decision_accuracy": _pct(action_matches, total),
        "heuristic_draft_score": avg_draft,
        "drafts_scored": len(draft_scores),
        # Live calls that errored and silently used the offline heuristic instead
        "llm_fallbacks": dict(FALLBACK_COUNTS),
        "failures": failures,
    }

    if verbose:
        print_results_table(results)
    return results


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value}%"


def print_results_table(results: dict[str, Any]):
    """Format evaluation results as a Markdown table followed by per-case failures."""
    scope = f"{results['total_cases']} cases" if results["complete"] else (
        f"PARTIAL: {results['total_cases']}/{results['dataset_size']} cases scored so far"
    )
    model = f", {results['model']}" if results["model"] else ""
    print(f"InboxPilot eval results — {scope}, {results['mode']} mode{model}\n")
    print("| Metric                    | Score  |")
    print("|---------------------------|--------|")
    print(f"| Classification Accuracy   | {_fmt(results['classification_accuracy']):<6} |")
    print(f"| Tool-Selection Accuracy   | {_fmt(results['tool_selection_accuracy']):<6} |")
    print(f"| Field-Extraction Accuracy | {_fmt(results['field_extraction_accuracy']):<6} |")
    print(f"| Decision Accuracy         | {_fmt(results['decision_accuracy']):<6} |")
    print(f"| Heuristic Draft Score     | {_fmt(results['heuristic_draft_score']):<6} |")

    fb = results["llm_fallbacks"]
    if results["mode"] == "live":
        print(f"\nLLM fallbacks to heuristic: {fb['extract']} extractions, {fb['draft']} drafts"
              + (" (these cases were NOT scored on the live model)" if any(fb.values()) else ""))

    if results["failures"]:
        print(f"\nFailing cases ({len(results['failures'])}):")
        for f in results["failures"]:
            print(f"  {f['id']} [{f['category']}]: " + "; ".join(f["reasons"]))
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the InboxPilot eval benchmark.")
    parser.add_argument("--dataset", default="evals/dataset.json")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--cache",
        default=None,
        help="JSON file to save/resume per-case results (use for rate-limited live runs)",
    )
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.dataset, args.limit, cache_path=args.cache))
