from __future__ import annotations

import hashlib
from dataclasses import dataclass

import torch

import guided_search_r0_2 as r02
import structural_trm_features as features
import structural_trm_generalization as r01


EXPECTED_VOCABULARY_DIGEST = (
    "dff5506be69bec65e121778274ea59c9900d843c334588bc72854f40c98a94d0"
)

ACTIVE_FAMILIES = (
    "PRECEDES",
    "CROSS_LANE_ROUTE",
    "MEMORY_SPAN",
    "CONSTRAINT_AFTER",
    "INTERFACE_TERMINAL",
)

EXPECTED_SPANS = {
    "PRECEDES": (9, 64),
    "CROSS_LANE_ROUTE": (65, 120),
    "MEMORY_SPAN": (121, 176),
    "CONSTRAINT_AFTER": (513, 520),
    "INTERFACE_TERMINAL": (521, 528),
}


class R03ContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class AblationMetadata:
    family: str
    mode: str
    target_removed: tuple[int, ...]
    actual_removed: tuple[int, ...]
    removed_count: int
    control_overlap_count: int
    control_distinct: bool
    control_alternative_exists: bool


def family_indices(family: str) -> tuple[int, ...]:
    if features.VOCABULARY_DIGEST != EXPECTED_VOCABULARY_DIGEST:
        raise R03ContractError("feature vocabulary digest mismatch")

    if family not in ACTIVE_FAMILIES:
        raise R03ContractError(f"unsupported active family: {family}")

    indices = tuple(
        i
        for i, (kind, lanes) in enumerate(features.SIGNATURES)
        if kind == family
    )

    if not indices:
        raise R03ContractError(f"family has no vocabulary indices: {family}")

    expected = EXPECTED_SPANS[family]
    if (min(indices), max(indices)) != expected:
        raise R03ContractError(
            f"family span mismatch for {family}: "
            f"{(min(indices), max(indices))} != {expected}"
        )

    if indices != tuple(range(expected[0], expected[1] + 1)):
        raise R03ContractError(f"family indices not contiguous: {family}")

    return indices


def active_indices(bits) -> tuple[int, ...]:
    return tuple(i for i, bit in enumerate(bits) if int(bit))


def target_family_active_indices(
    matched_active,
    family: str,
) -> tuple[int, ...]:
    support = set(family_indices(family))
    return tuple(
        i
        for i in active_indices(matched_active)
        if i in support
    )


def apply_family_ablation(
    matched_active,
    family: str,
) -> tuple[tuple[int, ...], AblationMetadata]:
    matched = tuple(int(v) for v in matched_active)
    target = target_family_active_indices(matched, family)

    out = list(matched)
    for i in target:
        out[i] = 0

    result = tuple(out)

    if any(result[i] > matched[i] for i in range(len(matched))):
        raise R03ContractError("family ablation activated an inactive bit")

    removed = tuple(
        i
        for i in range(len(matched))
        if matched[i] and not result[i]
    )

    if removed != target:
        raise R03ContractError("family ablation removed wrong bits")

    metadata = AblationMetadata(
        family=family,
        mode="family",
        target_removed=target,
        actual_removed=removed,
        removed_count=len(removed),
        control_overlap_count=len(removed),
        control_distinct=False,
        control_alternative_exists=False,
    )

    return result, metadata


def _control_rank(
    family: str,
    current,
    index: int,
) -> bytes:
    payload = (
        "C2R7C_R0_3_COUNT_CONTROL|"
        + family
        + "|"
        + ",".join(str(int(v)) for v in current)
        + "|"
        + str(int(index))
    )
    return hashlib.sha256(payload.encode("ascii")).digest()


def apply_count_control(
    matched_active,
    family: str,
    current,
) -> tuple[tuple[int, ...], AblationMetadata]:
    matched = tuple(int(v) for v in matched_active)
    active = active_indices(matched)
    target = target_family_active_indices(matched, family)
    k = len(target)

    if k == 0:
        metadata = AblationMetadata(
            family=family,
            mode="count_control",
            target_removed=(),
            actual_removed=(),
            removed_count=0,
            control_overlap_count=0,
            control_distinct=False,
            control_alternative_exists=False,
        )
        return matched, metadata

    if k > len(active):
        raise R03ContractError("control removal count exceeds active count")

    ranked = sorted(
        active,
        key=lambda i: (_control_rank(family, current, i), i),
    )

    selected = tuple(sorted(ranked[:k]))
    target_set = frozenset(target)

    alternative_exists = len(active) > k

    if frozenset(selected) == target_set and alternative_exists:
        replacement = next(
            i for i in ranked[k:]
            if i not in target_set
        )

        selected_list = list(selected)

        replace_candidates = sorted(
            (i for i in selected_list if i in target_set),
            key=lambda i: (_control_rank(family, current, i), i),
            reverse=True,
        )

        if not replace_candidates:
            raise R03ContractError(
                "unable to force count-control distinctness"
            )

        selected_list.remove(replace_candidates[0])
        selected_list.append(replacement)
        selected = tuple(sorted(selected_list))

    if len(selected) != k:
        raise R03ContractError("count-control dose changed")

    if any(not matched[i] for i in selected):
        raise R03ContractError("count control selected inactive bit")

    distinct = frozenset(selected) != target_set

    if alternative_exists and not distinct:
        raise R03ContractError(
            "count control equals family ablation despite alternative"
        )

    out = list(matched)
    for i in selected:
        out[i] = 0

    result = tuple(out)

    removed = tuple(
        i
        for i in range(len(matched))
        if matched[i] and not result[i]
    )

    if removed != selected:
        raise R03ContractError("count control removed wrong bits")

    if len(removed) != len(target):
        raise R03ContractError("count control is not dose matched")

    overlap = len(set(removed) & set(target))

    metadata = AblationMetadata(
        family=family,
        mode="count_control",
        target_removed=target,
        actual_removed=removed,
        removed_count=len(removed),
        control_overlap_count=overlap,
        control_distinct=distinct,
        control_alternative_exists=alternative_exists,
    )

    return result, metadata


def validate_residual_subset(
    declared,
    matched_active,
    manipulated,
):
    if len(declared) != features.FEATURE_WIDTH:
        raise R03ContractError("declared width mismatch")

    if len(matched_active) != features.FEATURE_WIDTH:
        raise R03ContractError("matched width mismatch")

    if len(manipulated) != features.FEATURE_WIDTH:
        raise R03ContractError("manipulated width mismatch")

    for i in range(features.FEATURE_WIDTH):
        if manipulated[i] and not matched_active[i]:
            raise R03ContractError(
                f"manipulation activated non-matched bit {i}"
            )

        if manipulated[i] and not declared[i]:
            raise R03ContractError(
                f"manipulation escaped declared universe at {i}"
            )


def build_proposal_fn(
    *,
    model,
    schema,
    residual_fn,
    mode: str,
    family: str | None,
):
    if mode not in {"matched", "family", "count_control"}:
        raise R03ContractError(f"unknown R0.3 mode: {mode}")

    if mode != "matched" and family not in ACTIVE_FAMILIES:
        raise R03ContractError(
            f"family required for mode {mode}: {family}"
        )

    initial_residual = residual_fn(
        schema.initial_grid,
        schema.invariants,
    )

    declared, _ = r01.encode_constraint_state(
        schema.invariants,
        initial_residual,
    )

    mask_t = r01.grid_tensor(schema.writable_mask)

    def proposal_fn(current):
        current_residual = residual_fn(
            current,
            schema.invariants,
        )

        _, matched_active = r01.encode_constraint_state(
            schema.invariants,
            current_residual,
        )

        if mode == "matched":
            active = tuple(matched_active)
            metadata = {
                "r03_family": "",
                "r03_mode": "matched",
                "r03_target_removed": 0,
                "r03_actual_removed": 0,
                "r03_control_overlap": 0,
                "r03_control_distinct": False,
                "r03_control_alternative_exists": False,
            }

        elif mode == "family":
            active, m = apply_family_ablation(
                matched_active,
                family,
            )
            metadata = {
                "r03_family": family,
                "r03_mode": "family",
                "r03_target_removed": len(m.target_removed),
                "r03_actual_removed": len(m.actual_removed),
                "r03_control_overlap": m.control_overlap_count,
                "r03_control_distinct": m.control_distinct,
                "r03_control_alternative_exists":
                    m.control_alternative_exists,
            }

        else:
            active, m = apply_count_control(
                matched_active,
                family,
                current,
            )
            metadata = {
                "r03_family": family,
                "r03_mode": "count_control",
                "r03_target_removed": len(m.target_removed),
                "r03_actual_removed": len(m.actual_removed),
                "r03_control_overlap": m.control_overlap_count,
                "r03_control_distinct": m.control_distinct,
                "r03_control_alternative_exists":
                    m.control_alternative_exists,
            }

        validate_residual_subset(
            declared,
            matched_active,
            active,
        )

        grid_t = r01.grid_tensor(current)

        with torch.inference_mode():
            _, proposed_tensor, _ = model.propose(
                grid_t,
                mask_t,
                r01.bits_tensor(declared),
                r01.bits_tensor(active),
                carry=None,
            )

        proposal = tuple(
            int(v)
            for v in proposed_tensor[0].tolist()
        )

        return proposal, metadata

    return proposal_fn


def refine_r03_search(
    grid,
    mask,
    invariants,
    rng,
    budget,
    *,
    proposal_fn,
):
    stats_accum = {
        "r03_queries": 0,
        "r03_target_removed_sum": 0,
        "r03_actual_removed_sum": 0,
        "r03_control_overlap_sum": 0,
        "r03_control_distinct_steps": 0,
        "r03_control_alternative_steps": 0,
        "r03_nonzero_dose_queries": 0,
        "r03_dose_mismatch_steps": 0,
    }

    def wrapped(current):
        proposal, metadata = proposal_fn(current)

        stats_accum["r03_queries"] += 1
        stats_accum["r03_target_removed_sum"] += int(
            metadata["r03_target_removed"]
        )
        stats_accum["r03_actual_removed_sum"] += int(
            metadata["r03_actual_removed"]
        )
        stats_accum["r03_control_overlap_sum"] += int(
            metadata["r03_control_overlap"]
        )
        stats_accum["r03_control_distinct_steps"] += int(
            metadata["r03_control_distinct"]
        )
        stats_accum["r03_control_alternative_steps"] += int(
            metadata["r03_control_alternative_exists"]
        )
        stats_accum["r03_nonzero_dose_queries"] += int(
            metadata["r03_target_removed"] > 0
        )
        stats_accum["r03_dose_mismatch_steps"] += int(
            metadata["r03_target_removed"]
            != metadata["r03_actual_removed"]
        )

        return proposal, metadata

    final, steps, search_stats = r02.refine_guided_search(
        grid,
        mask,
        invariants,
        rng,
        budget,
        proposal_fn=wrapped,
    )

    search_stats.update(stats_accum)
    return final, steps, search_stats
