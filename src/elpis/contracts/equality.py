# elpis/contracts/equality.py — §V predicates. bool(tensor) never occurs.
from __future__ import annotations
import numpy as np
import torch
from .envelope import ExecutionEnvelope


def same_instance(a: ExecutionEnvelope, b: ExecutionEnvelope) -> bool:
    return a.instance_id == b.instance_id


def same_content(a: ExecutionEnvelope, b: ExecutionEnvelope) -> bool:
    ca = a.content_checksum or a.payload.chi_p()
    cb = b.content_checksum or b.payload.chi_p()
    return ca == cb


def state_equal(x, y, *, atol: float = 1e-6, rtol: float = 1e-5,
                equal_nan: bool = False) -> bool:
    """Approximate numeric-state equality for tensor/array payload contents.
    Devices/dtypes normalized; signed zero compares equal (IEEE-754 ==);
    NaN != NaN unless equal_nan=True."""
    if isinstance(x, torch.Tensor) and isinstance(y, torch.Tensor):
        if x.shape != y.shape:
            return False
        xa = x.detach().to("cpu", torch.float64)
        ya = y.detach().to("cpu", torch.float64)
        return bool(torch.allclose(xa, ya, atol=atol, rtol=rtol,
                                   equal_nan=equal_nan))
    if isinstance(x, np.ndarray) and isinstance(y, np.ndarray):
        if x.shape != y.shape:
            return False
        return bool(np.allclose(x, y, atol=atol, rtol=rtol, equal_nan=equal_nan))
    raise TypeError("state_equal compares torch/torch or np/np")
