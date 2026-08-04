"""Memory-bounded live helpers for the P14.2b open-canary coding loop.

This module does not broaden the P14.1 runtime qualification.  It supports only
NONE, OBSERVE, and DOCK.  POST_LOGIT and HYBRID remain unavailable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping, Sequence

import numpy as np

from .cache_fingerprint import cache_fingerprint
from .coding_registry import (
    CodingRegistryEntry,
    RegistryPacketBinding,
    TaskPartition,
)
from .digest import canonical_digest, validate_digest
from .errors import PacketDerivationInputMismatch, RegistryDerivationUnavailable
from .hooks import default_registry
from .packet_derivation import (
    CodingTickSeed,
    PacketDerivationMethod,
    PacketDerivationReceipt,
    PacketDerivationRequest,
    PacketDerivationResult,
)
from .runtime_hooks import RuntimeHookSession, tensor_digest
from .runtime_probe import _base_forward, _tokenize, prompt_digest
from .schemas import ControlMode, GenerationShape


class CanaryRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GenerationResult:
    schema: str
    mode: str
    prompt_tokens: int
    generated_token_ids: tuple[int, ...]
    generated_text: str
    generated_text_digest: str
    eos_reached: bool
    realized_decode_steps: int
    prefill_cache_fingerprint: str
    final_cache_fingerprint: str
    hook_trace_digest: str | None
    hook_trace_payload: Mapping[str, Any] | None
    checkpoint_digests: Mapping[str, str]
    raw_logit_digests: tuple[str, ...]
    controlled_logit_digests: tuple[str, ...]
    first_dock_ulp: Mapping[str, Any] | None
    generation_result_digest: str = ""

    def with_digest(self) -> "GenerationResult":
        return GenerationResult(
            schema=self.schema,
            mode=self.mode,
            prompt_tokens=self.prompt_tokens,
            generated_token_ids=self.generated_token_ids,
            generated_text=self.generated_text,
            generated_text_digest=self.generated_text_digest,
            eos_reached=self.eos_reached,
            realized_decode_steps=self.realized_decode_steps,
            prefill_cache_fingerprint=self.prefill_cache_fingerprint,
            final_cache_fingerprint=self.final_cache_fingerprint,
            hook_trace_digest=self.hook_trace_digest,
            hook_trace_payload=self.hook_trace_payload,
            checkpoint_digests=self.checkpoint_digests,
            raw_logit_digests=self.raw_logit_digests,
            controlled_logit_digests=self.controlled_logit_digests,
            first_dock_ulp=self.first_dock_ulp,
            generation_result_digest=canonical_digest(
                self, digest_field="generation_result_digest"
            ),
        )


class CanaryRuntimeHookSession(RuntimeHookSession):
    """P14.1 hook semantics without unbounded full-logit retention.

    P14.1 retained every full vocabulary array because it measured exact
    post-logit fidelity over one decode step.  P14.2b excludes POST_LOGIT and
    HYBRID, so full arrays are unnecessary.  Digests, events, DOCK realization,
    and validation remain exact.
    """

    def __init__(self, **kwargs: Any) -> None:
        mode = kwargs.get("mode")
        if mode not in (ControlMode.OBSERVE, ControlMode.DOCK):
            raise CanaryRuntimeError("canary hook session supports OBSERVE or DOCK only")
        super().__init__(**kwargs)

    def _norm_post(self, module: Any, args: Any, output: Any) -> Any:
        result = super()._norm_post(module, args, output)
        # Retain only the first realized DOCK sample.  P14.1 already qualified
        # the ULP profile; this live phase needs a canary witness, not thousands
        # of repeated 3072-element arrays.
        for values in (self.ulp_intended, self.ulp_realized, self.ulp_spacing):
            if len(values) > 1:
                del values[1:]
        return result

    def _head_post(self, module: Any, args: Any, output: Any) -> Any:
        event = self._event(loop_index=None, ordinal=None)
        self.events["POST_LOGIT"].append(event)
        raw = output.float()
        digest = tensor_digest(raw)
        self.raw_logit_digests.append(digest)
        self.controlled_logit_digests.append(digest)
        self.tensor_digests["POST_LOGIT"].append(digest)
        # POST_LOGIT and HYBRID are excluded; never alter the output.
        return None


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def bounded_text(value: str, maximum_bytes: int) -> str:
    data = value.encode("utf-8", errors="replace")
    if len(data) <= maximum_bytes:
        return value
    suffix = b"\n<ELPIS_OUTPUT_TRUNCATED>\n"
    budget = max(0, maximum_bytes - len(suffix))
    return data[:budget].decode("utf-8", errors="replace") + suffix.decode("ascii")


def normalize_acceptance_output(value: str, shadow_root: Path) -> str:
    """Remove only nondeterministic path/time fields from evidence comparison.

    The raw bounded output is still retained and used as Lane-B feedback.
    """
    normalized = value.replace(str(shadow_root), "<SHADOW_ROOT>")
    normalized = re.sub(r"\bin \d+(?:\.\d+)?s\b", "in <SECONDS>s", normalized)
    return normalized


def binding_from_mapping(value: Mapping[str, Any]) -> RegistryPacketBinding:
    from .schemas import CollapseControlPacket

    packet_value = value["packet"]
    packet = CollapseControlPacket(
        schema=packet_value["schema"],
        common=float(packet_value["common"]),
        structural=tuple(float(item) for item in packet_value["structural"]),
        source_state_digest=str(packet_value["source_state_digest"]),
        gain=float(packet_value["gain"]),
        packet_digest=str(packet_value["packet_digest"]),
    )
    return RegistryPacketBinding(
        schema=value["schema"],
        registry_key=str(value["registry_key"]),
        task_id=str(value["task_id"]),
        family=str(value["family"]),
        source_class_primary=str(value["source_class_primary"]),
        source_split=value["source_split"],
        source_packet_digest=str(value["source_packet_digest"]),
        realized_packet_digest=str(value["realized_packet_digest"]),
        packet=packet,
        binding_digest=str(value["binding_digest"]),
    )


def derive_open_canary_packet(
    *,
    seed: CodingTickSeed,
    request: PacketDerivationRequest,
    entry: CodingRegistryEntry,
    binding: RegistryPacketBinding,
    registry_digest: str,
) -> PacketDerivationResult:
    """Exact canary subset of P14.2a REGISTRY_LOOKUP.

    The full frozen registry class intentionally requires all 24 entries.  The
    open-canary executor must not open the sealed-pilot registry, so this helper
    validates one already-frozen canary entry and its exact packet binding.
    """
    if not validate_digest(seed, digest_field="seed_digest"):
        raise PacketDerivationInputMismatch("coding tick seed digest invalid")
    if not validate_digest(request, digest_field="request_digest"):
        raise PacketDerivationInputMismatch("derivation request digest invalid")
    if request.method is not PacketDerivationMethod.REGISTRY_LOOKUP:
        raise PacketDerivationInputMismatch("open-canary derivation requires registry_lookup")
    if seed.control_mode is not ControlMode.DOCK:
        raise PacketDerivationInputMismatch("open-canary packets are DOCK-only")
    if entry.partition is not TaskPartition.OPEN_CANARY or entry.coding_utility_eligible:
        raise PacketDerivationInputMismatch("entry is not an ineligible open canary")
    if request.registry_key != entry.task_id:
        raise RegistryDerivationUnavailable("registry key does not identify this canary")
    if seed.task.task_id != entry.task_id:
        raise PacketDerivationInputMismatch("seed task does not match canary entry")
    if seed.workspace.repo_root != entry.workspace_root:
        raise PacketDerivationInputMismatch("workspace root does not match registry entry")
    if seed.workspace.tracked_file_manifest_digest != entry.workspace_snapshot_digest:
        raise PacketDerivationInputMismatch("workspace snapshot digest drift")
    if binding.task_id != entry.task_id or binding.registry_key != entry.task_id:
        raise PacketDerivationInputMismatch("canary packet task mismatch")
    if binding.binding_digest != entry.packet_binding_digest:
        raise PacketDerivationInputMismatch("canary packet binding drift")
    if not validate_digest(binding, digest_field="binding_digest"):
        raise PacketDerivationInputMismatch("canary packet binding digest invalid")
    packet = binding.packet
    if not validate_digest(packet, digest_field="packet_digest"):
        raise PacketDerivationInputMismatch("canary control packet digest invalid")

    receipt = PacketDerivationReceipt(
        schema="elpis.packet-derivation-receipt.v1",
        method=PacketDerivationMethod.REGISTRY_LOOKUP,
        seed_digest=seed.seed_digest,
        request_digest=request.request_digest,
        packet_digest=packet.packet_digest,
        producer_id=f"P14_2A_REGISTRY:{entry.task_id}",
        producer_state_digest=packet.source_state_digest,
        registry_digest=registry_digest,
        grid81_used=False,
        semantic_mapper_qualified=False,
        coding_utility_eligible=False,
    ).with_digest()
    return PacketDerivationResult(packet=packet, receipt=receipt)


def _eos_ids(tokenizer: Any) -> set[int]:
    value = getattr(tokenizer, "eos_token_id", None)
    if value is None:
        return set()
    if isinstance(value, (tuple, list, set)):
        return {int(item) for item in value}
    return {int(value)}


def greedy_generate(
    *,
    model: Any,
    tokenizer: Any,
    prompt: str,
    input_device: Any,
    mode: ControlMode,
    residual: np.ndarray | None,
    max_input_tokens: int,
    max_new_tokens: int,
) -> GenerationResult:
    """Deterministic greedy generation with exact P14 hook declarations."""
    import torch

    if mode not in (ControlMode.NONE, ControlMode.OBSERVE, ControlMode.DOCK):
        raise CanaryRuntimeError(f"unqualified live mode: {mode.value}")
    ids, mask = _tokenize(tokenizer, prompt, input_device)
    prompt_tokens = int(ids.shape[1])
    if prompt_tokens > max_input_tokens:
        raise CanaryRuntimeError(
            f"prompt tokens {prompt_tokens} exceed frozen maximum {max_input_tokens}"
        )
    if max_new_tokens < 1:
        raise CanaryRuntimeError("max_new_tokens must be positive")

    session: CanaryRuntimeHookSession | None = None
    if mode in (ControlMode.OBSERVE, ControlMode.DOCK):
        session = CanaryRuntimeHookSession(
            model=model,
            mode=mode,
            residual=residual if mode is ControlMode.DOCK else None,
            logit_bias=None,
            registry=default_registry(),
        )
        session.install()
        session.record_input_assembly(prompt_digest(prompt))

    generated: list[int] = []
    decode_steps = 0
    eos_reached = False
    prefill_fingerprint = ""
    final_fingerprint = ""
    trace_payload: Mapping[str, Any] | None = None
    trace_digest: str | None = None
    checkpoints: dict[str, str] = {}
    raw_digests: tuple[str, ...] = ()
    controlled_digests: tuple[str, ...] = ()
    first_ulp: Mapping[str, Any] | None = None

    try:
        with torch.inference_mode():
            if session is not None:
                session.begin_forward(phase="prefill", sequence_length=prompt_tokens)
            logits, cache, _ = _base_forward(
                model=model,
                input_ids=ids,
                attention_mask=mask,
                past_key_values=None,
            )
            if session is not None:
                session.end_forward()
            prefill_fingerprint = cache_fingerprint(cache)

            eos_ids = _eos_ids(tokenizer)
            for token_index in range(max_new_tokens):
                token = logits.float().argmax(dim=-1, keepdim=True)
                token_id = int(token.item())
                generated.append(token_id)
                if token_id in eos_ids:
                    eos_reached = True
                    break
                if token_index + 1 >= max_new_tokens:
                    break
                decode_mask = torch.cat(
                    (mask, torch.ones((1, len(generated)), dtype=mask.dtype, device=mask.device)),
                    dim=1,
                )
                if session is not None:
                    session.begin_forward(phase="decode", sequence_length=1)
                logits, cache, _ = _base_forward(
                    model=model,
                    input_ids=token,
                    attention_mask=decode_mask,
                    past_key_values=cache,
                )
                if session is not None:
                    session.end_forward()
                decode_steps += 1

            final_fingerprint = cache_fingerprint(cache)

        if session is not None:
            actual_shape = GenerationShape(
                num_loops=2,
                prefill_tokens=prompt_tokens,
                decode_steps=decode_steps,
            )
            session.validate(actual_shape)
            trace_payload = session.trace_payload()
            trace_digest = session.trace_digest
            checkpoints = {
                key: canonical_digest(value)
                for key, value in sorted(session.tensor_digests.items())
                if key not in ("INPUT_ASSEMBLY", "POST_LOGIT")
            }
            raw_digests = tuple(session.raw_logit_digests)
            controlled_digests = tuple(session.controlled_logit_digests)
            if mode is ControlMode.DOCK and session.ulp_intended:
                intended = np.asarray(session.ulp_intended[0], dtype=np.float32)
                realized = np.asarray(session.ulp_realized[0], dtype=np.float32)
                spacing = np.asarray(session.ulp_spacing[0], dtype=np.float32)
                denom = float(np.linalg.norm(intended))
                cosine_denom = float(np.linalg.norm(intended) * np.linalg.norm(realized))
                first_ulp = {
                    "intended_digest": sha256_bytes(intended.tobytes(order="C")),
                    "realized_digest": sha256_bytes(realized.tobytes(order="C")),
                    "spacing_digest": sha256_bytes(spacing.tobytes(order="C")),
                    "realized_relative_l2": float(np.linalg.norm(realized - intended) / max(denom, 1e-30)),
                    "realized_direction_cosine": float(np.dot(intended, realized) / max(cosine_denom, 1e-30)),
                    "realized_nonzero_fraction": float(np.count_nonzero(realized) / realized.size),
                }
    finally:
        if session is not None:
            session.remove()

    text = tokenizer.decode(
        generated,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    return GenerationResult(
        schema="elpis.p14.2b.generation-result.v1",
        mode=mode.value,
        prompt_tokens=prompt_tokens,
        generated_token_ids=tuple(generated),
        generated_text=text,
        generated_text_digest=sha256_text(text),
        eos_reached=eos_reached,
        realized_decode_steps=decode_steps,
        prefill_cache_fingerprint=prefill_fingerprint,
        final_cache_fingerprint=final_fingerprint,
        hook_trace_digest=trace_digest,
        hook_trace_payload=trace_payload,
        checkpoint_digests=checkpoints,
        raw_logit_digests=raw_digests,
        controlled_logit_digests=controlled_digests,
        first_dock_ulp=first_ulp,
    ).with_digest()


def build_bwrap_acceptance_command(
    *,
    bwrap: Path,
    repo_root: Path,
    canonical_task_root: Path,
    provenance_root: Path,
    shadow_root: Path,
    python: Path,
    pythonpath: str,
    relocated_argv: Sequence[str],
) -> tuple[str, ...]:
    """Build a no-network, shadow-write-only acceptance command."""
    for required in (bwrap, repo_root, canonical_task_root, provenance_root, shadow_root, python):
        if not required.exists():
            raise CanaryRuntimeError(f"acceptance sandbox path missing: {required}")
    return (
        str(bwrap),
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--ro-bind", "/", "/",
        "--tmpfs", "/home",
        "--tmpfs", "/tmp",
        "--tmpfs", str(canonical_task_root),
        "--tmpfs", str(provenance_root),
        "--bind", str(shadow_root), str(shadow_root),
        "--proc", "/proc",
        "--dev", "/dev",
        "--chdir", str(shadow_root),
        "--setenv", "HOME", "/tmp",
        "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
        "--setenv", "PYTHONPATH", pythonpath,
        "--setenv", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1",
        "--setenv", "PYTEST_ADDOPTS", "--color=no --no-header --no-summary",
        str(python), "-m", "pytest", *tuple(relocated_argv),
    )


def run_bounded_command(
    *,
    argv: Sequence[str],
    timeout_seconds: int,
    maximum_output_bytes: int,
) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            list(argv),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds,
            check=False,
        )
        return int(completed.returncode), bounded_text(completed.stdout, maximum_output_bytes)
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        output = bounded_text(output + "\n<ELPIS_ACCEPTANCE_TIMEOUT>\n", maximum_output_bytes)
        return 124, output


def deterministic_run_projection(run_record: Mapping[str, Any]) -> dict[str, Any]:
    """Project out volatile process paths, timing, and capability nonces."""
    ticks = []
    for tick in run_record.get("ticks", []):
        projected = {
            "tick_index": tick.get("tick_index"),
            "prompt_digest": tick.get("prompt_digest"),
            "seed_digest": tick.get("seed_digest"),
            "request_digest": tick.get("request_digest"),
            "packet_digest": tick.get("packet_digest"),
            "packet_receipt_digest": tick.get("packet_receipt_digest"),
            "coding_tick_digest": tick.get("coding_tick_digest"),
            "generation": tick.get("generation"),
            "parse_status": tick.get("parse_status"),
            "parse_error": tick.get("parse_error"),
            "action": tick.get("action"),
            "patch_receipt": None if tick.get("patch_receipt") is None else {
                key: value
                for key, value in tick["patch_receipt"].items()
                if key not in ("acceptance_output_digest", "receipt_digest")
            },
            "acceptance_exit_code": tick.get("acceptance_exit_code"),
            "acceptance_output_normalized_digest": tick.get("acceptance_output_normalized_digest"),
        }
        ticks.append(projected)
    return {
        "schema": "elpis.p14.2b.deterministic-run-projection.v1",
        "source_run_id": run_record.get("source_run_id", run_record.get("run_id")),
        "task_id": run_record.get("task_id"),
        "family": run_record.get("family"),
        "lane": run_record.get("lane"),
        "mode": run_record.get("mode"),
        "maximum_ticks": run_record.get("maximum_ticks"),
        "model_runtime_manifest_digest": run_record.get("model_runtime_manifest_digest"),
        "first_patch_accepted": run_record.get("first_patch_accepted"),
        "completed": run_record.get("completed"),
        "blocker_reported": run_record.get("blocker_reported"),
        "ticks": ticks,
    }
