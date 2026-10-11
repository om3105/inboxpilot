"""
tests/test_evals.py — Pytest regression test running the evaluation benchmark.
Asserts that performance across all core metrics exceeds strict thresholds.
"""

import pytest
from evals.runner import run_benchmark


@pytest.mark.asyncio
async def test_evaluation_benchmark_thresholds():
    """Ensure the agent meets high-performance quality gates."""
    # Run full 50-example benchmark
    results = await run_benchmark("evals/dataset.json")

    assert results["tool_selection_accuracy"] >= 85.0, (
        f"Tool-selection accuracy {results['tool_selection_accuracy']}% below 85% threshold"
    )
    assert results["field_extraction_accuracy"] >= 85.0, (
        f"Field-extraction accuracy {results['field_extraction_accuracy']}% below 85% threshold"
    )
    assert results["task_completion_rate"] >= 85.0, (
        f"Task completion rate {results['task_completion_rate']}% below 85% threshold"
    )
    assert results["llm_judge_draft_score"] >= 80.0, (
        f"LLM draft quality score {results['llm_judge_draft_score']}% below 80% threshold"
    )
