"""G5.3C Atomicity tests — rejected applications must leave state byte-identical."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_application_executor.application import apply_artifact
from elpis_grid81_application_executor.shadow_state import ShadowCapabilityState
from elpis_grid81_application_executor.ledger import ApplicationLedger
from elpis_grid81_application_executor.fixture import (
    create_shadow_fixture, create_shadow_artifact, mutate_and_rehash,
)
from elpis_grid81_application_executor.lifecycle import APPLICATION_ACCEPTED


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


class TestAtomicity:
    def test_rejection_state_unchanged(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        before_state = shadow.state_digest
        before_ledger = ledger.head

        mut = mutate_and_rehash(artifact, "consumer_class", "WRONG")
        receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)

        assert receipt["previous_state_digest"] == before_state
        assert receipt["resulting_state_digest"] == before_state
        assert receipt["previous_ledger_head"] == before_ledger
        assert receipt["resulting_ledger_head"] == before_ledger
        assert ledger.head == before_ledger

    def test_rejection_ledger_unchanged(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        before_ledger = ledger.head

        mut = mutate_and_rehash(artifact, "winner", "forbidden")
        receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)

        assert ledger.head == before_ledger
        assert receipt["previous_ledger_head"] == before_ledger
        assert receipt["resulting_ledger_head"] == before_ledger

    def test_acceptance_updates_ledger(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        before_ledger = ledger.head
        before_state = shadow.state_digest

        receipt = apply_artifact(artifact, shadow, ledger, compiler_contract_digest=ccd)

        assert receipt["application_outcome"] == APPLICATION_ACCEPTED
        assert receipt["previous_ledger_head"] == before_ledger
        assert receipt["resulting_ledger_head"] != before_ledger
        assert ledger.head == receipt["resulting_ledger_head"]

    def test_rejection_shadow_state_frozen(self, valid_context):
        _, artifact, shadow, ledger, ccd = valid_context
        before_state_digest = shadow.state_digest

        mut = mutate_and_rehash(artifact, "materialization_class", "INVALID")
        receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)

        # Shadow state object is frozen — its digest hasn't changed
        assert shadow.state_digest == before_state_digest
        assert receipt["resulting_state_digest"] == before_state_digest
