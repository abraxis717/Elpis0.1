from __future__ import annotations

import hashlib
from dataclasses import dataclass

import structural_trm_features as features
import family_necessity_r0_3 as r03


EXPECTED_VOCABULARY_DIGEST = (
    "dff5506be69bec65e121778274ea59c9900d843c334588bc72854f40c98a94d0"
)

POSITIVE_FAMILIES = (
    "CROSS_LANE_ROUTE",
    "MEMORY_SPAN",
    "CONSTRAINT_AFTER",
)

NEGATIVE_FAMILIES = (
    "PRECEDES",
    "INTERFACE_TERMINAL",
)

ALL_RESIDUAL_ACTIVE_FAMILIES = frozenset(
    POSITIVE_FAMILIES + NEGATIVE_FAMILIES
)


class R04ContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class CompositionMetadata:
    mode: str
    target_removed: tuple[int, ...]
    actual_removed: tuple[int, ...]
    removed_count: int
    control_overlap_count: int
    control_distinct: bool
    control_alternative_exists: bool


def signature_kind(index: int) -> str:
    return str(features.SIGNATURES[index][0])


def active_indices(bits) -> tuple[int, ...]:
    return tuple(
        i for i, bit in enumerate(bits)
        if int(bit)
    )


def validate_vocabulary():
    if features.FEATURE_WIDTH != 529:
        raise R04ContractError("feature width mismatch")

    if features.VOCABULARY_DIGEST != EXPECTED_VOCABULARY_DIGEST:
        raise R04ContractError("feature vocabulary digest mismatch")

    if frozenset(r03.ACTIVE_FAMILIES) != ALL_RESIDUAL_ACTIVE_FAMILIES:
        raise R04ContractError("R0.3 active-family authority mismatch")


def keep_families(
    matched_active,
    keep,
    *,
    mode: str,
):
    validate_vocabulary()

    keep = frozenset(keep)
    matched = tuple(int(v) for v in matched_active)

    out = list(matched)

    target_removed = tuple(
        i
        for i in active_indices(matched)
        if signature_kind(i) not in keep
    )

    for i in target_removed:
        out[i] = 0

    result = tuple(out)

    actual_removed = tuple(
        i
        for i in range(len(matched))
        if matched[i] and not result[i]
    )

    if actual_removed != target_removed:
        raise R04ContractError("composition removed unexpected bits")

    if any(result[i] > matched[i] for i in range(len(matched))):
        raise R04ContractError("composition activated inactive bit")

    return result, CompositionMetadata(
        mode=mode,
        target_removed=target_removed,
        actual_removed=actual_removed,
        removed_count=len(actual_removed),
        control_overlap_count=len(actual_removed),
        control_distinct=False,
        control_alternative_exists=False,
    )


def apply_positive_core(matched_active):
    return keep_families(
        matched_active,
        POSITIVE_FAMILIES,
        mode="positive_core",
    )


def apply_positive_plus_precedes(matched_active):
    return keep_families(
        matched_active,
        POSITIVE_FAMILIES + ("PRECEDES",),
        mode="positive_plus_PRECEDES",
    )


def apply_positive_plus_interface_terminal(matched_active):
    return keep_families(
        matched_active,
        POSITIVE_FAMILIES + ("INTERFACE_TERMINAL",),
        mode="positive_plus_INTERFACE_TERMINAL",
    )


def apply_negative_pair_only(matched_active):
    return keep_families(
        matched_active,
        NEGATIVE_FAMILIES,
        mode="negative_pair_only",
    )


def _rank(current, index: int) -> bytes:
    payload = (
        "C2R7C_R0_4_POSITIVE_CORE_COUNT_CONTROL|"
        + ",".join(str(int(v)) for v in current)
        + "|"
        + str(int(index))
    )
    return hashlib.sha256(payload.encode("ascii")).digest()


def apply_positive_core_count_control(
    matched_active,
    current,
):
    matched = tuple(int(v) for v in matched_active)

    _, core_meta = apply_positive_core(matched)
    target = core_meta.target_removed
    k = len(target)

    active = active_indices(matched)

    if k == 0:
        return matched, CompositionMetadata(
            mode="positive_core_count_control",
            target_removed=(),
            actual_removed=(),
            removed_count=0,
            control_overlap_count=0,
            control_distinct=False,
            control_alternative_exists=False,
        )

    if k > len(active):
        raise R04ContractError("control dose exceeds active residual")

    ranked = sorted(
        active,
        key=lambda i: (_rank(current, i), i),
    )

    selected = tuple(sorted(ranked[:k]))
    target_set = frozenset(target)

    alternative_exists = 0 < k < len(active)

    if frozenset(selected) == target_set and alternative_exists:
        replacement = next(
            i for i in ranked[k:]
            if i not in target_set
        )

        selected_list = list(selected)

        replace_candidates = sorted(
            (
                i
                for i in selected_list
                if i in target_set
            ),
            key=lambda i: (_rank(current, i), i),
            reverse=True,
        )

        if not replace_candidates:
            raise R04ContractError(
                "unable to force count-control distinctness"
            )

        selected_list.remove(replace_candidates[0])
        selected_list.append(replacement)
        selected = tuple(sorted(selected_list))

    if len(selected) != k:
        raise R04ContractError("count-control dose changed")

    if any(not matched[i] for i in selected):
        raise R04ContractError(
            "count control selected inactive bit"
        )

    distinct = frozenset(selected) != target_set

    if alternative_exists and not distinct:
        raise R04ContractError(
            "count control equals composition target"
        )

    out = list(matched)

    for i in selected:
        out[i] = 0

    result = tuple(out)

    actual_removed = tuple(
        i
        for i in range(len(matched))
        if matched[i] and not result[i]
    )

    if actual_removed != selected:
        raise R04ContractError(
            "count control removed unexpected bits"
        )

    if len(actual_removed) != len(target):
        raise R04ContractError(
            "count control is not dose matched"
        )

    overlap = len(
        set(actual_removed) & set(target)
    )

    return result, CompositionMetadata(
        mode="positive_core_count_control",
        target_removed=target,
        actual_removed=actual_removed,
        removed_count=len(actual_removed),
        control_overlap_count=overlap,
        control_distinct=distinct,
        control_alternative_exists=alternative_exists,
    )


def validate_subset(
    declared,
    matched_active,
    manipulated,
):
    if len(declared) != 529:
        raise R04ContractError("declared width mismatch")

    if len(matched_active) != 529:
        raise R04ContractError("matched width mismatch")

    if len(manipulated) != 529:
        raise R04ContractError("manipulated width mismatch")

    for i in range(529):
        if manipulated[i] and not matched_active[i]:
            raise R04ContractError(
                f"activated non-matched bit {i}"
            )

        if manipulated[i] and not declared[i]:
            raise R04ContractError(
                f"escaped declared universe at {i}"
            )
