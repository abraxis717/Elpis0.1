"""Held-out C2R7-C structural TRM-0 generalization probe (R0.1).

This probe never receives a hidden/final Grid81.

Each held-out fixture is generated from a deterministic seed (spanning several
seeds and the lane families 3..6 already supported by C2R7-C) that is disjoint
from the training seed. The frozen neural candidate receives only:

    current Grid81
    writable mask
    declared structural constraint signatures   (529-bit)
    residual-support signatures (529-bit)         per the selected ablation

The deterministic structural evaluator independently decides whether the
result is coherent/resolved. The model only ever *proposes* writable cell
edits; all authority (frozen loci, transition validation, residual
recomputation, resolution, materialisability) stays external.

Arms (unchanged from the predecessor C2R7-C probe):
    null                      identity map (teacher control)
    random                      uniform legal moves (teacher control)
    search                      residual-descent hill climb (teacher control)
    trm_matched                 TRM-0 with the correct (matched) residual
    trm_zero_residual           TRM-0 with an all-zero residual vector
    trm_mismatched_residual     TRM-0 with a DISTINCT same-cardinality residual

TRM-0 must NEVER: modify frozen cells, declare itself RESOLVED, bypass
transition validation, invent execution authority, receive the hidden final
Grid81, receive oracle edits, or receive semantic identifiers as hidden hints.

R0.1 repairs to the predecessor harness (known defects, fail-closed):
  A. exit status  : PASS -> rc 0, FAIL -> nonzero rc (was always 0).
  B. mismatched control : the mismatched-residual arm is constructed
     fail-closed. It only ever injects a residual that is (i) distinct from
     the matched residual, (ii) equal cardinality, (iii) inside the same
     declared invariant universe. If a distinct mismatch cannot be
     constructed at a step, that step is marked UNEVALUABLE (explicit reason)
     and the arm stops for that fixture -- it never silently substitutes the
     matched residual. The mechanism gate requires a minimum number of
     evaluable mismatched fixtures to be meaningful.
  C. checkpoint     : an explicit checkpoint path is required (no stale
     host-specific default); its absolute path and SHA-256 are recorded. The
     checkpoint is read in place and never copied into the source tree.
  D. train corpus   : a non-dry-run REQUIRES --train-corpus. Without it the
     held-out population cannot be proven disjoint from training, so the run
     is BLOCKED with an explicit message and nonzero rc.
  E. unevaluable vs degeneracy : an explicitly UNEVALUABLE mismatch step
     (fail-closed: no distinct same-cardinality residual exists) is NOT a
     degenerate control. A degeneracy is an allegedly valid mismatch that
     violated its own contract (equals matched / wrong cardinality / outside
     the declared universe); that condition fails loudly (typed exception)
     and is counted separately.
  F. paired comparison : matched-vs-mismatched statistics are computed ONLY
     over fixtures where the mismatched arm remained evaluable, comparing
     the matched outcome and the mismatched outcome on the SAME fixture.
     The gate's better_than_mismatch clause uses only this paired subset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import sys
import time

import torch

from structural_trm_dataset import _load_probe_namespace
from structural_trm_features import (
    FEATURE_WIDTH,
    VOCABULARY_DIGEST,
    encode_constraint_state,
)
from structural_trm_model import StructuralTRM64


HELDOUT_DEFAULT_SEED = 20260926
HELDOUT_DEFAULT_SEED_COUNT = 4
MIN_MISMATCH_EVALUABLE_FRACTION = 0.25


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def bits_tensor(bits):
    return torch.tensor([bits], dtype=torch.float32)


def grid_tensor(grid):
    return torch.tensor([grid], dtype=torch.long)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# defect B : fail-closed mismatched-residual construction
# ---------------------------------------------------------------------------


class MismatchContractError(RuntimeError):
    """Raised when an ALLEGEDLY VALID mismatched residual violates its own
    contract: it equals the matched residual, its cardinality differs from
    the matched residual, or it escapes the declared invariant universe.

    This is a TRUE degeneracy (the fail-closed path emitted a mismatch it
    should not have been able to emit). It is NOT the explicit UNEVALUABLE
    outcome, which is a legitimate fail-closed result, not a contract
    violation.
    """


def validate_mismatch_contract(declared, matched_active, mismatch_bits):
    """Check one allegedly valid mismatch against its contract.

    Returns a list of human-readable contract violations (empty == valid).
    The three contract conditions are exactly the defect-2 definitions:
      1. distinct from the matched residual,
      2. same cardinality as the matched residual,
      3. support inside the declared invariant universe.
    """
    violations = []
    if tuple(mismatch_bits) == tuple(matched_active):
        violations.append("equals_matched")
    if sum(int(v) for v in mismatch_bits) != sum(int(v) for v in matched_active):
        violations.append("cardinality_mismatch")
    for i in range(FEATURE_WIDTH):
        if mismatch_bits[i] and not declared[i]:
            violations.append(f"outside_declared_universe:index={i}")
            break
    return violations


@dataclass(frozen=True)
class MismatchResult:
    """Outcome of constructing a mismatched residual for one step.

    distinct == True  -> ``bits`` is a valid mismatch (distinct from matched,
                          equal cardinality, inside the declared universe).
    distinct == False -> the step is UNEVALUABLE for the mismatched arm;
                          ``reason`` names why, and ``bits`` is NOT the matched
                          residual (it is left as an all-zero marker so a
                          consumer can never mistake it for the real one).

    An explicit UNEVALUABLE result is a LEGITIMATE fail-closed outcome. It
    must never be counted as a degenerate step; a degenerate step is an
    allegedly valid mismatch that violates validate_mismatch_contract().
    """

    bits: tuple
    distinct: bool
    reason: str


def _sparse(bits):
    return [i for i, value in enumerate(bits) if value]


def construct_distinct_mismatch(declared, matched_active):
    """Build a mismatched residual that is a *different* subset of the same
    declared invariant universe, with the *same* cardinality as the matched
    (currently violated) residual.

    Construction (deterministic, maximal perturbation, same as the predecessor
    arm): take all declared-but-inactive constraints first, then fill with the
    matched active constraints, to the matched count. This yields a subset that
    is distinct from the matched residual exactly when there is at least one
    declared constraint that is not currently active.

    Fail-closed: when no distinct same-cardinality subset exists (empty active
    residual, or every declared constraint already active), return
    distinct=False with an explicit reason. Never return the matched residual
    as a "mismatch".
    """
    declared_indices = _sparse(declared)
    active_indices = _sparse(matched_active)
    inactive_declared = [i for i in declared_indices if not matched_active[i]]

    count = len(active_indices)

    if count == 0:
        return MismatchResult(
            bits=(0,) * FEATURE_WIDTH,
            distinct=False,
            reason="active_residual_empty",
        )

    if not inactive_declared:
        return MismatchResult(
            bits=(0,) * FEATURE_WIDTH,
            distinct=False,
            reason="no_inactive_declared_to_swap",
        )

    candidates = inactive_declared + active_indices
    selected = candidates[:count]

    # Distinctness guard (should hold by construction once inactive_declared
    # is non-empty, but verify fail-closed).
    if set(selected) == set(active_indices):
        return MismatchResult(
            bits=(0,) * FEATURE_WIDTH,
            distinct=False,
            reason="constructed_subset_equals_matched",
        )

    out = [0] * FEATURE_WIDTH
    for index in selected:
        out[index] = 1

    # cardinality preserved
    if sum(out) != sum(matched_active):
        raise MismatchContractError(
            "mismatched residual cardinality changed "
            f"({sum(out)} != {sum(matched_active)})"
        )
    # stays inside the declared invariant universe
    if any(out[i] and not declared[i] for i in range(FEATURE_WIDTH)):
        raise MismatchContractError("mismatched residual escaped declared universe")
    # distinct from matched
    if tuple(out) == tuple(matched_active):
        raise MismatchContractError("mismatched residual equals matched residual")

    return MismatchResult(bits=tuple(out), distinct=True, reason="ok")


def select_arm_residual(mode, declared, matched_active):
    """Return (active_bits, mismatch_result) for a TRM arm's residual input.

    matched   -> the correct current residual.
    zero      -> the all-zero 529-vector (no active residual features).
    mismatched-> a distinct same-cardinality residual (fail-closed).
    """
    if mode == "matched":
        return tuple(matched_active), None
    if mode == "zero":
        return (0,) * FEATURE_WIDTH, None
    if mode == "mismatched":
        result = construct_distinct_mismatch(declared, matched_active)
        return result.bits, result
    raise ValueError(f"unknown TRM mode {mode!r}")


# ---------------------------------------------------------------------------
# model loading
# ---------------------------------------------------------------------------


def load_model(checkpoint_path: Path):
    checkpoint = torch.load(checkpoint_path, map_location="cpu")

    config = checkpoint.get("config", {})
    hidden = int(config.get("hidden", 64))
    h_cycles = int(config.get("h_cycles", 3))
    l_cycles = int(config.get("l_cycles", 6))

    model = StructuralTRM64(
        hidden=hidden, h_cycles=h_cycles, l_cycles=l_cycles
    )
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model, checkpoint


# ---------------------------------------------------------------------------
# per-fixture result record (uniform shape across all six arms)
# ---------------------------------------------------------------------------


def _empty_result(arm_name, initial_residual):
    return {
        "arm": arm_name,
        "resolved": False,
        "initial_residual": int(initial_residual),
        "final_residual": int(initial_residual),
        "residual_reduction": 0,
        "steps": 0,
        "valid_transitions": 0,
        "invalid_transitions": 0,
        "frozen_cell_violations": 0,
        "materialisable": False,
        "quiescent": False,
        "authority_granted": 0,
        "proposed_edits": 0,
        "accepted_edits": 0,
        "rejected_edits": 0,
        "mismatch_distinct_steps": 0,
        "mismatch_unevaluable": False,
        "mismatch_reason": "",
        "error": "",
    }


@torch.no_grad()
def run_trm(
    *,
    model,
    schema,
    residual_fn,
    is_resolved_fn,
    validate_transition_fn,
    materialisable_fn,
    quiescent_fn,
    mode,
    max_steps,
):
    """Run one TRM arm over one held-out fixture.

    Returns (result_dict, per_step_records). The model proposes writable edits
    only; every transition is validated by the external deterministic
    validate_transition_fn. For the mismatched arm, a step that cannot be
    given a distinct residual is marked unevaluable and stops the arm.
    """
    current = schema.initial_grid
    initial_residual = residual_fn(current, schema.invariants)
    declared, _ = encode_constraint_state(schema.invariants, initial_residual)

    res = _empty_result("trm_" + mode, len(initial_residual))
    if mode == "matched":
        res["arm"] = "trm_matched"
    elif mode == "zero":
        res["arm"] = "trm_zero_residual"
    elif mode == "mismatched":
        res["arm"] = "trm_mismatched_residual"

    mask = schema.writable_mask
    step_records = []
    steps = 0
    authority_violations = 0
    stalled = False
    error = ""
    frozen_violations = 0

    for step in range(max_steps):
        current_residual = residual_fn(current, schema.invariants)
        if not current_residual:
            break

        _, matched_active = encode_constraint_state(
            schema.invariants, current_residual
        )
        active, mismatch = select_arm_residual(
            mode, declared, matched_active
        )

        if mode == "mismatched":
            if not mismatch.distinct:
                res["mismatch_unevaluable"] = True
                res["mismatch_reason"] = mismatch.reason
                step_records.append(
                    {"step": step, "distinct": False, "reason": mismatch.reason}
                )
                break
            res["mismatch_distinct_steps"] += 1
            step_records.append(
                {
                    "step": step,
                    "distinct": True,
                    "bits": active,
                    # the CURRENT step's matched residual: the mismatch
                    # contract (distinct / same cardinality / same universe)
                    # is relative to THIS step's matched residual, which may
                    # differ from the initial one after accepted edits.
                    "matched_active": tuple(matched_active),
                    "declared": tuple(declared),
                }
            )

        grid = grid_tensor(current)
        mask_t = grid_tensor(mask)

        _, proposed_tensor, _ = model.propose(
            grid,
            mask_t,
            bits_tensor(declared),
            bits_tensor(active),
            carry=None,
        )
        proposed = tuple(int(v) for v in proposed_tensor[0].tolist())

        # frozen-locus audit (external authority: the model must not move a
        # frozen cell).
        changed = [i for i in range(81) if proposed[i] != current[i]]
        frozen_changed = [i for i in changed if not mask[i]]
        frozen_violations += len(frozen_changed)

        # count proposed edits for this step
        res["proposed_edits"] += len(changed)

        try:
            validate_transition_fn(current, proposed, schema)
        except Exception as exc:
            authority_violations += 1
            res["invalid_transitions"] += 1
            res["rejected_edits"] += len(changed)
            error = f"{type(exc).__name__}: {exc}"
            break

        # transition accepted by the external validator
        res["valid_transitions"] += 1
        res["accepted_edits"] += len(changed)
        steps = step + 1

        if proposed == current:
            stalled = True
            break

        current = proposed

    final_residual = residual_fn(current, schema.invariants)

    res["final_residual"] = len(final_residual)
    res["residual_reduction"] = len(initial_residual) - len(final_residual)
    res["steps"] = steps
    res["resolved"] = bool(is_resolved_fn(current, schema))
    res["materialisable"] = bool(materialisable_fn(current, schema))
    res["quiescent"] = bool(quiescent_fn(current))
    res["frozen_cell_violations"] = frozen_violations
    # authority_granted stays 0: every applied transition passed the external
    # validator; the model never self-executes.
    res["authority_granted"] = 0
    if authority_violations:
        res["error"] = error
    elif stalled:
        res["error"] = "stalled_no_change"

    return res, step_records


def run_control_arm(
    *,
    arm_name,
    refine_fn,
    schema,
    rng,
    budget,
    residual_fn,
    is_resolved_fn,
    validate_transition_fn,
    materialisable_fn,
    quiescent_fn,
):
    """Run one teacher/control arm (null/random/search) over one fixture.

    Uses the probe's own refiner + the external deterministic validator so the
    control arms keep exactly the predecessor authority boundary.
    """
    initial = schema.initial_grid
    initial_residual = residual_fn(initial, schema.invariants)
    res = _empty_result(arm_name, len(initial_residual))

    try:
        final, steps = refine_fn(
            initial, schema.writable_mask, schema.invariants, rng, budget
        )
        validate_transition_fn(initial, final, schema)
        res["valid_transitions"] = 1
    except Exception as exc:
        # validator rejected the control's net transition
        res["invalid_transitions"] = 1
        res["error"] = f"{type(exc).__name__}: {exc}"
        final = initial
        steps = 0

    # frozen-locus audit on the net transition
    if res["valid_transitions"]:
        changed = [i for i in range(81) if final[i] != initial[i]]
        res["frozen_cell_violations"] = sum(
            1 for i in changed if not schema.writable_mask[i]
        )

    final_residual = residual_fn(final, schema.invariants)
    res["final_residual"] = len(final_residual)
    res["residual_reduction"] = len(initial_residual) - len(final_residual)
    res["steps"] = int(steps)
    res["resolved"] = bool(is_resolved_fn(final, schema))
    res["materialisable"] = bool(materialisable_fn(final, schema))
    res["quiescent"] = bool(quiescent_fn(final))
    res["proposed_edits"] = sum(
        1 for i in range(81) if final[i] != initial[i]
    ) if res["valid_transitions"] else 0
    res["accepted_edits"] = res["proposed_edits"] if res["valid_transitions"] else 0
    res["authority_granted"] = 0
    return res


# ---------------------------------------------------------------------------
# held-out fixture generation (multi-seed, lane families 3..6)
# ---------------------------------------------------------------------------


def heldout_seeds(base_seed: int, seed_count: int):
    return [int(base_seed) + k for k in range(int(seed_count))]


def build_heldout_fixtures(*, make_fixture, cases, base_seed, seed_count):
    """Deterministic held-out population.

    Spans ``seed_count`` distinct deterministic seeds and the C2R7-C lane
    families 3..6. Fixture i uses rng seeded by (seed_i, i) so the population
    is reproducible and seed-disjoint from the training seed.
    """
    seeds = heldout_seeds(base_seed, seed_count)
    fixtures = []
    for i in range(cases):
        seed_i = seeds[i % len(seeds)]
        rng = random.Random(seed_i * 1_000_003 + i)
        lane_count = rng.randint(3, 6)
        fixtures.append(make_fixture(rng, lane_count))
    return fixtures


def build_heldout_manifest(
    *,
    make_fixture,
    residual_fn,
    train_jsonl: Path,
    cases: int,
    base_seed: int,
    seed_count: int,
    max_candidates: int = 256,
):
    """Select the first ``cases`` held-out candidates (scanned in deterministic
    order) that are provably disjoint from the training transition corpus.

    Disjointness (fail-closed) requires, for a candidate:
      * its initial grid is NOT a training source grid,
      * its initial grid is NOT a training final/target grid,
      * its (grid, mask, declared, residual) input key is NOT a training key.

    Candidates that fail are recorded with an explicit reason and skipped.
    This is how the held-out population is guaranteed genuinely held out.
    Returns (fixtures, manifest_rows) where manifest_rows covers every
    scanned candidate (selected or skipped).
    """
    source, target, input_keys = load_training_grids(train_jsonl)
    seeds = heldout_seeds(base_seed, seed_count)

    fixtures = []
    rows = []
    scanned = 0
    while len(fixtures) < cases and scanned < max_candidates:
        seed_i = seeds[scanned % len(seeds)]
        rng = random.Random(seed_i * 1_000_003 + scanned)
        lane_count = rng.randint(3, 6)
        schema = make_fixture(rng, lane_count)

        init = tuple(schema.initial_grid)
        ids = residual_fn(init, schema.invariants)
        declared, active = encode_constraint_state(schema.invariants, ids)
        init_key = (
            init,
            tuple(schema.writable_mask),
            tuple(declared),
            tuple(active),
        )

        in_source = init in source
        in_target = init in target
        key_in_train = init_key in input_keys
        disjoint = not (in_source or in_target or key_in_train)

        reason = "selected"
        if not disjoint:
            if in_source:
                reason = "initial_grid_in_train_source"
            elif in_target:
                reason = "initial_grid_in_train_target"
            else:
                reason = "input_key_in_train"

        row = {
            "candidate_index": scanned,
            "seed": seed_i,
            "lane_count": lane_count,
            "in_source": in_source,
            "in_target": in_target,
            "key_in_train": key_in_train,
            "disjoint": disjoint,
            "reason": reason,
        }
        rows.append(row)

        if disjoint:
            fixtures.append(schema)

        scanned += 1

    if len(fixtures) < cases:
        raise RuntimeError(
            "held-out manifest exhausted "
            f"{max_candidates} candidates; only {len(fixtures)} disjoint "
            f"of {cases} required"
        )

    return fixtures, rows


# ---------------------------------------------------------------------------
# held-out <-> training disjointness
# ---------------------------------------------------------------------------


def load_training_grids(train_jsonl: Path):
    """Return (source_grids, target_grids, input_keys) from a raw training
    transition file. Used to PROVE held-out fixtures are disjoint from the
    training corpus."""
    source = set()
    target = set()
    input_keys = set()
    for line in Path(train_jsonl).read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        source.add(tuple(row["grid81"]))
        target.add(tuple(row["next_grid81"]))
        input_keys.add(
            (
                tuple(row["grid81"]),
                tuple(row["writable_mask81"]),
                tuple(row["declared_indices529"]),
                tuple(row["residual_indices529"]),
            )
        )
    return source, target, input_keys


def heldout_disjointness(fixtures, *, residual_fn, train_jsonl: Path):
    """For each held-out fixture, prove its initial grid and (grid, declared,
    residual) input key do not occur in the training transition corpus, and
    that no training final/target grid equals a held-out initial grid.

    Returns a list of per-fixture dicts + an overall ok flag.
    """
    source, target, input_keys = load_training_grids(train_jsonl)
    out = []
    ok = True
    for i, schema in enumerate(fixtures):
        init = tuple(schema.initial_grid)
        ids = residual_fn(init, schema.invariants)
        declared, active = encode_constraint_state(
            schema.invariants, ids
        )
        init_key = (
            init,
            tuple(schema.writable_mask),
            tuple(declared),
            tuple(active),
        )
        in_source = init in source
        in_target = init in target
        key_in_train = init_key in input_keys
        disjoint = not (in_source or in_target or key_in_train)
        ok = ok and disjoint
        out.append(
            {
                "fixture": i,
                "lanes": None,
                "initial_in_train_source": in_source,
                "initial_in_train_target": in_target,
                "input_key_in_train": key_in_train,
                "disjoint": disjoint,
            }
        )
    return ok, out


# ---------------------------------------------------------------------------
# per-fixture mismatch accounting (defect E) and paired comparison (defect F)
# ---------------------------------------------------------------------------


def aggregate_mismatch_fixture(
    *,
    declared,
    matched_active,
    step_records,
    distinct_steps,
    unevaluable,
    unevaluable_reason,
):
    """Classify ONE fixture's mismatched arm (pure function).

    Returns a dict with:
      evaluable            : bool -- the mismatched arm produced a valid
                                     distinct residual at its (only) attempt.
      unevaluable            : bool -- explicit fail-closed UNEVALUABLE step
                                     (no distinct same-cardinality residual
                                     could be constructed).
      unevaluable_reason     : str
      valid_distinct_steps   : int
      degenerate_steps       : int  -- ONLY allegedly valid mismatches that
                                      violated the contract (see
                                      validate_mismatch_contract). A normal
                                      UNEVALUABLE step contributes 0.
      contract_violations    : list[str]

    Each allegedly valid step (distinct=True) is checked against ITS OWN
    step context: a step record may carry ``matched_active``/``declared``
    (the residual state at that step, which can differ from the fixture
    initial state once edits have been accepted); otherwise the fixture
    initial ``declared``/``matched_active`` are used. A contract violation
    (equals matched / wrong cardinality / outside declared universe) fails
    loudly via MismatchContractError -- it is never silently emitted as a
    degenerate step.
    """
    violations = []
    degenerate = 0
    for record in step_records:
        if record.get("distinct"):
            # allegedly valid mismatch -> verify the contract against the
            # residual state at THIS step.
            bits = record.get("bits")
            if bits is None:
                raise MismatchContractError(
                    "distinct step record carries no residual bits"
                )
            step_matched = record.get("matched_active", matched_active)
            step_declared = record.get("declared", declared)
            record_violations = validate_mismatch_contract(
                step_declared, step_matched, bits
            )
            if record_violations:
                violations.extend(record_violations)
                degenerate += 1
    if violations:
        raise MismatchContractError(
            "mismatch contract violated on allegedly valid step: "
            + "; ".join(violations)
        )

    return {
        "evaluable": bool(distinct_steps) and not unevaluable,
        "unevaluable": bool(unevaluable),
        "unevaluable_reason": unevaluable_reason or "",
        "valid_distinct_steps": int(distinct_steps),
        "degenerate_steps": int(degenerate),
        "contract_violations": [],
    }


def compute_mismatch_stats(fixtures):
    """Aggregate per-fixture mismatch accounting over a population (pure)."""
    evaluable = sum(1 for f in fixtures if f["evaluable"])
    unevaluable = sum(1 for f in fixtures if f["unevaluable"])
    valid_distinct = sum(int(f["valid_distinct_steps"]) for f in fixtures)
    degenerate = sum(int(f["degenerate_steps"]) for f in fixtures)
    return {
        "evaluable_fixtures": evaluable,
        "unevaluable_fixtures": unevaluable,
        "valid_distinct_steps": valid_distinct,
        "degenerate_steps": degenerate,
    }


def compute_paired_mismatch_stats(fixtures, matched_rows, mismatch_rows):
    """Paired matched-vs-mismatched statistics (pure function, defect F).

    Include ONLY fixtures where the mismatched arm remained evaluable. For
    each such fixture, compare the matched outcome and the mismatched
    outcome on the SAME fixture. Unevaluable mismatched fixtures contribute
    NEITHER their mismatched result NOR their matched result to the paired
    subset.

    Returns a dict with:
      paired_fixture_count, matched_resolved, mismatched_resolved,
      matched_mean_final_residual, mismatched_mean_final_residual,
      matched_fixture_ids, mismatched_fixture_ids.
    """
    paired_fixture_ids = [
        int(f["fixture"]) for f in fixtures if f["evaluable"]
    ]
    idset = set(paired_fixture_ids)
    matched_rows = [
        r for i, r in enumerate(matched_rows) if i in idset
    ]
    mismatch_rows = [
        r for i, r in enumerate(mismatch_rows) if i in idset
    ]
    n = len(paired_fixture_ids)
    m_res = sum(int(r["resolved"]) for r in matched_rows)
    x_res = sum(int(r["resolved"]) for r in mismatch_rows)
    m_final = sum(int(r["final_residual"]) for r in matched_rows)
    x_final = sum(int(r["final_residual"]) for r in mismatch_rows)
    return {
        "paired_fixture_count": n,
        "matched_resolved": m_res,
        "mismatched_resolved": x_res,
        "matched_mean_final_residual": (m_final / n) if n else None,
        "mismatched_mean_final_residual": (x_final / n) if n else None,
        "matched_fixture_ids": paired_fixture_ids,
        "mismatched_fixture_ids": paired_fixture_ids,
    }


# ---------------------------------------------------------------------------
# mechanism gate (pure, testable)
# ---------------------------------------------------------------------------


def min_evaluable_required(total_fixtures: int) -> int:
    return max(
        2,
        math.ceil(int(total_fixtures) * MIN_MISMATCH_EVALUABLE_FRACTION),
    )


def compute_mechanism_gate(arm_totals, mismatch_stats, total_fixtures,
                           paired_stats=None):
    """Evaluate the R0.1 causal mechanism signal. Pure function.

    Returns (passed: bool, clauses: dict). Faithful to the goal's 5 clauses:
      1. matched materially outperforms null
      2. matched materially outperforms >=1 residual ablation (zero/mismatch)
         on resolution rate and/or residual reduction
      3. mismatched comparison constructed correctly and remains distinct
      4. frozen-cell violations == 0
      5. execution/authority granted by TRM == 0

    Paired comparison (defect F): when ``paired_stats`` is provided, the
    better_than_mismatch comparison uses ONLY the paired subset -- fixtures
    where the mismatched arm remained evaluable, comparing the matched and
    mismatched outcomes on the same fixture. When omitted (backwards
    compatible), the full-population totals are used.
    """
    matched = arm_totals["trm_matched"]
    null_arm = arm_totals["null"]
    zero = arm_totals["trm_zero_residual"]
    mismatch = arm_totals["trm_mismatched_residual"]

    clauses = {}

    c1 = (
        matched["resolved"] > null_arm["resolved"]
        or matched["mean_final_residual"] < null_arm["mean_final_residual"]
    )
    clauses["c1_matched_beats_null"] = {
        "passed": bool(c1),
        "detail": (
            f"matched={matched['resolved']}/{matched['cases']} "
            f"null={null_arm['resolved']}/{null_arm['cases']} "
            f"matched_mean_final_residual="
            f"{matched['mean_final_residual']:.3f} "
            f"null_mean_final_residual="
            f"{null_arm['mean_final_residual']:.3f}"
        ),
    }

    better_zero = (
        matched["resolved"] > zero["resolved"]
        or matched["mean_final_residual"] < zero["mean_final_residual"]
    )

    if paired_stats is not None:
        # paired subset only: fixtures where the mismatched arm stayed
        # evaluable; matched vs mismatched on the SAME fixture.
        paired = paired_stats
        if paired["paired_fixture_count"] > 0:
            better_mismatch = (
                paired["matched_resolved"] > paired["mismatched_resolved"]
                or paired["matched_mean_final_residual"]
                < paired["mismatched_mean_final_residual"]
            )
            paired_detail = (
                f"paired_fixtures={paired['paired_fixture_count']} "
                f"paired_matched_resolved={paired['matched_resolved']} "
                f"paired_mismatched_resolved="
                f"{paired['mismatched_resolved']} "
                f"paired_matched_mean_final_residual="
                f"{paired['matched_mean_final_residual']:.3f} "
                f"paired_mismatched_mean_final_residual="
                f"{paired['mismatched_mean_final_residual']:.3f}"
            )
        else:
            better_mismatch = False
            paired_detail = "no paired evaluable mismatched fixtures"
    else:
        # backwards-compatible full-population comparison
        better_mismatch = (
            matched["resolved"] > mismatch["resolved"]
            or matched["mean_final_residual"] < mismatch["mean_final_residual"]
        )
        paired_detail = (
            "full-population totals (no paired stats provided)"
        )

    c2 = better_zero or better_mismatch
    clauses["c2_matched_beats_ablation"] = {
        "passed": bool(c2),
        "better_than_zero": bool(better_zero),
        "better_than_mismatch": bool(better_mismatch),
        "better_than_mismatch_paired_only": paired_stats is not None,
        "paired_mismatch_detail": paired_detail,
        "detail": (
            f"matched_resolved={matched['resolved']} "
            f"zero_resolved={zero['resolved']} "
            f"mismatch_resolved={mismatch['resolved']} "
            f"matched_mean={matched['mean_final_residual']:.3f} "
            f"zero_mean={zero['mean_final_residual']:.3f} "
            f"mismatch_mean={mismatch['mean_final_residual']:.3f}"
        ),
    }

    required = min_evaluable_required(total_fixtures)
    c3 = (
        mismatch_stats["evaluable_fixtures"] >= required
        and mismatch_stats["degenerate_steps"] == 0
        and mismatch_stats["valid_distinct_steps"] > 0
    )
    clauses["c3_mismatch_distinct"] = {
        "passed": bool(c3),
        "evaluable_fixtures": mismatch_stats["evaluable_fixtures"],
        "required": required,
        "valid_distinct_steps": mismatch_stats["valid_distinct_steps"],
        "degenerate_steps": mismatch_stats["degenerate_steps"],
        "unevaluable_fixtures": mismatch_stats["unevaluable_fixtures"],
    }

    total_frozen = sum(
        a["frozen_cell_violations"] for a in arm_totals.values()
    )
    c4 = total_frozen == 0
    clauses["c4_frozen_violations_zero"] = {
        "passed": bool(c4),
        "total_frozen_cell_violations": total_frozen,
    }

    total_auth = sum(a["authority_granted"] for a in arm_totals.values())
    c5 = total_auth == 0
    clauses["c5_authority_granted_zero"] = {
        "passed": bool(c5),
        "total_authority_granted": total_auth,
    }

    passed = bool(c1 and c2 and c3 and c4 and c5)
    return passed, clauses


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _aggregate(arm_totals, results_by_arm):
    for arm in arm_totals:
        stats = arm_totals[arm]
        rows = results_by_arm.get(arm, [])
        stats["cases"] = len(rows)
        stats["resolved"] = sum(int(r["resolved"]) for r in rows)
        stats["frozen_cell_violations"] = sum(
            int(r["frozen_cell_violations"]) for r in rows
        )
        stats["authority_granted"] = sum(
            int(r["authority_granted"]) for r in rows
        )
        stats["valid_transitions"] = sum(
            int(r["valid_transitions"]) for r in rows
        )
        stats["invalid_transitions"] = sum(
            int(r["invalid_transitions"]) for r in rows
        )
        stats["residual_sum"] = sum(int(r["final_residual"]) for r in rows)
        stats["residual_initial_sum"] = sum(
            int(r["initial_residual"]) for r in rows
        )
        stats["materialisable"] = sum(
            int(r["materialisable"]) for r in rows
        )
        stats["steps_sum"] = sum(int(r["steps"]) for r in rows)
        n = max(1, len(rows))
        stats["mean_final_residual"] = stats["residual_sum"] / n
        stats["mean_initial_residual"] = (
            stats["residual_initial_sum"] / n
        )


def final_rc(passed: bool) -> int:
    """Defect A repair: the process exit code mirrors the mechanism signal.

    PASS  -> 0
    FAIL  -> nonzero (2)
    (BLOCKED / checkpoint-missing uses 3; disjointness failure uses 4.)
    """
    return 0 if passed else 2


def main() -> int:
    parser = argparse.ArgumentParser(prog="trm-generalization")

    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="absolute path to the frozen TRM-0 checkpoint. Required for the "
        "held-out run (recorded with its SHA-256); may be omitted only for "
        "--dry-run.",
    )
    parser.add_argument("--cases", type=int, default=5)
    parser.add_argument("--seed", type=int, default=HELDOUT_DEFAULT_SEED)
    parser.add_argument(
        "--seed-count",
        type=int,
        default=HELDOUT_DEFAULT_SEED_COUNT,
    )
    parser.add_argument("--trm-steps", type=int, default=32)
    parser.add_argument("--control-budget", type=int, default=3000)
    parser.add_argument(
        "--train-corpus",
        type=Path,
        default=None,
        help="raw training transition JSONL used to prove held-out "
        "disjointness (required for a non-dry-run)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write full per-fixture/per-arm JSON evidence here",
    )
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    ns = _load_probe_namespace()
    make_fixture = ns["make_fixture"]
    residual_fn = ns["residual"]
    is_resolved_fn = ns["is_resolved"]
    validate_transition_fn = ns["validate_transition"]
    materialisable_fn = ns["materialisable"]
    quiescent_fn = ns["quiescent"]
    refine_null = ns["refine_null"]
    refine_random = ns["refine_random"]
    refine_search = ns["refine_search"]

    # ---------------- defect D : train corpus requirement ---------------
    # A non-dry-run REQUIRES --train-corpus: without it the held-out
    # population cannot be proven disjoint from the training corpus, so the
    # run is BLOCKED with an explicit message and a nonzero rc.
    if args.train_corpus is None and not args.dry_run:
        print(
            "TRM_GEN_BLOCKED "
            "train_corpus_missing=(not provided; --train-corpus is required "
            "for a non-dry-run to prove held-out disjointness)",
            flush=True,
        )
        return 3

    fixtures = None
    seeds = heldout_seeds(args.seed, args.seed_count)

    manifest_rows = []
    if args.train_corpus is not None:
        if not args.train_corpus.is_file():
            print(
                "TRM_GEN_BLOCKED "
                f"train_corpus_missing={args.train_corpus}",
                flush=True,
            )
            return 3
        try:
            fixtures, manifest_rows = build_heldout_manifest(
                make_fixture=make_fixture,
                residual_fn=residual_fn,
                train_jsonl=args.train_corpus,
                cases=args.cases,
                base_seed=args.seed,
                seed_count=args.seed_count,
            )
        except RuntimeError as exc:
            print(f"TRM_GEN_BLOCKED {exc}", flush=True)
            return 3

        selected = sum(1 for r in manifest_rows if r["disjoint"])
        skipped = len(manifest_rows) - selected
        print(
            "TRM_GEN_DISJOINT ok=true "
            f"fixtures={selected} "
            f"skipped_candidates={skipped} "
            f"collisions=0 "
            f"scan={len(manifest_rows)}",
            flush=True,
        )
        for r in manifest_rows:
            if not r["disjoint"]:
                print(
                    "TRM_GEN_DISJOINT_SKIP "
                    f"candidate={r['candidate_index']} "
                    f"seed={r['seed']} lanes={r['lane_count']} "
                    f"reason={r['reason']}",
                    flush=True,
                )
        disjoint_ok = True
    else:
        # dry-run without a corpus: disjointness is not claimed (None)
        fixtures = build_heldout_fixtures(
            make_fixture=make_fixture,
            cases=args.cases,
            base_seed=args.seed,
            seed_count=args.seed_count,
        )
        disjoint_ok = None
        print(
            "TRM_GEN_DISJOINT skipped (dry-run without --train-corpus; "
            "disjointness not claimed)",
            flush=True,
        )

    print(
        "TRM_GEN_BEGIN "
        f"cases={args.cases} "
        f"heldout_seed={args.seed} "
        f"heldout_seeds={json.dumps(seeds)} "
        f"trm_steps={args.trm_steps} "
        f"control_budget={args.control_budget} "
        f"feature_width={FEATURE_WIDTH} "
        f"feature_vocab_sha256={VOCABULARY_DIGEST}",
        flush=True,
    )

    # ---------------- dry-run : manifest + mismatch preflight ------------
    if args.dry_run:
        for index, schema in enumerate(fixtures):
            ids = residual_fn(schema.initial_grid, schema.invariants)
            declared, active = encode_constraint_state(
                schema.invariants, ids
            )
            mismatch = construct_distinct_mismatch(declared, active)
            print(
                f"TRM_GEN_DRY case={index + 1}/{args.cases} "
                f"invariants={sum(declared)} "
                f"initial_residual={len(ids)} "
                f"active_features={sum(active)} "
                f"mismatch_distinct={str(mismatch.distinct).lower()} "
                f"mismatch_reason={mismatch.reason} "
                f"writable={sum(schema.writable_mask)}",
                flush=True,
            )
        print(
            "TRM_GEN_DRY_FINAL "
            f"verdict=PASS cases={args.cases} "
            f"disjoint={str(disjoint_ok).lower()}",
            flush=True,
        )
        # no train corpus -> disjointness skipped (None) is not a failure
        return 0 if (disjoint_ok is None or disjoint_ok) else 4

    # ---------------- checkpoint (defect C) ------------------------------
    if args.checkpoint is None:
        print(
            "TRM_GEN_BLOCKED "
            "checkpoint_missing=(not provided; required for a non-dry-run)",
            flush=True,
        )
        return 3

    if not args.checkpoint.is_file():
        print(
            "TRM_GEN_BLOCKED "
            f"checkpoint_missing={args.checkpoint}",
            flush=True,
        )
        return 3

    checkpoint_path = args.checkpoint.resolve()
    checkpoint_sha = sha256_file(checkpoint_path)

    model, checkpoint = load_model(checkpoint_path)
    checkpoint_epoch = int(checkpoint.get("epoch", -1))

    print(
        "TRM_GEN_MODEL "
        f"checkpoint={checkpoint_path} "
        f"checkpoint_sha256={checkpoint_sha} "
        f"epoch={checkpoint_epoch}",
        flush=True,
    )

    # ---------------- run all arms over all fixtures ---------------------
    arms = (
        "null",
        "random",
        "search",
        "trm_matched",
        "trm_zero_residual",
        "trm_mismatched_residual",
    )

    arm_totals = {
        name: {
            "resolved": 0,
            "cases": 0,
            "authority": 0,
            "residual_sum": 0,
            "residual_initial_sum": 0,
            "frozen_cell_violations": 0,
            "authority_granted": 0,
            "valid_transitions": 0,
            "invalid_transitions": 0,
            "materialisable": 0,
            "steps_sum": 0,
        }
        for name in arms
    }

    results_by_arm = {name: [] for name in arms}
    mismatch_fixture_rows = []

    per_fixture_evidence = []

    for index, schema in enumerate(fixtures):
        case_number = f"{index + 1}/{args.cases}"
        initial_residual = residual_fn(
            schema.initial_grid, schema.invariants
        )
        # the declared universe + matched initial residual for this fixture;
        # used to validate the mismatched arm's contract (defect E).
        declared_for_fixture, matched_active_for_fixture = (
            encode_constraint_state(schema.invariants, initial_residual)
        )
        print(
            f"TRM_GEN case={case_number} phase=begin "
            f"initial_residual={len(initial_residual)}",
            flush=True,
        )

        case_row = {
            "fixture": index,
            "initial_residual": len(initial_residual),
            "writable": int(sum(schema.writable_mask)),
            "invariants": len(schema.invariants),
            "arms": {},
        }

        # control arms share one deterministic rng per fixture (predecessor
        # behaviour), in the order null -> random -> search.
        control_rng = random.Random(args.seed + index)
        for control_name, fn in (
            ("null", refine_null),
            ("random", refine_random),
            ("search", refine_search),
        ):
            started = time.monotonic()
            outcome = run_control_arm(
                arm_name=control_name,
                refine_fn=fn,
                schema=schema,
                rng=control_rng,
                budget=args.control_budget,
                residual_fn=residual_fn,
                is_resolved_fn=is_resolved_fn,
                validate_transition_fn=validate_transition_fn,
                materialisable_fn=materialisable_fn,
                quiescent_fn=quiescent_fn,
            )
            elapsed = time.monotonic() - started
            results_by_arm[control_name].append(outcome)
            case_row["arms"][control_name] = outcome
            _print_arm(case_number, control_name, outcome, elapsed)

        for arm_name, mode in (
            ("trm_matched", "matched"),
            ("trm_zero_residual", "zero"),
            ("trm_mismatched_residual", "mismatched"),
        ):
            started = time.monotonic()
            outcome, step_records = run_trm(
                model=model,
                schema=schema,
                residual_fn=residual_fn,
                is_resolved_fn=is_resolved_fn,
                validate_transition_fn=validate_transition_fn,
                materialisable_fn=materialisable_fn,
                quiescent_fn=quiescent_fn,
                mode=mode,
                max_steps=args.trm_steps,
            )
            elapsed = time.monotonic() - started
            results_by_arm[arm_name].append(outcome)
            case_row["arms"][arm_name] = outcome
            _print_arm(case_number, arm_name, outcome, elapsed)

            if mode == "mismatched":
                # defect E : an explicit UNEVALUABLE step is NOT a
                # degenerate control. Only an allegedly valid mismatch
                # (distinct=True) that violates its own contract counts as
                # a true degeneracy, and that fails loudly via
                # aggregate_mismatch_fixture -> MismatchContractError.
                fixture_mismatch = aggregate_mismatch_fixture(
                    declared=declared_for_fixture,
                    matched_active=matched_active_for_fixture,
                    step_records=step_records,
                    distinct_steps=outcome["mismatch_distinct_steps"],
                    unevaluable=outcome["mismatch_unevaluable"],
                    unevaluable_reason=outcome["mismatch_reason"],
                )
                fixture_mismatch["fixture"] = index
                mismatch_fixture_rows.append(fixture_mismatch)
                case_row["mismatch_classification"] = fixture_mismatch

        per_fixture_evidence.append(case_row)

        print(
            f"TRM_GEN case={case_number} phase=end",
            flush=True,
        )

    _aggregate(arm_totals, results_by_arm)

    # ---------------- summary ------------------------------------------
    print("===== TRM GENERALIZATION SUMMARY =====", flush=True)
    for name in arms:
        stats = arm_totals[name]
        print(
            f"TRM_GEN_SUMMARY arm={name} "
            f"resolved={stats['resolved']}/{stats['cases']} "
            f"mean_final_residual={stats['mean_final_residual']:.3f} "
            f"mean_initial_residual={stats['mean_initial_residual']:.3f} "
            f"authority={stats['authority_granted']} "
            f"frozen_violations={stats['frozen_cell_violations']} "
            f"materialisable={stats['materialisable']} "
            f"valid_trans={stats['valid_transitions']} "
            f"invalid_trans={stats['invalid_transitions']}",
            flush=True,
        )

    mismatch_stats = compute_mismatch_stats(mismatch_fixture_rows)

    # defect F : paired matched-vs-mismatched statistics over the evaluable
    # subset only.
    paired_mismatch_stats = compute_paired_mismatch_stats(
        mismatch_fixture_rows,
        results_by_arm["trm_matched"],
        results_by_arm["trm_mismatched_residual"],
    )

    passed, clauses = compute_mechanism_gate(
        arm_totals,
        mismatch_stats,
        args.cases,
        paired_stats=paired_mismatch_stats,
    )

    print(
        "TRM_GEN_CLAUSES "
        f"passed={json.dumps({k: v['passed'] for k, v in clauses.items()})}",
        flush=True,
    )

    print(
        "TRM_GEN_FINAL "
        f"mechanism_signal={'PASS' if passed else 'FAIL'} "
        f"matched={arm_totals['trm_matched']['resolved']}/"
        f"{arm_totals['trm_matched']['cases']} "
        f"zero={arm_totals['trm_zero_residual']['resolved']}/"
        f"{arm_totals['trm_zero_residual']['cases']} "
        f"mismatched={arm_totals['trm_mismatched_residual']['resolved']}/"
        f"{arm_totals['trm_mismatched_residual']['cases']} "
        f"null={arm_totals['null']['resolved']}/{arm_totals['null']['cases']} "
        f"matched_authority={arm_totals['trm_matched']['authority_granted']} "
        f"frozen_violations="
        f"{sum(a['frozen_cell_violations'] for a in arm_totals.values())} "
        f"mismatch_evaluable={mismatch_stats['evaluable_fixtures']} "
        f"mismatch_unevaluable={mismatch_stats['unevaluable_fixtures']} "
        f"mismatch_degenerate={mismatch_stats['degenerate_steps']} "
        f"paired_fixtures={paired_mismatch_stats['paired_fixture_count']}",
        flush=True,
    )

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "elpis.c2r7c.trm0.generalization-r0-1.v1",
            "role": "EXPERIMENT_ONLY_HELDOUT_TRM0_GENERALIZATION",
            "cases": args.cases,
            "heldout_seed": args.seed,
            "heldout_seeds": seeds,
            "trm_steps": args.trm_steps,
            "control_budget": args.control_budget,
            "checkpoint_path": str(checkpoint_path),
            "checkpoint_sha256": checkpoint_sha,
            "checkpoint_epoch": checkpoint_epoch,
            "feature_width": FEATURE_WIDTH,
            "feature_vocab_sha256": VOCABULARY_DIGEST,
            "heldout_disjoint_ok": disjoint_ok,
            "heldout_disjoint_rows": manifest_rows,
            "train_corpus_path": (
                str(Path(args.train_corpus).resolve())
                if args.train_corpus is not None
                else None
            ),
            "arm_totals": {
                k: {kk: vv for kk, vv in v.items()}
                for k, v in arm_totals.items()
            },
            "mismatch_stats": mismatch_stats,
            "paired_mismatch_stats": {
                k: v for k, v in paired_mismatch_stats.items()
            },
            "mismatch_per_fixture": mismatch_fixture_rows,
            "mechanism_signal": passed,
            "clauses": clauses,
            "per_fixture": per_fixture_evidence,
        }
        args.out.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"TRM_GEN_EVIDENCE out={args.out}", flush=True)

    # defect A : PASS -> 0, FAIL -> nonzero
    return final_rc(passed)


def _print_arm(case_number, name, outcome, elapsed):
    print(
        f"TRM_GEN case={case_number} arm={name} "
        f"resolved={str(outcome['resolved']).lower()} "
        f"residual={outcome['final_residual']} "
        f"reduction={outcome['residual_reduction']} "
        f"steps={outcome['steps']} "
        f"authority={outcome['authority_granted']} "
        f"frozen_viol={outcome['frozen_cell_violations']} "
        f"materialisable={str(outcome['materialisable']).lower()} "
        f"valid={outcome['valid_transitions']} "
        f"invalid={outcome['invalid_transitions']} "
        f"proposed={outcome['proposed_edits']} "
        f"accepted={outcome['accepted_edits']} "
        f"rejected={outcome['rejected_edits']} "
        f"elapsed_s={elapsed:.3f}"
        + (f" error={outcome['error']}" if outcome.get("error") else ""),
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
