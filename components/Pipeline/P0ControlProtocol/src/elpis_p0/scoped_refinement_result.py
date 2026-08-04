"""G3.0 — Scoped refinement controller result contract.

Binds the scope decision, scope derivation record, input envelope,
proposal validation record, and Gate-2 invocation receipt into a
single frozen result with a terminal status and result digest.

Terminal states:
  PROPOSED_SCOPE_VALID
  PROPOSED_SCOPE_INVALID

Does NOT contain committed state, oracle verdict, repair output,
activation decision, or progress claim.
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
from .initial_void_scope_provider import ScopeDerivationRecordV1
from .refinement_receipt import RefinementInvocationReceiptV1
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
# ScopedRefinementControllerResultV1
# ---------------------------------------------------------------------------

SCOPED_RESULT_SCHEMA = "p0.scoped.refinement.result.v1"


@dataclass(frozen=True, slots=True)
class ScopedRefinementControllerResultV1:
    """G3 controller result binding scope derivation with proposal chain.

    Binds:
    - scope decision (from scope provider)
    - scope derivation record (provenance of mask derivation)
    - input envelope (P0 refinement input)
    - proposal (TRM refinement proposal)
    - validation record (Gate-2 validation)
    - invocation receipt (Gate-2 receipt)

    Terminal status:
    - PROPOSED_SCOPE_VALID  if validation scope_validity == PASS
    - PROPOSED_SCOPE_INVALID if validation scope_validity == FAIL

    Result digest binds all nested identity digests.
    """

    schema_version: str = SCOPED_RESULT_SCHEMA
    scope_decision: RefinementScopeDecisionV1 = None  # type: ignore[assignment]
    scope_derivation_record: ScopeDerivationRecordV1 = None  # type: ignore[assignment]
    input_envelope: P0RefinementInputV1 = None  # type: ignore[assignment]
    proposal: TRMRefinementProposal = None  # type: ignore[assignment]
    validation: RefinementValidationRecordV1 = None  # type: ignore[assignment]
    receipt: RefinementInvocationReceiptV1 = None  # type: ignore[assignment]
    terminal_status: str = ""
    result_digest: str = ""

    def __post_init__(self) -> None:
        # Validate schema
        if self.schema_version != SCOPED_RESULT_SCHEMA:
            raise ValueError(
                f"schema_version must be {SCOPED_RESULT_SCHEMA!r}, "
                f"got {self.schema_version!r}"
            )

        # Validate all nested objects present
        for field_name in (
            "scope_decision",
            "scope_derivation_record",
            "input_envelope",
            "proposal",
            "validation",
            "receipt",
        ):
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} must not be None")

        # Derive terminal status from validation
        scope_validity = self.validation.scope_validity
        if scope_validity == "PASS":
            terminal = "PROPOSED_SCOPE_VALID"
        else:
            terminal = "PROPOSED_SCOPE_INVALID"

        if self.terminal_status and self.terminal_status != terminal:
            raise ValueError(
                f"terminal_status mismatch: "
                f"supplied {self.terminal_status!r} != derived {terminal!r}"
            )
        object.__setattr__(self, "terminal_status", terminal)

        # Compute result digest binding all nested digests
        payload = {
            "schema_version": self.schema_version,
            "scope_decision_digest": self.scope_decision.decision_digest,
            "scope_derivation_digest": (
                self.scope_derivation_record.derivation_digest
            ),
            "envelope_digest": self.input_envelope.envelope_digest,
            "proposal_digest": self.proposal.digest,
            "validation_digest": self.validation.validation_digest,
            "receipt_digest": self.receipt.receipt_digest,
            "terminal_status": terminal,
        }
        computed = _sha256_hex(_canonical_bytes(payload))
        if self.result_digest and self.result_digest != computed:
            raise ValueError(
                f"result_digest mismatch: "
                f"supplied {self.result_digest!r} != computed {computed!r}"
            )
        object.__setattr__(self, "result_digest", computed)
