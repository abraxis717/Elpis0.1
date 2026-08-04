"""Loop-qualified runtime hooks for the P14.1 Nanbeige instrument."""
from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from .digest import canonical_digest
from .errors import HookInvocationDrift, HookResolutionFailure, HookTeardownFailure
from .hooks import HookRegistry, InvocationEvent, default_registry
from .schemas import ControlMode, GenerationShape


def tensor_digest(tensor: Any) -> str:
    value = tensor.detach().contiguous().to("cpu")
    digest = hashlib.sha256()
    digest.update(str(value.dtype).encode("ascii"))
    digest.update(b"\0")
    digest.update(",".join(map(str, value.shape)).encode("ascii"))
    digest.update(b"\0")
    digest.update(value.numpy().tobytes(order="C"))
    return "sha256:" + digest.hexdigest()


def _first_tensor(value: Any) -> Any:
    if hasattr(value, "shape") and hasattr(value, "detach"):
        return value
    if isinstance(value, (tuple, list)):
        for child in value:
            try:
                return _first_tensor(child)
            except TypeError:
                pass
    if isinstance(value, dict):
        for key in sorted(value):
            try:
                return _first_tensor(value[key])
            except TypeError:
                pass
    raise TypeError(f"no tensor in hook value {type(value)!r}")


def _resolve_path(model: Any, path: str) -> Any:
    if path == "elpis.host.input_assembly":
        return None
    parts = path.split(".")
    if not parts or parts[0] != "model":
        raise HookResolutionFailure(f"unsupported hook path: {path}")
    value: Any = model
    for part in parts[1:]:
        if part.isdigit():
            value = value[int(part)]
        else:
            if not hasattr(value, part):
                raise HookResolutionFailure(f"hook path missing: {path}")
            value = getattr(value, part)
    return value


def resolve_registry(model: Any, registry: HookRegistry | None = None) -> dict[str, Any]:
    selected = registry or default_registry()
    resolved_paths: dict[str, list[str]] = {}
    modules: dict[str, Any] = {}
    for hook in selected.hooks:
        module = _resolve_path(model, hook.module_path)
        resolved_paths[hook.anchor_id] = [hook.module_path]
        modules[hook.anchor_id] = module
    selected.resolve_exactly_once(resolved_paths)
    return modules


class RuntimeHookSession:
    def __init__(
        self,
        *,
        model: Any,
        mode: ControlMode,
        residual: np.ndarray | None = None,
        logit_bias: np.ndarray | None = None,
        registry: HookRegistry | None = None,
    ) -> None:
        self.model = model
        self.mode = mode
        self.residual = None if residual is None else np.asarray(residual, dtype=np.float32).reshape(-1)
        self.logit_bias = None if logit_bias is None else np.asarray(logit_bias, dtype=np.float32).reshape(-1)
        self.registry = registry or default_registry()
        self.modules = resolve_registry(model, self.registry)
        self.handles: list[Any] = []
        self.handle_bindings: list[tuple[Any, int, str]] = []
        self.events: dict[str, list[InvocationEvent]] = {hook.anchor_id: [] for hook in self.registry.hooks}
        self.tensor_digests: dict[str, list[str]] = {hook.anchor_id: [] for hook in self.registry.hooks}
        self.raw_logit_digests: list[str] = []
        self.controlled_logit_digests: list[str] = []
        self.raw_logits: list[np.ndarray] = []
        self.controlled_logits: list[np.ndarray] = []
        self.ulp_intended: list[np.ndarray] = []
        self.ulp_realized: list[np.ndarray] = []
        self.ulp_spacing: list[np.ndarray] = []
        self.current_phase: str | None = None
        self.current_sequence_length: int | None = None
        self.norm_ordinal = 0
        self.layer_loop: dict[int, int] = {}
        self.forward_index = -1
        self._installed = False

    @property
    def dock_enabled(self) -> bool:
        return self.mode in (ControlMode.DOCK, ControlMode.HYBRID)

    @property
    def post_logit_enabled(self) -> bool:
        return self.mode in (ControlMode.POST_LOGIT, ControlMode.HYBRID)

    def _append_handle(self, module: Any, handle: Any, anchor: str) -> None:
        self.handles.append(handle)
        self.handle_bindings.append((module, int(handle.id), anchor))

    def install(self) -> None:
        if self._installed:
            raise HookResolutionFailure("runtime hooks already installed")
        norm = self.modules["INTER_LOOP_SEAM_PRE"]
        self._append_handle(norm, norm.register_forward_pre_hook(self._norm_pre), "INTER_LOOP_SEAM_PRE")
        self._append_handle(norm, norm.register_forward_hook(self._norm_post), "INTER_LOOP_SEAM_POST")
        for index in (0, 10, 16, 21):
            anchor = f"LAYER_{index:02d}_L1_POST"
            layer = self.modules[anchor]
            self._append_handle(
                layer,
                layer.register_forward_pre_hook(self._layer_pre(index), with_kwargs=True),
                anchor + ":pre",
            )
            self._append_handle(layer, layer.register_forward_hook(self._layer_post(index)), anchor)
        head = self.modules["POST_LOGIT"]
        self._append_handle(head, head.register_forward_hook(self._head_post), "POST_LOGIT")
        self._installed = True

    def record_input_assembly(self, prompt_digest: str) -> None:
        self.events["INPUT_ASSEMBLY"].append(
            InvocationEvent(0, None, None, 0, "terminal")
        )
        self.tensor_digests["INPUT_ASSEMBLY"].append(prompt_digest)

    def begin_forward(self, *, phase: str, sequence_length: int) -> None:
        if phase not in ("prefill", "decode"):
            raise HookInvocationDrift(f"invalid forward phase: {phase}")
        self.forward_index += 1
        self.current_phase = phase
        self.current_sequence_length = int(sequence_length)
        self.norm_ordinal = 0
        self.layer_loop.clear()

    def end_forward(self) -> None:
        if self.norm_ordinal != 2:
            raise HookInvocationDrift(f"norm invocation drift: {self.norm_ordinal}")
        self.current_phase = None
        self.current_sequence_length = None
        self.layer_loop.clear()

    def _event(self, *, loop_index: int | None, ordinal: int | None) -> InvocationEvent:
        if self.current_phase is None or self.current_sequence_length is None:
            raise HookInvocationDrift("hook invoked outside declared forward")
        return InvocationEvent(
            call_index=self.forward_index,
            loop_index=loop_index,
            module_call_ordinal=ordinal,
            sequence_length=self.current_sequence_length,
            phase=self.current_phase,  # type: ignore[arg-type]
        )

    def _norm_pre(self, module: Any, args: tuple[Any, ...]) -> None:
        tensor = _first_tensor(args)
        ordinal = self.norm_ordinal
        if ordinal == 0:
            anchor = "INTER_LOOP_SEAM_PRE"
            self.events[anchor].append(self._event(loop_index=None, ordinal=0))
            self.tensor_digests[anchor].append(tensor_digest(tensor[:, -1, :]))

    def _norm_post(self, module: Any, args: Any, output: Any) -> Any:
        import torch

        ordinal = self.norm_ordinal
        self.norm_ordinal += 1
        if ordinal == 0:
            anchor = "INTER_LOOP_SEAM_POST"
            self.events[anchor].append(self._event(loop_index=None, ordinal=0))
            if self.dock_enabled:
                if self.residual is None or self.residual.shape != (3072,):
                    raise HookInvocationDrift("dock residual unavailable or wrong shape")
                intended = np.asarray(self.residual, dtype=np.float32)
                residual_native = torch.as_tensor(intended, dtype=output.dtype, device=output.device)
                before = output[:, -1, :]
                after = output + residual_native.reshape(1, 1, -1).expand_as(output)
                realized = (after[:, -1, :].float() - before.float()).detach().cpu().numpy().reshape(-1)
                native = before.detach().to("cpu").numpy()
                next_native = np.nextafter(native, np.asarray(np.inf, dtype=native.dtype))
                spacing = np.abs(next_native.astype(np.float32) - native.astype(np.float32)).reshape(-1)
                self.ulp_intended.append(intended.copy())
                self.ulp_realized.append(realized.astype(np.float32))
                self.ulp_spacing.append(spacing.astype(np.float32))
                self.tensor_digests[anchor].append(tensor_digest(after[:, -1, :]))
                return after
            self.tensor_digests[anchor].append(tensor_digest(output[:, -1, :]))
            return None
        if ordinal == 1:
            anchor = "FINAL_NORM_POST"
            self.events[anchor].append(self._event(loop_index=None, ordinal=1))
            self.tensor_digests[anchor].append(tensor_digest(output[:, -1, :]))
            return None
        raise HookInvocationDrift(f"unexpected norm ordinal: {ordinal}")

    def _layer_pre(self, index: int):
        def hook(module: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
            self.layer_loop[index] = int(kwargs.get("loop_idx", -1))
        return hook

    def _layer_post(self, index: int):
        anchor = f"LAYER_{index:02d}_L1_POST"
        def hook(module: Any, args: Any, output: Any) -> None:
            loop_index = self.layer_loop.pop(index, -1)
            if loop_index == 1:
                tensor = _first_tensor(output)
                self.events[anchor].append(self._event(loop_index=1, ordinal=None))
                self.tensor_digests[anchor].append(tensor_digest(tensor[:, -1, :]))
        return hook

    def _head_post(self, module: Any, args: Any, output: Any) -> Any:
        import torch

        event = self._event(loop_index=None, ordinal=None)
        self.events["POST_LOGIT"].append(event)
        raw = output.float()
        self.raw_logit_digests.append(tensor_digest(raw))
        self.raw_logits.append(raw.detach().cpu().numpy().astype(np.float32).reshape(-1))
        if self.post_logit_enabled:
            if self.logit_bias is None or self.logit_bias.shape != (int(raw.shape[-1]),):
                raise HookInvocationDrift("exact post-logit bias unavailable or wrong shape")
            bias = torch.as_tensor(self.logit_bias, dtype=torch.float32, device=raw.device)
            controlled = raw + bias.reshape(1, -1)
        else:
            controlled = raw
        self.controlled_logit_digests.append(tensor_digest(controlled))
        self.controlled_logits.append(controlled.detach().cpu().numpy().astype(np.float32).reshape(-1))
        self.tensor_digests["POST_LOGIT"].append(self.controlled_logit_digests[-1])
        if self.post_logit_enabled:
            return controlled
        return None

    def validate(self, shape: GenerationShape) -> None:
        for hook in self.registry.hooks:
            hook.invocation_rule.validate(self.events[hook.anchor_id], shape)

    def trace_payload(self) -> dict[str, Any]:
        return {
            "schema": "elpis.nanbeige42.hook-trace.v1",
            "mode": self.mode.value,
            "events": {
                anchor: [
                    {
                        "call_index": event.call_index,
                        "loop_index": event.loop_index,
                        "module_call_ordinal": event.module_call_ordinal,
                        "sequence_length": event.sequence_length,
                        "phase": event.phase,
                    }
                    for event in values
                ]
                for anchor, values in sorted(self.events.items())
            },
            "tensor_digests": {
                anchor: list(values) for anchor, values in sorted(self.tensor_digests.items())
            },
        }

    @property
    def trace_digest(self) -> str:
        return canonical_digest(self.trace_payload())

    def remove(self) -> None:
        for handle in reversed(self.handles):
            handle.remove()
        for module, handle_id, anchor in self.handle_bindings:
            registries = (
                getattr(module, "_forward_pre_hooks", {}),
                getattr(module, "_forward_hooks", {}),
            )
            if any(handle_id in registry for registry in registries):
                raise HookTeardownFailure(f"hook remains installed: {anchor}:{handle_id}")
        self.handles.clear()
        self.handle_bindings.clear()
        self._installed = False
