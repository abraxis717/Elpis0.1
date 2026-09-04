from __future__ import annotations

import signed_composition_r0_4 as r04
import structural_trm_features as features


def bits(indices):
    out = [0] * features.FEATURE_WIDTH
    for i in indices:
        out[i] = 1
    return tuple(out)


def test_vocabulary_authority_exact():
    r04.validate_vocabulary()
    assert features.FEATURE_WIDTH == 529


def test_family_partition_exact():
    assert r04.POSITIVE_FAMILIES == (
        "CROSS_LANE_ROUTE",
        "MEMORY_SPAN",
        "CONSTRAINT_AFTER",
    )

    assert r04.NEGATIVE_FAMILIES == (
        "PRECEDES",
        "INTERFACE_TERMINAL",
    )


def test_positive_core_removes_only_negative_families():
    active = bits([
        9,
        17,
        67,
        121,
        513,
        521,
    ])

    out, meta = r04.apply_positive_core(active)

    assert r04.active_indices(out) == (
        67,
        121,
        513,
    )

    assert meta.target_removed == (
        9,
        17,
        521,
    )


def test_positive_plus_precedes_removes_only_interface():
    active = bits([
        9,
        67,
        121,
        513,
        521,
    ])

    out, meta = r04.apply_positive_plus_precedes(active)

    assert r04.active_indices(out) == (
        9,
        67,
        121,
        513,
    )

    assert meta.target_removed == (521,)


def test_positive_plus_interface_removes_only_precedes():
    active = bits([
        9,
        67,
        121,
        513,
        521,
    ])

    out, meta = r04.apply_positive_plus_interface_terminal(active)

    assert r04.active_indices(out) == (
        67,
        121,
        513,
        521,
    )

    assert meta.target_removed == (9,)


def test_negative_pair_only_removes_positive_families():
    active = bits([
        9,
        67,
        121,
        513,
        521,
    ])

    out, meta = r04.apply_negative_pair_only(active)

    assert r04.active_indices(out) == (
        9,
        521,
    )

    assert meta.target_removed == (
        67,
        121,
        513,
    )


def test_count_control_exact_same_dose():
    active = bits([
        9,
        17,
        25,
        67,
        121,
        513,
        521,
    ])

    core, cm = r04.apply_positive_core(active)

    control, dm = r04.apply_positive_core_count_control(
        active,
        tuple(range(81)),
    )

    assert cm.removed_count == dm.removed_count

    assert (
        len(r04.active_indices(active))
        - len(r04.active_indices(core))
        ==
        len(r04.active_indices(active))
        - len(r04.active_indices(control))
    )


def test_count_control_deterministic():
    active = bits([
        9,
        17,
        67,
        121,
        513,
        521,
    ])

    current = tuple(
        (i * 11) % 13
        for i in range(81)
    )

    a, ma = r04.apply_positive_core_count_control(
        active,
        current,
    )

    b, mb = r04.apply_positive_core_count_control(
        active,
        current,
    )

    assert a == b
    assert ma == mb


def test_count_control_distinct_when_alternative_exists():
    active = bits([
        9,
        17,
        67,
        121,
        513,
        521,
    ])

    current = tuple(
        (i * 17) % 19
        for i in range(81)
    )

    core, cm = r04.apply_positive_core(active)

    control, dm = r04.apply_positive_core_count_control(
        active,
        current,
    )

    assert cm.removed_count == dm.removed_count
    assert dm.control_alternative_exists
    assert dm.control_distinct
    assert control != core


def test_zero_negative_dose_is_noop_control():
    active = bits([
        67,
        121,
        513,
    ])

    core, cm = r04.apply_positive_core(active)

    control, dm = r04.apply_positive_core_count_control(
        active,
        tuple(range(81)),
    )

    assert core == active
    assert control == active
    assert cm.removed_count == 0
    assert dm.removed_count == 0


def test_subset_contract_rejects_activation():
    declared = bits([9, 67])
    matched = bits([67])
    manipulated = bits([9, 67])

    try:
        r04.validate_subset(
            declared,
            matched,
            manipulated,
        )
    except r04.R04ContractError:
        pass
    else:
        raise AssertionError(
            "activation was not rejected"
        )
