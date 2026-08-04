"""Non-self-executing canonical promotion plan."""

from .canonical import (
    CanonicalPromotionPlan,
    PlanIntention,
    PromotionDecision,
    SourceChain,
)
from .decision import DECISION_READY


INTENTIONS = [
    PlanIntention(
        intention_type="VERIFY_CANONICAL_LEDGER_HEAD",
        description="Verify the expected canonical ledger head matches the state produced by G5.3C shadow applications.",
        parameter_digest="ledger_head_verification",
    ),
    PlanIntention(
        intention_type="VERIFY_CAPABILITY_GRANTED_UNCONSUMED",
        description="Verify the capability remains granted and canonically unconsumed before any canonical application.",
        parameter_digest="capability_state_verification",
    ),
    PlanIntention(
        intention_type="VERIFY_ARTIFACT_CANONICALLY_UNAPPLIED",
        description="Verify structural-influence artifacts remain canonically unapplied.",
        parameter_digest="artifact_state_verification",
    ),
    PlanIntention(
        intention_type="RESERVE_TRANSACTION_IDENTIFIER",
        description="Reserve a unique transaction identifier for the future canonical application.",
        parameter_digest="transaction_reservation",
    ),
    PlanIntention(
        intention_type="PERFORM_CANONICAL_APPLICATION",
        description="Execute the canonical application of shadow-qualified capability artifacts under canonical authority.",
        precondition="all_preconditions_verified",
        parameter_digest="canonical_application_execution",
    ),
    PlanIntention(
        intention_type="APPEND_CANONICAL_RECEIPT",
        description="Append a canonical application receipt to the canonical ledger.",
        precondition="canonical_application_completed",
        parameter_digest="canonical_receipt_append",
    ),
    PlanIntention(
        intention_type="VERIFY_POST_COMMIT_STATE",
        description="Verify post-commit canonical state matches expected transition.",
        precondition="canonical_receipt_appended",
        parameter_digest="post_commit_verification",
    ),
]


def render_plan(decision: PromotionDecision, chain: SourceChain) -> CanonicalPromotionPlan | None:
    """Render a non-executable promotion plan. Only when decision is READY."""
    if decision.decision != DECISION_READY:
        return None

    intention_digests = tuple(i.intention_type for i in INTENTIONS)

    return CanonicalPromotionPlan(
        intentions=intention_digests,
        decision_digest=decision.digest,
        source_chain_digest=chain.chain_digest,
        executable=False,
        self_applying=False,
        authoritative=False,
        canonical_write_permitted=False,
    )


def get_intentions() -> list:
    """Return the list of typed intentions for reporting."""
    return INTENTIONS
