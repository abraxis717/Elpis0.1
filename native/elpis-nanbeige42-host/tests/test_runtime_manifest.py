from dataclasses import replace
import pytest

from elpis_nanbeige42_host.errors import RuntimeModeUnqualified
from elpis_nanbeige42_host.runtime_manifest import (
    RuntimeQualificationProfile,
    SeamULPProfile,
    SeamULPThresholds,
    qualify_ulp,
)
from elpis_nanbeige42_host.schemas import ControlMode


def good_metrics():
    return {
        "p05_abs_residual_over_ulp": 0.1,
        "median_abs_residual_over_ulp": 2.0,
        "realized_nonzero_fraction": 0.9,
        "realized_direction_cosine": 0.98,
        "realized_relative_l2": 0.2,
    }


def test_ulp_thresholds_accept_good_profile():
    assert qualify_ulp(good_metrics(), SeamULPThresholds())


def test_ulp_thresholds_reject_low_p05():
    metrics = good_metrics()
    metrics["p05_abs_residual_over_ulp"] = 0.01
    assert not qualify_ulp(metrics, SeamULPThresholds())


def test_runtime_profile_mode_gate_and_digest():
    ulp = SeamULPProfile(3072, 0.1, 2.0, 0.1, 0.9, 0.98, 0.2, True)
    profile = RuntimeQualificationProfile(
        schema="elpis.nanbeige42.runtime-profile.v1",
        host_version="test",
        claim_scope="runtime_instrument_only",
        runtime_qualified=True,
        coding_utility_status="UNDEMONSTRATED",
        enabled_control_modes=(ControlMode.NONE, ControlMode.OBSERVE),
        model_runtime_manifest_digest="sha256:model",
        p14_0b_manifest_digest="sha256:a",
        p14_0b_protocol_digest="sha256:b",
        hook_registry_digest="sha256:c",
        packet_derivation_policy_digest="sha256:d",
        executor_policy_digest="sha256:e",
        replay_index_digest="sha256:f",
        qualification_report_digest="sha256:g",
        dock_ulp_profile=ulp,
        no_op_cache_equivalence=True,
        hook_teardown_exact=True,
        exact_post_logit_qualified=True,
        fresh_process_replay_exact=True,
    ).with_digest()
    profile.assert_mode_enabled(ControlMode.OBSERVE)
    with pytest.raises(RuntimeModeUnqualified):
        profile.assert_mode_enabled(ControlMode.DOCK)
