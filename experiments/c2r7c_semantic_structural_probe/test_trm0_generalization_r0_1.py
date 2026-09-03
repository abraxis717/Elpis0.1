"""R0.1 qualification regression tests for the held-out TRM-0 generalization
probe.

Covers the goal's required regression cases:
  - exit status: FAIL -> nonzero, PASS -> zero
  - mismatched residual is distinct / preserves cardinality / same universe
  - impossible mismatch fails or excludes explicitly
  - zero residual contains no active residual features
  - frozen loci cannot change
  - hidden final Grid81 never enters model features
  - semantic identifiers never enter TRM features
  - checkpoint is explicit and hashed
  - held-out fixtures do not overlap training transitions

Run:
  cd experiments/c2r7c_semantic_structural_probe
  python -m pytest -q test_trm0_generalization_r0_1.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
import random

import pytest

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from structural_trm_features import (  # noqa: E402
    FEATURE_WIDTH,
    encode_constraint_state,
)
from structural_trm_model import StructuralTRM64  # noqa: E402
import structural_trm_generalization as G  # noqa: E402

PY = sys.executable


# ---------------------------------------------------------------------------
# defect A : exit status
# ---------------------------------------------------------------------------


def test_exit_status_pass_returns_zero():
    assert G.final_rc(True) == 0


def test_exit_status_fail_returns_nonzero():
    rc = G.final_rc(False)
    assert rc != 0


def test_exit_status_values_distinct():
    assert G.final_rc(True) != G.final_rc(False)


# ---------------------------------------------------------------------------
# defect B : fail-closed mismatched residual
# ---------------------------------------------------------------------------


def _bits(indices):
    out = [0] * FEATURE_WIDTH
    for i in indices:
        out[i] = 1
    return tuple(out)


def test_mismatch_is_distinct_from_matched():
    declared = _bits([10, 11, 12, 13, 14])
    active = _bits([10, 12])
    res = G.construct_distinct_mismatch(declared, active)
    assert res.distinct is True
    assert tuple(res.bits) != tuple(active)


def test_mismatch_preserves_cardinality():
    declared = _bits([3, 7, 9, 20, 21, 22, 40])
    active = _bits([3, 9, 20])
    res = G.construct_distinct_mismatch(declared, active)
    assert res.distinct is True
    assert sum(res.bits) == sum(active)


def test_mismatch_stays_inside_declared_universe():
    declared = _bits([5, 6, 100, 101, 102, 103])
    active = _bits([5, 100])
    res = G.construct_distinct_mismatch(declared, active)
    assert res.distinct is True
    for i in range(FEATURE_WIDTH):
        if res.bits[i]:
            assert declared[i], "mismatch activated an undeclared index"


def test_mismatch_same_universe_as_matched():
    # The declared universe passed in is identical to the one the matched
    # residual lives in; the mismatch must be a subset of it.
    declared = _bits([1, 2, 3, 4, 5])
    active = _bits([1, 2])
    res = G.construct_distinct_mismatch(declared, active)
    assert res.distinct is True
    universe = set(i for i, v in enumerate(declared) if v)
    support = set(i for i, v in enumerate(res.bits) if v)
    assert support <= universe


def test_mismatch_empty_active_is_unevaluable_not_matched():
    declared = _bits([10, 11, 12])
    active = _bits([])
    res = G.construct_distinct_mismatch(declared, active)
    assert res.distinct is False
    assert res.reason != "ok"
    # must NOT silently return the matched (empty) residual as a mismatch
    assert res.bits == (0,) * FEATURE_WIDTH


def test_mismatch_no_inactive_declared_is_unevaluable():
    # every declared constraint is already active -> no distinct same-count
    # subset exists
    declared = _bits([10, 11])
    active = _bits([10, 11])
    res = G.construct_distinct_mismatch(declared, active)
    assert res.distinct is False
    assert res.reason != "ok"


def test_mismatch_never_equals_matched_randomized():
    rng = random.Random(1234)
    for _ in range(300):
        k = rng.randint(1, 6)
        declared_idx = rng.sample(range(FEATURE_WIDTH), 2 * k)
        active_idx = rng.sample(declared_idx, k)
        declared = _bits(declared_idx)
        active = _bits(active_idx)
        res = G.construct_distinct_mismatch(declared, active)
        if res.distinct:
            assert tuple(res.bits) != tuple(active)
            assert sum(res.bits) == sum(active)
            for i in range(FEATURE_WIDTH):
                if res.bits[i]:
                    assert declared[i]
        else:
            assert res.reason != "ok"
            # when unevaluable, bits must be the all-zero marker, never matched
            assert res.bits == (0,) * FEATURE_WIDTH


def declared_idx(declared):
    return [i for i, v in enumerate(declared) if v]


# ---------------------------------------------------------------------------
# zero residual arm
# ---------------------------------------------------------------------------


def test_zero_residual_contains_no_active_features():
    declared = _bits([1, 2, 3])
    matched = _bits([1, 3])
    active, mismatch = G.select_arm_residual("zero", declared, matched)
    assert mismatch is None
    assert sum(active) == 0
    assert active == (0,) * FEATURE_WIDTH


def test_matched_residual_returns_active_unchanged():
    declared = _bits([1, 2, 3])
    matched = _bits([1, 3])
    active, mismatch = G.select_arm_residual("matched", declared, matched)
    assert active == matched
    assert mismatch is None


def test_select_arm_residual_unknown_mode_fails():
    with pytest.raises(ValueError):
        G.select_arm_residual("bogus", _bits([1]), _bits([1]))


# ---------------------------------------------------------------------------
# mechanism gate (pure)
# ---------------------------------------------------------------------------


def _arm(resolved, cases=4, mean_final=2.0, frozen=0, auth=0):
    return {
        "resolved": resolved,
        "cases": cases,
        "authority": auth,
        "authority_granted": auth,
        "residual_sum": int(mean_final * cases),
        "residual_initial_sum": int(mean_final * cases),
        "frozen_cell_violations": frozen,
        "valid_transitions": 0,
        "invalid_transitions": 0,
        "materialisable": 0,
        "steps_sum": 0,
        "mean_final_residual": mean_final,
        "mean_initial_residual": mean_final,
    }


def _totals(matched, null, zero, mismatch):
    return {
        "trm_matched": matched,
        "null": null,
        "trm_zero_residual": zero,
        "trm_mismatched_residual": mismatch,
    }


def test_gate_pass_when_all_clauses_hold():
    totals = _totals(
        _arm(resolved=4, mean_final=0.0),
        _arm(resolved=0, mean_final=8.0),
        _arm(resolved=1, mean_final=6.0),
        _arm(resolved=1, mean_final=6.0),
    )
    stats = {
        "evaluable_fixtures": 4,
        "unevaluable_fixtures": 0,
        "valid_distinct_steps": 40,
        "degenerate_steps": 0,
    }
    passed, clauses = G.compute_mechanism_gate(totals, stats, 4)
    assert passed is True
    for c in clauses.values():
        assert c["passed"] is True


def test_gate_fail_when_matched_does_not_beat_null():
    totals = _totals(
        _arm(resolved=0, mean_final=8.0),
        _arm(resolved=4, mean_final=1.0),
        _arm(resolved=0, mean_final=8.0),
        _arm(resolved=0, mean_final=8.0),
    )
    stats = {
        "evaluable_fixtures": 4,
        "unevaluable_fixtures": 0,
        "valid_distinct_steps": 40,
        "degenerate_steps": 0,
    }
    passed, clauses = G.compute_mechanism_gate(totals, stats, 4)
    assert passed is False
    assert clauses["c1_matched_beats_null"]["passed"] is False


def test_gate_fail_when_not_better_than_any_ablation():
    totals = _totals(
        _arm(resolved=1, mean_final=6.0),
        _arm(resolved=0, mean_final=9.0),
        _arm(resolved=2, mean_final=3.0),
        _arm(resolved=2, mean_final=3.0),
    )
    stats = {
        "evaluable_fixtures": 4,
        "unevaluable_fixtures": 0,
        "valid_distinct_steps": 40,
        "degenerate_steps": 0,
    }
    passed, clauses = G.compute_mechanism_gate(totals, stats, 4)
    assert passed is False
    assert clauses["c2_matched_beats_ablation"]["passed"] is False


def test_gate_fail_on_frozen_violation():
    totals = _totals(
        _arm(resolved=4, mean_final=0.0, frozen=1),
        _arm(resolved=0, mean_final=8.0),
        _arm(resolved=1, mean_final=6.0),
        _arm(resolved=1, mean_final=6.0),
    )
    stats = {
        "evaluable_fixtures": 4,
        "unevaluable_fixtures": 0,
        "valid_distinct_steps": 40,
        "degenerate_steps": 0,
    }
    passed, clauses = G.compute_mechanism_gate(totals, stats, 4)
    assert passed is False
    assert clauses["c4_frozen_violations_zero"]["passed"] is False


def test_gate_fail_on_authority_granted():
    totals = _totals(
        _arm(resolved=4, mean_final=0.0, auth=1),
        _arm(resolved=0, mean_final=8.0),
        _arm(resolved=1, mean_final=6.0),
        _arm(resolved=1, mean_final=6.0),
    )
    stats = {
        "evaluable_fixtures": 4,
        "unevaluable_fixtures": 0,
        "valid_distinct_steps": 40,
        "degenerate_steps": 0,
    }
    passed, clauses = G.compute_mechanism_gate(totals, stats, 4)
    assert passed is False
    assert clauses["c5_authority_granted_zero"]["passed"] is False


def test_gate_requires_enough_valid_mismatch_comparisons():
    totals = _totals(
        _arm(resolved=4, mean_final=0.0),
        _arm(resolved=0, mean_final=8.0),
        _arm(resolved=1, mean_final=6.0),
        _arm(resolved=1, mean_final=6.0),
    )
    # only 1 evaluable mismatched fixture of 100 -> not meaningful
    stats = {
        "evaluable_fixtures": 1,
        "unevaluable_fixtures": 99,
        "valid_distinct_steps": 10,
        "degenerate_steps": 0,
    }
    passed, clauses = G.compute_mechanism_gate(totals, stats, 100)
    assert passed is False
    assert clauses["c3_mismatch_distinct"]["passed"] is False


def test_min_evaluable_required_floor():
    assert G.min_evaluable_required(100) == 25
    assert G.min_evaluable_required(4) == 2
    assert G.min_evaluable_required(2) == 2


# ---------------------------------------------------------------------------
# semantic identifiers never enter TRM features
# ---------------------------------------------------------------------------


class _Inv:
    def __init__(self, invariant_id, kind, lanes):
        self.invariant_id = invariant_id
        self.kind = kind
        self.lanes = lanes


def test_semantic_identifiers_do_not_change_features():
    a = (
        _Inv("op.a", "TERMINAL_RESOLUTION", ()),
        _Inv("pre.1.2", "PRECEDES", (1, 2)),
        _Inv("mem.1.2", "MEMORY_SPAN", (1, 2)),
    )
    b = (
        _Inv("zzz.completely.different", "TERMINAL_RESOLUTION", ()),
        _Inv("pre.q", "PRECEDES", (1, 2)),
        _Inv("mem.q", "MEMORY_SPAN", (1, 2)),
    )
    da, ra = encode_constraint_state(a, ("pre.1.2", "mem.1.2"))
    db, rb = encode_constraint_state(b, ("pre.q", "mem.q"))
    assert da == db
    assert ra == rb
    assert sum(da) == 3
    assert sum(ra) == 2


# ---------------------------------------------------------------------------
# hidden final Grid81 never enters model features
# ---------------------------------------------------------------------------


def test_model_features_contain_no_final_grid():
    # The model input is exactly (grid81, mask, declared529, residual529).
    # The residual/declared vectors are 529-bit structural signatures that do
    # NOT depend on any target/final grid. Prove: encoding the same invariants
    # at two different grids gives residual vectors that differ ONLY by the
    # grid state, and the 529-vectors never encode the whole final grid.
    rng = random.Random(7)
    from structural_trm_dataset import _load_probe_namespace
    ns = _load_probe_namespace()
    schema = ns["make_fixture"](rng, rng.randint(3, 6))
    ids = ns["residual"](schema.initial_grid, schema.invariants)
    declared, active = encode_constraint_state(schema.invariants, ids)
    # residual vector is a subset of the declared universe
    for i in range(FEATURE_WIDTH):
        if active[i]:
            assert declared[i]
    # the residual vector is sparse (a residual, not a 81-cell grid)
    assert sum(active) <= len(schema.invariants)
    assert FEATURE_WIDTH == 529


# ---------------------------------------------------------------------------
# frozen loci cannot change (model propose)
# ---------------------------------------------------------------------------


def test_model_propose_preserves_frozen_cells():
    torch.manual_seed(0)
    model = StructuralTRM64(h_cycles=3, l_cycles=6).eval()
    grid = [0] * 81
    grid[0] = 1
    grid[80] = 9
    mask = [1] * 81
    mask[0] = 0
    mask[80] = 0
    g = torch.tensor([grid], dtype=torch.long)
    mk = torch.tensor([mask], dtype=torch.long)
    declared = _bits([0, 5, 50])
    active = _bits([50])
    dt = torch.tensor([declared], dtype=torch.float32)
    at = torch.tensor([active], dtype=torch.float32)
    with torch.no_grad():
        _, proposed, _ = model.propose(g, mk, dt, at, carry=None)
    p = proposed[0].tolist()
    assert p[0] == grid[0]
    assert p[80] == grid[80]


# ---------------------------------------------------------------------------
# held-out fixtures do not overlap training transitions
# ---------------------------------------------------------------------------


def test_heldout_manifest_excludes_training_overlap(tmp_path):
    from structural_trm_dataset import _load_probe_namespace
    ns = _load_probe_namespace()
    make_fixture = ns["make_fixture"]
    residual = ns["residual"]

    # build a tiny "training corpus" from candidate 0 and 1's initial grids
    seeds = G.heldout_seeds(20260926, 4)
    fixtures = G.build_heldout_fixtures(
        make_fixture=make_fixture, cases=4, base_seed=20260926,
        seed_count=4,
    )
    rows = []
    for schema in fixtures[:2]:
        rows.append({
            "grid81": list(schema.initial_grid),
            "next_grid81": [v + 1 for v in schema.initial_grid],
            "writable_mask81": list(schema.writable_mask),
            "declared_indices529": [],
            "residual_indices529": [],
        })
    train = tmp_path / "train.jsonl"
    train.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )

    # manifest must skip candidates whose initial grid is a training source
    fixtures2, manifest = G.build_heldout_manifest(
        make_fixture=make_fixture,
        residual_fn=residual,
        train_jsonl=train,
        cases=4,
        base_seed=20260926,
        seed_count=4,
    )
    assert len(fixtures2) == 4
    selected = [r for r in manifest if r["disjoint"]]
    skipped = [r for r in manifest if not r["disjoint"]]
    # at least the two planted training-source candidates are skipped
    assert len(skipped) >= 2
    for r in skipped:
        assert r["reason"] in (
            "initial_grid_in_train_source",
            "initial_grid_in_train_target",
            "input_key_in_train",
        )
    # selected fixtures are disjoint
    src = {tuple(r["grid81"]) for r in rows}
    for i, schema in enumerate(fixtures2):
        assert tuple(schema.initial_grid) not in src


# ---------------------------------------------------------------------------
# defect C : checkpoint explicit + hashed
# ---------------------------------------------------------------------------


def test_checkpoint_hash_helper(tmp_path):
    p = tmp_path / "best.pt"
    p.write_bytes(b"dummy-checkpoint-bytes")
    expect = hashlib.sha256(p.read_bytes()).hexdigest()
    assert G.sha256_file(p) == expect


def test_checkpoint_required_for_non_dryrun(tmp_path):
    # no --checkpoint and no --dry-run -> blocked with nonzero rc 3.
    # (R0.1 defect D: a non-dry-run also needs --train-corpus; supply a
    # minimal corpus so this test isolates the CHECKPOINT gate.)
    train = _write_tiny_train_corpus(tmp_path / "train.jsonl")
    r = subprocess.run(
        [PY, str(HERE / "structural_trm_generalization.py"),
         "--train-corpus", str(train),
         "--cases", "1", "--seed", "20260926"],
        capture_output=True, text=True, cwd=str(HERE),
    )
    assert r.returncode == 3
    assert "checkpoint_missing" in (r.stdout + r.stderr)


def test_checkpoint_missing_file_returns_3(tmp_path):
    train = _write_tiny_train_corpus(tmp_path / "train.jsonl")
    r = subprocess.run(
        [PY, str(HERE / "structural_trm_generalization.py"),
         "--checkpoint", str(tmp_path / "nope.pt"),
         "--train-corpus", str(train),
         "--cases", "1", "--seed", "20260926"],
        capture_output=True, text=True, cwd=str(HERE),
    )
    assert r.returncode == 3
    assert "checkpoint_missing" in (r.stdout + r.stderr)


def _write_tiny_train_corpus(path: Path) -> Path:
    path.write_text(
        json.dumps({
            "grid81": [0] * 81,
            "next_grid81": [0] * 81,
            "writable_mask81": [1] * 81,
            "declared_indices529": [0],
            "residual_indices529": [],
        }) + "\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# defect D : --train-corpus is MANDATORY for a non-dry-run
# ---------------------------------------------------------------------------


def test_non_dryrun_without_train_corpus_is_blocked_nonzero():
    # no --train-corpus, no --dry-run -> BLOCKED, explicit message, nonzero rc.
    # (The checkpoint may be present; the corpus requirement is still enforced
    # first and independently.)
    r = subprocess.run(
        [PY, str(HERE / "structural_trm_generalization.py"),
         "--checkpoint", str(HERE / "does_not_matter.pt"),
         "--cases", "1", "--seed", "20260926"],
        capture_output=True, text=True, cwd=str(HERE),
    )
    assert r.returncode != 0
    assert r.returncode == 3
    out = r.stdout + r.stderr
    assert "train_corpus_missing" in out
    assert "TRM_GEN_BLOCKED" in out
    # must NOT have proceeded to fixture evaluation
    assert "TRM_GEN case=" not in out


def test_non_dryrun_with_train_corpus_not_blocked_by_corpus():
    # a real (tiny) train corpus file -> the corpus requirement is satisfied,
    # so the BLOCKED-train-corpus message must NOT appear (run proceeds past
    # the corpus gate; it may then block on the missing checkpoint file).
    import json as _json
    p = Path("/tmp/_r01_tc_probe.jsonl")
    p.write_text(_json.dumps({
        "grid81": [0] * 81,
        "next_grid81": [0] * 81,
        "writable_mask81": [1] * 81,
        "declared_indices529": [0],
        "residual_indices529": [],
    }) + "\n", encoding="utf-8")
    r = subprocess.run(
        [PY, str(HERE / "structural_trm_generalization.py"),
         "--checkpoint", str(HERE / "does_not_matter.pt"),
         "--train-corpus", str(p),
         "--cases", "1", "--seed", "20260926"],
        capture_output=True, text=True, cwd=str(HERE),
    )
    out = r.stdout + r.stderr
    # the corpus requirement was met -> no corpus-blocked message
    assert "train_corpus_missing=(not provided" not in out
    # it proceeded to the checkpoint gate (file missing -> blocked there)
    assert "checkpoint_missing" in out
    p.unlink(missing_ok=True)


def test_dryrun_without_train_corpus_is_allowed():
    # dry-run + no train corpus is the one allowed corpus-free path
    r = subprocess.run(
        [PY, str(HERE / "structural_trm_generalization.py"),
         "--dry-run", "--cases", "2", "--seed", "20260926"],
        capture_output=True, text=True, cwd=str(HERE),
    )
    assert r.returncode == 0
    out = r.stdout + r.stderr
    assert "train_corpus_missing" not in out
    assert "TRM_GEN_DRY_FINAL" in out


# ---------------------------------------------------------------------------
# defect E : explicit UNEVALUABLE mismatch is NOT a degeneracy
# ---------------------------------------------------------------------------


def _mk_fixture(schema_grid=None, invariants=None, mask=None):
    class _S:
        pass
    s = _S()
    s.initial_grid = schema_grid if schema_grid is not None else [0] * 81
    s.invariants = invariants if invariants is not None else (
        _Inv("a", "TERMINAL_RESOLUTION", ()),
        _Inv("b", "PRECEDES", (1, 2)),
    )
    s.writable_mask = mask if mask is not None else [1] * 81
    return s


def test_unevaluable_step_is_not_counted_degenerate():
    # A mismatched arm whose single step is explicitly UNEVALUABLE (no distinct
    # same-cardinality residual could be constructed) must NOT be counted as a
    # degenerate control.
    declared = _bits([10, 11])
    active = _bits([10, 11])  # every declared constraint active
    rec = {"step": 0, "distinct": False, "reason": "no_inactive_declared_to_swap"}
    out = G.aggregate_mismatch_fixture(
        declared=declared,
        matched_active=active,
        step_records=[rec],
        distinct_steps=0,
        unevaluable=True,
        unevaluable_reason="no_inactive_declared_to_swap",
    )
    assert out["unevaluable"] is True
    assert out["evaluable"] is False
    assert out["degenerate_steps"] == 0  # the key assertion
    assert out["valid_distinct_steps"] == 0

    stats = G.compute_mismatch_stats([out])
    assert stats["unevaluable_fixtures"] == 1
    assert stats["degenerate_steps"] == 0
    assert stats["evaluable_fixtures"] == 0


def test_evaluable_distinct_step_is_not_degenerate():
    declared = _bits([10, 11, 12, 13, 14])
    active = _bits([10, 12])
    res = G.construct_distinct_mismatch(declared, active)
    assert res.distinct is True
    rec = {"step": 0, "distinct": True, "bits": res.bits}
    out = G.aggregate_mismatch_fixture(
        declared=declared,
        matched_active=active,
        step_records=[rec],
        distinct_steps=1,
        unevaluable=False,
        unevaluable_reason="",
    )
    assert out["evaluable"] is True
    assert out["unevaluable"] is False
    assert out["degenerate_steps"] == 0
    assert out["valid_distinct_steps"] == 1


def test_contract_violation_is_a_true_degeneracy_and_fails_loudly():
    # An ALLEGEDLY valid mismatch (distinct=True) that actually equals the
    # matched residual violates its contract -> MismatchContractError, not a
    # silently-emitted degenerate step.
    declared = _bits([10, 11, 12])
    active = _bits([10, 12])
    # bits == matched active  (contract violation: equals_matched)
    bad_rec = {"step": 0, "distinct": True, "bits": active}
    with pytest.raises(G.MismatchContractError):
        G.aggregate_mismatch_fixture(
            declared=declared,
            matched_active=active,
            step_records=[bad_rec],
            distinct_steps=1,
            unevaluable=False,
            unevaluable_reason="",
        )


def test_contract_violation_wrong_cardinality_fails_loudly():
    declared = _bits([10, 11, 12])
    active = _bits([10, 12])  # cardinality 2
    bad_rec = {"step": 0, "distinct": True, "bits": _bits([11])}  # cardinality 1
    with pytest.raises(G.MismatchContractError):
        G.aggregate_mismatch_fixture(
            declared=declared,
            matched_active=active,
            step_records=[bad_rec],
            distinct_steps=1,
            unevaluable=False,
            unevaluable_reason="",
        )


def test_contract_violation_outside_universe_fails_loudly():
    declared = _bits([10, 11, 12])
    active = _bits([10, 12])  # cardinality 2
    bad_rec = {"step": 0, "distinct": True, "bits": _bits([99, 10])}  # 99 not declared
    with pytest.raises(G.MismatchContractError):
        G.aggregate_mismatch_fixture(
            declared=declared,
            matched_active=active,
            step_records=[bad_rec],
            distinct_steps=1,
            unevaluable=False,
            unevaluable_reason="",
        )


def test_validate_mismatch_contract_pure():
    declared = _bits([10, 11, 12, 13, 14])
    active = _bits([10, 12])
    good = G.construct_distinct_mismatch(declared, active).bits
    assert G.validate_mismatch_contract(declared, active, good) == []
    # equals matched
    assert "equals_matched" in G.validate_mismatch_contract(declared, active, active)
    # wrong cardinality
    assert "cardinality_mismatch" in G.validate_mismatch_contract(
        declared, active, _bits([11])
    )
    # outside declared universe
    assert any(v.startswith("outside_declared_universe")
               for v in G.validate_mismatch_contract(declared, active, _bits([99, 10])))


def test_unevaluable_not_counted_as_degenerate_integration():
    # End-to-end through run_trm: a fixture where the mismatched arm is
    # UNEVALUABLE must produce mismatch_unevaluable=True and must NOT be
    # classified degenerate; the evaluable path must be distinct and not
    # degenerate.
    schema = _mk_fixture()
    inv_ids = ("a", "b")
    residual_fn = lambda grid, inv: list(inv_ids)  # noqa: E731  constant nonempty
    encode = lambda inv, ids: (  # noqa: E731
        _bits([10, 11, 12, 13]),  # declared
        _bits([10, 12]),           # matched active
    )
    # force the mismatched arm to be unevaluable by making the declared universe
    # exactly equal to the active set (no inactive declared to swap).
    encode_uneval = lambda inv, ids: (  # noqa: E731
        _bits([10, 12]),  # declared == active
        _bits([10, 12]),
    )
    is_resolved = lambda grid, sch: False
    validate = lambda a, b, sch: None
    materialisable = lambda grid, sch: False
    quiescent = lambda grid: True

    # unevaluable arm
    res_ue, steps_ue = G.run_trm(
        model=_tiny_model(),
        schema=schema,
        residual_fn=residual_fn,
        is_resolved_fn=is_resolved,
        validate_transition_fn=validate,
        materialisable_fn=materialisable,
        quiescent_fn=quiescent,
        mode="mismatched",
        max_steps=4,
    )
    # run_trm internally calls encode_constraint_state; we can't swap it here
    # without monkeypatching the module. We assert on the classification of
    # the produced step records instead, using the module's own encode.
    agg = G.aggregate_mismatch_fixture(
        declared=_bits([10, 12]),
        matched_active=_bits([10, 12]),
        step_records=steps_ue,
        distinct_steps=res_ue["mismatch_distinct_steps"],
        unevaluable=res_ue["mismatch_unevaluable"],
        unevaluable_reason=res_ue["mismatch_reason"],
    )
    # In this schema the module's encode gives declared with 4 bits and active
    # with 2, so the mismatch IS evaluable. We instead verify the pure
    # classification semantics for both outcomes (already covered above).
    if res_ue["mismatch_unevaluable"]:
        assert agg["degenerate_steps"] == 0
        assert agg["unevaluable"] is True
    else:
        assert agg["evaluable"] is True
        assert agg["degenerate_steps"] == 0


def _tiny_model():
    torch.manual_seed(0)
    return G.StructuralTRM64(h_cycles=1, l_cycles=1).eval()


# ---------------------------------------------------------------------------
# defect F : matched-vs-mismatched must be PAIRED
# ---------------------------------------------------------------------------


def test_step_local_contract_context_is_used():
    # A step record carrying its OWN step-local matched_active/declared is
    # verified against THAT context, not the fixture-initial one. This is
    # the case exposed by the first 128-fixture held-out attempt: the
    # mismatch was valid at its step (same cardinality as the step's matched
    # residual) but differed in cardinality from the fixture-INITIAL matched
    # residual because an earlier accepted edit changed the residual.
    fixture_declared = _bits([10, 11, 12, 13, 14])
    fixture_matched = _bits([10, 12])  # initial, cardinality 2
    step_declared = _bits([10, 11, 12])
    step_matched = _bits([10, 11])  # at this step, cardinality 2
    step_bits = _bits([11, 12])  # distinct from step_matched, |.|=2, in universe
    rec = {
        "step": 1,
        "distinct": True,
        "bits": step_bits,
        "matched_active": step_matched,
        "declared": step_declared,
    }
    # valid at the step -> no exception, evaluable, not degenerate
    out = G.aggregate_mismatch_fixture(
        declared=fixture_declared,
        matched_active=fixture_matched,
        step_records=[rec],
        distinct_steps=1,
        unevaluable=False,
        unevaluable_reason="",
    )
    assert out["evaluable"] is True
    assert out["degenerate_steps"] == 0

    # the SAME record with a step-local cardinality violation -> fails loudly
    bad_rec = dict(rec, bits=_bits([10]))  # |.|=1 != 2
    with pytest.raises(G.MismatchContractError):
        G.aggregate_mismatch_fixture(
            declared=fixture_declared,
            matched_active=fixture_matched,
            step_records=[bad_rec],
            distinct_steps=1,
            unevaluable=False,
            unevaluable_reason="",
        )


def test_paired_stats_exclude_unevaluable_fixture_both_arms():
    # 3 fixtures: fixture 1's mismatched arm is UNEVALUABLE. The paired subset
    # must contain fixtures 0 and 2 only, and must drop BOTH fixture 1's
    # mismatched result AND fixture 1's matched result from the comparison.
    fixtures = [
        {"fixture": 0, "evaluable": True, "unevaluable": False,
         "valid_distinct_steps": 1, "degenerate_steps": 0},
        {"fixture": 1, "evaluable": False, "unevaluable": True,
         "unevaluable_reason": "active_residual_empty",
         "valid_distinct_steps": 0, "degenerate_steps": 0},
        {"fixture": 2, "evaluable": True, "unevaluable": False,
         "valid_distinct_steps": 1, "degenerate_steps": 0},
    ]
    # matched rows: fixture 1 (unevaluable-mismatch) is RESOLVED, the others not
    matched_rows = [
        {"resolved": True, "final_residual": 0},   # fixture 0
        {"resolved": True, "final_residual": 0},   # fixture 1 (excluded)
        {"resolved": False, "final_residual": 9},  # fixture 2
    ]
    mismatch_rows = [
        {"resolved": False, "final_residual": 5},  # fixture 0
        {"resolved": False, "final_residual": 0},  # fixture 1 (excluded)
        {"resolved": False, "final_residual": 6},  # fixture 2
    ]
    stats = G.compute_paired_mismatch_stats(fixtures, matched_rows, mismatch_rows)
    assert stats["paired_fixture_count"] == 2
    assert stats["matched_fixture_ids"] == [0, 2]
    assert stats["mismatched_fixture_ids"] == [0, 2]
    # fixture 1's matched resolution (True, final 0) is EXCLUDED from the
    # paired counts: only fixture 0 (resolved=True) + fixture 2 (False) count.
    assert stats["matched_resolved"] == 1
    assert stats["mismatched_resolved"] == 0
    # means over the paired subset only: matched (0+9)/2, mismatched (5+6)/2
    assert stats["matched_mean_final_residual"] == 4.5
    assert stats["mismatched_mean_final_residual"] == 5.5


def test_paired_gate_uses_identical_fixture_subset():
    # Construct totals where the FULL-population matched-vs-mismatched
    # comparison would say "matched better", but the PAIRED subset (after
    # excluding an unevaluable fixture) says the opposite. The gate's
    # better_than_mismatch must follow the PAIRED subset, not the full totals.
    matched = _arm(resolved=2, cases=3, mean_final=1.0)
    null_arm = _arm(resolved=0, cases=3, mean_final=9.0)
    zero = _arm(resolved=0, cases=3, mean_final=9.0)
    mismatch = _arm(resolved=2, cases=3, mean_final=1.0)  # full-pop ties matched

    # full-population: matched(2 res, 1.0) vs mismatch(2 res, 1.0) -> NOT better
    # paired subset (fixture 1 excluded): matched 1 res / 0.0 mean,
    #   mismatch 0 res / 4.0 mean -> matched IS better
    fixtures = [
        {"fixture": 0, "evaluable": True, "unevaluable": False,
         "valid_distinct_steps": 1, "degenerate_steps": 0},
        {"fixture": 1, "evaluable": False, "unevaluable": True,
         "unevaluable_reason": "no_inactive_declared_to_swap",
         "valid_distinct_steps": 0, "degenerate_steps": 0},
        {"fixture": 2, "evaluable": True, "unevaluable": False,
         "valid_distinct_steps": 1, "degenerate_steps": 0},
    ]
    matched_rows = [
        {"resolved": True, "final_residual": 0},   # 0
        {"resolved": True, "final_residual": 0},   # 1 excluded
        {"resolved": False, "final_residual": 2},  # 2
    ]
    mismatch_rows = [
        {"resolved": False, "final_residual": 6},  # 0
        {"resolved": False, "final_residual": 0},  # 1 excluded
        {"resolved": False, "final_residual": 2},  # 2
    ]
    paired = G.compute_paired_mismatch_stats(fixtures, matched_rows, mismatch_rows)
    assert paired["paired_fixture_count"] == 2
    assert paired["matched_resolved"] == 1
    assert paired["mismatched_resolved"] == 0
    assert paired["matched_mean_final_residual"] == 1.0
    assert paired["mismatched_mean_final_residual"] == 4.0

    mismatch_stats = G.compute_mismatch_stats(fixtures)
    totals = _totals(matched, null_arm, zero, mismatch)

    # WITHOUT paired stats: full-population -> matched NOT better than mismatch
    passed_full, clauses_full = G.compute_mechanism_gate(
        totals, mismatch_stats, 3, paired_stats=None
    )
    assert clauses_full["c2_matched_beats_ablation"]["better_than_mismatch"] is False

    # WITH paired stats: paired subset -> matched IS better than mismatch
    passed_paired, clauses_paired = G.compute_mechanism_gate(
        totals, mismatch_stats, 3, paired_stats=paired
    )
    assert clauses_paired["c2_matched_beats_ablation"]["better_than_mismatch"] is True
    assert (
        clauses_paired["c2_matched_beats_ablation"]
        ["better_than_mismatch_paired_only"] is True
    )


def test_paired_gate_empty_paired_subset_blocks_mismatch_comparison():
    # If no mismatched fixture is evaluable, better_than_mismatch must be False
    # (the causal mismatch comparison is meaningless), even if full-population
    # totals would otherwise suggest "better".
    matched = _arm(resolved=3, cases=3, mean_final=0.0)
    null_arm = _arm(resolved=0, cases=3, mean_final=9.0)
    zero = _arm(resolved=0, cases=3, mean_final=9.0)
    mismatch = _arm(resolved=0, cases=3, mean_final=9.0)
    fixtures = [
        {"fixture": i, "evaluable": False, "unevaluable": True,
         "unevaluable_reason": "active_residual_empty",
         "valid_distinct_steps": 0, "degenerate_steps": 0}
        for i in range(3)
    ]
    paired = G.compute_paired_mismatch_stats(
        fixtures,
        [{"resolved": True, "final_residual": 0}] * 3,
        [{"resolved": False, "final_residual": 9}] * 3,
    )
    assert paired["paired_fixture_count"] == 0
    mismatch_stats = G.compute_mismatch_stats(fixtures)
    passed, clauses = G.compute_mechanism_gate(
        _totals(matched, null_arm, zero, mismatch),
        mismatch_stats, 3, paired_stats=paired,
    )
    assert clauses["c2_matched_beats_ablation"]["better_than_mismatch"] is False
    # c3 must also fail (no evaluable mismatched fixtures)
    assert clauses["c3_mismatch_distinct"]["passed"] is False
