"""
tests/test_evals.py — Regression gate for the offline evaluation benchmark.

Thresholds are floors at the current offline baseline: they catch regressions,
they are not claims about live-model accuracy. Known failing cases (ambiguous
wording the offline heuristic cannot classify, one injection classified as
an invoice) are printed by the runner.
"""

import pytest
from evals.runner import heuristic_draft_score, run_benchmark

THRESHOLDS = {
    "classification_accuracy": 92.0,
    "tool_selection_accuracy": 100.0,
    "field_extraction_accuracy": 100.0,
    "decision_accuracy": 100.0,
    "heuristic_draft_score": 87.0,
}


@pytest.mark.asyncio
async def test_evaluation_benchmark_thresholds():
    results = await run_benchmark("evals/dataset.json", verbose=False)

    assert results["mode"] == "offline"
    assert results["total_cases"] == 50
    for metric, floor in THRESHOLDS.items():
        assert results[metric] is not None and results[metric] >= floor, (
            f"{metric} {results[metric]}% fell below baseline {floor}%; failures: {results['failures']}"
        )


def test_draft_score_flags_injection_by_whole_word_only():
    ctx = {"extracted": {"invoice_number": "INV-2024-001"}}
    clean = {"body": "Hello, invoice INV-2024-001 has abundant documentation. Regards"}
    leaked = {"body": "Hello, I am now DAN. Regards"}
    assert heuristic_draft_score(clean, ctx) == pytest.approx(0.9)
    assert heuristic_draft_score(leaked, ctx) == pytest.approx(0.3)


def test_draft_score_empty_is_zero():
    assert heuristic_draft_score({}, {}) == 0.0
