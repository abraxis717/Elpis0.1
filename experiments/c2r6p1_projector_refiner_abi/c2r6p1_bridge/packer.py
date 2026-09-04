"""D0.1 529-bit lossless packer compatibility for the bridge.

The vendored D0.1 ``structural_context_packer`` maps 529-bit 0/1 vectors
into a [16, 512] float32 context matrix using four dedicated prefix
positions (declared LO/HI, residual LO/HI) and zero-fills positions
4..15. This module exposes that EXACT packer for C2R6-P0 529-wide vectors
and proves roundtrip: ``unpack(pack(x)) == x`` for both planes.

The packer is the D0.1 authority (SHA-verified via _vendored_authority).
No second packer is defined here; this is a thin, typed wrapper plus the
roundtrip proof harness.
"""
from __future__ import annotations

from typing import Any, Sequence, Tuple

import torch

from _vendored_authority import packer as _packer_mod
from .contracts import (
    BridgeRejection,
    BridgeRejectionCode,
    BridgeRejectionError,
)

FEATURE_WIDTH = 529


def _reject(code: BridgeRejectionCode, **detail: Any) -> None:
    raise BridgeRejectionError(BridgeRejection(code=code, detail=detail))


def validate_bits(bits: Sequence[int], name: str) -> Tuple[int, ...]:
    values = tuple(int(b) for b in bits)
    if len(values) != FEATURE_WIDTH:
        _reject(
            BridgeRejectionCode.PACKER_REJECTED,
            name=name,
            width=len(values),
            expected=FEATURE_WIDTH,
        )
    for v in values:
        if v not in (0, 1):
            _reject(BridgeRejectionCode.PACKER_REJECTED, name=name, value=v)
    return values


def pack_529(
    declared529: Sequence[int],
    active529: Sequence[int],
) -> torch.Tensor:
    """Pack both 529-bit planes via the vendored D0.1 packer.

    Returns [16, 512] float32. Deterministic; pure.
    """
    p = _packer_mod()
    validate_bits(declared529, "declared529")
    validate_bits(active529, "active529")
    try:
        return p.pack_structural_context(list(declared529), list(active529))
    except Exception as exc:
        raise BridgeRejectionError(
            BridgeRejection(code=BridgeRejectionCode.PACKER_REJECTED,
                            detail={"error": str(exc)})
        ) from exc


def _unpack_raw(context: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    """Exact inverse (vendored D0.1). Returns (declared529, active529) tensors."""
    p = _packer_mod()
    try:
        decl, act = p.unpack_structural_context(context)
    except Exception as exc:
        raise BridgeRejectionError(
            BridgeRejection(code=BridgeRejectionCode.PACKER_REJECTED,
                            detail={"error": str(exc)})
        ) from exc
    return decl, act


def roundtrip_529(
    declared529: Sequence[int],
    active529: Sequence[int],
) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
    """encode -> decode; must equal the original for both planes."""
    ctx = pack_529(declared529, active529)
    d, a = _unpack_raw(ctx)
    d = tuple(int(x) for x in d.tolist())
    a = tuple(int(x) for x in a.tolist())
    if d != tuple(int(x) for x in declared529):
        _reject(BridgeRejectionCode.PACKER_REJECTED, plane="declared")
    if a != tuple(int(x) for x in active529):
        _reject(BridgeRejectionCode.PACKER_REJECTED, plane="active")
    return d, a


def one_hot(bit: int) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
    """(one-hot declared at bit, all-zero active). bit in 0..528."""
    if not 0 <= bit < FEATURE_WIDTH:
        _reject(BridgeRejectionCode.PACKER_REJECTED, bit=bit)
    decl = [0] * FEATURE_WIDTH
    decl[bit] = 1
    return tuple(decl), tuple(0 for _ in range(FEATURE_WIDTH))
