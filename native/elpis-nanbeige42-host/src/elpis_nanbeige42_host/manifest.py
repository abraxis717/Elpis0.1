"""Host ABI manifest and sealed evidence bindings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .digest import SCHEMA as DIGEST_SCHEMA, canonical_digest
from .schemas import ControlMode


@dataclass(frozen=True, slots=True)
class EvidenceBinding:
    name: str
    digest: str
    claim: str


@dataclass(frozen=True, slots=True)
class HostAbiManifest:
    schema: Literal["elpis.nanbeige42.host-abi-manifest.v2"]
    host_version: str
    claim_scope: Literal["instrument_abi_and_packet_derivation_contract"]
    digest_rule: str
    enabled_control_modes: tuple[ControlMode, ...]
    packet_derivation_status: Literal[
        "CONTRACT_FROZEN_DIAGNOSTIC_PRODUCERS_ONLY"
    ]
    packet_derivation_policy_digest: str
    grid81_packet_derivation: Literal["FORBIDDEN_UNLESS_SEPARATELY_QUALIFIED"]
    registry_packet_derivation: Literal["RESERVED_NOT_IMPLEMENTED"]
    model_runtime_qualified: bool
    coding_utility_status: Literal["UNDEMONSTRATED"]
    imports_from_markov_header_forbidden: bool
    evidence_bindings: tuple[EvidenceBinding, ...]
    hook_registry_digest: str
    executor_policy_digest: str
    supersedes_manifest_digest: str
    manifest_digest: str = ""

    def with_digest(self) -> "HostAbiManifest":
        digest = canonical_digest(self, digest_field="manifest_digest")
        return HostAbiManifest(
            schema=self.schema,
            host_version=self.host_version,
            claim_scope=self.claim_scope,
            digest_rule=self.digest_rule,
            enabled_control_modes=self.enabled_control_modes,
            packet_derivation_status=self.packet_derivation_status,
            packet_derivation_policy_digest=self.packet_derivation_policy_digest,
            grid81_packet_derivation=self.grid81_packet_derivation,
            registry_packet_derivation=self.registry_packet_derivation,
            model_runtime_qualified=self.model_runtime_qualified,
            coding_utility_status=self.coding_utility_status,
            imports_from_markov_header_forbidden=self.imports_from_markov_header_forbidden,
            evidence_bindings=self.evidence_bindings,
            hook_registry_digest=self.hook_registry_digest,
            executor_policy_digest=self.executor_policy_digest,
            supersedes_manifest_digest=self.supersedes_manifest_digest,
            manifest_digest=digest,
        )


def build_manifest(
    *,
    hook_registry_digest: str,
    executor_policy_digest: str,
    packet_derivation_policy_digest: str,
    supersedes_manifest_digest: str = "sha256:d59d03c2ed3bf4032c5dc140cbbb5cc84b1353175a3978b24f339b110d272a8f",
) -> HostAbiManifest:
    bindings = (
        EvidenceBinding(
            "P14_0A_NANBEIGE42_HOST_ABI",
            supersedes_manifest_digest,
            "instrument-only host ABI frozen; packet derivation unimplemented",
        ),
        EvidenceBinding(
            "P13_PHASE4B0J_COLLAPSE_CONTROL_ABI",
            "sha256:1b67f8b825578ebc56c695bc3e5dd5e4985cecd8abf40182050e2825848884d6",
            "22-scalar collapse control surfaces characterized, not qualified",
        ),
        EvidenceBinding(
            "P13_PHASE4B0L_EXACT_POST_LOGIT_AND_DOCK_REFERENCE",
            "sha256:f8bbbfd591c066edabe391be9211a2dc5088d3f54dc9d346032ba452969c8f8c",
            "exact post-logit instrument qualified; dock equivalence not qualified",
        ),
        EvidenceBinding(
            "P13_PHASE4B0M_DOCK_CAUSAL_TRANSPORT",
            "sha256:da70937b485b154b9594f48b45344869c149083b608fe62a39092aa18cf9bb28",
            "dock internal state-specific transport measured, not production qualified",
        ),
    )
    return HostAbiManifest(
        schema="elpis.nanbeige42.host-abi-manifest.v2",
        host_version="ELPIS_NANBEIGE42_HOST_V0_1_ABI_B",
        claim_scope="instrument_abi_and_packet_derivation_contract",
        digest_rule=DIGEST_SCHEMA,
        enabled_control_modes=(ControlMode.NONE, ControlMode.OBSERVE),
        packet_derivation_status="CONTRACT_FROZEN_DIAGNOSTIC_PRODUCERS_ONLY",
        packet_derivation_policy_digest=packet_derivation_policy_digest,
        grid81_packet_derivation="FORBIDDEN_UNLESS_SEPARATELY_QUALIFIED",
        registry_packet_derivation="RESERVED_NOT_IMPLEMENTED",
        model_runtime_qualified=False,
        coding_utility_status="UNDEMONSTRATED",
        imports_from_markov_header_forbidden=True,
        evidence_bindings=bindings,
        hook_registry_digest=hook_registry_digest,
        executor_policy_digest=executor_policy_digest,
        supersedes_manifest_digest=supersedes_manifest_digest,
    ).with_digest()
