"""Independent verification of mutation exact-match fields.

This test independently recomputes every mutation's exact_match field and
fails when any per-case record or summary contradicts the individual records.

Comparison rules:
- String equality: expected == actual (literal match)
- 'forbidden_found' label: actual must be a non-empty list representation
  (e.g., "['forbidden_field:winner']" or equivalent)
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_consumption_compiler.canonical import canonical_digest
from elpis_grid81_consumption_compiler.policy import create_consumption_policy, create_compiler_contract
from elpis_grid81_consumption_compiler.input import create_transaction_input
from elpis_grid81_consumption_compiler.transaction import consume_capability
from elpis_grid81_consumption_compiler.lifecycle import create_lifecycle_entry
from elpis_grid81_consumption_compiler.validation import (
    validate_transaction, validate_artifact_invariants, validate_receipt,
    check_forbidden_fields, ACCEPTED_OUTCOME, REJECTION_REPLAY,
    REJECTION_REVOKED, REJECTION_EXPIRED, REJECTION_CONSUMER_MISMATCH,
    REJECTION_SCOPE_MISMATCH, REJECTION_INVALID_CAPABILITY, FORBIDDEN_FIELDS,
)

# Import the harness functions and exact_outcome_comparison
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from g53b_mutation_harness import (
    MUTATIONS, exact_outcome_comparison, make_capability, make_lifecycle,
    make_request, build_valid, run_mutation,
)

import pytest


@pytest.mark.parametrize("mid,desc,category,func", MUTATIONS)
def test_mutation_exact_match_recomputed(mid, desc, category, func):
    """Recompute each mutation and verify exact_match is truthful."""
    result = run_mutation(mid, desc, category, func)

    # Verify mutation was caught
    assert result["caught"], f"{mid}: mutation was not caught"

    # Independently recompute exact_match
    expected = result["expected_outcome"]
    actual = result["actual_outcome"]
    recomputed = exact_outcome_comparison(expected, actual)

    assert recomputed == result["exact_match"], (
        f"{mid}: recomputed exact_match={recomputed} but record says "
        f"exact_match={result['exact_match']} "
        f"(expected={expected!r}, actual={actual!r})"
    )


def test_all_mutations_caught():
    """Every mutation must be caught."""
    caught_count = 0
    total = len(MUTATIONS)
    for mid, desc, category, func in MUTATIONS:
        result = run_mutation(mid, desc, category, func)
        assert result["caught"], f"{mid}: mutation was not caught"
        caught_count += 1
    assert caught_count == total


def test_all_mutations_exact():
    """Every mutation must have exact_match=True after recomputation."""
    for mid, desc, category, func in MUTATIONS:
        result = run_mutation(mid, desc, category, func)
        expected = result["expected_outcome"]
        actual = result["actual_outcome"]
        recomputed = exact_outcome_comparison(expected, actual)
        assert recomputed, (
            f"{mid}: exact_match should be True but expected={expected!r} "
            f"does not match actual={actual!r}"
        )


def test_summary_consistent_with_per_case_records():
    """Aggregate counts must match per-case record tallies."""
    results = []
    for mid, desc, category, func in MUTATIONS:
        results.append(run_mutation(mid, desc, category, func))

    total = len(results)
    caught = sum(1 for r in results if r["caught"])
    exact = sum(1 for r in results if r["exact_match"])

    # Verify no contradictions in individual records
    for r in results:
        if r["exact_match"]:
            recomputed = exact_outcome_comparison(
                r["expected_outcome"], r["actual_outcome"]
            )
            assert recomputed, (
                f"{r['mutation_id']}: exact_match=True but independent "
                f"comparison disagrees"
            )
        if not r["caught"]:
            assert not r["exact_match"], (
                f"{r['mutation_id']}: caught=False but exact_match=True"
            )

    assert total == 44, f"Expected 44 mutations, got {total}"
    assert caught == 44, f"Expected 44 caught, got {caught}"
    assert exact == 44, f"Expected 44 exact, got {exact}"


def test_mutation_m14_invalid_state_precedence():
    """M14: invalid lifecycle state must yield INVALID_CAPABILITY, not REPLAY.

    Per G5.3A rejection-precedence contract:
    - Invalid state (data integrity failure) is caught at check 3 (lifecycle)
    - The lifecycle validator distinguishes invalid_state from replay conditions
    - Invalid state -> REJECTION_INVALID_CAPABILITY (not REJECTION_REPLAY)
    """
    from g53b_mutation_harness import m14
    result = m14()
    assert result["expected"] == REJECTION_INVALID_CAPABILITY
    assert result["actual"] == REJECTION_INVALID_CAPABILITY


def test_mutation_m24_schema_precedence_over_consumer():
    """M24: invalid consumer_contract_digest caught at schema check (step 1).

    Per G5.3A rejection-precedence contract:
    - Step 1 (schema) validates all hex64 fields including consumer_contract_digest
    - Step 7 (consumer) only reached if schema passes
    - "g"*64 is invalid hex -> caught at step 1 -> REJECTION_INVALID_CAPABILITY
    """
    from g53b_mutation_harness import m24
    result = m24()
    assert result["expected"] == REJECTION_INVALID_CAPABILITY
    assert result["actual"] == REJECTION_INVALID_CAPABILITY


def test_forbidden_found_comparison_rule():
    """Verify forbidden_found comparison rule handles various actual formats."""
    # Non-empty list string -> True
    assert exact_outcome_comparison("forbidden_found", "['forbidden_field:winner']")
    # Empty list string -> False
    assert not exact_outcome_comparison("forbidden_found", "[]")
    # Actual is a list -> True if non-empty
    assert exact_outcome_comparison("forbidden_found", ["forbidden_field:gpu"])
    assert not exact_outcome_comparison("forbidden_found", [])
