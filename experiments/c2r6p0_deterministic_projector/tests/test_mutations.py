"""Mutation-suite test (mission 28).

Runs the deterministic mutation harness: 26 single-site semantic
mutants applied to a disposable copy of the worktree, each checked
against the core test suite. Every mutant must be KILLED. The report
lands in the persistent evidence directory as MUTATION_REPORT.json.

Runtime is dominated by 27 worktree copies (~12MB each); the mutation
checks themselves are the fast core suite.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

EXP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP_DIR / "scripts"))

import mutation_harness as MH  # noqa: E402


def test_all_substantive_mutants_killed():
    rep = MH.run_all()
    assert rep["mutants_total"] >= 20, rep
    assert rep["mutants_killed"] == rep["mutants_total"], rep["rows"]
    assert rep["mutants_survived"] == 0
    assert rep["all_killed"] is True
    assert rep["target_met"] is True
    # every row must record a kill (no vacuous pass); syntax-breaking
    # mutants are rejected at patch application (exact-1-occurrence
    # precondition), so none are counted.
    assert all(r["killed"] for r in rep["rows"])
    assert rep["baseline_core_suite_pass"] is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
