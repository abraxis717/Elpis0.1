"""Phase G+H — Structural/scope validation and validation-tier record.

Phase G: Pure deterministic validator for a proposal against its input.
Phase H: Immutable validation-tier record with explicit NOT_EVALUATED tiers.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

from elpis_fractal_spine.structural_refinement import (
    STRUCTURAL_OPCODE_DOMAIN,
)

from .contracts import P0RefinementInputV1, TRMRefinementProposal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Phase G — Structural and scope validator
# ---------------------------------------------------------------------------

ScopeValidity = Literal["PASS", "FAIL"]
TransitionKind = Literal[
    "NOOP", "SINGLE_EDIT",
    "MULTIPLE_EDITS", "LOCKED_CELL_WRITE",
    "STRUCTURAL_INVALID", "INPUT_DIGEST_MISMATCH",
]
RejectionStatus = Literal[
    "ACCEPTED_P0_REFINEMENT_VALID",
    "ACCEPTED_P0_REFINEMENT_NOOP",
    "REJECTED_P0_REFINEMENT_MULTIPLE_EDITS",
    "REJECTED_P0_REFINEMENT_LOCKED_CELL_WRITE",
    "REJECTED_P0_REFINEMENT_STRUCTURAL_INVALID",
    "REJECTED_P0_REFINEMENT_INPUT_DIGEST_MISMATCH",
]


@dataclass(frozen=True, slots=True)
class _ValidationIntermediate:
    """Internal working record before final tier record."""
    changed_cells: tuple[int, ...]
    transition_kind: TransitionKind
    scope_validity: ScopeValidity
    status: RejectionStatus


def validate_refinement_proposal(
    input_envelope: P0RefinementInputV1,
    proposal: TRMRefinementProposal,
) -> _ValidationIntermediate:
    """Pure deterministic validation of a proposal against its envelope input.

    Does NOT call the structural oracle. Does NOT decide semantic legality.
    Evaluates only:
      - input binding
      - shape validity
      - token-domain validity
      - single-edit locality
      - writable-scope validity
    """
    input_grid = input_envelope.structural_input.grid81
    input_mask = input_envelope.structural_input.writable_mask81
    proposed_grid = proposal.proposed_grid81

    # 1. Input digest binding
    if proposal.input_digest != input_envelope.envelope_digest:
        return _ValidationIntermediate(
            changed_cells=(),
            transition_kind="INPUT_DIGEST_MISMATCH",
            scope_validity="FAIL",
            status="REJECTED_P0_REFINEMENT_INPUT_DIGEST_MISMATCH",
        )

    # 2. Shape validity
    if len(proposed_grid) != 81:
        return _ValidationIntermediate(
            changed_cells=(),
            transition_kind="STRUCTURAL_INVALID",
            scope_validity="FAIL",
            status="REJECTED_P0_REFINEMENT_STRUCTURAL_INVALID",
        )

    # 3. Token-domain validity
    for i, v in enumerate(proposed_grid):
        if v not in STRUCTURAL_OPCODE_DOMAIN:
            return _ValidationIntermediate(
                changed_cells=(),
                transition_kind="STRUCTURAL_INVALID",
                scope_validity="FAIL",
                status="REJECTED_P0_REFINEMENT_STRUCTURAL_INVALID",
            )

    # 4. Compute changed cells
    changed_cells = tuple(
        i
        for i, (before, after) in enumerate(zip(input_grid, proposed_grid))
        if before != after
    )

    # 5. NOOP
    if len(changed_cells) == 0:
        return _ValidationIntermediate(
            changed_cells=(),
            transition_kind="NOOP",
            scope_validity="PASS",
            status="ACCEPTED_P0_REFINEMENT_NOOP",
        )

    # 6. Multiple edits
    if len(changed_cells) > 1:
        return _ValidationIntermediate(
            changed_cells=changed_cells,
            transition_kind="MULTIPLE_EDITS",
            scope_validity="FAIL",
            status="REJECTED_P0_REFINEMENT_MULTIPLE_EDITS",
        )

    # 7. Single edit — check scope
    changed_cell = changed_cells[0]
    if input_mask[changed_cell] != 1:
        return _ValidationIntermediate(
            changed_cells=changed_cells,
            transition_kind="LOCKED_CELL_WRITE",
            scope_validity="FAIL",
            status="REJECTED_P0_REFINEMENT_LOCKED_CELL_WRITE",
        )

    # 8. Single writable edit — valid
    return _ValidationIntermediate(
        changed_cells=changed_cells,
        transition_kind="SINGLE_EDIT",
        scope_validity="PASS",
        status="ACCEPTED_P0_REFINEMENT_VALID",
    )


# ---------------------------------------------------------------------------
# Phase H — Validation-tier record
# ---------------------------------------------------------------------------

VALIDATION_SCHEMA_VERSION = "p0.refinement.validation.v1"


@dataclass(frozen=True, slots=True)
class RefinementValidationRecordV1:
    """Immutable validation record with explicit tier separation.

    Gate 2 evaluates only scope_validity. The remaining tiers are
    explicitly NOT_EVALUATED to prevent mislabeling scope checks
    as full transition admission.
    """

    schema_version: str = VALIDATION_SCHEMA_VERSION
    envelope_digest: str = ""
    proposal_digest: str = ""
    transition_kind: str = ""
    changed_cells: tuple[int, ...] = ()
    scope_validity: str = ""
    oracle_legality: str = "NOT_EVALUATED"
    policy_admissibility: str = "NOT_EVALUATED"
    progress_verdict: str = "NOT_EVALUATED"
    status: str = ""
    validation_digest: str = ""

    def __post_init__(self) -> None:
        # Tier separation enforcement
        if self.oracle_legality != "NOT_EVALUATED":
            raise ValueError(
                f"oracle_legality must be NOT_EVALUATED, "
                f"got {self.oracle_legality!r}"
            )
        if self.policy_admissibility != "NOT_EVALUATED":
            raise ValueError(
                f"policy_admissibility must be NOT_EVALUATED, "
                f"got {self.policy_admissibility!r}"
            )
        if self.progress_verdict != "NOT_EVALUATED":
            raise ValueError(
                f"progress_verdict must be NOT_EVALUATED, "
                f"got {self.progress_verdict!r}"
            )

        # Compute validation digest
        payload = {
            "schema_version": self.schema_version,
            "envelope_digest": self.envelope_digest,
            "proposal_digest": self.proposal_digest,
            "transition_kind": self.transition_kind,
            "changed_cells": list(self.changed_cells),
            "scope_validity": self.scope_validity,
            "oracle_legality": self.oracle_legality,
            "policy_admissibility": self.policy_admissibility,
            "progress_verdict": self.progress_verdict,
            "status": self.status,
        }
        computed = _sha256_hex(_canonical_bytes(payload))
        if self.validation_digest and self.validation_digest != computed:
            raise ValueError(
                f"validation_digest mismatch: "
                f"supplied {self.validation_digest!r} != computed {computed!r}"
            )
        object.__setattr__(self, "validation_digest", computed)


def build_validation_record(
    input_envelope: P0RefinementInputV1,
    proposal: TRMRefinementProposal,
) -> RefinementValidationRecordV1:
    """Run validation and produce immutable record."""
    intermediate = validate_refinement_proposal(input_envelope, proposal)

    return RefinementValidationRecordV1(
        envelope_digest=input_envelope.envelope_digest,
        proposal_digest=proposal.digest,
        transition_kind=intermediate.transition_kind,
        changed_cells=intermediate.changed_cells,
        scope_validity=intermediate.scope_validity,
        status=intermediate.status,
    )
