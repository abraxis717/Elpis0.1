from __future__ import annotations

import hashlib
from pathlib import Path

import torch
from torch import nn
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file, save_file

from .vendor.trm import TinyRecursiveReasoningModel_ACTV1

MODEL_REPO = "Sanjin2024/TinyRecursiveModels-Sudoku-Extreme-mlp"
MODEL_REVISION = "256f32fcbe7123e8bf8c449410773a5ad311dbc5"
MODEL_FILENAME = "step_16275"
MODEL_SHA256 = "20e9dc7ebf83b9b41a8b3f58f5fd94ee3a7eb0b0d245bdeeb14e2f1488d1daaf"
UPSTREAM_TRM_COMMIT = "c01103738605ba39d1430519b1ee0c62f4c707f8d"
REGISTERED_PARAMETER_COUNT = 5_028_866


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "elpis" / "models" / "trm-sudoku-extreme-mlp"


def _ensure_torch_buffer_compat() -> None:
    if hasattr(nn, "Buffer"):
        return

    def _buffer_compat(data, persistent=True):
        del persistent
        return data

    nn.Buffer = _buffer_compat  # type: ignore[attr-defined]


def _register_existing_buffer(module: nn.Module, name: str, persistent: bool) -> None:
    if name in module._buffers:
        return
    value = getattr(module, name, None)
    if value is None:
        raise RuntimeError(f"required compatibility buffer {name!r} absent")
    delattr(module, name)
    module.register_buffer(name, value, persistent=persistent)


def _repair_torch_buffers(model: TinyRecursiveReasoningModel_ACTV1) -> None:
    inner = model.inner
    _register_existing_buffer(inner, "H_init", True)
    _register_existing_buffer(inner, "L_init", True)

    if inner.config.puzzle_emb_ndim > 0:
        sparse = inner.puzzle_emb
        _register_existing_buffer(sparse, "weights", True)
        _register_existing_buffer(sparse, "local_weights", False)
        _register_existing_buffer(sparse, "local_ids", False)


def _extract_state_dict(payload: object) -> dict[str, torch.Tensor]:
    if not isinstance(payload, dict):
        raise RuntimeError("checkpoint root is not a mapping")

    for key in ("model", "model_state_dict", "state_dict"):
        nested = payload.get(key)
        if (
            isinstance(nested, dict)
            and nested
            and all(isinstance(name, str) and torch.is_tensor(value) for name, value in nested.items())
        ):
            return dict(nested)

    if payload and all(
        isinstance(name, str) and torch.is_tensor(value)
        for name, value in payload.items()
    ):
        return dict(payload)

    raise RuntimeError("no pure tensor state dictionary found in checkpoint")


def _strip_prefix(
    state: dict[str, torch.Tensor],
    prefix: str,
) -> dict[str, torch.Tensor]:
    if state and all(key.startswith(prefix) for key in state):
        return {key[len(prefix):]: value for key, value in state.items()}
    return state


def _state_variants(
    state: dict[str, torch.Tensor],
) -> tuple[dict[str, torch.Tensor], ...]:
    variants: list[dict[str, torch.Tensor]] = []
    queue = [state]
    seen: set[tuple[str, ...]] = set()

    while queue:
        candidate = queue.pop(0)
        signature = tuple(sorted(candidate))
        if signature in seen:
            continue

        seen.add(signature)
        variants.append(candidate)

        for prefix in ("_orig_mod.", "module.", "model."):
            stripped = _strip_prefix(candidate, prefix)
            if tuple(sorted(stripped)) != signature:
                queue.append(stripped)

        if candidate and not all(key.startswith("inner.") for key in candidate):
            queue.append({"inner." + key: value for key, value in candidate.items()})

    return tuple(variants)


def _device_from_name(name: str) -> torch.device:
    if name != "auto":
        return torch.device(name)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def model_config(device: torch.device) -> dict[str, object]:
    forward_dtype = "bfloat16" if device.type == "cuda" else "float32"
    return {
        "batch_size": 1,
        "seq_len": 81,
        "puzzle_emb_ndim": 512,
        "num_puzzle_identifiers": 1,
        "vocab_size": 11,
        "H_cycles": 3,
        "L_cycles": 6,
        "H_layers": 0,
        "L_layers": 2,
        "hidden_size": 512,
        "expansion": 4.0,
        "num_heads": 8,
        "pos_encodings": "none",
        "halt_max_steps": 16,
        "halt_exploration_prob": 0.1,
        "forward_dtype": forward_dtype,
        "mlp_t": True,
        "puzzle_emb_len": 16,
        "no_ACT_continue": True,
    }


def _new_model(device: torch.device) -> TinyRecursiveReasoningModel_ACTV1:
    _ensure_torch_buffer_compat()
    torch.manual_seed(0)
    model = TinyRecursiveReasoningModel_ACTV1(model_config(device))
    _repair_torch_buffers(model)
    count = sum(int(parameter.numel()) for parameter in model.parameters())
    if count != REGISTERED_PARAMETER_COUNT:
        raise RuntimeError(
            f"registered parameter ABI mismatch: {count} != {REGISTERED_PARAMETER_COUNT}"
        )
    return model


def _select_strict_state(
    raw_state: dict[str, torch.Tensor],
    model: TinyRecursiveReasoningModel_ACTV1,
) -> dict[str, torch.Tensor]:
    expected_keys = set(model.state_dict())

    for candidate in _state_variants(raw_state):
        if set(candidate) == expected_keys:
            return {
                key: value.detach().cpu().contiguous()
                for key, value in candidate.items()
            }

    raw_keys = set(raw_state)
    raise RuntimeError(
        "no strict checkpoint normalization matched model state: "
        f"raw={len(raw_keys)} expected={len(expected_keys)} "
        f"missing={sorted(expected_keys - raw_keys)[:8]} "
        f"unexpected={sorted(raw_keys - expected_keys)[:8]}"
    )


def fetch_model(cache_dir: Path | None = None, force: bool = False) -> Path:
    cache_dir = Path(cache_dir or default_cache_dir())
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / "model.safetensors"

    if target.exists() and not force:
        verify_model(target)
        return target

    raw = Path(
        hf_hub_download(
            repo_id=MODEL_REPO,
            filename=MODEL_FILENAME,
            revision=MODEL_REVISION,
        )
    )

    observed = _sha256(raw)
    if observed != MODEL_SHA256:
        raise RuntimeError(
            f"checkpoint SHA-256 mismatch: {observed} != {MODEL_SHA256}"
        )

    payload = torch.load(raw, map_location="cpu", weights_only=True)
    raw_state = _extract_state_dict(payload)

    model = _new_model(torch.device("cpu"))
    normalized = _select_strict_state(raw_state, model)

    load_result = model.load_state_dict(normalized, strict=True)
    if load_result.missing_keys or load_result.unexpected_keys:
        raise RuntimeError("strict checkpoint verification produced key drift")

    save_file(
        normalized,
        str(target),
        metadata={
            "source_repo": MODEL_REPO,
            "source_revision": MODEL_REVISION,
            "source_sha256": MODEL_SHA256,
            "upstream_trm_commit": UPSTREAM_TRM_COMMIT,
            "registered_parameter_count": str(REGISTERED_PARAMETER_COUNT),
        },
    )

    verify_model(target)
    return target


def verify_model(path: Path) -> dict[str, object]:
    path = Path(path)
    state = load_file(str(path), device="cpu")

    model = _new_model(torch.device("cpu"))
    load_result = model.load_state_dict(state, strict=True)

    if load_result.missing_keys or load_result.unexpected_keys:
        raise RuntimeError(
            "checkpoint/model ABI mismatch: "
            f"missing={list(load_result.missing_keys)} "
            f"unexpected={list(load_result.unexpected_keys)}"
        )

    return {
        "path": str(path),
        "sha256": _sha256(path),
        "tensor_count": len(state),
        "registered_parameters": REGISTERED_PARAMETER_COUNT,
        "state_elements": sum(int(tensor.numel()) for tensor in state.values()),
        "strict_load": True,
    }


def load_model(
    model_path: Path | None = None,
    device: str = "auto",
) -> tuple[TinyRecursiveReasoningModel_ACTV1, torch.device]:
    model_path = Path(model_path or fetch_model())
    target_device = _device_from_name(device)

    model = _new_model(target_device)
    state = load_file(str(model_path), device="cpu")
    load_result = model.load_state_dict(state, strict=True)

    if load_result.missing_keys or load_result.unexpected_keys:
        raise RuntimeError(
            "checkpoint/model ABI mismatch: "
            f"missing={list(load_result.missing_keys)} "
            f"unexpected={list(load_result.unexpected_keys)}"
        )

    model.to(target_device)
    model.eval()
    return model, target_device
