from __future__ import annotations

import json
from pathlib import Path

import signed_composition_generalization_r0_4 as h
import structural_trm_features as features


def prereg():
    p = Path(__file__).with_name(
        "PREREGISTRATION_R0_4.json"
    )
    return json.loads(
        p.read_text()
    )


def bits(indices):
    out = [0] * features.FEATURE_WIDTH
    for i in indices:
        out[i] = 1
    return tuple(out)


def test_dev_population_exact():
    assert h.population_spec(
        prereg(),
        "dev",
    ) == {
        "base_seed": 1418886784,
        "cases": 32,
        "seed_count": 8,
        "budget": 128,
    }


def test_final_population_exact():
    assert h.population_spec(
        prereg(),
        "final",
    ) == {
        "base_seed": 454443961,
        "cases": 128,
        "seed_count": 8,
        "budget": 128,
    }


def test_final_is_explicitly_gated():
    assert h.final_open_allowed(
        "dev",
        False,
    )
    assert not h.final_open_allowed(
        "final",
        False,
    )
    assert h.final_open_allowed(
        "final",
        True,
    )


def test_arm_surface_exact():
    assert h.ARMS == (
        "plain_search",
        "matched_full",
        "positive_core",
        "positive_core_count_control",
        "positive_plus_PRECEDES",
        "positive_plus_INTERFACE_TERMINAL",
        "negative_pair_only",
    )


def test_active_support_accepts_five_authorized_families():
    active = bits([
        9,
        67,
        121,
        513,
        521,
    ])

    kinds = h.validate_active_family_support(
        active
    )

    assert set(kinds) == {
        "PRECEDES",
        "CROSS_LANE_ROUTE",
        "MEMORY_SPAN",
        "CONSTRAINT_AFTER",
        "INTERFACE_TERMINAL",
    }


def test_dynamic_mutation_hazard_is_valid_runtime_residual():
    active = bits([
        177,
    ])

    kinds = h.validate_active_family_support(
        active
    )

    assert kinds == ("MUTATION_HAZARD",)


def test_positive_core_filters_dynamic_mutation_hazard():
    active = bits([
        9,
        67,
        121,
        177,
        513,
        521,
    ])

    out, meta = h.manipulate_active(
        "positive_core",
        active,
        tuple(range(81)),
    )

    assert h.r04.active_indices(out) == (
        67,
        121,
        513,
    )

    assert set(meta.actual_removed) == {
        9,
        177,
        521,
    }


def test_count_control_dose_includes_dynamic_noncore_family():
    active = bits([
        9,
        17,
        67,
        121,
        177,
        513,
        521,
    ])

    current = tuple(
        (i * 19) % 23
        for i in range(81)
    )

    core, core_meta = h.manipulate_active(
        "positive_core",
        active,
        current,
    )

    control, control_meta = h.manipulate_active(
        "positive_core_count_control",
        active,
        current,
    )

    assert core_meta.removed_count == 4
    assert control_meta.removed_count == 4
    assert len(h.r04.active_indices(core)) == 3
    assert len(h.r04.active_indices(control)) == 3


def test_matched_full_is_identity():
    active = bits([
        9,
        67,
        121,
        513,
        521,
    ])

    out, meta = h.manipulate_active(
        "matched_full",
        active,
        tuple(range(81)),
    )

    assert out == active
    assert meta.removed_count == 0


def test_runner_core_matches_primitive():
    active = bits([
        9,
        67,
        121,
        513,
        521,
    ])

    current = tuple(range(81))

    a, ma = h.manipulate_active(
        "positive_core",
        active,
        current,
    )

    b, mb = h.r04.apply_positive_core(
        active
    )

    assert a == b
    assert ma == mb


def test_runner_count_control_matches_primitive():
    active = bits([
        9,
        17,
        67,
        121,
        513,
        521,
    ])

    current = tuple(
        (i * 7) % 13
        for i in range(81)
    )

    a, ma = h.manipulate_active(
        "positive_core_count_control",
        active,
        current,
    )

    b, mb = (
        h.r04.apply_positive_core_count_control(
            active,
            current,
        )
    )

    assert a == b
    assert ma == mb
