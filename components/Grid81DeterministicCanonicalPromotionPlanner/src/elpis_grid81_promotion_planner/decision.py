"""Promotion decision logic."""

from .canonical import (
    GateResult,
    PromotionDecision,
    SourceChain,
)
from .gates import first_failure


DECISION_READY = "READY_FOR_CANONICAL_REVIEW"
DECISION_NOT_READY = "NOT_READY_FOR_CANONICAL_REVIEW"


def make_decision(gate_results: list, chain: SourceChain) -> PromotionDecision:
    """Produce advisory promotion decision from gate results and source chain."""
    failure = first_failure(gate_results)
    decision = DECISION_READY if failure is None else DECISION_NOT_READY

    gate_vector = tuple(r.digest for r in gate_results)

    preconditions = (
        "canonical_ledger_head_verified",
        "capability_granted_and_unconsumed",
        "artifact_canonically_unapplied",
        "transaction_identifier_reserved",
        "post_commit_state_verified",
    )

    return PromotionDecision(
        decision=decision,
        gate_vector=gate_vector,
        source_chain_digest=chain.chain_digest,
        expected_canonical_preconditions=preconditions,
    )
