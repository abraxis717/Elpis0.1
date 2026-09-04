from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .authority import (
    FROZEN_TRM0_CHECKPOINT_SHA256,
)
from .receipt import (
    SCHEMA as RECEIPT_SCHEMA,
    StructuralGuidanceReceiptV1,
)
from ._authority.c2r6p0.contracts import (
    ProjectionResultV1,
)
from ._authority.c2r6p1_bridge.adapter import (
    adapt_projection_to_refiner_input,
    build_envelope,
)
from ._authority.c2r6p1_bridge.contracts import (
    RefinerInputV1,
)
from ._authority.core import (
    FrozenTRM0ProposalSource,
    TRM0GuidedRefiner,
    replay_candidate_path,
)


@dataclass(frozen=True)
class StructuralGuidanceAdmissionConfig:
    enabled: bool = False

    checkpoint_path: str = ""

    seed: int = 0
    budget: int = 128
    restarts: int = 8
    plateau: int = 25

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError(
                "enabled must be bool"
            )

        if not isinstance(self.checkpoint_path, str):
            raise TypeError(
                "checkpoint_path must be str"
            )

        if self.budget < 0:
            raise ValueError(
                "budget cannot be negative"
            )

        if self.restarts < 1:
            raise ValueError(
                "restarts must be >= 1"
            )

        if self.plateau < 0:
            raise ValueError(
                "plateau cannot be negative"
            )


@dataclass(frozen=True)
class StructuralGuidanceAdmissionResult:
    admitted: bool
    fallback_required: bool

    final_input: RefinerInputV1 | None

    envelope: object | None

    receipt: StructuralGuidanceReceiptV1


def _projection_digest(
    projection: object,
) -> str:
    return str(
        getattr(
            projection,
            "projection_digest",
            "",
        )
    )


def _projection_fingerprint(
    projection: object,
) -> str:
    return str(
        getattr(
            projection,
            "structural_input_fingerprint",
            "",
        )
    )


def _stats_value(
    result: object,
    name: str,
    default: int,
) -> int:
    direct = getattr(
        result,
        name,
        None,
    )

    if direct is not None:
        return int(direct)

    stats = getattr(
        result,
        "stats",
        None,
    )

    if stats is not None:
        value = getattr(
            stats,
            name,
            None,
        )

        if value is not None:
            return int(value)

    return int(default)


def _chosen_path(
    result: object,
):
    path = getattr(
        result,
        "chosen_path",
        None,
    )

    if path is None:
        raise RuntimeError(
            "guided refiner returned no replay path"
        )

    return tuple(path)


def _final_input(
    result: object,
) -> RefinerInputV1:
    value = getattr(
        result,
        "final_input",
        None,
    )

    if not isinstance(
        value,
        RefinerInputV1,
    ):
        raise RuntimeError(
            "guided refiner returned no typed final input"
        )

    return value


def _receipt(
    *,
    outcome: str,
    enabled: bool,
    projection_digest: str,
    envelope_digest: str,
    input_fp: str,
    output_fp: str,
    checkpoint_sha256: str,
    config: StructuralGuidanceAdmissionConfig,
    iterations: int = 0,
    best_cost: int = -1,
    applied_moves: int = 0,
    error_code: str = "",
) -> StructuralGuidanceReceiptV1:
    return StructuralGuidanceReceiptV1(
        schema=RECEIPT_SCHEMA,
        outcome=outcome,
        enabled=enabled,
        projection_digest=projection_digest,
        envelope_digest=envelope_digest,
        input_refinement_fingerprint=input_fp,
        output_refinement_fingerprint=output_fp,
        checkpoint_sha256=checkpoint_sha256,
        seed=config.seed,
        budget=config.budget,
        restarts=config.restarts,
        plateau=config.plateau,
        iterations=iterations,
        best_cost=best_cost,
        applied_moves=applied_moves,
        authority_granted=0,
        error_code=error_code,
    )


def admit_projection(
    projection: ProjectionResultV1,
    config: StructuralGuidanceAdmissionConfig = (
        StructuralGuidanceAdmissionConfig()
    ),
) -> StructuralGuidanceAdmissionResult:
    projection_digest = _projection_digest(
        projection
    )

    projection_fp = _projection_fingerprint(
        projection
    )

    if not config.enabled:
        receipt = _receipt(
            outcome="BYPASSED",
            enabled=False,
            projection_digest=projection_digest,
            envelope_digest="",
            input_fp=projection_fp,
            output_fp="",
            checkpoint_sha256="",
            config=config,
        )

        return StructuralGuidanceAdmissionResult(
            admitted=False,
            fallback_required=False,
            final_input=None,
            envelope=None,
            receipt=receipt,
        )

    try:
        if not isinstance(
            projection,
            ProjectionResultV1,
        ):
            raise TypeError(
                "projection must be production ProjectionResultV1"
            )

        if not config.checkpoint_path:
            raise ValueError(
                "enabled structural guidance requires checkpoint_path"
            )

        ri = adapt_projection_to_refiner_input(
            projection
        )

        envelope = build_envelope(
            projection,
            ri,
        )

        source = (
            FrozenTRM0ProposalSource
            .from_checkpoint(
                Path(config.checkpoint_path),
                expected_sha256=(
                    FROZEN_TRM0_CHECKPOINT_SHA256
                ),
            )
        )

        refiner = TRM0GuidedRefiner(
            proposal_source=source,
            seed=config.seed,
            budget=config.budget,
            restarts=config.restarts,
            plateau=config.plateau,
        )

        result = refiner.refine(ri)

        chosen_path = _chosen_path(
            result
        )

        declared_final = _final_input(
            result
        )

        replayed = replay_candidate_path(
            ri,
            chosen_path,
        )

        if (
            replayed.refinement_state_fingerprint
            != declared_final.refinement_state_fingerprint
        ):
            raise RuntimeError(
                "runtime replay fingerprint mismatch"
            )

        if (
            replayed.grid81
            != declared_final.grid81
        ):
            raise RuntimeError(
                "runtime replay grid mismatch"
            )

        if replayed.frozen_mask != ri.frozen_mask:
            raise RuntimeError(
                "runtime guidance changed frozen mask"
            )

        if (
            replayed.writable_mask
            != ri.writable_mask
        ):
            raise RuntimeError(
                "runtime guidance changed writable mask"
            )

        if replayed.invariants != ri.invariants:
            raise RuntimeError(
                "runtime guidance changed invariants"
            )

        authority = _stats_value(
            result,
            "authority_granted",
            0,
        )

        if authority != 0:
            raise RuntimeError(
                "runtime guidance authority widened"
            )

        receipt = _receipt(
            outcome="ADMITTED",
            enabled=True,
            projection_digest=projection_digest,
            envelope_digest=str(
                getattr(
                    envelope,
                    "envelope_digest",
                    "",
                )
            ),
            input_fp=(
                ri.refinement_state_fingerprint
            ),
            output_fp=(
                replayed
                .refinement_state_fingerprint
            ),
            checkpoint_sha256=(
                source.checkpoint_sha256
            ),
            config=config,
            iterations=_stats_value(
                result,
                "iterations",
                0,
            ),
            best_cost=_stats_value(
                result,
                "best_cost",
                -1,
            ),
            applied_moves=len(
                chosen_path
            ),
        )

        return StructuralGuidanceAdmissionResult(
            admitted=True,
            fallback_required=False,
            final_input=replayed,
            envelope=envelope,
            receipt=receipt,
        )

    except Exception as exc:
        receipt = _receipt(
            outcome="FALLBACK_REQUIRED",
            enabled=True,
            projection_digest=projection_digest,
            envelope_digest="",
            input_fp=projection_fp,
            output_fp="",
            checkpoint_sha256="",
            config=config,
            error_code=type(exc).__name__,
        )

        return StructuralGuidanceAdmissionResult(
            admitted=False,
            fallback_required=True,
            final_input=None,
            envelope=None,
            receipt=receipt,
        )
