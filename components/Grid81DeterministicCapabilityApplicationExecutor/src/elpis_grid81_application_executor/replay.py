"""G5.3C Replay semantics and idempotence verification.

Replay rules:
- Applying same artifact twice: second application is rejected (ALREADY_APPLIED_ARTIFACT)
- Replaying accepted application: returns exact prior receipt or deterministic replay rejection
- Replaying rejected application: cannot mutate state
- Two artifacts competing for same capability: only first commits
"""
import copy
from .application import apply_artifact
from .shadow_state import ShadowCapabilityState
from .ledger import ApplicationLedger
from .canonical import canonical_json
from .lifecycle import (
    APPLICATION_ACCEPTED,
    REJECTION_ALREADY_APPLIED_ARTIFACT,
    REJECTION_STALE_LEDGER_HEAD,
)


def replay_application(
    artifact: dict,
    shadow_state: ShadowCapabilityState,
    ledger: ApplicationLedger,
    *,
    compiler_contract_digest: str = "",
) -> dict:
    """Replay an application attempt.

    Returns application receipt. If already applied, returns rejection.
    """
    return apply_artifact(
        artifact,
        shadow_state,
        ledger,
        compiler_contract_digest=compiler_contract_digest,
    )


def verify_double_application_rejected(
    artifact: dict,
    shadow_state: ShadowCapabilityState,
    ledger: ApplicationLedger,
    *,
    compiler_contract_digest: str = "",
) -> tuple[bool, dict, dict]:
    """Verify that applying the same artifact twice rejects the second.

    Returns (passed, first_receipt, second_receipt).
    """
    # First application
    receipt1 = apply_artifact(
        artifact, shadow_state, ledger,
        compiler_contract_digest=compiler_contract_digest,
    )

    # Second application with same artifact
    receipt2 = apply_artifact(
        artifact, shadow_state, ledger,
        compiler_contract_digest=compiler_contract_digest,
    )

    passed = (
        receipt1["application_outcome"] == APPLICATION_ACCEPTED
        and receipt2["application_outcome"] == REJECTION_ALREADY_APPLIED_ARTIFACT
        and receipt1["previous_state_digest"] == receipt2["previous_state_digest"]
        and receipt1["resulting_state_digest"] == receipt2["previous_state_digest"]
    )

    return passed, receipt1, receipt2


def verify_rejected_does_not_mutate(
    artifact: dict,
    shadow_state: ShadowCapabilityState,
    ledger: ApplicationLedger,
    *,
    compiler_contract_digest: str = "",
) -> tuple[bool, dict, str, str]:
    """Verify that a rejected application does not mutate shadow state or ledger.

    Returns (passed, receipt, state_digest_before, state_digest_after).
    """
    before_digest = shadow_state.state_digest
    before_ledger = ledger.head

    receipt = apply_artifact(
        artifact, shadow_state, ledger,
        compiler_contract_digest=compiler_contract_digest,
    )

    after_digest = shadow_state.state_digest
    after_ledger = ledger.head

    passed = (
        receipt["application_outcome"] != APPLICATION_ACCEPTED
        and before_digest == after_digest
        and before_ledger == after_ledger
    )

    return passed, receipt, before_digest, after_digest


def verify_concurrent_artifacts(
    artifact1: dict,
    artifact2: dict,
    shadow_state: ShadowCapabilityState,
    ledger: ApplicationLedger,
    *,
    compiler_contract_digest: str = "",
) -> tuple[bool, dict, dict]:
    """Verify that two artifacts for the same capability can't both commit.

    Returns (passed, receipt1, receipt2).
    """
    receipt1 = apply_artifact(
        artifact1, shadow_state, ledger,
        compiler_contract_digest=compiler_contract_digest,
    )

    receipt2 = apply_artifact(
        artifact2, shadow_state, ledger,
        compiler_contract_digest=compiler_contract_digest,
    )

    # At most one should succeed
    accepted_count = sum(1 for r in [receipt1, receipt2]
                         if r["application_outcome"] == APPLICATION_ACCEPTED)
    passed = accepted_count <= 1

    return passed, receipt1, receipt2
