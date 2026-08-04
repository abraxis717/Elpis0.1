"""Provenance independence tests for typed orbit identities.

Verifies that orbit digests depend ONLY on semantic content, not on
provenance-bound fields (source_case_id, source_row_digest, view digests,
stored_quiescence, lineage_status, split labels).
"""

import copy
import sys
import os

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_typed.typed_orbits import (
    TransitionOrbitV1,
    ExpansionOrbitV1,
    QuiescenceOrbitV1,
    RationaleOrbitV1,
)

# ---------------------------------------------------------------------------
# Fixture: a realistic source row
# ---------------------------------------------------------------------------

BASE_ROW = {
    "input_grid": [i % 10 for i in range(81)],
    "input_mask": [1 if i % 3 == 0 else 0 for i in range(81)],
    "canonical_target_grid": [((i + 1) % 10) for i in range(81)],
    "expansion_targets": [5, 14, 23, 32, 41],
    "quiescence_target": False,
    "rationale_codes": ["CODE_A", "CODE_B"],
}

BASE_CASE_ID = "case_alpha_001"
BASE_ROW_DIGEST = "sha256_abc123"
BASE_SPLIT = "train"


def _make_transition_view(case_id=BASE_CASE_ID, row_digest=BASE_ROW_DIGEST):
    grid = list(BASE_ROW["input_grid"])
    target = list(BASE_ROW["canonical_target_grid"])
    delta_cells = [i for i in range(81) if grid[i] != target[i]]
    target_cell = delta_cells[0] if delta_cells else None
    target_value = target[target_cell] if target_cell is not None else 0
    return {
        "source_case_id": case_id,
        "source_row_digest": row_digest,
        "input_grid": grid,
        "input_mask": list(BASE_ROW["input_mask"]),
        "canonical_target_grid": target,
        "delta_kind": "EDIT",
        "target_cell": target_cell,
        "target_value": target_value,
        "transition_digest": "t_digest_original",
    }


def _make_expansion_view(case_id=BASE_CASE_ID, row_digest=BASE_ROW_DIGEST):
    return {
        "source_case_id": case_id,
        "source_row_digest": row_digest,
        "input_grid": list(BASE_ROW["input_grid"]),
        "expansion_locus_mask81": [
            1 if i in BASE_ROW["expansion_targets"] else 0 for i in range(81)
        ],
        "expansion_cells": sorted(BASE_ROW["expansion_targets"]),
        "expansion_view_digest": "e_digest_original",
    }


def _make_quiescence_view(case_id=BASE_CASE_ID, row_digest=BASE_ROW_DIGEST):
    grid = list(BASE_ROW["input_grid"])
    has_void = any(c == 0 for c in grid)
    has_expansion = any(c == 6 for c in grid)
    derived = not has_void and not has_expansion
    return {
        "source_case_id": case_id,
        "source_row_digest": row_digest,
        "input_grid": grid,
        "derived_quiescence": derived,
        "stored_quiescence": BASE_ROW["quiescence_target"],
        "lineage_status": "AGREED",
        "quiescence_view_digest": "q_digest_original",
    }


def _make_rationale_view(case_id=BASE_CASE_ID, row_digest=BASE_ROW_DIGEST):
    grid = list(BASE_ROW["input_grid"])
    target = list(BASE_ROW["canonical_target_grid"])
    delta_cells = sorted([i for i in range(81) if grid[i] != target[i]])
    return {
        "source_case_id": case_id,
        "source_row_digest": row_digest,
        "input_grid": grid,
        "canonical_target_grid": target,
        "transition_delta": {
            "delta_cells": delta_cells,
            "delta_size": len(delta_cells),
        },
        "rationale_codes": list(BASE_ROW["rationale_codes"]),
        "rationale_view_digest": "r_digest_original",
    }


# ---------------------------------------------------------------------------
# Test 1: Provenance-field independence
# ---------------------------------------------------------------------------

def test_provenance_field_independence():
    # Transition
    tv_base = _make_transition_view()
    orbit_base = TransitionOrbitV1.compute(tv_base)
    tv_mut = copy.deepcopy(tv_base)
    tv_mut["source_case_id"] = "case_mutated_999"
    tv_mut["source_row_digest"] = "sha256_mutated_xyz"
    tv_mut["transition_digest"] = "t_digest_mutated"
    orbit_mut = TransitionOrbitV1.compute(tv_mut)
    assert orbit_base.orbit_digest == orbit_mut.orbit_digest, (
        "transition orbit digest depends on provenance fields"
    )

    # Expansion
    ev_base = _make_expansion_view()
    orbit_base = ExpansionOrbitV1.compute(ev_base)
    ev_mut = copy.deepcopy(ev_base)
    ev_mut["source_case_id"] = "case_mutated_999"
    ev_mut["source_row_digest"] = "sha256_mutated_xyz"
    ev_mut["expansion_view_digest"] = "e_digest_mutated"
    orbit_mut = ExpansionOrbitV1.compute(ev_mut)
    assert orbit_base.orbit_digest == orbit_mut.orbit_digest, (
        "expansion orbit digest depends on provenance fields"
    )

    # Quiescence
    qv_base = _make_quiescence_view()
    orbit_base = QuiescenceOrbitV1.compute(qv_base)
    qv_mut = copy.deepcopy(qv_base)
    qv_mut["source_case_id"] = "case_mutated_999"
    qv_mut["source_row_digest"] = "sha256_mutated_xyz"
    qv_mut["quiescence_view_digest"] = "q_digest_mutated"
    orbit_mut = QuiescenceOrbitV1.compute(qv_mut)
    assert orbit_base.orbit_digest == orbit_mut.orbit_digest, (
        "quiescence orbit digest depends on provenance fields"
    )

    # Rationale
    rv_base = _make_rationale_view()
    orbit_base = RationaleOrbitV1.compute(rv_base)
    rv_mut = copy.deepcopy(rv_base)
    rv_mut["source_case_id"] = "case_mutated_999"
    rv_mut["source_row_digest"] = "sha256_mutated_xyz"
    rv_mut["rationale_view_digest"] = "r_digest_mutated"
    orbit_mut = RationaleOrbitV1.compute(rv_mut)
    assert orbit_base.orbit_digest == orbit_mut.orbit_digest, (
        "rationale orbit digest depends on provenance fields"
    )


# ---------------------------------------------------------------------------
# Test 2: Case-ID independence
# ---------------------------------------------------------------------------

def test_case_id_independence():
    tv_a = _make_transition_view(case_id="case_X")
    tv_b = _make_transition_view(case_id="case_Y")
    assert TransitionOrbitV1.compute(tv_a).orbit_digest == TransitionOrbitV1.compute(tv_b).orbit_digest, (
        "transition orbit depends on case_id"
    )

    ev_a = _make_expansion_view(case_id="case_X")
    ev_b = _make_expansion_view(case_id="case_Y")
    assert ExpansionOrbitV1.compute(ev_a).orbit_digest == ExpansionOrbitV1.compute(ev_b).orbit_digest, (
        "expansion orbit depends on case_id"
    )

    qv_a = _make_quiescence_view(case_id="case_X")
    qv_b = _make_quiescence_view(case_id="case_Y")
    assert QuiescenceOrbitV1.compute(qv_a).orbit_digest == QuiescenceOrbitV1.compute(qv_b).orbit_digest, (
        "quiescence orbit depends on case_id"
    )

    rv_a = _make_rationale_view(case_id="case_X")
    rv_b = _make_rationale_view(case_id="case_Y")
    assert RationaleOrbitV1.compute(rv_a).orbit_digest == RationaleOrbitV1.compute(rv_b).orbit_digest, (
        "rationale orbit depends on case_id"
    )


# ---------------------------------------------------------------------------
# Test 3: Split independence
# ---------------------------------------------------------------------------

def test_split_independence():
    """Orbit digests must not depend on source_split."""
    tv = _make_transition_view()
    tv_with_split = {**tv, "source_split": "train"}
    tv_other_split = {**tv, "source_split": "validation"}
    assert TransitionOrbitV1.compute(tv_with_split).orbit_digest == TransitionOrbitV1.compute(tv_other_split).orbit_digest, (
        "transition orbit depends on source_split"
    )

    ev = _make_expansion_view()
    ev_with_split = {**ev, "source_split": "train"}
    ev_other_split = {**ev, "source_split": "test"}
    assert ExpansionOrbitV1.compute(ev_with_split).orbit_digest == ExpansionOrbitV1.compute(ev_other_split).orbit_digest, (
        "expansion orbit depends on source_split"
    )

    qv = _make_quiescence_view()
    qv_with_split = {**qv, "source_split": "train"}
    qv_other_split = {**qv, "source_split": "validation"}
    assert QuiescenceOrbitV1.compute(qv_with_split).orbit_digest == QuiescenceOrbitV1.compute(qv_other_split).orbit_digest, (
        "quiescence orbit depends on source_split"
    )

    rv = _make_rationale_view()
    rv_with_split = {**rv, "source_split": "train"}
    rv_other_split = {**rv, "source_split": "test"}
    assert RationaleOrbitV1.compute(rv_with_split).orbit_digest == RationaleOrbitV1.compute(rv_other_split).orbit_digest, (
        "rationale orbit depends on source_split"
    )


# ---------------------------------------------------------------------------
# Test 4: Quiescence-lineage independence
# ---------------------------------------------------------------------------

def test_quiescence_lineage_independence():
    qv_base = _make_quiescence_view()
    orbit_base = QuiescenceOrbitV1.compute(qv_base)

    qv_mut = copy.deepcopy(qv_base)
    qv_mut["stored_quiescence"] = not qv_mut["stored_quiescence"]
    qv_mut["lineage_status"] = "STALE_STORED_LABEL"
    qv_mut["quiescence_view_digest"] = "completely_different_digest"
    orbit_mut = QuiescenceOrbitV1.compute(qv_mut)

    assert orbit_base.orbit_digest == orbit_mut.orbit_digest, (
        "quiescence orbit depends on lineage fields (stored_quiescence, lineage_status, quiescence_view_digest)"
    )


# ---------------------------------------------------------------------------
# Test 5: Semantic sensitivity
# ---------------------------------------------------------------------------

def test_semantic_sensitivity():
    # (a) transition target_cell changed
    tv_base = _make_transition_view()
    tv_mut = copy.deepcopy(tv_base)
    tv_mut["target_cell"] = 77
    assert TransitionOrbitV1.compute(tv_base).orbit_digest != TransitionOrbitV1.compute(tv_mut).orbit_digest, (
        "transition orbit not sensitive to target_cell change"
    )

    # (b) transition target_value changed
    tv_base = _make_transition_view()
    tv_mut = copy.deepcopy(tv_base)
    tv_mut["target_value"] = 99
    assert TransitionOrbitV1.compute(tv_base).orbit_digest != TransitionOrbitV1.compute(tv_mut).orbit_digest, (
        "transition orbit not sensitive to target_value change"
    )

    # (c) expansion cell removed
    ev_base = _make_expansion_view()
    ev_mut = copy.deepcopy(ev_base)
    ev_mut["expansion_cells"] = ev_mut["expansion_cells"][:-1]
    assert ExpansionOrbitV1.compute(ev_base).orbit_digest != ExpansionOrbitV1.compute(ev_mut).orbit_digest, (
        "expansion orbit not sensitive to cell removal"
    )

    # (d) derived_quiescence flipped
    qv_base = _make_quiescence_view()
    qv_mut = copy.deepcopy(qv_base)
    qv_mut["derived_quiescence"] = not qv_mut["derived_quiescence"]
    assert QuiescenceOrbitV1.compute(qv_base).orbit_digest != QuiescenceOrbitV1.compute(qv_mut).orbit_digest, (
        "quiescence orbit not sensitive to derived_quiescence flip"
    )

    # (e) rationale code changed
    rv_base = _make_rationale_view()
    rv_mut = copy.deepcopy(rv_base)
    rv_mut["rationale_codes"] = ["CODE_X", "CODE_Y"]
    assert RationaleOrbitV1.compute(rv_base).orbit_digest != RationaleOrbitV1.compute(rv_mut).orbit_digest, (
        "rationale orbit not sensitive to rationale_codes change"
    )
