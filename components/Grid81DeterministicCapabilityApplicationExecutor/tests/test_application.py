"""G5.3C Application acceptance/rejection tests."""
import pytest
import copy
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_application_executor.canonical import canonical_digest
from elpis_grid81_application_executor.application import apply_artifact
from elpis_grid81_application_executor.shadow_state import ShadowCapabilityState
from elpis_grid81_application_executor.ledger import ApplicationLedger
from elpis_grid81_application_executor.fixture import (
    create_shadow_fixture, create_shadow_artifact, mutate_and_rehash,
)
from elpis_grid81_application_executor.lifecycle import (
    APPLICATION_ACCEPTED,
    REJECTION_ARTIFACT_SCHEMA_INVALID,
    REJECTION_ARTIFACT_DIGEST_MISMATCH,
    REJECTION_LIFECYCLE_INELIGIBLE,
    REJECTION_ALREADY_APPLIED_ARTIFACT,
    REJECTION_STALE_LEDGER_HEAD,
    REJECTION_CONSUMER_IDENTITY_MISMATCH,
    REJECTION_SCOPE_MISMATCH,
    REJECTION_PURPOSE_MISMATCH,
    REJECTION_BUDGET_EXCEEDED,
    REJECTION_AUTHORITY_DOMAIN_VIOLATION,
    REJECTION_CANONICAL_WRITE_ATTEMPT,
)


@pytest.fixture
def valid_context():
    fixture = create_shadow_fixture(0, scope_size=1)
    artifact = create_shadow_artifact(fixture, 0)
    shadow = ShadowCapabilityState(
        capability_digest=fixture["capability_digest"],
        application_state="UNAPPLIED",
        consumption_count=1,
        current_lifecycle_state="CONSUMED",
        applied_artifact_digest=None,
    )
    ledger = ApplicationLedger()
    ccd = artifact["compiler_contract_digest"]
    return fixture, artifact, shadow, ledger, ccd


class TestApplicationAcceptance:
    def test_valid_application_accepted(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        receipt = apply_artifact(artifact, shadow, ledger, compiler_contract_digest=ccd)
        assert receipt["application_outcome"] == APPLICATION_ACCEPTED

    def test_accepted_receipt_has_state(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        receipt = apply_artifact(artifact, shadow, ledger, compiler_contract_digest=ccd)
        assert receipt["application_outcome"] == APPLICATION_ACCEPTED
        assert "new_shadow_state" in receipt
        assert receipt["new_shadow_state"]["application_state"] == "APPLIED"
        assert receipt["previous_state_digest"] != receipt["resulting_state_digest"]

    def test_accepted_receipt_ledger_advanced(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        before_head = ledger.head
        receipt = apply_artifact(artifact, shadow, ledger, compiler_contract_digest=ccd)
        assert ledger.head != before_head
        assert receipt["resulting_ledger_head"] == ledger.head


class TestApplicationRejection:
    def test_invalid_schema(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        mut = copy.deepcopy(artifact)
        mut["schema_version"] = "invalid"
        receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
        assert receipt["application_outcome"] == REJECTION_ARTIFACT_SCHEMA_INVALID

    def test_digest_mismatch(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        mut = copy.deepcopy(artifact)
        mut["artifact_digest"] = "0" * 64
        receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
        assert receipt["application_outcome"] == REJECTION_ARTIFACT_DIGEST_MISMATCH

    def test_lifecycle_ineligible(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        shadow_wrong = ShadowCapabilityState(
            capability_digest=artifact["source_capability_digest"],
            application_state="UNAPPLIED",
            consumption_count=0,
            current_lifecycle_state="GRANTED_UNCONSUMED",
            applied_artifact_digest=None,
        )
        receipt = apply_artifact(artifact, shadow_wrong, ledger, compiler_contract_digest=ccd)
        assert receipt["application_outcome"] == REJECTION_LIFECYCLE_INELIGIBLE

    def test_double_application(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        receipt1 = apply_artifact(artifact, shadow, ledger, compiler_contract_digest=ccd)
        assert receipt1["application_outcome"] == APPLICATION_ACCEPTED
        receipt2 = apply_artifact(artifact, shadow, ledger, compiler_contract_digest=ccd)
        assert receipt2["application_outcome"] == REJECTION_ALREADY_APPLIED_ARTIFACT

    def test_stale_ledger_head(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        receipt = apply_artifact(artifact, shadow, ledger, compiler_contract_digest=ccd,
                                  expected_ledger_head="0" * 64)
        assert receipt["application_outcome"] == REJECTION_STALE_LEDGER_HEAD

    def test_consumer_mismatch(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        mut = mutate_and_rehash(artifact, "consumer_class", "WRONG_CONSUMER")
        receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
        assert receipt["application_outcome"] == REJECTION_CONSUMER_IDENTITY_MISMATCH

    def test_scope_mismatch(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        mut = mutate_and_rehash(artifact, "proposal_bindings", [])
        receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
        assert receipt["application_outcome"] == REJECTION_SCOPE_MISMATCH

    def test_purpose_mismatch(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        mut = mutate_and_rehash(artifact, "materialization_class", "WRONG_PURPOSE")
        receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
        assert receipt["application_outcome"] == REJECTION_PURPOSE_MISMATCH

    def test_budget_exceeded(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        shadow_exhausted = ShadowCapabilityState(
            capability_digest=artifact["source_capability_digest"],
            application_state="UNAPPLIED",
            consumption_count=10,
            current_lifecycle_state="CONSUMED",
            applied_artifact_digest=None,
        )
        receipt = apply_artifact(artifact, shadow_exhausted, ledger,
                                  compiler_contract_digest=ccd, budget_limit=10)
        assert receipt["application_outcome"] == REJECTION_BUDGET_EXCEEDED

    def test_forbidden_field(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        mut = mutate_and_rehash(artifact, "winner", "forbidden")
        receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
        assert receipt["application_outcome"] == REJECTION_AUTHORITY_DOMAIN_VIOLATION

    def test_canonical_write(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        mut = mutate_and_rehash(artifact, "canonical_path", "/bad")
        receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
        assert receipt["application_outcome"] == REJECTION_CANONICAL_WRITE_ATTEMPT
