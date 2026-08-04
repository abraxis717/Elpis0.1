"""P14.2a frozen coding-task and packet registry.

This module implements a finite, digest-bound task registry. It does not infer a
control packet from arbitrary coding prose and does not use Grid81. Registry
lookup is utility-eligible only for entries sealed in the pilot partition and
only under the exact repository snapshot, acceptance command, packet, and mode
plan bound into the registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import Literal, Mapping

from .digest import canonical_digest, validate_digest
from .errors import (
    PacketDerivationInputMismatch,
    RegistryDerivationUnavailable,
)
from .packet_derivation import (
    CodingTickSeed,
    FrozenV01PacketDerivation,
    PacketDerivationMethod,
    PacketDerivationPolicy,
    PacketDerivationReceipt,
    PacketDerivationRequest,
    PacketDerivationResult,
)
from .schemas import CollapseControlPacket, ControlMode


class TaskPartition(str, Enum):
    OPEN_CANARY = "open_canary"
    SEALED_PILOT = "sealed_pilot"


@dataclass(frozen=True, slots=True)
class AcceptanceCommandSpec:
    schema: Literal["elpis.nanbeige42.acceptance-command.v1"]
    command_id: Literal["pytest_registry"]
    argv: tuple[str, ...]
    timeout_seconds: int
    command_digest: str = ""

    def __post_init__(self) -> None:
        if not self.argv:
            raise PacketDerivationInputMismatch("acceptance argv must be non-empty")
        if self.timeout_seconds < 1 or self.timeout_seconds > 300:
            raise PacketDerivationInputMismatch("acceptance timeout outside [1, 300]")
        forbidden = (";", "&&", "||", "`", "$(")
        if any(token in arg for arg in self.argv for token in forbidden):
            raise PacketDerivationInputMismatch("acceptance command contains shell syntax")

    def with_digest(self) -> "AcceptanceCommandSpec":
        digest = canonical_digest(self, digest_field="command_digest")
        return AcceptanceCommandSpec(
            schema=self.schema,
            command_id=self.command_id,
            argv=self.argv,
            timeout_seconds=self.timeout_seconds,
            command_digest=digest,
        )


@dataclass(frozen=True, slots=True)
class RegistryPacketBinding:
    schema: Literal["elpis.nanbeige42.registry-packet-binding.v1"]
    registry_key: str
    task_id: str
    family: str
    source_class_primary: str
    source_split: Literal["train"]
    source_packet_digest: str
    realized_packet_digest: str
    packet: CollapseControlPacket
    binding_digest: str = ""

    def __post_init__(self) -> None:
        if self.registry_key != self.task_id:
            raise PacketDerivationInputMismatch("v0.1 registry key must equal task_id")
        if self.source_split != "train":
            raise PacketDerivationInputMismatch("P14.2a packet bindings require P13 train packets")
        if not self.source_packet_digest.startswith("sha256:"):
            raise PacketDerivationInputMismatch("source packet digest must be sha256-prefixed")
        if self.packet.packet_digest != self.realized_packet_digest:
            raise PacketDerivationInputMismatch("realized packet digest mismatch")

    def with_digest(self) -> "RegistryPacketBinding":
        digest = canonical_digest(self, digest_field="binding_digest")
        return RegistryPacketBinding(
            schema=self.schema,
            registry_key=self.registry_key,
            task_id=self.task_id,
            family=self.family,
            source_class_primary=self.source_class_primary,
            source_split=self.source_split,
            source_packet_digest=self.source_packet_digest,
            realized_packet_digest=self.realized_packet_digest,
            packet=self.packet,
            binding_digest=digest,
        )


@dataclass(frozen=True, slots=True)
class CodingRegistryEntry:
    schema: Literal["elpis.nanbeige42.coding-registry-entry.v1"]
    task_id: str
    partition: TaskPartition
    family: str
    objective: str
    constraints: tuple[str, ...]
    workspace_root: str
    workspace_snapshot_digest: str
    allowed_path_prefixes: tuple[str, ...]
    acceptance_condition_digest: str
    acceptance_command: AcceptanceCommandSpec
    packet_binding_digest: str
    mode_plan: tuple[ControlMode, ...]
    maximum_ticks: int
    maximum_patch_bytes: int
    independent_unit: Literal["task"]
    first_patch_primary: bool
    coding_utility_eligible: bool
    entry_digest: str = ""

    def __post_init__(self) -> None:
        expected = (ControlMode.NONE, ControlMode.OBSERVE, ControlMode.DOCK)
        if self.mode_plan != expected:
            raise PacketDerivationInputMismatch("mode plan must be NONE, OBSERVE, DOCK")
        if self.partition is TaskPartition.OPEN_CANARY and self.coding_utility_eligible:
            raise PacketDerivationInputMismatch("open canaries cannot carry utility evidence")
        if self.partition is TaskPartition.SEALED_PILOT and not self.coding_utility_eligible:
            raise PacketDerivationInputMismatch("sealed pilot entries must be utility eligible")
        if self.maximum_ticks < 1 or self.maximum_ticks > 8:
            raise PacketDerivationInputMismatch("maximum_ticks outside [1, 8]")
        if self.maximum_patch_bytes < 1 or self.maximum_patch_bytes > 65536:
            raise PacketDerivationInputMismatch("maximum_patch_bytes outside bounds")
        root = PurePosixPath(self.workspace_root)
        if not root.is_absolute():
            raise PacketDerivationInputMismatch("workspace root must be absolute")
        if not self.allowed_path_prefixes:
            raise PacketDerivationInputMismatch("allowed path prefixes cannot be empty")
        for prefix in self.allowed_path_prefixes:
            p = PurePosixPath(prefix)
            if not p.is_absolute() or not str(p).startswith(str(root)):
                raise PacketDerivationInputMismatch("allowed path outside task workspace")

    def with_digest(self) -> "CodingRegistryEntry":
        digest = canonical_digest(self, digest_field="entry_digest")
        return CodingRegistryEntry(
            schema=self.schema,
            task_id=self.task_id,
            partition=self.partition,
            family=self.family,
            objective=self.objective,
            constraints=self.constraints,
            workspace_root=self.workspace_root,
            workspace_snapshot_digest=self.workspace_snapshot_digest,
            allowed_path_prefixes=self.allowed_path_prefixes,
            acceptance_condition_digest=self.acceptance_condition_digest,
            acceptance_command=self.acceptance_command,
            packet_binding_digest=self.packet_binding_digest,
            mode_plan=self.mode_plan,
            maximum_ticks=self.maximum_ticks,
            maximum_patch_bytes=self.maximum_patch_bytes,
            independent_unit=self.independent_unit,
            first_patch_primary=self.first_patch_primary,
            coding_utility_eligible=self.coding_utility_eligible,
            entry_digest=digest,
        )


@dataclass(frozen=True, slots=True)
class FrozenCodingRegistry:
    schema: Literal["elpis.nanbeige42.coding-registry.v1"]
    registry_name: Literal["ELPIS_NANBEIGE42_CODING_PILOT_V0_1"]
    entries: tuple[CodingRegistryEntry, ...]
    packet_bindings: tuple[RegistryPacketBinding, ...]
    source_packet_registry_sha256: str
    p14_1_runtime_profile_digest: str
    p14_1_report_digest: str
    grid81_used: bool
    learned_mapper_used: bool
    generalization_claimed: bool
    registry_digest: str = ""

    def __post_init__(self) -> None:
        if self.grid81_used or self.learned_mapper_used or self.generalization_claimed:
            raise PacketDerivationInputMismatch("P14.2a registry scope violation")
        if len(self.entries) != 24 or len(self.packet_bindings) != 24:
            raise PacketDerivationInputMismatch("registry requires exactly 24 entries/bindings")
        ids = [entry.task_id for entry in self.entries]
        if len(set(ids)) != len(ids):
            raise PacketDerivationInputMismatch("duplicate task id")
        binding_ids = [binding.task_id for binding in self.packet_bindings]
        if sorted(ids) != sorted(binding_ids):
            raise PacketDerivationInputMismatch("entry/binding task set mismatch")
        canaries = [e for e in self.entries if e.partition is TaskPartition.OPEN_CANARY]
        pilots = [e for e in self.entries if e.partition is TaskPartition.SEALED_PILOT]
        if len(canaries) != 6 or len(pilots) != 18:
            raise PacketDerivationInputMismatch("registry requires 6 canaries and 18 pilots")
        families = sorted(set(e.family for e in self.entries))
        if len(families) != 6:
            raise PacketDerivationInputMismatch("registry requires six families")
        for family in families:
            family_entries = [e for e in self.entries if e.family == family]
            if sum(e.partition is TaskPartition.OPEN_CANARY for e in family_entries) != 1:
                raise PacketDerivationInputMismatch("each family requires one canary")
            if sum(e.partition is TaskPartition.SEALED_PILOT for e in family_entries) != 3:
                raise PacketDerivationInputMismatch("each family requires three pilots")

    def with_digest(self) -> "FrozenCodingRegistry":
        digest = canonical_digest(self, digest_field="registry_digest")
        return FrozenCodingRegistry(
            schema=self.schema,
            registry_name=self.registry_name,
            entries=self.entries,
            packet_bindings=self.packet_bindings,
            source_packet_registry_sha256=self.source_packet_registry_sha256,
            p14_1_runtime_profile_digest=self.p14_1_runtime_profile_digest,
            p14_1_report_digest=self.p14_1_report_digest,
            grid81_used=self.grid81_used,
            learned_mapper_used=self.learned_mapper_used,
            generalization_claimed=self.generalization_claimed,
            registry_digest=digest,
        )

    def entry_map(self) -> dict[str, CodingRegistryEntry]:
        return {entry.task_id: entry for entry in self.entries}

    def binding_map(self) -> dict[str, RegistryPacketBinding]:
        return {binding.registry_key: binding for binding in self.packet_bindings}


class RegistryPacketDerivation(FrozenV01PacketDerivation):
    """Finite task-registry lookup; not an arbitrary semantic mapper."""

    def __init__(self, registry: FrozenCodingRegistry) -> None:
        if not validate_digest(registry, digest_field="registry_digest"):
            raise RegistryDerivationUnavailable("coding registry digest invalid")
        policy = PacketDerivationPolicy(
            schema="elpis.packet-derivation-policy.v1",
            implemented_methods=(
                PacketDerivationMethod.NONE,
                PacketDerivationMethod.NEUTRAL_STUB,
                PacketDerivationMethod.EXPLICIT_SEALED_VECTOR,
                PacketDerivationMethod.REGISTRY_LOOKUP,
            ),
            coding_utility_eligible_methods=(PacketDerivationMethod.REGISTRY_LOOKUP,),
            grid81_allowed=False,
            registry_lookup_available=True,
            explicit_vector_purpose="runtime_qualification_diagnostic",
        ).with_digest()
        super().__init__(policy=policy)
        self.registry = registry
        self._entries = registry.entry_map()
        self._bindings = registry.binding_map()

    def derive(self, seed: CodingTickSeed, request: PacketDerivationRequest) -> PacketDerivationResult:
        if request.method is not PacketDerivationMethod.REGISTRY_LOOKUP:
            return super().derive(seed, request)
        self._validate_inputs(seed, request)
        if seed.control_mode is not ControlMode.DOCK:
            raise PacketDerivationInputMismatch(
                "P14.2a registry packets are qualified for DOCK mode only"
            )
        key = request.registry_key
        if key is None or key not in self._entries or key not in self._bindings:
            raise RegistryDerivationUnavailable("registry key is absent from frozen registry")
        entry = self._entries[key]
        binding = self._bindings[key]
        if seed.task.task_id != entry.task_id:
            raise PacketDerivationInputMismatch("seed task does not match registry entry")
        if seed.workspace.repo_root != entry.workspace_root:
            raise PacketDerivationInputMismatch("workspace root does not match registry entry")
        if seed.workspace.tracked_file_manifest_digest != entry.workspace_snapshot_digest:
            raise PacketDerivationInputMismatch("workspace snapshot digest drift")
        if binding.task_id != entry.task_id or binding.binding_digest != entry.packet_binding_digest:
            raise PacketDerivationInputMismatch("task packet binding drift")
        packet = binding.packet
        receipt = PacketDerivationReceipt(
            schema="elpis.packet-derivation-receipt.v1",
            method=PacketDerivationMethod.REGISTRY_LOOKUP,
            seed_digest=seed.seed_digest,
            request_digest=request.request_digest,
            packet_digest=packet.packet_digest,
            producer_id=f"P14_2A_REGISTRY:{entry.task_id}",
            producer_state_digest=packet.source_state_digest,
            registry_digest=self.registry.registry_digest,
            grid81_used=False,
            semantic_mapper_qualified=False,
            coding_utility_eligible=entry.coding_utility_eligible,
        ).with_digest()
        return PacketDerivationResult(packet=packet, receipt=receipt)
