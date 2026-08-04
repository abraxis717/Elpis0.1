"""Deterministic runtime probes used by P14.1."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
from typing import Any

import numpy as np

from .cache_fingerprint import cache_fingerprint
from .digest import canonical_digest
from .hooks import default_registry
from .runtime_hooks import RuntimeHookSession, tensor_digest
from .schemas import ControlMode, GenerationShape


def prompt_digest(prompt: str) -> str:
    return "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _tokenize(tokenizer: Any, prompt: str, input_device: Any) -> tuple[Any, Any]:
    import torch

    encoded = tokenizer(prompt, return_tensors="pt", add_special_tokens=True)
    ids = encoded["input_ids"].to(input_device)
    mask = encoded.get("attention_mask", torch.ones_like(ids)).to(input_device)
    if ids.ndim != 2 or ids.shape[0] != 1 or int(ids.shape[1]) < 2:
        raise RuntimeError("qualification prompt tokenization drift")
    return ids, mask


def _base_forward(
    *, model: Any, input_ids: Any, attention_mask: Any, past_key_values: Any | None
) -> tuple[Any, Any, Any]:
    kwargs: dict[str, Any] = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "use_cache": True,
        "output_hidden_states": False,
        "return_dict": True,
    }
    if past_key_values is not None:
        kwargs["past_key_values"] = past_key_values
    out = model.model(**kwargs)
    hidden = out.last_hidden_state[:, -1, :]
    logits = model.lm_head(hidden)
    return logits, out.past_key_values, out


def run_plain(*, model: Any, tokenizer: Any, prompt: str, input_device: Any) -> dict[str, Any]:
    import torch

    ids, mask = _tokenize(tokenizer, prompt, input_device)
    with torch.inference_mode():
        prefill_logits, prefill_cache, _ = _base_forward(
            model=model, input_ids=ids, attention_mask=mask, past_key_values=None
        )
        prefill_cache_fingerprint = cache_fingerprint(prefill_cache)
        token = prefill_logits.float().argmax(dim=-1, keepdim=True)
        decode_mask = torch.cat((mask, torch.ones_like(token, dtype=mask.dtype)), dim=1)
        decode_logits, decode_cache, _ = _base_forward(
            model=model,
            input_ids=token,
            attention_mask=decode_mask,
            past_key_values=prefill_cache,
        )
    return {
        "prefill_tokens": int(ids.shape[1]),
        "greedy_token_id": int(token.item()),
        "prefill_logits_digest": tensor_digest(prefill_logits.float()),
        "decode_logits_digest": tensor_digest(decode_logits.float()),
        "prefill_cache_fingerprint": prefill_cache_fingerprint,
        "decode_cache_fingerprint": cache_fingerprint(decode_cache),
    }


def run_instrumented(
    *,
    model: Any,
    tokenizer: Any,
    prompt: str,
    input_device: Any,
    mode: ControlMode,
    residual: np.ndarray | None,
    logit_bias: np.ndarray | None,
) -> dict[str, Any]:
    import torch

    ids, mask = _tokenize(tokenizer, prompt, input_device)
    shape = GenerationShape(num_loops=2, prefill_tokens=int(ids.shape[1]), decode_steps=1)
    session = RuntimeHookSession(
        model=model,
        mode=mode,
        residual=residual,
        logit_bias=logit_bias,
        registry=default_registry(),
    )
    session.install()
    session.record_input_assembly(prompt_digest(prompt))
    try:
        with torch.inference_mode():
            session.begin_forward(phase="prefill", sequence_length=int(ids.shape[1]))
            prefill_logits, prefill_cache, _ = _base_forward(
                model=model, input_ids=ids, attention_mask=mask, past_key_values=None
            )
            session.end_forward()
            prefill_cache_fingerprint = cache_fingerprint(prefill_cache)
            token = prefill_logits.float().argmax(dim=-1, keepdim=True)
            decode_mask = torch.cat((mask, torch.ones_like(token, dtype=mask.dtype)), dim=1)
            session.begin_forward(phase="decode", sequence_length=1)
            decode_logits, decode_cache, _ = _base_forward(
                model=model,
                input_ids=token,
                attention_mask=decode_mask,
                past_key_values=prefill_cache,
            )
            session.end_forward()
        session.validate(shape)
        result = {
            "mode": mode.value,
            "generation_shape": asdict(shape),
            "greedy_token_id": int(token.item()),
            "prefill_logits_digest": tensor_digest(prefill_logits.float()),
            "decode_logits_digest": tensor_digest(decode_logits.float()),
            "prefill_cache_fingerprint": prefill_cache_fingerprint,
            "decode_cache_fingerprint": cache_fingerprint(decode_cache),
            "hook_trace_digest": session.trace_digest,
            "checkpoint_digests": {
                key: canonical_digest(value)
                for key, value in sorted(session.tensor_digests.items())
                if key not in ("INPUT_ASSEMBLY", "POST_LOGIT")
            },
            "raw_logit_digests": list(session.raw_logit_digests),
            "controlled_logit_digests": list(session.controlled_logit_digests),
            "raw_logits": [value.copy() for value in session.raw_logits],
            "controlled_logits": [value.copy() for value in session.controlled_logits],
            "ulp_intended": [value.copy() for value in session.ulp_intended],
            "ulp_realized": [value.copy() for value in session.ulp_realized],
            "ulp_spacing": [value.copy() for value in session.ulp_spacing],
        }
    finally:
        session.remove()
    return result
