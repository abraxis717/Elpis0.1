"""Phase J — Proposal-only result contract.

Bundles the complete refinement invocation result. Does not expose
apply(), commit(), or automatic mutation methods.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import P0RefinementInputV1, TRMRefinementProposal
from .refinement_receipt import RefinementInvocationReceiptV1
from .refinement_scope import RefinementScopeDecisionV1
from .refinement_validation import RefinementValidationRecordV1


@dataclass(frozen=True, slots=True)
class RefinementControllerResultV1:
    """Proposal-only result for a refinement invocation.

    Contains the full invocation chain: input envelope, scope decision,
    proposal, validation, and receipt.

    A failed proposal is retained as evidence but its validation status
    prevents downstream interpretation as accepted state.

    This result does NOT have apply(), commit(), or mutation methods.
    """

    input_envelope: P0RefinementInputV1
    scope_decision: RefinementScopeDecisionV1
    proposal: TRMRefinementProposal
    validation: RefinementValidationRecordV1
    receipt: RefinementInvocationReceiptV1
