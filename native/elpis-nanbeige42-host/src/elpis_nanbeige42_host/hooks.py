"""Loop-qualified anchor and invocation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from .digest import canonical_digest
from .errors import HookInvocationDrift, HookResolutionFailure
from .schemas import GenerationShape


@dataclass(frozen=True, slots=True)
class InvocationEvent:
    call_index: int
    loop_index: int | None
    module_call_ordinal: int | None
    sequence_length: int
    phase: Literal["prefill", "decode", "terminal"]


@dataclass(frozen=True, slots=True)
class InvocationRule:
    kind: Literal[
        "one_per_forward_for_loop",
        "one_per_forward_for_module_ordinal",
        "one_per_forward",
        "one_per_generation",
        "one_per_decode_step",
    ]
    loop_index: int | None
    module_call_ordinal: int | None = None

    def validate(self, events: Sequence[InvocationEvent], shape: GenerationShape) -> None:
        if self.kind == "one_per_forward_for_loop":
            if self.loop_index is None:
                raise HookInvocationDrift("loop-qualified rule missing loop index")
            expected = shape.forward_passes
            if len(events) != expected:
                raise HookInvocationDrift(f"expected {expected} calls, observed {len(events)}")
            for idx, event in enumerate(events):
                if event.loop_index != self.loop_index:
                    raise HookInvocationDrift("loop index drift")
                expected_phase = "prefill" if idx == 0 else "decode"
                expected_length = shape.prefill_tokens if idx == 0 else 1
                if event.phase != expected_phase or event.sequence_length != expected_length:
                    raise HookInvocationDrift("generation-shape invocation drift")
        elif self.kind == "one_per_forward_for_module_ordinal":
            if self.module_call_ordinal is None:
                raise HookInvocationDrift("module-ordinal rule missing ordinal")
            expected = shape.forward_passes
            if len(events) != expected:
                raise HookInvocationDrift(f"expected {expected} calls, observed {len(events)}")
            for idx, event in enumerate(events):
                expected_phase = "prefill" if idx == 0 else "decode"
                expected_length = shape.prefill_tokens if idx == 0 else 1
                if event.module_call_ordinal != self.module_call_ordinal:
                    raise HookInvocationDrift("module call ordinal drift")
                if event.phase != expected_phase or event.sequence_length != expected_length:
                    raise HookInvocationDrift("generation-shape invocation drift")
        elif self.kind == "one_per_forward":
            expected = shape.forward_passes
            if len(events) != expected:
                raise HookInvocationDrift(f"expected {expected} calls, observed {len(events)}")
            for idx, event in enumerate(events):
                expected_phase = "prefill" if idx == 0 else "decode"
                expected_length = shape.prefill_tokens if idx == 0 else 1
                if event.phase != expected_phase or event.sequence_length != expected_length:
                    raise HookInvocationDrift("generation-shape invocation drift")
        elif self.kind == "one_per_generation":
            if len(events) != 1:
                raise HookInvocationDrift("expected one invocation per generation")
        elif self.kind == "one_per_decode_step":
            if len(events) != shape.decode_steps:
                raise HookInvocationDrift("decode-step invocation count drift")
            if any(event.phase != "decode" or event.sequence_length != 1 for event in events):
                raise HookInvocationDrift("decode-step invocation shape drift")
        else:
            raise HookInvocationDrift(f"unknown invocation rule {self.kind}")


@dataclass(frozen=True, slots=True)
class HookSpec:
    anchor_id: str
    module_path: str
    phase: Literal["pre", "post"]
    expected_width: int | None
    writable: bool
    semantic_role: str
    invocation_rule: InvocationRule


@dataclass(frozen=True, slots=True)
class HookRegistry:
    schema: Literal["elpis.nanbeige42.hook-registry.v1"]
    hooks: tuple[HookSpec, ...]
    registry_digest: str = ""

    def __post_init__(self) -> None:
        ids = [hook.anchor_id for hook in self.hooks]
        if len(ids) != len(set(ids)):
            raise HookResolutionFailure("duplicate anchor id")
        for hook in self.hooks:
            if "LAYER_" in hook.anchor_id and "_L" not in hook.anchor_id:
                raise HookResolutionFailure("layer anchor is not loop-qualified")

    def with_digest(self) -> "HookRegistry":
        digest = canonical_digest(self, digest_field="registry_digest")
        return HookRegistry(schema=self.schema, hooks=self.hooks, registry_digest=digest)

    def resolve_exactly_once(self, resolved_paths: dict[str, list[str]]) -> None:
        for hook in self.hooks:
            matches = resolved_paths.get(hook.anchor_id, [])
            if matches != [hook.module_path]:
                raise HookResolutionFailure(
                    f"{hook.anchor_id} expected exactly {hook.module_path}, observed {matches}"
                )


def default_registry() -> HookRegistry:
    loop1 = InvocationRule("one_per_forward_for_loop", 1)
    seam_ordinal = InvocationRule("one_per_forward_for_module_ordinal", None, 0)
    final_norm_ordinal = InvocationRule("one_per_forward_for_module_ordinal", None, 1)
    every_forward = InvocationRule("one_per_forward", None)
    once = InvocationRule("one_per_generation", None)
    hooks = (
        HookSpec(
            "INPUT_ASSEMBLY", "elpis.host.input_assembly", "post", None, False,
            "canonical tick-to-prompt assembly", once,
        ),
        HookSpec(
            "INTER_LOOP_SEAM_PRE", "model.model.norm", "pre", 3072, False,
            "state immediately before the loop-1 dock seam; first norm call per forward", seam_ordinal,
        ),
        HookSpec(
            "INTER_LOOP_SEAM_POST", "model.model.norm", "post", 3072, True,
            "sole writable hidden-state dock anchor; first norm call per forward", seam_ordinal,
        ),
        HookSpec(
            "LAYER_00_L1_POST", "model.model.layers.0", "post", 3072, False,
            "loop-1 early transport observation", loop1,
        ),
        HookSpec(
            "LAYER_10_L1_POST", "model.model.layers.10", "post", 3072, False,
            "loop-1 mid transport observation", loop1,
        ),
        HookSpec(
            "LAYER_16_L1_POST", "model.model.layers.16", "post", 3072, False,
            "loop-1 late-mid transport observation", loop1,
        ),
        HookSpec(
            "LAYER_21_L1_POST", "model.model.layers.21", "post", 3072, False,
            "loop-1 late transport observation", loop1,
        ),
        HookSpec(
            "FINAL_NORM_POST", "model.model.norm", "post", 3072, False,
            "final normalized hidden representation; second norm call per forward", final_norm_ordinal,
        ),
        HookSpec(
            "POST_LOGIT", "model.lm_head", "post", None, True,
            "exact analytic post-logit lowering anchor", every_forward,
        ),
    )
    return HookRegistry(schema="elpis.nanbeige42.hook-registry.v1", hooks=hooks).with_digest()
