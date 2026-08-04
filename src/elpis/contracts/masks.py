# elpis/contracts/masks.py — §VII ruling: masks are NOT one concept. Four types.
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


class MaskError(ValueError): ...


def _frozen_bool(a: np.ndarray, shape: tuple[int, ...]) -> np.ndarray:
    arr = np.ascontiguousarray(a, dtype=bool)
    if arr.shape != shape:
        raise MaskError(f"mask shape {arr.shape} != {shape}")
    arr.setflags(write=False)
    return arr


@dataclass(frozen=True, slots=True)
class ValidityMask:            # which Grid81 cells are semantically valid
    bits: np.ndarray
    def __post_init__(self):
        object.__setattr__(self, "bits", _frozen_bool(self.bits, (81,)))
    def to_bytes(self) -> bytes: return np.packbits(self.bits).tobytes()


@dataclass(frozen=True, slots=True)
class RegionMask:              # declared child-expansion region (Q23 ownership)
    bits: np.ndarray
    def __post_init__(self):
        object.__setattr__(self, "bits", _frozen_bool(self.bits, (81,)))


@dataclass(frozen=True, slots=True)
class LogitMask:               # per-cell symbol legality; applied as -inf at ONE site
    bits: np.ndarray
    def __post_init__(self):
        object.__setattr__(self, "bits", _frozen_bool(self.bits, (81, 10)))


@dataclass(frozen=True, slots=True)
class BatchMask:               # batch validity
    bits: np.ndarray
    def __post_init__(self):
        arr = np.ascontiguousarray(self.bits, dtype=bool)
        if arr.ndim != 1:
            raise MaskError("batch mask must be 1-D")
        arr.setflags(write=False)
        object.__setattr__(self, "bits", arr)


