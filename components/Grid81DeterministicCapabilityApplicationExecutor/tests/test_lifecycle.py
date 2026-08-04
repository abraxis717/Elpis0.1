"""G5.3C Lifecycle transition tests."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_application_executor.lifecycle import (
    validate_lifecycle_transition, validate_artifact_lifecycle,
    APPLICATION_ACCEPTED,
    REJECTION_LIFECYCLE_INELIGIBLE,
    REJECTION_ARTIFACT_LIFECYCLE_NOT_UNAPPLIED,
    REJECTION_ALREADY_APPLIED_ARTIFACT,
    VALID_LIFECYCLE_STATES,
    VALID_APPLICATION_STATES,
)


class TestLifecycleTransition:
    def test_consumed_is_eligible(self):
        outcome, reasons = validate_lifecycle_transition(
            {"current_lifecycle_state": "CONSUMED"}
        )
        assert outcome == APPLICATION_ACCEPTED

    def test_granted_unconsumed_ineligible(self):
        outcome, reasons = validate_lifecycle_transition(
            {"current_lifecycle_state": "GRANTED_UNCONSUMED"}
        )
        assert outcome == REJECTION_LIFECYCLE_INELIGIBLE

    def test_applied_ineligible(self):
        outcome, reasons = validate_lifecycle_transition(
            {"current_lifecycle_state": "APPLIED"}
        )
        assert outcome == REJECTION_LIFECYCLE_INELIGIBLE

    def test_revoked_ineligible(self):
        outcome, reasons = validate_lifecycle_transition(
            {"current_lifecycle_state": "REVOKED"}
        )
        assert outcome == REJECTION_LIFECYCLE_INELIGIBLE

    def test_expired_ineligible(self):
        outcome, reasons = validate_lifecycle_transition(
            {"current_lifecycle_state": "EXPIRED"}
        )
        assert outcome == REJECTION_LIFECYCLE_INELIGIBLE


class TestArtifactLifecycle:
    def test_unapplied_accepted(self):
        outcome, reasons = validate_artifact_lifecycle(
            {"application_state": "UNAPPLIED"}
        )
        assert outcome == APPLICATION_ACCEPTED

    def test_applied_rejected(self):
        outcome, reasons = validate_artifact_lifecycle(
            {"application_state": "APPLIED"}
        )
        assert outcome == REJECTION_ALREADY_APPLIED_ARTIFACT

    def test_unknown_state_rejected(self):
        outcome, reasons = validate_artifact_lifecycle(
            {"application_state": "UNKNOWN"}
        )
        assert outcome == REJECTION_ARTIFACT_LIFECYCLE_NOT_UNAPPLIED

    def test_missing_state_rejected(self):
        outcome, reasons = validate_artifact_lifecycle({})
        assert outcome == REJECTION_ARTIFACT_LIFECYCLE_NOT_UNAPPLIED

    def test_valid_lifecycle_states_non_empty(self):
        assert len(VALID_LIFECYCLE_STATES) >= 4

    def test_valid_application_states_non_empty(self):
        assert len(VALID_APPLICATION_STATES) >= 2
