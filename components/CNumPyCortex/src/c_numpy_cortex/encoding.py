from __future__ import annotations

import hashlib
import json
import struct
from typing import Any

import numpy as np

from .contracts import (
    ChannelDescriptor,
    ChannelSchema,
    ObservedValue,
    ObservationValidity,
    TensorSpaceIdentity,
    ObservationPacketV2,
    PacketLifecycle,
)


# ─── Quantizer ──────────────────────────────────────────────────────────

QUANTIZER_VERSION = "robust_z.v1"
NORMALIZATION_WINDOW = 256
MIN_SUPPORT = 32
MAD_SCALE = 1.4826
Z_CLIP = 3.0


class QuantizerState:
    """Per-channel normalization state."""

    def __init__(self):
        self.median: float | None = None
        self.scale: float | None = None
        self.support: int = 0

    def update(self, value: float) -> None:
        """Track running history for quantization."""
        pass  # Managed by caller

    def to_digest_parts(self) -> tuple:
        """Return serializable parts for digest computation."""
        m = self.median if self.median is not None else 0.0
        s = self.scale if self.scale is not None else 0.0
        return (m, s, self.support)


def compute_quantizer_state(
    history: tuple[float, ...],
) -> QuantizerState:
    """Compute median and MAD scale from valid history."""
    state = QuantizerState()

    if len(history) == 0:
        return state

    arr = np.array(history, dtype=np.float64)
    finite = arr[np.isfinite(arr)]

    if len(finite) == 0:
        return state

    state.support = len(finite)
    state.median = float(np.nanmedian(finite))

    mad = float(np.nanmedian(np.abs(finite - state.median)))

    if mad < 1e-6:
        state.scale = 1.0
    else:
        state.scale = MAD_SCALE * mad

    return state


def quantize_value(
    value: float,
    state: QuantizerState,
    validity: ObservationValidity,
) -> tuple[int, int]:
    """Quantize a single observation to (token, mask).

    Returns:
        token: 0..9 (0 = absent)
        mask: 0 or 1 (1 = valid)
    """
    # Absent / invalid values -> token=0, mask=0
    if (
        validity != ObservationValidity.FRESH
        or value is None
        or not np.isfinite(value)
        or state.support < MIN_SUPPORT
    ):
        return (0, 0)

    median = state.median
    scale = state.scale

    if median is None or scale is None:
        return (0, 0)

    z = (value - median) / scale
    z = np.clip(z, -Z_CLIP, Z_CLIP)

    # Map [-3, +3] -> [0, 1] -> bin index 0..8 -> token 1..9
    bin_index = int(np.clip(
        np.floor(((z + 3.0) / 6.0) * 9.0),
        0,
        8,
    ))

    token = bin_index + 1
    return (token, 1)


# ─── Bitplanes ──────────────────────────────────────────────────────────

def encode_bitplanes(tokens: np.ndarray) -> np.ndarray:
    """Encode 9x9 uint8 tokens into 4 binary planes (4, 9, 9).

    Properties:
    - Exact shape (4, 9, 9)
    - Exact dtype uint8
    - Token round-trip via decode
    - Token 0 round-trips as all-zero plane
    - No semantic reinterpretation of individual bits
    """
    if tokens.shape != (9, 9):
        raise ValueError(
            f"tokens must be (9,9), got {tokens.shape}"
        )

    bits = np.zeros((4, 9, 9), dtype=np.uint8)

    for bit in range(4):
        bits[bit] = ((tokens >> bit) & 1).astype(np.uint8)

    return bits


def decode_bitplanes(bits: np.ndarray) -> np.ndarray:
    """Decode 4 binary planes back to 9x9 tokens."""
    if bits.shape != (4, 9, 9):
        raise ValueError(
            f"bits must be (4,9,9), got {bits.shape}"
        )

    output = np.zeros((9, 9), dtype=np.uint8)

    for bit in range(4):
        output |= (bits[bit].astype(np.uint8) & 1) << bit

    return output


# ─── Normalizer digest ─────────────────────────────────────────────────

def compute_normalizer_digest(
    channel_schema: ChannelSchema,
    quantizer_states: dict[str, QuantizerState],
) -> str:
    """Compute deterministic normalizer state digest.

    Uses little-endian float32 encoding for numerical state.
    Does NOT include clocks.
    """
    parts = bytearray()

    # Domain separator
    parts.extend(b"cnumpycortex.normalizer.v1\x00")

    # Quantizer version
    parts.extend(QUANTIZER_VERSION.encode())
    parts.extend(b"\x00")

    # Schema digest
    parts.extend(channel_schema.digest.encode())
    parts.extend(b"\x00")

    # Ordered channel states
    for row in channel_schema.rows:
        state = quantizer_states.get(row.channel_id)

        if state:
            m = state.median if state.median is not None else 0.0
            s = state.scale if state.scale is not None else 0.0
        else:
            m = 0.0
            s = 0.0

        parts.extend(struct.pack("<ffii", m, s, state.support if state else 0, 0))

    return hashlib.sha256(parts).hexdigest()


# ─── Frame compilation ─────────────────────────────────────────────────

def compile_thermal_frame(
    schema: ChannelSchema,
    ring_data: dict[str, tuple[ObservedValue, ...]],
    quantizer_states: dict[str, QuantizerState],
    generation: int,
    wall_time_ns: int,
    monotonic_ns: int,
    lifecycle: PacketLifecycle,
    lifecycle_reasons: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """Compile a 9x9 thermal frame from ring data.

    Returns:
        tokens: (9, 9) uint8
        valid_mask: (9, 9) uint8
        bitplanes: (4, 9, 9) uint8
        cell_meta: dict mapping (row, col) -> provenance dict
    """
    tokens = np.zeros((9, 9), dtype=np.uint8)
    valid_mask = np.zeros((9, 9), dtype=np.uint8)

    cell_meta: dict[tuple[int, int], dict] = {}

    for row_idx, row_desc in enumerate(schema.rows):
        ch_id = row_desc.channel_id
        samples = ring_data.get(ch_id, ())

        # Last 9 chronological samples
        recent = samples[-9:] if len(samples) >= 9 else samples

        for col_idx in range(9):
            if col_idx < len(recent):
                obs = recent[col_idx]
                state = quantizer_states.get(ch_id)

                if state is not None and obs.value is not None:
                    token, mask = quantize_value(
                        obs.value, state, obs.validity
                    )
                else:
                    token, mask = 0, 0
            else:
                token, mask = 0, 0
                obs = None

            tokens[row_idx, col_idx] = token
            valid_mask[row_idx, col_idx] = mask

            cell_meta[(row_idx, col_idx)] = {
                "channel_id": ch_id,
                "source_sequence": (
                    obs.source_sequence if obs else None
                ),
                "observed_monotonic_ns": (
                    obs.observed_monotonic_ns if obs else None
                ),
                "validity": (
                    obs.validity.value if obs else None
                ),
            }

    bitplanes = encode_bitplanes(tokens)

    return tokens, valid_mask, bitplanes, cell_meta


# ─── Legacy compatibility ───────────────────────────────────────────────

class Grid81Compiler:
    """Legacy wrapper for backward compatibility."""

    def __init__(
        self,
        channel_names: tuple[str, ...],
        preferred_channels: tuple[str, ...] = (),
        normalization_window: int = 256,
        clip_z: float = 3.0,
    ):
        self.channel_names = channel_names
        self.normalization_window = int(normalization_window)
        self.clip_z = float(clip_z)

        self.selected_indices = self._select_indices(
            preferred_channels
        )
        self.selected_names = tuple(
            channel_names[i] for i in self.selected_indices
        )

    def _select_indices(
        self,
        preferred: tuple[str, ...],
    ) -> tuple[int, ...]:
        name_to_index = {
            name: idx
            for idx, name in enumerate(self.channel_names)
        }

        selected: list[int] = []

        for name in preferred:
            idx = name_to_index.get(name)
            if idx is not None and idx not in selected:
                selected.append(idx)

        priorities = (
            lambda n: n.startswith("temp."),
            lambda n: n.startswith("cpu.thread_"),
            lambda n: n.startswith("gpu."),
            lambda n: n.startswith("llama."),
            lambda n: True,
        )

        for pred in priorities:
            for idx, name in enumerate(self.channel_names):
                if len(selected) >= 9:
                    break
                if idx not in selected and pred(name):
                    selected.append(idx)

        while len(selected) < 9:
            selected.append(selected[-1])

        return tuple(selected[:9])

    def compile(
        self,
        wall_time_ns: np.ndarray,
        values: np.ndarray,
    ) -> Any:
        from .contracts import GridPacket

        history = values[
            -self.normalization_window :,
            self.selected_indices,
        ].astype(np.float64)

        median = np.nanmedian(history, axis=0)
        mad = np.nanmedian(np.abs(history - median), axis=0)
        scale = np.where(
            np.isfinite(mad) & (mad > 1e-6),
            1.4826 * mad,
            1.0,
        )

        recent = values[-9:, self.selected_indices].astype(
            np.float64
        )

        if recent.shape[0] < 9:
            padding = np.full(
                (9 - recent.shape[0], 9),
                np.nan,
                dtype=np.float64,
            )
            recent = np.vstack((padding, recent))

        z = (recent - median) / scale
        z = np.clip(z, -self.clip_z, self.clip_z)

        valid = np.isfinite(z)
        scaled = (z + self.clip_z) / (2.0 * self.clip_z)
        digits_tc = (
            np.floor(scaled * 9.0).astype(np.int16) + 1
        )
        digits_tc = np.clip(digits_tc, 1, 9)
        digits_tc[~valid] = 0

        digits = digits_tc.T.astype(np.uint8, copy=False)
        valid_mask = valid.T.astype(np.uint8, copy=False)

        bits = np.stack(
            [((digits >> b) & 1) for b in range(4)],
            axis=0,
        ).astype(np.uint8)

        signature = self._recursive_signature(digits, valid_mask)

        packet = GridPacket(
            wall_time_ns=int(wall_time_ns[-1]),
            digits=digits,
            bits=bits,
            valid_mask=valid_mask,
            channel_names=self.selected_names,
            recursive_signature=signature,
        )

        packet.validate()
        return packet

    @staticmethod
    def _recursive_signature(
        digits: np.ndarray,
        mask: np.ndarray,
    ) -> np.ndarray:
        normalized = digits.astype(np.float32) / 9.0
        normalized = np.where(mask > 0, normalized, 0.0)

        features: list[float] = normalized.reshape(-1).tolist()

        for row in range(0, 9, 3):
            for col in range(0, 9, 3):
                block = normalized[row:row+3, col:col+3]
                features.extend([
                    float(block.mean()),
                    float(block.std()),
                    float(np.ptp(block)),
                ])

        features.extend(normalized.mean(axis=0).tolist())
        features.extend(normalized.mean(axis=1).tolist())

        return np.asarray(features, dtype=np.float32)


def decode_digit_bits(bits: np.ndarray) -> np.ndarray:
    """Reconstruct 0..9 digits from four bit planes."""
    if bits.shape != (4, 9, 9):
        raise ValueError("bits must have shape (4, 9, 9)")

    output = np.zeros((9, 9), dtype=np.uint8)

    for bit in range(4):
        output |= (bits[bit].astype(np.uint8) & 1) << bit

    return output
