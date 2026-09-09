from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import AdmissionIntegrityViolation, AdmissionUnavailable
from .inactive_receipt import InactiveGuidanceReceiptV2, UnavailableDetail

from .authority import (
    FROZEN_TRM0_CHECKPOINT_SHA256,
)
from .receipt import (
    SCHEMA as RECEIPT_SCHEMA,
    StructuralGuidanceReceiptV1,
)
from ._authority.c2r6p0.contracts import (
    ProjectionResultV1,
    ProjectionBudgetExhaustedV2,
    ProjectionSearchBudgetExhausted,
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
    GuidedSearchResult as RefinerResult,
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

    receipt: StructuralGuidanceReceiptV1 | InactiveGuidanceReceiptV2


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
    iterations: int,
    best_cost: int,
    applied_moves: int,
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
    if isinstance(projection, ProjectionBudgetExhaustedV2):
        raise ProjectionSearchBudgetExhausted(projection)
    if not isinstance(projection, ProjectionResultV1):
        raise TypeError("projection must be production ProjectionResultV1")
    projection_digest = projection.projection_digest
    projection_fp = projection.structural_input_fingerprint

    if not config.enabled:
        return StructuralGuidanceAdmissionResult(
            admitted=False, fallback_required=False,
            final_input=None, envelope=None,
            receipt=InactiveGuidanceReceiptV2(
                outcome="BYPASSED", projection_digest=projection_digest,
                input_refinement_fingerprint=projection_fp, errors=(),
            ),
        )

    if not config.checkpoint_path:
        raise AdmissionIntegrityViolation("enabled guidance requires a pinned checkpoint")

    try:
        ri = adapt_projection_to_refiner_input(
            projection
        )

        envelope = build_envelope(
            projection,
            ri,
        )

        try:
            source = FrozenTRM0ProposalSource.from_checkpoint(
                Path(config.checkpoint_path),
                expected_sha256=FROZEN_TRM0_CHECKPOINT_SHA256,
            )
        except ModuleNotFoundError as exc:
            if exc.name != "torch":
                raise
            raise AdmissionUnavailable("TORCH_UNAVAILABLE") from exc

        refiner = TRM0GuidedRefiner(
            proposal_source=source,
            seed=config.seed,
            budget=config.budget,
            restarts=config.restarts,
            plateau=config.plateau,
        )

        from copy import deepcopy
        original = deepcopy(ri)
        result = refiner.refine(ri)
        if ri != original:
            raise AdmissionIntegrityViolation("refiner mutated its input")

        if not isinstance(result, RefinerResult):
            raise TypeError("guided refiner must return RefinerResult")
        if not isinstance(result.final_input, RefinerInputV1):
            raise TypeError("refiner final input must be RefinerInputV1")
        if type(result.authority_granted) is not int:
            raise TypeError("refiner authority_granted must be int")
        if result.authority_granted != 0:
            raise AdmissionIntegrityViolation("runtime guidance authority widened")
        if type(result.iterations) is not int or type(result.best_cost) is not int:
            raise TypeError("refiner measurements must be required integer fields")
        chosen_path = tuple(result.chosen_path)
        declared_final = result.final_input
        for field in ("frozen_mask", "writable_mask", "invariants"):
            if getattr(declared_final, field) != getattr(ri, field):
                raise AdmissionIntegrityViolation("runtime guidance changed " + field)

        replayed = replay_candidate_path(
            ri,
            chosen_path,
        )

        if (
            replayed.refinement_state_fingerprint
            != declared_final.refinement_state_fingerprint
        ):
            raise AdmissionIntegrityViolation(
                "runtime replay fingerprint mismatch"
            )

        if (
            replayed.grid81
            != declared_final.grid81
        ):
            raise AdmissionIntegrityViolation(
                "runtime replay grid mismatch"
            )

        if replayed.frozen_mask != ri.frozen_mask:
            raise AdmissionIntegrityViolation(
                "runtime guidance changed frozen mask"
            )

        if (
            replayed.writable_mask
            != ri.writable_mask
        ):
            raise AdmissionIntegrityViolation(
                "runtime guidance changed writable mask"
            )

        if replayed.invariants != ri.invariants:
            raise AdmissionIntegrityViolation(
                "runtime guidance changed invariants"
            )

        receipt = _receipt(
            outcome="ADMITTED",
            enabled=True,
            projection_digest=projection_digest,
            envelope_digest=envelope.envelope_digest,
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
            iterations=result.iterations,
            best_cost=result.best_cost,
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

    except AdmissionUnavailable as exc:
        return StructuralGuidanceAdmissionResult(
            admitted=False, fallback_required=True,
            final_input=None, envelope=None,
            receipt=InactiveGuidanceReceiptV2(
                outcome="FALLBACK_REQUIRED", projection_digest=projection_digest,
                input_refinement_fingerprint=projection_fp,
                errors=(UnavailableDetail.from_error(exc),),
            ),
        )
