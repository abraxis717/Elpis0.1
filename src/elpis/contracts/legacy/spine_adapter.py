# elpis/contracts/legacy/spine_adapter.py — Wave-1 canary adapter (§XI, §XVIII).
# Wraps the live uint8[9,9] Grid81 produced at the Bridge→Spine ingress
# into ExecutionEnvelope[GridPayload] and unwraps it back, with shadow
# byte-equality verification. Spine is UNTOUCHED — this runs at the Bridge
# ingress behind ELPIS_ENVELOPE_CANARY=1.
#
# Concrete binding verified against A0 census:
#   Legacy packet: elpis.spine.latent_packet.LatentPacket
#   Grid field:    latent: np.ndarray[float32, 81]
#   Grid81 produced by: GridTopology.encode() → uint8[9,9], row-major, symbols 0..9
#   Mask:          mask: np.ndarray | None — "valid positions (1 = active)"
#                  → ValidityMask semantics confirmed by source docstring.
#   Budget:        budget: int — scalar, default 64 (remaining TRM invocations)
#   Route:         routing: RoutingHint (IntEnum: PASS_THROUGH=0, ORTHOGONALIZE=1,
#                  DECOMPOSE=2, DECODE_DIRECT=3)
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from ..budget import from_legacy_scalar
from ..envelope import ExecutionEnvelope, root_envelope
from ..masks import ValidityMask
from ..payloads import GridPayload
from ..phases import Phase
from ..routing import parse_route

if TYPE_CHECKING:
    from elpis.spine.latent_packet import LatentPacket as SpineLatentPacket


class SpineAdapterError(RuntimeError):
    """Errors in spine adapter wrap/unwrap/verify."""


@dataclass(frozen=True, slots=True)
class ShadowVerification:
    """Typed shadow-verification result (production telemetry, not bare bool)."""
    passed: bool
    reason_code: str
    original_checksum: str
    envelope_checksum: str
    grid_bytes_match: bool
    dtype_match: bool
    shape_match: bool
    budget_correct: bool
    route_mapped: bool


# ---- Grid-level wrap / unwrap / verify ------------------------------------

def wrap_grid(
    grid: np.ndarray,
    *,
    steps_budget: int,
    route_raw: str = "structural",
    validity: ValidityMask | None = None,
) -> ExecutionEnvelope[GridPayload]:
    """Wrap uint8[9,9] Grid81 into ExecutionEnvelope[GridPayload]."""
    a = np.ascontiguousarray(grid, dtype=np.uint8)
    if a.shape != (9, 9):
        raise SpineAdapterError(f"grid shape {a.shape} != (9,9)")
    if validity is None:
        validity = ValidityMask(np.ones(81, dtype=bool))
    payload = GridPayload.from_numpy(a, validity)
    return root_envelope(
        payload,
        budget=from_legacy_scalar(steps_budget),
        route=parse_route(route_raw),
        phase=Phase.STRUCTURAL_PROJECTION,
    )


def unwrap_grid(
    env: ExecutionEnvelope[GridPayload],
) -> np.ndarray:
    """Unwrap ExecutionEnvelope[GridPayload] back to uint8[9,9] grid."""
    arr = env.payload.to_numpy()  # [B, 81]
    if arr.shape != (1, 81):
        raise SpineAdapterError(f"expected batch=1, got shape {arr.shape}")
    return arr.reshape(9, 9)


def shadow_verify_grid(
    original_grid: np.ndarray,
    env: ExecutionEnvelope[GridPayload],
    reconstructed_grid: np.ndarray,
) -> ShadowVerification:
    """Shadow verification: original grid bytes == envelope == reconstructed."""
    orig = np.ascontiguousarray(original_grid, dtype=np.uint8).reshape(1, 81)
    recon = np.ascontiguousarray(reconstructed_grid, dtype=np.uint8).reshape(1, 81)

    grid_bytes_match = orig.tobytes() == env.payload.data
    recon_bytes_match = recon.tobytes() == env.payload.data
    all_bytes_match = grid_bytes_match and recon_bytes_match

    dtype_match = (
        original_grid.dtype == np.uint8
        and reconstructed_grid.dtype == np.uint8
    )
    shape_match = (
        original_grid.shape == (9, 9)
        and reconstructed_grid.shape == (9, 9)
    )

    # Checksum: envelope.content_checksum must equal payload.chi_p()
    checksum_ok = env.content_checksum == env.payload.chi_p()

    # Budget: only steps granted, rest NOT_GRANTED
    budget_correct = (
        env.budget.steps is not None
        and env.budget.depth is None
        and env.budget.backend is None
        and env.budget.tokens is None
        and env.budget.energy is None
        and env.budget.wall_ms is None
        and env.budget.writes is None
    )

    # Route: provenance must be a known value
    route_mapped = env.route.provenance.value in (
        "declared", "legacy_mapped", "unknown_input"
    )

    passed = (
        all_bytes_match
        and dtype_match
        and shape_match
        and checksum_ok
        and budget_correct
    )

    reason = "OK" if passed else "; ".join(
        name for name, ok in [
            ("bytes_mismatch", not all_bytes_match),
            ("dtype_mismatch", not dtype_match),
            ("shape_mismatch", not shape_match),
            ("checksum_mismatch", not checksum_ok),
            ("budget_incorrect", not budget_correct),
        ]
        if not ok
    )

    return ShadowVerification(
        passed=passed,
        reason_code=reason,
        original_checksum=orig.tobytes().hex()[:32],
        envelope_checksum=env.content_checksum,
        grid_bytes_match=all_bytes_match,
        dtype_match=dtype_match,
        shape_match=shape_match,
        budget_correct=budget_correct,
        route_mapped=route_mapped,
    )


# ---- Spine packet helpers (wrap with packet context) ----------------------

def _grid_from_packet(packet: "SpineLatentPacket") -> np.ndarray:
    """Derive uint8[9,9] grid from Spine packet latent, matching topology.encode."""
    latent = packet.latent
    if latent.shape != (81,):
        raise SpineAdapterError(
            f"Spine latent shape {latent.shape} != (81,); cannot derive grid"
        )
    grid = latent.reshape(9, 9).astype(np.uint8)
    return np.clip(grid, 0, 9)


def _validity_from_packet(packet: "SpineLatentPacket") -> ValidityMask:
    """Derive ValidityMask from Spine packet mask field.

    The Spine packet's mask is documented as 'valid positions (1 = active)',
    which IS ValidityMask semantics. If mask is None, all cells are valid.
    """
    if packet.mask is not None:
        m = np.asarray(packet.mask, dtype=bool).reshape(81)
        return ValidityMask(m)
    return ValidityMask(np.ones(81, dtype=bool))


def wrap_spine_packet(
    packet: "SpineLatentPacket",
    *,
    steps_budget: int,
    route_raw: str = "structural",
) -> ExecutionEnvelope[GridPayload]:
    """Wrap Spine LatentPacket's derived grid into ExecutionEnvelope[GridPayload]."""
    grid = _grid_from_packet(packet)
    validity = _validity_from_packet(packet)
    return wrap_grid(grid, steps_budget=steps_budget, route_raw=route_raw, validity=validity)


def reconstruct_spine_packet(
    original: "SpineLatentPacket",
    envelope: ExecutionEnvelope[GridPayload],
) -> "SpineLatentPacket":
    """Reconstruct Spine packet from envelope, preserving ALL non-grid fields.

    Uses type(original) constructor — Spine LatentPacket is a non-frozen
    dataclass, so dataclasses.replace would work but the constructor gives
    full control and avoids accidental field drops.
    """
    reconstructed_grid = unwrap_grid(envelope)
    new_latent = reconstructed_grid.astype(np.float32).reshape(81)
    return type(original)(
        packet_id=original.packet_id,
        version=original.version,
        created_at=original.created_at,
        latent=new_latent,
        latent_shape=original.latent_shape,
        mask=original.mask,
        routing=original.routing,
        budget=original.budget,
        energy_estimate=original.energy_estimate,
        source_module=original.source_module,
        prompt_hash=original.prompt_hash,
    )


def shadow_verify(
    original: "SpineLatentPacket",
    envelope: ExecutionEnvelope[GridPayload],
    reconstructed: "SpineLatentPacket",
) -> ShadowVerification:
    """Shadow verification using derived grids from original and reconstructed packets."""
    orig_grid = _grid_from_packet(original)
    recon_grid = _grid_from_packet(reconstructed)
    return shadow_verify_grid(orig_grid, envelope, recon_grid)
