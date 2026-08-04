"""G5.3C Shadow state immutability tests."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_application_executor.shadow_state import (
    ShadowCapabilityState, deep_copy_state,
)
from elpis_grid81_application_executor.canonical import canonical_digest


class TestShadowState:
    def test_frozen(self):
        state = ShadowCapabilityState(
            capability_digest="a" * 64,
            application_state="UNAPPLIED",
            consumption_count=0,
            current_lifecycle_state="CONSUMED",
            applied_artifact_digest=None,
        )
        with pytest.raises(Exception):
            state.application_state = "APPLIED"

    def test_state_digest_deterministic(self):
        state1 = ShadowCapabilityState(
            capability_digest="a" * 64,
            application_state="UNAPPLIED",
            consumption_count=0,
            current_lifecycle_state="CONSUMED",
            applied_artifact_digest=None,
        )
        state2 = ShadowCapabilityState(
            capability_digest="a" * 64,
            application_state="UNAPPLIED",
            consumption_count=0,
            current_lifecycle_state="CONSUMED",
            applied_artifact_digest=None,
        )
        assert state1.state_digest == state2.state_digest

    def test_apply_artifact_returns_new_state(self):
        state = ShadowCapabilityState(
            capability_digest="a" * 64,
            application_state="UNAPPLIED",
            consumption_count=0,
            current_lifecycle_state="CONSUMED",
            applied_artifact_digest=None,
        )
        new_state = state.apply_artifact("b" * 64)
        assert state.application_state == "UNAPPLIED"
        assert new_state.application_state == "APPLIED"
        assert new_state.consumption_count == 1

    def test_deep_copy_identical_digest(self):
        state = ShadowCapabilityState(
            capability_digest="a" * 64,
            application_state="UNAPPLIED",
            consumption_count=0,
            current_lifecycle_state="CONSUMED",
            applied_artifact_digest=None,
        )
        copy = deep_copy_state(state)
        assert copy.state_digest == state.state_digest
        assert copy is not state

    def test_from_capability_record(self):
        cap = {"capability_digest": "a" * 64, "current_lifecycle_state": "CONSUMED", "consumption_count": 1}
        state = ShadowCapabilityState.from_capability_record(cap)
        assert state.capability_digest == "a" * 64
        assert state.current_lifecycle_state == "CONSUMED"
        assert state.consumption_count == 1
