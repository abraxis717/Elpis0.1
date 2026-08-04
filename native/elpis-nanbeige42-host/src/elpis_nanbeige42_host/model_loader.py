"""Standalone Nanbeige4.2 loader for P14.1.

This module deliberately does not import experiment scripts. It uses only the
sealed execution view and reusable runtime components.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .digest import canonical_digest
from .errors import ModelIdentityDrift

DEFAULT_GPU_MAX_MEMORY_MIB = 3600
DEFAULT_CPU_MAX_MEMORY_MIB = 22528
MIN_GPU_HEADROOM_MIB = 2500
MIN_CPU_HEADROOM_MIB = 12288


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ModelIdentityDrift(message)


def _mem_available_mib() -> int:
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    raise ModelIdentityDrift("MemAvailable missing")


def _identity_record(value: Any) -> Any:
    from enum import Enum

    if is_dataclass(value):
        return _identity_record(asdict(value))
    if isinstance(value, Enum):
        return _identity_record(value.value)
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        key_origins: dict[str, Any] = {}
        for key, child in value.items():
            normalized_key = str(key)
            if normalized_key in result:
                prior = key_origins[normalized_key]
                raise ModelIdentityDrift(
                    "identity mapping key collision after string normalization: "
                    f"{prior!r} versus {key!r}"
                )
            key_origins[normalized_key] = key
            result[normalized_key] = _identity_record(child)
        return result
    if isinstance(value, (list, tuple)):
        return [_identity_record(child) for child in value]
    if hasattr(value, "__dict__"):
        return _identity_record(dict(value.__dict__))
    return str(value)


def _tokenizer_digest(tokenizer: Any) -> str:
    backend = getattr(tokenizer, "backend_tokenizer", None)
    if backend is not None and hasattr(backend, "to_str"):
        payload = backend.to_str().encode("utf-8")
    else:
        payload = json.dumps(tokenizer.get_vocab(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    record = {
        "backend_sha256": hashlib.sha256(payload).hexdigest(),
        "class": tokenizer.__class__.__qualname__,
        "vocab_size": int(len(tokenizer)),
        "bos_token_id": tokenizer.bos_token_id,
        "eos_token_id": tokenizer.eos_token_id,
        "pad_token_id": tokenizer.pad_token_id,
    }
    return canonical_digest(record)


def load_nanbeige42(*, repo_root: Path, view_root: Path | None = None) -> tuple[Any, Any, Any, dict[str, Any]]:
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from elpis_header.nanbeige_dock.real_phase2 import build_real_model_identity, verify_execution_view

    _require(transformers.__version__ == "4.51.0", "Transformers 4.51.0 required")
    _require(os.environ.get("CUDA_VISIBLE_DEVICES") == "1", "physical GPU 1 required")
    _require(os.environ.get("CUBLAS_WORKSPACE_CONFIG") == ":16:8", "deterministic cuBLAS workspace missing")
    _require(torch.cuda.is_available(), "CUDA unavailable")
    _require(torch.cuda.device_count() == 1, "exactly one GPU must be visible")
    gpu_name = torch.cuda.get_device_name(0)
    _require("2080" in gpu_name.upper(), f"visible GPU is not RTX 2080: {gpu_name}")
    total_mib = int(torch.cuda.get_device_properties(0).total_memory // (1024 * 1024))
    _require(total_mib < 10000, "runtime refuses non-8GB-class visible GPU")

    gpu_mib = int(os.environ.get("P14_1_RTX2080_GPU_MAX_MEMORY_MIB", str(DEFAULT_GPU_MAX_MEMORY_MIB)))
    cpu_mib = int(os.environ.get("P14_1_RTX2080_CPU_MAX_MEMORY_MIB", str(DEFAULT_CPU_MAX_MEMORY_MIB)))
    _require(2800 <= gpu_mib <= 4400, "GPU memory cap outside 2800..4400 MiB")
    _require(16384 <= cpu_mib <= 49152, "CPU model cap outside 16384..49152 MiB")
    available = _mem_available_mib()
    _require(available - cpu_mib >= MIN_CPU_HEADROOM_MIB, "insufficient CPU activation headroom")
    _require(total_mib - gpu_mib >= MIN_GPU_HEADROOM_MIB, "insufficient GPU activation headroom")

    view = verify_execution_view(repo_root, view_root)
    identity = _identity_record(build_real_model_identity(view))

    tokenizer = AutoTokenizer.from_pretrained(
        str(view.root), local_files_only=True, trust_remote_code=True, use_fast=True
    )
    _require(bool(getattr(tokenizer, "is_fast", False)), "fast tokenizer required")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    torch.set_num_threads(2)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False

    with tempfile.TemporaryDirectory(prefix="p14-1-load-", dir="$HOME") as temporary_offload:
        model = AutoModelForCausalLM.from_pretrained(
            str(view.root),
            local_files_only=True,
            trust_remote_code=True,
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
            device_map="auto",
            max_memory={0: f"{gpu_mib}MiB", "cpu": f"{cpu_mib}MiB"},
            offload_state_dict=True,
            offload_folder=temporary_offload,
            attn_implementation="eager",
        )
        model.eval()
        _require(len(model.model.layers) == 22, "decoder layer count drift")
        _require(int(model.config.num_loops) == 2, "num_loops drift")
        _require(bool(model.config.skip_loop_final_norm) is False, "loop-final norm drift")
        device_map = {str(k): str(v) for k, v in dict(getattr(model, "hf_device_map", {})).items()}
        _require(all(value.lower() != "disk" for value in device_map.values()), "final disk offload detected")

    for parameter in model.parameters():
        parameter.requires_grad_(False)
        parameter.grad = None

    input_device = next(model.get_input_embeddings().parameters()).device
    model_record = {
        "schema": "elpis.nanbeige42.model-runtime-manifest.v1",
        "execution_view_identity": identity,
        "execution_view_identity_digest": canonical_digest(identity),
        "config_digest": canonical_digest(_identity_record(model.config.to_dict())),
        "tokenizer_digest": _tokenizer_digest(tokenizer),
        "transformers_version": transformers.__version__,
        "torch_version": torch.__version__,
        "model_class": model.__class__.__qualname__,
        "tokenizer_class": tokenizer.__class__.__qualname__,
        "hidden_width": int(model.config.hidden_size),
        "layer_count": int(len(model.model.layers)),
        "num_loops": int(model.config.num_loops),
        "skip_loop_final_norm": bool(model.config.skip_loop_final_norm),
        "parameter_dtype": str(next(model.parameters()).dtype),
        "attention_implementation": "eager",
        "device_map": device_map,
        "visible_gpu_name": gpu_name,
        "visible_gpu_total_mib": total_mib,
        "gpu_memory_cap_mib": gpu_mib,
        "cpu_memory_cap_mib": cpu_mib,
        "model_runtime_manifest_digest": "",
    }
    model_record["model_runtime_manifest_digest"] = canonical_digest(
        model_record, digest_field="model_runtime_manifest_digest"
    )
    volatile = {
        "system_mem_available_before_load_mib": available,
        "input_device": str(input_device),
    }
    return model, tokenizer, input_device, {"deterministic": model_record, "volatile": volatile}
