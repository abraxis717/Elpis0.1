from __future__ import annotations

import family_necessity_r0_3 as r03
import structural_trm_features as features


def bits(indices):
    out = [0] * features.FEATURE_WIDTH
    for i in indices:
        out[i] = 1
    return tuple(out)


def test_vocabulary_authority_is_exact():
    assert features.FEATURE_WIDTH == 529
    assert features.VOCABULARY_DIGEST == r03.EXPECTED_VOCABULARY_DIGEST


def test_active_family_spans_are_exact():
    assert r03.family_indices("PRECEDES") == tuple(range(9, 65))
    assert r03.family_indices("CROSS_LANE_ROUTE") == tuple(range(65, 121))
    assert r03.family_indices("MEMORY_SPAN") == tuple(range(121, 177))
    assert r03.family_indices("CONSTRAINT_AFTER") == tuple(range(513, 521))
    assert r03.family_indices("INTERFACE_TERMINAL") == tuple(range(521, 529))


def test_family_ablation_removes_only_target_active_bits():
    active = bits([9, 17, 67, 121, 513, 521])

    out, meta = r03.apply_family_ablation(
        active,
        "PRECEDES",
    )

    assert r03.active_indices(out) == (
        67,
        121,
        513,
        521,
    )
    assert meta.target_removed == (9, 17)
    assert meta.actual_removed == (9, 17)
    assert meta.removed_count == 2


def test_family_ablation_is_noop_when_family_inactive():
    active = bits([67, 121, 513, 521])

    out, meta = r03.apply_family_ablation(
        active,
        "PRECEDES",
    )

    assert out == active
    assert meta.removed_count == 0


def test_count_control_removes_exact_same_dose():
    active = bits([9, 17, 25, 67, 121, 513, 521])

    family_out, family_meta = r03.apply_family_ablation(
        active,
        "PRECEDES",
    )

    control_out, control_meta = r03.apply_count_control(
        active,
        "PRECEDES",
        tuple(range(81)),
    )

    assert family_meta.removed_count == 3
    assert control_meta.removed_count == 3

    assert (
        len(r03.active_indices(active))
        - len(r03.active_indices(family_out))
        == 3
    )

    assert (
        len(r03.active_indices(active))
        - len(r03.active_indices(control_out))
        == 3
    )


def test_count_control_is_deterministic():
    active = bits([9, 17, 25, 67, 121, 513, 521])
    current = tuple((i * 7) % 11 for i in range(81))

    a, ma = r03.apply_count_control(
        active,
        "PRECEDES",
        current,
    )

    b, mb = r03.apply_count_control(
        active,
        "PRECEDES",
        current,
    )

    assert a == b
    assert ma == mb


def test_count_control_forced_distinct_when_alternative_exists():
    active = bits([9, 17, 67, 121, 513, 521])
    current = tuple((i * 13) % 9 for i in range(81))

    family_out, family_meta = r03.apply_family_ablation(
        active,
        "PRECEDES",
    )

    control_out, control_meta = r03.apply_count_control(
        active,
        "PRECEDES",
        current,
    )

    assert family_meta.removed_count == control_meta.removed_count
    assert control_meta.control_alternative_exists
    assert control_meta.control_distinct
    assert control_out != family_out


def test_count_control_noop_when_target_family_inactive():
    active = bits([67, 121, 513, 521])

    out, meta = r03.apply_count_control(
        active,
        "PRECEDES",
        tuple(range(81)),
    )

    assert out == active
    assert meta.removed_count == 0


def test_residual_subset_contract_rejects_activation():
    declared = bits([9, 17, 67])
    matched = bits([9])
    manipulated = bits([9, 17])

    try:
        r03.validate_residual_subset(
            declared,
            matched,
            manipulated,
        )
    except r03.R03ContractError:
        pass
    else:
        raise AssertionError("activation was not rejected")


def test_declared_vector_is_not_modified_by_ablation_helpers():
    declared = bits([9, 17, 67, 121, 513, 521])
    original = declared

    active = bits([9, 17, 67, 121, 513, 521])

    r03.apply_family_ablation(
        active,
        "PRECEDES",
    )

    r03.apply_count_control(
        active,
        "PRECEDES",
        tuple(range(81)),
    )

    assert declared == original
