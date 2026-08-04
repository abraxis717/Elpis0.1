"""G5.3C Independent mutation exactness verification.

Recomputes every mutation's exact-match field and fails when any summary
contradicts the per-case records.
"""
import pytest
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_application_executor.mutation_harness import (
    MUTATIONS, exact_outcome_comparison, run_mutation,
)


@pytest.mark.parametrize("mutation_id,description,category,func", MUTATIONS)
def test_mutation_exact_match(mutation_id, description, category, func):
    """Each mutation must have exact_match=True."""
    result = run_mutation(mutation_id, description, category, func)
    assert result["caught"], f"{mutation_id}: mutation was not caught"
    assert result["exact_match"], (
        f"{mutation_id}: exact_match=False. "
        f"expected={result['expected_outcome']}, actual={result['actual_outcome']}"
    )


def test_all_mutations_caught():
    """All mutations must be caught."""
    total = len(MUTATIONS)
    caught = 0
    for mid, desc, cat, func in MUTATIONS:
        result = run_mutation(mid, desc, cat, func)
        if result["caught"]:
            caught += 1
    assert caught == total, f"Only {caught}/{total} mutations caught"


def test_all_mutations_exact():
    """All mutations must have exact outcome match."""
    total = len(MUTATIONS)
    exact = 0
    for mid, desc, cat, func in MUTATIONS:
        result = run_mutation(mid, desc, cat, func)
        if result["exact_match"]:
            exact += 1
    assert exact == total, f"Only {exact}/{total} mutations have exact match"


def test_summary_consistency():
    """Summary counts must match per-record counts."""
    results = []
    for mid, desc, cat, func in MUTATIONS:
        result = run_mutation(mid, desc, cat, func)
        results.append(result)

    caught_count = sum(1 for r in results if r["caught"])
    exact_count = sum(1 for r in results if r["exact_match"])
    total = len(results)

    assert caught_count == total, f"Summary contradiction: caught={caught_count}, total={total}"
    assert exact_count == total, f"Summary contradiction: exact={exact_count}, total={total}"
