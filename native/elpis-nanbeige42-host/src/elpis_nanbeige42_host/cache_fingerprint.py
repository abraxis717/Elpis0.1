"""Exact cache fingerprints for NO_OP corruption detection."""
from __future__ import annotations

import hashlib
from typing import Any, Iterable


def _iter_cache_tensors(value: Any, path: str = "cache") -> Iterable[tuple[str, Any]]:
    if value is None:
        return
    if hasattr(value, "to_legacy_cache") and callable(value.to_legacy_cache):
        value = value.to_legacy_cache()
    if hasattr(value, "detach") and hasattr(value, "shape") and hasattr(value, "dtype"):
        yield path, value
        return
    if isinstance(value, dict):
        for key in sorted(value):
            yield from _iter_cache_tensors(value[key], f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _iter_cache_tensors(child, f"{path}[{index}]")
        return
    key_cache = getattr(value, "key_cache", None)
    value_cache = getattr(value, "value_cache", None)
    if key_cache is not None or value_cache is not None:
        yield from _iter_cache_tensors(key_cache, f"{path}.key_cache")
        yield from _iter_cache_tensors(value_cache, f"{path}.value_cache")
        return
    raise TypeError(f"unsupported cache node at {path}: {type(value)!r}")


def cache_fingerprint(cache: Any) -> str:
    digest = hashlib.sha256()
    count = 0
    for path, tensor in _iter_cache_tensors(cache):
        count += 1
        detached = tensor.detach().contiguous().to("cpu")
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(detached.dtype).encode("ascii"))
        digest.update(b"\0")
        digest.update(",".join(map(str, detached.shape)).encode("ascii"))
        digest.update(b"\0")
        digest.update(detached.numpy().tobytes(order="C"))
    if count == 0:
        raise ValueError("cache contains no tensors")
    return "sha256:" + digest.hexdigest()
