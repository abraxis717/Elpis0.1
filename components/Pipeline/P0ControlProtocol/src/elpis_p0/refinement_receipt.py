"""Phase I — Immutable refinement invocation receipt.

Binds all identity fields into a single receipt digest. Does not contain
wall-clock time, raw logits, chain-of-thought, mutable references, or
unbounded rationale.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .contracts import (
    P0RefinementInputV1,
    TRMRefinementProposal,
)
from .refinement_scope import RefinementScopeDecisionV1
from .refinement_validation import RefinementValidationRecordV1


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
# Receipt
# ---------------------------------------------------------------------------

RECEIPT_SCHEMA_VERSION = "p0.refinement.receipt.v1"


@dataclass(frozen=True, slots=True)
class RefinementInvocationReceiptV1:
    """Immutable receipt for a refinement invocation.

    Binds: request, tick, snapshot, projection, scope, input,
    proposal, validation, proposer identity, and terminal status.
    """

    schema_version: str = RECEIPT_SCHEMA_VERSION
    request_id: str = ""
    logical_tick: int = -1
    snapshot_digest: str = ""
    projection_digest: str = ""
    scope_decision_digest: str = ""
    grid_digest: str = ""
    mask_digest: str = ""
    structural_input_digest: str = ""
    envelope_digest: str = ""
    proposer_id: str = ""
    proposer_version: str = ""
    proposal_digest: str = ""
    validation_digest: str = ""
    terminal_status: str = ""
    receipt_digest: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != RECEIPT_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {RECEIPT_SCHEMA_VERSION!r}, "
                f"got {self.schema_version!r}"
            )

        # Bind all fields
        payload = {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "logical_tick": self.logical_tick,
            "snapshot_digest": self.snapshot_digest,
            "projection_digest": self.projection_digest,
            "scope_decision_digest": self.scope_decision_digest,
            "grid_digest": self.grid_digest,
            "mask_digest": self.mask_digest,
            "structural_input_digest": self.structural_input_digest,
            "envelope_digest": self.envelope_digest,
            "proposer_id": self.proposer_id,
            "proposer_version": self.proposer_version,
            "proposal_digest": self.proposal_digest,
            "validation_digest": self.validation_digest,
            "terminal_status": self.terminal_status,
        }
        computed = _sha256_hex(_canonical_bytes(payload))
        if self.receipt_digest and self.receipt_digest != computed:
            raise ValueError(
                f"receipt_digest mismatch: "
                f"supplied {self.receipt_digest!r} != computed {computed!r}"
            )
        object.__setattr__(self, "receipt_digest", computed)


def build_receipt(
    *,
    request_id: str,
    logical_tick: int,
    snapshot_digest: str,
    projection_digest: str,
    scope_decision: RefinementScopeDecisionV1,
    input_envelope: P0RefinementInputV1,
    proposer_id: str,
    proposer_version: str,
    proposal: TRMRefinementProposal,
    validation: RefinementValidationRecordV1,
) -> RefinementInvocationReceiptV1:
    """Build immutable receipt from all identity components."""
    return RefinementInvocationReceiptV1(
        request_id=request_id,
        logical_tick=logical_tick,
        snapshot_digest=snapshot_digest,
        projection_digest=projection_digest,
        scope_decision_digest=scope_decision.decision_digest,
        grid_digest=input_envelope.structural_input.grid_digest,
        mask_digest=input_envelope.structural_input.mask_digest,
        structural_input_digest=(
            input_envelope.structural_input.combined_digest
        ),
        envelope_digest=input_envelope.envelope_digest,
        proposer_id=proposer_id,
        proposer_version=proposer_version,
        proposal_digest=proposal.digest,
        validation_digest=validation.validation_digest,
        terminal_status=validation.status,
    )
