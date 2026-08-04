# elpis/contracts/codecs/grid_numpy_torch.py — §IV Option B: Grid81 is
# canonically BYTES (row-major, uint8, symbols 0..9, length 81·B); NumPy and
# Torch are VIEWS produced only here. Laws (T1, tested):
#   np_from_torch(torch_from_np(G)) == G           for every valid G
#   bytes round-trips through both views bit-exactly
#   all conversions COPY (never alias), detach, land on CPU for NumPy,
#   validate range, enforce C-contiguity; implicit .numpy()/as_tensor()
#   anywhere else in the codebase is a contract violation.
# Spine keeps NumPy (deterministic CPU boundary); Torch owns learned state only.
from __future__ import annotations

import numpy as np
import torch

SYMBOLS = 10
CELLS = 81


class GridCodecError(ValueError): ...


# ------------------------------------------------------------- bytes core
def bytes_from_np(g: np.ndarray) -> bytes:
    a = np.ascontiguousarray(g)
    if a.dtype != np.uint8:
        raise GridCodecError(f"grid dtype must be uint8, got {a.dtype}")
    if a.ndim == 2 and a.shape == (9, 9):
        a = a.reshape(1, CELLS)
    elif a.ndim == 1 and a.shape == (CELLS,):
        a = a.reshape(1, CELLS)
    elif a.ndim == 2 and a.shape[1] == CELLS:
        pass
    else:
        raise GridCodecError(f"grid shape must be (9,9), (81,) or (B,81); got {a.shape}")
    if a.max(initial=0) >= SYMBOLS:
        raise GridCodecError("symbol out of range 0..9")
    return a.tobytes()


def np_from_bytes(b: bytes, *, batch: int | None = None) -> np.ndarray:
    if len(b) % CELLS:
        raise GridCodecError(f"byte length {len(b)} not a multiple of 81")
    B = len(b) // CELLS
    if batch is not None and batch != B:
        raise GridCodecError(f"declared batch {batch} != {B}")
    a = np.frombuffer(b, dtype=np.uint8).reshape(B, CELLS).copy()  # COPY: no view
    if a.max(initial=0) >= SYMBOLS:
        raise GridCodecError("symbol out of range 0..9")
    a.setflags(write=False)
    return a


def grid9x9(a: np.ndarray) -> np.ndarray:
    """Display/Spine-local view law: [81] <-> [9,9] row-major."""
    if a.shape == (CELLS,):
        return a.reshape(9, 9)
    if a.shape[-1] == CELLS and a.ndim == 2 and a.shape[0] == 1:
        return a.reshape(9, 9)
    raise GridCodecError(f"cannot view {a.shape} as 9x9")


# ---------------------------------------------------------- named boundaries
def torch_from_np(g: np.ndarray, *, device: str | torch.device = "cpu",
                  dtype: torch.dtype = torch.long) -> torch.Tensor:
    """np uint8 -> torch (default long, embedding-ready). Copy, no grad."""
    b = bytes_from_np(g)
    B = len(b) // CELLS
    t = torch.frombuffer(bytearray(b), dtype=torch.uint8).reshape(B, CELLS)
    return t.to(device=device, dtype=dtype, copy=True).requires_grad_(False)


def np_from_torch(t: torch.Tensor) -> np.ndarray:
    """torch -> np uint8[B,81]. CPU, detached, copied, range-validated."""
    if t.dtype not in (torch.uint8, torch.int32, torch.int64):
        raise GridCodecError(f"symbol tensor dtype must be integral, got {t.dtype}")
    if t.ndim == 1:
        t = t.reshape(1, -1)
    if t.ndim != 2 or t.shape[1] != CELLS:
        raise GridCodecError(f"symbol tensor must be [B,81], got {tuple(t.shape)}")
    a = t.detach().to("cpu", copy=True).numpy()
    if a.min(initial=0) < 0 or a.max(initial=0) >= SYMBOLS:
        raise GridCodecError("symbol out of range 0..9")
    out = np.ascontiguousarray(a.astype(np.uint8))
    out.setflags(write=False)
    return out


def project_logits(logits: torch.Tensor) -> torch.Tensor:
    """THE single named projection [B,81,10] -> [B,81] (long).
    Deterministic tie-break: torch.argmax returns the first maximal index.
    Grid81 argmax is discontinuous: contraction claims stop here (F0 §6)."""
    if logits.ndim != 3 or logits.shape[1:] != (CELLS, SYMBOLS):
        raise GridCodecError(f"logits must be [B,81,10], got {tuple(logits.shape)}")
    return torch.argmax(logits.detach(), dim=-1)
