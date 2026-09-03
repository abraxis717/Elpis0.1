from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import torch
from huggingface_hub import hf_hub_download

from .vendor.fprm.models.fixed_point_reasoning.fp_trm_singlez import (
    FPTinyRecursiveReasoningModelSingleZ_ACTV1,
)


MODEL_REPO = "fixed-point-reasoners/fprm"

# Canonical Elpis runtime name. Do not rename this to the upstream filename.
MODEL_FILENAME = "FPRM.Samsung_TRM"

# Provenance only. This is never the local/runtime filename.
UPSTREAM_MODEL_FILENAME = "sudoku/step_78120"

MODEL_SHA256 = (
    "6daec5f499d115beb14e23f3a9cf56d1166b99c1ccd36b185a19ea5dfec9a137"
)

QUALIFICATION_RUNTIME_HEAD = "d0be6fc2311f69a9f39964f21ecb0c50ac425b97"

STATE_KEY_COUNT = 26
STATE_ELEMENTS = 13_656_578
REGISTERED_PARAMETER_COUNT = 6_833_666

FPRM_MAX_ITER = 1000
FPRM_STEPSIZE_DECAY = 0.997
FPRM_DECAY_PATIENCE = 10
FPRM_RETRY_SEEDS = (0, 1)

_PREFIX = "_orig_mod.model."


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_cache_dir() -> Path:
    override = os.environ.get("ELPIS_FPRM_MODEL_DIR")
    if override:
        return Path(override)
    return _repo_root() / "models"


def default_model_path() -> Path:
    override = os.environ.get("ELPIS_FPRM_MODEL")
    if override:
        return Path(override)
    return default_cache_dir() / MODEL_FILENAME


def _config_path() -> Path:
    return (
        Path(__file__).resolve().parent
        / "vendor"
        / "fprm"
        / "sudoku_inference_config.json"
    )


def _model_config(device: torch.device) -> dict[str, object]:
    cfg = json.loads(_config_path().read_text())

    # Preserve the qualified FPRM inference configuration.
    # Runtime batches may contain fewer puzzles, but the model-side
    # batch_size remains 32 exactly as in fprm_eval32 qualification.
    cfg["batch_size"] = 32
    cfg["seq_len"] = 81
    cfg["vocab_size"] = 11
    cfg["num_puzzle_identifiers"] = 1
    cfg["max_iter_eval"] = FPRM_MAX_ITER

    if device.type == "cuda":
        cfg["forward_dtype"] = "bfloat16"
    else:
        cfg["forward_dtype"] = "float32"

    return cfg


def _device_from_name(name: str) -> torch.device:
    if name != "auto":
        return torch.device(name)

    configured = os.environ.get("ELPIS_FPRM_DEVICE")
    if configured:
        return torch.device(configured)

    if torch.cuda.is_available():
        return torch.device("cuda")

    return torch.device("cpu")


def _extract_state_dict(payload: object) -> dict[str, torch.Tensor]:
    if not isinstance(payload, dict):
        raise RuntimeError("FPRM checkpoint root is not a mapping")

    for key in ("model", "model_state_dict", "state_dict"):
        nested = payload.get(key)
        if (
            isinstance(nested, dict)
            and nested
            and all(
                isinstance(name, str) and torch.is_tensor(value)
                for name, value in nested.items()
            )
        ):
            payload = nested
            break

    if not (
        isinstance(payload, dict)
        and payload
        and all(
            isinstance(name, str) and torch.is_tensor(value)
            for name, value in payload.items()
        )
    ):
        raise RuntimeError("FPRM checkpoint does not contain a pure tensor state")

    state = dict(payload)

    if state and all(name.startswith(_PREFIX) for name in state):
        state = {
            name[len(_PREFIX):]: value
            for name, value in state.items()
        }

    return state


def _load_checkpoint_state(path: Path) -> dict[str, torch.Tensor]:
    observed = _sha256(path)
    if observed != MODEL_SHA256:
        raise RuntimeError(
            f"FPRM checkpoint SHA-256 mismatch: {observed} != {MODEL_SHA256}"
        )

    payload = torch.load(path, map_location="cpu", weights_only=True)
    state = _extract_state_dict(payload)

    if len(state) != STATE_KEY_COUNT:
        raise RuntimeError(
            f"FPRM state-key ABI mismatch: {len(state)} != {STATE_KEY_COUNT}"
        )

    elements = sum(int(tensor.numel()) for tensor in state.values())
    if elements != STATE_ELEMENTS:
        raise RuntimeError(
            f"FPRM state-element ABI mismatch: {elements} != {STATE_ELEMENTS}"
        )

    return state


def _new_model(device: torch.device) -> FPTinyRecursiveReasoningModelSingleZ_ACTV1:
    cfg = _model_config(device)

    # Match the qualified FPRM evaluator: construct directly on the target
    # device. The vendored Turing-compatible initializer handles GPU1.
    with torch.device(device):
        model = FPTinyRecursiveReasoningModelSingleZ_ACTV1(cfg)

    count = sum(int(parameter.numel()) for parameter in model.parameters())
    if count != REGISTERED_PARAMETER_COUNT:
        raise RuntimeError(
            "FPRM registered-parameter ABI mismatch: "
            f"{count} != {REGISTERED_PARAMETER_COUNT}"
        )

    return model


def verify_model(path: Path) -> dict[str, object]:
    path = Path(path)

    if path.name != MODEL_FILENAME:
        raise RuntimeError(
            f"canonical FPRM checkpoint filename must be {MODEL_FILENAME!r}; "
            f"got {path.name!r}"
        )

    state = _load_checkpoint_state(path)
    model = _new_model(torch.device("cpu"))

    expected = set(model.state_dict())
    observed = set(state)

    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)

    if missing or unexpected:
        raise RuntimeError(
            "strict FPRM checkpoint ABI mismatch: "
            f"missing={missing[:8]} unexpected={unexpected[:8]}"
        )

    model.load_state_dict(state, strict=True)

    return {
        "path": str(path),
        "filename": MODEL_FILENAME,
        "sha256": _sha256(path),
        "source_repo": MODEL_REPO,
        "upstream_checkpoint": UPSTREAM_MODEL_FILENAME,
        "qualification_runtime_head": QUALIFICATION_RUNTIME_HEAD,
        "state_keys": len(state),
        "state_elements": STATE_ELEMENTS,
        "registered_parameters": REGISTERED_PARAMETER_COUNT,
        "strict_load": True,
    }


def fetch_model(
    cache_dir: Path | None = None,
    force: bool = False,
) -> Path:
    cache_dir = Path(cache_dir or default_cache_dir())
    cache_dir.mkdir(parents=True, exist_ok=True)

    target = cache_dir / MODEL_FILENAME

    if target.exists() and not force:
        verify_model(target)
        return target

    hf_cache = cache_dir / ".hf-cache"
    hf_cache.mkdir(parents=True, exist_ok=True)

    raw = Path(
        hf_hub_download(
            repo_id=MODEL_REPO,
            filename=UPSTREAM_MODEL_FILENAME,
            cache_dir=str(hf_cache),
        )
    )

    observed = _sha256(raw)
    if observed != MODEL_SHA256:
        raise RuntimeError(
            "downloaded FPRM authority mismatch: "
            f"{observed} != {MODEL_SHA256}"
        )

    tmp = target.with_name(target.name + ".tmp")
    shutil.copyfile(raw, tmp)
    tmp.replace(target)

    verify_model(target)
    return target


def load_model(
    model_path: Path | None = None,
    device: str = "auto",
    seed: int | None = None,
) -> tuple[FPTinyRecursiveReasoningModelSingleZ_ACTV1, torch.device]:
    path = Path(model_path or default_model_path())

    if not path.exists():
        if model_path is not None:
            raise FileNotFoundError(path)
        path = fetch_model()

    verify_model(path)

    target_device = _device_from_name(device)
    state = _load_checkpoint_state(path)

    # The official evaluator seeds BEFORE CUDA model construction. Model
    # construction consumes RNG before initial_carry(), so seed placement is
    # part of the reproducible FP-initialization contract.
    if seed is not None:
        torch.manual_seed(seed)
        if target_device.type == "cuda":
            torch.cuda.manual_seed_all(seed)

    model = _new_model(target_device)
    model.load_state_dict(state, strict=True)

    # set_num_iters() selects train/eval budget from model.training.
    # Enter eval mode FIRST so max_iter_eval=1000 is selected rather
    # than the training max_iter=12.
    model.eval()
    model.config.max_iter_eval = FPRM_MAX_ITER
    model.set_num_iters()

    inner = model.inner
    inner.L_optimizer.stepsize_decay = FPRM_STEPSIZE_DECAY
    inner.L_optimizer.decay_patience = FPRM_DECAY_PATIENCE

    return model, target_device
