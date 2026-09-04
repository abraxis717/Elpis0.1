"""Deterministic structural-context packing for the 16-position prefix.

Rule (fixed, documented, no learned components) — C2R7-D0.1 lossless
repair. The D0 OR-fold (bits 512..528 OR'd into channels 0..16 of the
same position) ALIASED distinct structural features (e.g. feature 0
TERMINAL_RESOLUTION and feature 512 produced the identical channel
pattern). D0.1 replaces the fold with four dedicated prefix positions:

    context position 0 (PREFIX_DECLARED_LO):
        declared bits 0..511   -> channels 0..511
    context position 1 (PREFIX_DECLARED_HI):
        declared bits 512..528 -> channels 0..16
        channels 17..511 = 0
    context position 2 (PREFIX_RESIDUAL_LO):
        active residual bits 0..511 -> channels 0..511
    context position 3 (PREFIX_RESIDUAL_HI):
        active residual bits 512..528 -> channels 0..16
        channels 17..511 = 0
    context positions 4..15: zero (reserved)

    bit -> channel mapping per slot: direct index copy, fixed scaling
    1.0. No learned projection, no hashing, no folding, no OR collisions.

The mapping is INJECTIVE: every one of the 529 declared feature
vectors maps to a unique position-0/1 byte pattern, and every one of
the 529 active feature vectors maps to a unique position-2/3 pattern.
`unpack_structural_context` / `unpack_batched_context` are the exact
inverse for 0/1 inputs (roundtrip: unpack(pack(x)) == x).

Inputs are pure 529-bit structural vectors. No semantic/request/
fixture identifiers, no seed identity, no learned lookup key.
Changing semantic or request identifiers while preserving the
structural bit vectors MUST produce byte-identical context matrices.
"""
from __future__ import annotations

from typing import Sequence, Tuple

import torch

from c2r7d0_constants import (
    FEATURE_WIDTH,
    HIDDEN_SIZE,
    PREFIX_DECLARED_HI,
    PREFIX_DECLARED_LO,
    PREFIX_LEN,
    PREFIX_RESIDUAL_HI,
    PREFIX_RESIDUAL_LO,
)

# Number of channels a slot uses (512 full slots, 17 for the HI slots).
_HI_CHANNELS = FEATURE_WIDTH - HIDDEN_SIZE  # 17


class StructuralContextPackingError(ValueError):
    pass


def _validate_bits(bits: Sequence[int], name: str) -> Tuple[int, ...]:
    values = tuple(int(b) for b in bits)
    if len(values) != FEATURE_WIDTH:
        raise StructuralContextPackingError(
            f"{name} must have {FEATURE_WIDTH} bits, got {len(values)}"
        )
    for value in values:
        if value not in (0, 1):
            raise StructuralContextPackingError(
                f"{name} bits must be 0/1, got {value!r}"
            )
    return values


def _slot_bits(bits: Sequence[int], name: str) -> torch.Tensor:
    """Map one 529-bit vector to its two [512] channel slots.

    Returns (lo [512], hi [512]): lo = bits[0:512], hi = bits[512:529]
    in channels 0..16 with channels 17..511 zero. Direct index copy,
    scaling 1.0. No fold, no OR.
    """
    _validate_bits(bits, name)
    lo = torch.zeros(HIDDEN_SIZE, dtype=torch.float32)
    hi = torch.zeros(HIDDEN_SIZE, dtype=torch.float32)
    lo[:HIDDEN_SIZE] = torch.tensor(
        list(bits[:HIDDEN_SIZE]), dtype=torch.float32
    )
    hi[:_HI_CHANNELS] = torch.tensor(
        list(bits[HIDDEN_SIZE:]), dtype=torch.float32
    )
    return lo, hi


def pack_structural_context(
    declared529: Sequence[int],
    active529: Sequence[int],
) -> torch.Tensor:
    """Pack (declared529, active529) into a [16, 512] float32 context
    matrix per the documented lossless rule. Deterministic."""
    context = torch.zeros(PREFIX_LEN, HIDDEN_SIZE, dtype=torch.float32)
    d_lo, d_hi = _slot_bits(declared529, "declared529")
    context[PREFIX_DECLARED_LO] = d_lo
    context[PREFIX_DECLARED_HI] = d_hi
    a_lo, a_hi = _slot_bits(active529, "active529")
    context[PREFIX_RESIDUAL_LO] = a_lo
    context[PREFIX_RESIDUAL_HI] = a_hi
    return context


def pack_batched_context(
    declared529: torch.Tensor,
    active529: torch.Tensor,
) -> torch.Tensor:
    """Batched variant: [B, 529] 0/1 tensors -> [B, 16, 512] float32.

    Uses the identical per-row rule as pack_structural_context.
    """
    for name, t in (("declared529", declared529), ("active529", active529)):
        if t.ndim != 2 or t.shape[1] != FEATURE_WIDTH:
            raise StructuralContextPackingError(
                f"{name} must be [B,{FEATURE_WIDTH}], got {tuple(t.shape)}"
            )
        if t.dtype not in (torch.bool, torch.uint8, torch.int8,
                            torch.int32, torch.int64, torch.float32):
            raise StructuralContextPackingError(
                f"{name} has unsupported dtype {t.dtype}"
            )
    if declared529.shape != active529.shape:
        raise StructuralContextPackingError(
            "declared529 and active529 shapes differ"
        )

    batch = declared529.shape[0]
    context = torch.zeros(
        batch, PREFIX_LEN, HIDDEN_SIZE,
        dtype=torch.float32, device=declared529.device,
    )

    decl = declared529.to(torch.float32)
    act = active529.to(torch.float32)

    context[:, PREFIX_DECLARED_LO, :HIDDEN_SIZE] = decl[:, :HIDDEN_SIZE]
    context[:, PREFIX_DECLARED_HI, :_HI_CHANNELS] = (
        decl[:, HIDDEN_SIZE:]
    )
    context[:, PREFIX_RESIDUAL_LO, :HIDDEN_SIZE] = act[:, :HIDDEN_SIZE]
    context[:, PREFIX_RESIDUAL_HI, :_HI_CHANNELS] = (
        act[:, HIDDEN_SIZE:]
    )
    return context


# ---------------------------------------------------------------------------
# Exact inverse (roundtrip proof machinery, test-only consumers)
# ---------------------------------------------------------------------------


def _slot_to_bits(lo: torch.Tensor, hi: torch.Tensor) -> torch.Tensor:
    """Recover the 529-bit vector from one slot pair."""
    lo = lo.to(torch.float32)
    hi = hi.to(torch.float32)
    if lo.shape != (HIDDEN_SIZE,) or hi.shape != (HIDDEN_SIZE,):
        raise StructuralContextPackingError("slot shape is not [512]")
    # Fail closed on any non-0/1 channel value (lossy inputs).
    for t, label in ((lo, "lo"), (hi, "hi")):
        if bool(((t != 0.0) & (t != 1.0)).any()):
            raise StructuralContextPackingError(
                f"{label} slot has non-0/1 channel values"
            )
    low = lo.bool()
    high = hi[:_HI_CHANNELS].bool()
    if bool(hi[_HI_CHANNELS:].any()):
        raise StructuralContextPackingError(
            "hi slot has nonzero channels beyond 0..16"
        )
    return torch.cat((low, high), dim=0).to(torch.int64)


def unpack_structural_context(context: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    """Exact inverse of pack_structural_context for 0/1 inputs.

    Returns (declared529 [529] int64, active529 [529] int64).
    Raises on any reserved-position nonzero value or non-0/1 slot.
    """
    if context.ndim != 2 or context.shape != (PREFIX_LEN, HIDDEN_SIZE):
        raise StructuralContextPackingError(
            f"context must be [{PREFIX_LEN},{HIDDEN_SIZE}], got "
            f"{tuple(context.shape)}"
        )
    ctx = context.to(torch.float32)
    reserved = ctx[4:PREFIX_LEN]
    if bool(reserved.abs().any()):
        raise StructuralContextPackingError(
            "reserved prefix positions 4..15 must be exactly zero"
        )
    decl = _slot_to_bits(
        ctx[PREFIX_DECLARED_LO], ctx[PREFIX_DECLARED_HI]
    )
    active = _slot_to_bits(
        ctx[PREFIX_RESIDUAL_LO], ctx[PREFIX_RESIDUAL_HI]
    )
    return decl, active


def unpack_batched_context(
    context: torch.Tensor,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Exact inverse of pack_batched_context for 0/1 inputs.

    [B, 16, 512] -> (declared [B, 529], active [B, 529]).
    """
    if context.ndim != 3 or context.shape[1:] != (PREFIX_LEN, HIDDEN_SIZE):
        raise StructuralContextPackingError(
            f"context must be [B,{PREFIX_LEN},{HIDDEN_SIZE}], got "
            f"{tuple(context.shape)}"
        )
    batch = context.shape[0]
    decl = torch.zeros(batch, FEATURE_WIDTH, dtype=torch.int64,
                       device=context.device)
    active = torch.zeros(batch, FEATURE_WIDTH, dtype=torch.int64,
                         device=context.device)
    ctx = context.to(torch.float32)
    reserved = ctx[:, 4:PREFIX_LEN]
    if bool(reserved.abs().any()):
        raise StructuralContextPackingError(
            "reserved prefix positions 4..15 must be exactly zero"
        )
    decl[:, :HIDDEN_SIZE] = (
        ctx[:, PREFIX_DECLARED_LO, :HIDDEN_SIZE].bool().to(torch.int64)
    )
    decl[:, HIDDEN_SIZE:] = (
        ctx[:, PREFIX_DECLARED_HI, :_HI_CHANNELS].bool().to(torch.int64)
    )
    active[:, :HIDDEN_SIZE] = (
        ctx[:, PREFIX_RESIDUAL_LO, :HIDDEN_SIZE].bool().to(torch.int64)
    )
    active[:, HIDDEN_SIZE:] = (
        ctx[:, PREFIX_RESIDUAL_HI, :_HI_CHANNELS].bool().to(torch.int64)
    )
    # fail closed on channels beyond the documented ranges
    if bool(ctx[:, PREFIX_DECLARED_HI, _HI_CHANNELS:].abs().any()) or \
       bool(ctx[:, PREFIX_RESIDUAL_HI, _HI_CHANNELS:].abs().any()):
        raise StructuralContextPackingError(
            "HI slot has nonzero channels beyond 0..16"
        )
    bad = ((ctx != 0.0) & (ctx != 1.0)).any(dim=(1, 2))
    if bool(bad.any()):
        raise StructuralContextPackingError(
            f"context rows with non-0/1 channels: {bad.nonzero().flatten().tolist()}"
        )
    return decl, active
