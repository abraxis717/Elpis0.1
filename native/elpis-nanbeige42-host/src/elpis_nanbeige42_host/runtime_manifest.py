"""P14.1 runtime qualification contracts.

The runtime profile is generated only after three fresh-process replay canaries,
hook validation, NO_OP cache equivalence, seam ULP measurement, exact
post-logit fidelity, and teardown checks complete.  It qualifies the host as an
instrument only; coding utility remains explicitly undemonstrated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from .digest import canonical_digest, validate_digest
from .errors import RuntimeModeUnqualified, RuntimeProfileInvalid
from .schemas import ControlMode


@dataclass(frozen=True, slots=True)
class SeamULPThresholds:
    p05_abs_residual_over_ulp_min: float = 0.0625
    median_abs_residual_over_ulp_min: float = 1.0
    realized_nonzero_fraction_min: float = 0.70
    realized_direction_cosine_min: float = 0.95
    realized_relative_l2_max: float = 0.35


@dataclass(frozen=True, slots=True)
class SeamULPProfile:
    count: int
    p05_abs_residual_over_ulp: float
    median_abs_residual_over_ulp: float
    fraction_below_half_ulp: float
    realized_nonzero_fraction: float
    realized_direction_cosine: float
    realized_relative_l2: float
    qualified: bool


@dataclass(frozen=True, slots=True)
class RuntimeQualificationProfile:
    schema: Literal["elpis.nanbeige42.runtime-profile.v1"]
    host_version: str
    claim_scope: Literal["runtime_instrument_only"]
    runtime_qualified: bool
    coding_utility_status: Literal["UNDEMONSTRATED"]
    enabled_control_modes: tuple[ControlMode, ...]
    model_runtime_manifest_digest: str
    p14_0b_manifest_digest: str
    p14_0b_protocol_digest: str
    hook_registry_digest: str
    packet_derivation_policy_digest: str
    executor_policy_digest: str
    replay_index_digest: str
    qualification_report_digest: str
    dock_ulp_profile: SeamULPProfile
    no_op_cache_equivalence: bool
    hook_teardown_exact: bool
    exact_post_logit_qualified: bool
    fresh_process_replay_exact: bool
    profile_digest: str = ""

    def with_digest(self) -> "RuntimeQualificationProfile":
        digest = canonical_digest(self, digest_field="profile_digest")
        return RuntimeQualificationProfile(
            schema=self.schema,
            host_version=self.host_version,
            claim_scope=self.claim_scope,
            runtime_qualified=self.runtime_qualified,
            coding_utility_status=self.coding_utility_status,
            enabled_control_modes=self.enabled_control_modes,
            model_runtime_manifest_digest=self.model_runtime_manifest_digest,
            p14_0b_manifest_digest=self.p14_0b_manifest_digest,
            p14_0b_protocol_digest=self.p14_0b_protocol_digest,
            hook_registry_digest=self.hook_registry_digest,
            packet_derivation_policy_digest=self.packet_derivation_policy_digest,
            executor_policy_digest=self.executor_policy_digest,
            replay_index_digest=self.replay_index_digest,
            qualification_report_digest=self.qualification_report_digest,
            dock_ulp_profile=self.dock_ulp_profile,
            no_op_cache_equivalence=self.no_op_cache_equivalence,
            hook_teardown_exact=self.hook_teardown_exact,
            exact_post_logit_qualified=self.exact_post_logit_qualified,
            fresh_process_replay_exact=self.fresh_process_replay_exact,
            profile_digest=digest,
        )

    def assert_mode_enabled(self, mode: ControlMode) -> None:
        if not validate_digest(self, digest_field="profile_digest"):
            raise RuntimeProfileInvalid("runtime profile digest invalid")
        if mode not in self.enabled_control_modes:
            raise RuntimeModeUnqualified(mode.value)


def qualify_ulp(metrics: Mapping[str, float], thresholds: SeamULPThresholds) -> bool:
    return (
        float(metrics["p05_abs_residual_over_ulp"]) >= thresholds.p05_abs_residual_over_ulp_min
        and float(metrics["median_abs_residual_over_ulp"]) >= thresholds.median_abs_residual_over_ulp_min
        and float(metrics["realized_nonzero_fraction"]) >= thresholds.realized_nonzero_fraction_min
        and float(metrics["realized_direction_cosine"]) >= thresholds.realized_direction_cosine_min
        and float(metrics["realized_relative_l2"]) <= thresholds.realized_relative_l2_max
    )
