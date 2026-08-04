from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .identity import require_hex


class GovernanceContractError(RuntimeError):
    pass


class DecisionKind(str, Enum):
    EMIT = "emit"
    REPAIR = "repair"
    REPROJECT = "reproject"
    ESCALATE = "escalate"
    ABSTAIN = "abstain"
    ABORT = "abort"
    COMMIT_MEMORY_CANDIDATE = "commit_memory_candidate"


AUTHORITY_REQUIRED = frozenset({
    DecisionKind.EMIT,
    DecisionKind.COMMIT_MEMORY_CANDIDATE,
})


@dataclass(frozen=True, slots=True)
class AuthorityReceipt:
    """
    Opaque evidence that a capability issuer consumed authority.

    This value is not itself a capability and cannot be reused to authorize a
    second transition. Verification belongs to the future affine logic layer.
    """

    issuer_id: str
    request_id: str
    scope: str
    nonce: str
    sequence: int
    signature: str

    def __post_init__(self) -> None:
        if not all((
            self.issuer_id,
            self.request_id,
            self.scope,
            self.nonce,
        )):
            raise ValueError("authority receipt fields must not be empty")
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("authority receipt sequence must be positive")
        require_hex(
            self.signature,
            field_name="authority receipt signature",
            exact_length=64,
        )


@dataclass(frozen=True, slots=True)
class GovernanceDecision:
    decision: DecisionKind
    request_id: str
    evidence_refs: tuple[str, ...]
    policy_version: str
    reason_codes: tuple[str, ...]
    authority_receipt: AuthorityReceipt | None = None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request_id is required")
        if not self.policy_version:
            raise ValueError("policy_version is required")
        if not self.reason_codes:
            raise ValueError("at least one reason code is required")


def validate_governance_decision(
    decision: GovernanceDecision,
) -> None:
    if decision.decision in AUTHORITY_REQUIRED:
        receipt = decision.authority_receipt
        if receipt is None:
            raise GovernanceContractError(
                f"{decision.decision.value} requires consumed authority evidence"
            )
        if receipt.request_id != decision.request_id:
            raise GovernanceContractError(
                "authority receipt belongs to another request"
            )
        expected_scope = (
            "emit"
            if decision.decision is DecisionKind.EMIT
            else "commit_memory_candidate"
        )
        if receipt.scope != expected_scope:
            raise GovernanceContractError(
                f"authority scope must be {expected_scope!r}"
            )
        if not decision.evidence_refs:
            raise GovernanceContractError(
                "authority-bearing decisions require evidence references"
            )
