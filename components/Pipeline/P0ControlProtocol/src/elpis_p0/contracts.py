from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any

from elpis_fractal_spine.structural_refinement import (
    StructuralRefinementInputV1,
    StructuralRefinementError,
)


# ---------------------------------------------------------------------------
# Canonical helpers (P0-local digest utilities)
# ---------------------------------------------------------------------------

def _p0_canonical_bytes(obj: Any) -> bytes:
    """Minimal canonical JSON bytes: sorted keys, compact separators."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _p0_sha256_hex(data: bytes) -> str:
    """Lowercase SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


class BasisToken(IntEnum):
    """P0 structural instruction vocabulary."""

    VOID = 0
    INPUT = 1
    TRANSFORM = 2
    OUTPUT = 3
    MEMORY = 4
    CONSTRAINT = 5
    EXPANSION = 6
    ROUTE = 7
    INTERFACE = 8
    RESOLUTION = 9


class BudgetAxis(str, Enum):
    PROJECTION = "projection"
    REFINEMENT = "refinement"
    ROUTING = "routing"
    DECODING = "decoding"
    VALIDATION = "validation"


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str
    prompt: str
    domain: str = "python"
    entrypoint: str = "solution"
    parameters: tuple[str, ...] = ()
    decoder_hints: tuple[tuple[str, str], ...] = ()
    allowed_experts: tuple[str, ...] = (
        "python.codegen",
        "python.ast",
        "python.tests",
        "python.typing",
    )
    max_tokens: int = 512
    budget_units: int = 32

    def hint(self, key: str, default: str = "") -> str:
        return dict(self.decoder_hints).get(key, default)


@dataclass(frozen=True, slots=True)
class StructuralProjection:
    grid81: tuple[int, ...]
    semantic_rows: tuple[str, ...]
    features: tuple[tuple[str, float], ...]
    digest: str

    def validate(self) -> None:
        if len(self.grid81) != 81:
            raise ValueError(
                "StructuralProjection.grid81 must contain 81 cells"
            )

        if len(self.semantic_rows) != 9:
            raise ValueError(
                "StructuralProjection requires nine semantic rows"
            )

        if any(value < 0 or value > 9 for value in self.grid81):
            raise ValueError(
                "StructuralProjection cells must be in [0, 9]"
            )


@dataclass(frozen=True, slots=True)
class TRMRefinementProposal:
    input_digest: str
    proposed_grid81: tuple[int, ...]
    residual81: tuple[float, ...]
    halt_score: float
    expansion_cells: tuple[int, ...]
    rationale: tuple[str, ...]
    digest: str

    def validate(self) -> None:
        if len(self.proposed_grid81) != 81:
            raise ValueError(
                "TRM proposal must contain 81 proposed cells"
            )

        if len(self.residual81) != 81:
            raise ValueError(
                "TRM proposal must contain 81 residuals"
            )

        if not 0.0 <= self.halt_score <= 1.0:
            raise ValueError(
                "halt_score must be in [0, 1]"
            )

        if any(
            index < 0 or index >= 81
            for index in self.expansion_cells
        ):
            raise ValueError(
                "expansion cell index outside Grid81"
            )


@dataclass(frozen=True, slots=True)
class ExpertCandidate:
    expert_id: str
    score: float
    reason: str


@dataclass(frozen=True, slots=True)
class ExpertActivationProposal:
    candidates: tuple[ExpertCandidate, ...]
    digest: str


@dataclass(frozen=True, slots=True)
class DecoderControlPlan:
    backend: str
    language: str
    temperature: float
    max_tokens: int
    selected_experts: tuple[str, ...]
    function_name: str
    parameters: tuple[str, ...]
    body_lines: tuple[str, ...]
    structural_digest: str
    plan_digest: str


@dataclass(frozen=True, slots=True)
class ArtifactCandidate:
    language: str
    source: str
    digest: str


@dataclass(frozen=True, slots=True)
class ValidatorEvidence:
    validator_id: str
    passed: bool
    code: str
    message: str
    details: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class AccountingEvent:
    sequence: int
    axis: BudgetAxis
    units: int
    reason: str
    remaining: int
    shadow: bool = True


@dataclass(frozen=True, slots=True)
class TraceEvent:
    sequence: int
    stage: str
    action: str
    digest: str
    details: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class P0Result:
    request_id: str
    accepted: bool

    projection: StructuralProjection
    trm_proposal: TRMRefinementProposal
    expert_proposal: ExpertActivationProposal
    decoder_plan: DecoderControlPlan
    artifact: ArtifactCandidate

    evidence: tuple[ValidatorEvidence, ...]
    accounting: tuple[AccountingEvent, ...]
    trace: tuple[TraceEvent, ...]

    proposed_expansions: tuple[int, ...]
    expansion_executed: bool
    executed_experts: tuple[str, ...]
    governance_invoked: bool

    result_digest: str


# ---------------------------------------------------------------------------
# P0.3 — Runtime refinement envelope
# ---------------------------------------------------------------------------

P0_REFINEMENT_SCHEMA_VERSION = "p0.refinement.input.v1"


class P0RefinementError(ValueError):
    """Raised when P0RefinementInputV1 validation fails."""

    pass


@dataclass(frozen=True, slots=True)
class P0RefinementInputV1:
    """P0 runtime envelope for structural refinement input.

    Binds a P0-specific request context around the lower-level
    StructuralRefinementInputV1 contract.  The envelope digest binds
    all fields to prevent tampering.

    Dependency direction: elpis_p0 imports elpis_fractal_spine.
    The lower-level package must not import elpis_p0.
    """

    schema_version: str = P0_REFINEMENT_SCHEMA_VERSION
    request_id: str = ""
    logical_tick: int = -1
    snapshot_digest: str = ""
    structural_input: StructuralRefinementInputV1 = None  # type: ignore[assignment]
    envelope_digest: str = ""

    def __post_init__(self) -> None:
        # Validate schema version
        if self.schema_version != P0_REFINEMENT_SCHEMA_VERSION:
            raise P0RefinementError(
                f"schema_version must be {P0_REFINEMENT_SCHEMA_VERSION!r}, "
                f"got {self.schema_version!r}"
            )

        # Validate request_id
        if not self.request_id:
            raise P0RefinementError("request_id must be non-empty")

        # Validate logical_tick
        if self.logical_tick < 0:
            raise P0RefinementError(
                f"logical_tick must be non-negative, got {self.logical_tick}"
            )

        # Validate snapshot_digest format
        if len(self.snapshot_digest) != 64:
            raise P0RefinementError(
                f"snapshot_digest must be 64 hex chars, "
                f"got {len(self.snapshot_digest)}"
            )
        try:
            int(self.snapshot_digest, 16)
        except ValueError:
            raise P0RefinementError("snapshot_digest contains non-hex characters")

        # Validate structural_input
        if self.structural_input is None:
            raise P0RefinementError("structural_input must not be None")
        if not isinstance(self.structural_input, StructuralRefinementInputV1):
            raise P0RefinementError(
                f"structural_input must be StructuralRefinementInputV1, "
                f"got {type(self.structural_input).__name__}"
            )

        # Compute envelope digest
        payload = {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "logical_tick": self.logical_tick,
            "snapshot_digest": self.snapshot_digest,
            "structural_combined_digest": self.structural_input.combined_digest,
        }
        envelope = _p0_sha256_hex(_p0_canonical_bytes(payload))
        if self.envelope_digest and self.envelope_digest != envelope:
            raise P0RefinementError(
                f"envelope_digest mismatch: "
                f"supplied {self.envelope_digest!r} != computed {envelope!r}"
            )
        object.__setattr__(self, "envelope_digest", envelope)


# ---------------------------------------------------------------------------
# Conversion: StructuralProjection -> P0RefinementInputV1
# ---------------------------------------------------------------------------


def build_refinement_input(
    projection: StructuralProjection,
    *,
    writable_mask81: tuple[int, ...],
    request_id: str,
    logical_tick: int,
    snapshot_digest: str,
) -> P0RefinementInputV1:
    """Convert a StructuralProjection to P0RefinementInputV1.

    Requires an explicit writable_mask81 — the mask must NOT be read
    from features, semantic_rows, decoder_hints, metadata, or rationale.

    Args:
        projection: Existing StructuralProjection (unchanged).
        writable_mask81: Explicit binary mask of length 81.
        request_id: P0 request identifier.
        logical_tick: Non-negative logical tick counter.
        snapshot_digest: SHA-256 hex digest of the snapshot state.

    Returns:
        P0RefinementInputV1 with computed envelope digest.

    Raises:
        StructuralRefinementError: If mask or grid validation fails.
        P0RefinementError: If envelope validation fails.
    """
    projection.validate()

    structural = StructuralRefinementInputV1(
        grid81=projection.grid81,
        writable_mask81=writable_mask81,
    )

    return P0RefinementInputV1(
        request_id=request_id,
        logical_tick=logical_tick,
        snapshot_digest=snapshot_digest,
        structural_input=structural,
    )
