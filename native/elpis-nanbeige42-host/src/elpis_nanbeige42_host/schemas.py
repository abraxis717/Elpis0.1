"""Frozen public schemas for P14.0a.

P14.0a deliberately exposes no PacketDerivation implementation. Therefore the
manifest enables only NONE and OBSERVE. DOCK, POST_LOGIT, and HYBRID remain enum
values for forward compatibility but are runtime-prohibited until later gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Mapping, Sequence

from .digest import canonical_digest
from .errors import ActionSchemaViolation, ControlShapeMismatch, GenerationShapeViolation


class ControlMode(str, Enum):
    NONE = "none"
    OBSERVE = "observe"
    DOCK = "dock"
    POST_LOGIT = "post_logit"
    HYBRID = "hybrid"


@dataclass(frozen=True, slots=True)
class GenerationShape:
    num_loops: int
    prefill_tokens: int
    decode_steps: int

    def __post_init__(self) -> None:
        if self.num_loops != 2:
            raise GenerationShapeViolation("Nanbeige42 v0.1 requires exactly two loops")
        if self.prefill_tokens < 1:
            raise GenerationShapeViolation("prefill_tokens must be positive")
        if self.decode_steps < 0:
            raise GenerationShapeViolation("decode_steps must be non-negative")

    @property
    def forward_passes(self) -> int:
        return 1 + self.decode_steps


@dataclass(frozen=True, slots=True)
class CodingTask:
    task_id: str
    objective: str
    constraints: tuple[str, ...]
    acceptance_condition_ids: tuple[str, ...]
    prohibited_action_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkspaceState:
    repo_root: str
    branch: str
    head_commit: str
    tracked_file_manifest_digest: str
    dirty_patch_digest: str | None
    relevant_file_ids: tuple[str, ...]
    recent_result_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ToolEvidence:
    evidence_id: str
    kind: Literal[
        "file_read", "search_result", "compiler_result", "test_result",
        "runtime_result", "diff_result", "executor_receipt",
        "packet_derivation_receipt"
    ]
    payload_digest: str
    summary: str


@dataclass(frozen=True, slots=True)
class CollapseControlPacket:
    """Exact 22-coordinate packet.

    `gain` is a bounded measurement parameter, not authority. Actuation requires
    a separate opaque, use-once ActuationCapability issued by the token layer.
    Sign is represented only by the structural coordinates. No self-reported
    confidence field exists in v0.1.
    """

    schema: Literal["elpis.collapse-control.v1"]
    common: float
    structural: tuple[float, ...]
    source_state_digest: str
    gain: float
    packet_digest: str = ""

    def __post_init__(self) -> None:
        if len(self.structural) != 21:
            raise ControlShapeMismatch("structural must contain exactly 21 coordinates")
        if not (0.0 <= self.gain <= 8.0):
            raise ControlShapeMismatch("gain must be within frozen diagnostic bound [0, 8]")

    def with_digest(self) -> "CollapseControlPacket":
        digest = canonical_digest(self, digest_field="packet_digest")
        return CollapseControlPacket(
            schema=self.schema,
            common=self.common,
            structural=self.structural,
            source_state_digest=self.source_state_digest,
            gain=self.gain,
            packet_digest=digest,
        )


@dataclass(frozen=True, slots=True)
class ElpisCodingTick:
    schema: Literal["elpis.nanbeige42.coding-tick.v1", "elpis.nanbeige42.coding-tick.v2"]
    tick_id: str
    parent_tick_id: str | None
    logical_time: int
    task: CodingTask
    workspace: WorkspaceState
    evidence: tuple[ToolEvidence, ...]
    control_mode: ControlMode
    control: CollapseControlPacket | None
    generation_shape: GenerationShape
    packet_derivation_receipt_digest: str | None = None
    input_digest: str = ""

    def with_digest(self) -> "ElpisCodingTick":
        digest = canonical_digest(self, digest_field="input_digest")
        return ElpisCodingTick(
            schema=self.schema,
            tick_id=self.tick_id,
            parent_tick_id=self.parent_tick_id,
            logical_time=self.logical_time,
            task=self.task,
            workspace=self.workspace,
            evidence=self.evidence,
            control_mode=self.control_mode,
            control=self.control,
            generation_shape=self.generation_shape,
            packet_derivation_receipt_digest=self.packet_derivation_receipt_digest,
            input_digest=digest,
        )


class ActionKind(str, Enum):
    INSPECT = "inspect"
    SEARCH = "search"
    PATCH = "patch"
    RUN_TEST = "run_test"
    RUN_COMMAND = "run_command"
    EXPLAIN = "explain"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class InspectPayload:
    file_ids: tuple[str, ...]
    symbol_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SearchPayload:
    query: str
    root_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PatchOperation:
    target_path: str
    expected_preimage_digest: str
    unified_diff: str


@dataclass(frozen=True, slots=True)
class PatchPayload:
    operations: tuple[PatchOperation, ...]
    verification_command_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CommandPayload:
    command_id: str
    argv: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExplainPayload:
    summary: str


@dataclass(frozen=True, slots=True)
class StopPayload:
    status: Literal["verified", "blocked", "failed"]
    evidence_ids: tuple[str, ...]


ActionPayload = InspectPayload | SearchPayload | PatchPayload | CommandPayload | ExplainPayload | StopPayload


@dataclass(frozen=True, slots=True)
class CodingAction:
    schema: Literal["elpis.nanbeige42.coding-action.v1"]
    action_id: str
    tick_id: str
    kind: ActionKind
    payload: ActionPayload
    rationale_summary: str
    expected_result: str
    action_digest: str = ""

    def __post_init__(self) -> None:
        expected = {
            ActionKind.INSPECT: InspectPayload,
            ActionKind.SEARCH: SearchPayload,
            ActionKind.PATCH: PatchPayload,
            ActionKind.RUN_TEST: CommandPayload,
            ActionKind.RUN_COMMAND: CommandPayload,
            ActionKind.EXPLAIN: ExplainPayload,
            ActionKind.STOP: StopPayload,
        }[self.kind]
        if not isinstance(self.payload, expected):
            raise ActionSchemaViolation(
                f"payload type {type(self.payload).__name__} invalid for {self.kind.value}"
            )

    def with_digest(self) -> "CodingAction":
        digest = canonical_digest(self, digest_field="action_digest")
        return CodingAction(
            schema=self.schema,
            action_id=self.action_id,
            tick_id=self.tick_id,
            kind=self.kind,
            payload=self.payload,
            rationale_summary=self.rationale_summary,
            expected_result=self.expected_result,
            action_digest=digest,
        )


@dataclass(frozen=True, slots=True)
class TickEvidence:
    schema: Literal["elpis.nanbeige42.tick-evidence.v1"]
    tick_id: str
    input_digest: str
    model_manifest_digest: str
    hook_registry_digest: str
    executor_policy_digest: str
    control_mode: ControlMode
    control_packet_digest: str | None
    hook_trace_digest: str
    seam_pre_digest: str | None
    seam_post_digest: str | None
    checkpoint_digests: Mapping[str, str]
    kv_cache_fingerprint_before: str | None
    kv_cache_fingerprint_after: str | None
    raw_logits_digest: str | None
    controlled_logits_digest: str | None
    generated_action_digest: str | None
    executor_receipt_digest: str | None
    failure_code: str | None
    evidence_digest: str = ""

    def with_digest(self) -> "TickEvidence":
        digest = canonical_digest(self, digest_field="evidence_digest")
        return TickEvidence(
            schema=self.schema,
            tick_id=self.tick_id,
            input_digest=self.input_digest,
            model_manifest_digest=self.model_manifest_digest,
            hook_registry_digest=self.hook_registry_digest,
            executor_policy_digest=self.executor_policy_digest,
            control_mode=self.control_mode,
            control_packet_digest=self.control_packet_digest,
            hook_trace_digest=self.hook_trace_digest,
            seam_pre_digest=self.seam_pre_digest,
            seam_post_digest=self.seam_post_digest,
            checkpoint_digests=self.checkpoint_digests,
            kv_cache_fingerprint_before=self.kv_cache_fingerprint_before,
            kv_cache_fingerprint_after=self.kv_cache_fingerprint_after,
            raw_logits_digest=self.raw_logits_digest,
            controlled_logits_digest=self.controlled_logits_digest,
            generated_action_digest=self.generated_action_digest,
            executor_receipt_digest=self.executor_receipt_digest,
            failure_code=self.failure_code,
            evidence_digest=digest,
        )
