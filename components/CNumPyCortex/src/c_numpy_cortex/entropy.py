from __future__ import annotations

import math

import numpy as np

from .contracts import (
    EntropyState,
    GridPacket,
)


def _binary_entropy(probability: float) -> float:
    if probability <= 0.0 or probability >= 1.0:
        return 0.0

    return float(
        -(
            probability * math.log2(probability)
            + (1.0 - probability) * math.log2(1.0 - probability)
        )
    )


# ─── Masked entropy metrics ─────────────────────────────────────────────

def masked_digit_entropy(
    tokens: np.ndarray,
    valid_mask: np.ndarray,
) -> float | None:
    """Compute digit entropy over valid cells only.

    Token support 1..9, normalized by log(9).
    Returns None if no valid cells exist.
    """
    valid_tokens = tokens[valid_mask > 0]

    if len(valid_tokens) == 0:
        return None

    # Count tokens 1..9 among valid cells
    counts = np.bincount(
        valid_tokens.astype(np.intp),
        minlength=10,
    ).astype(np.float64)

    # Only consider tokens 1..9
    counts = counts[1:]

    total = counts.sum()

    if total == 0:
        return None

    probs = counts / total
    nonzero = probs > 0

    entropy = -np.sum(probs[nonzero] * np.log2(probs[nonzero]))

    # Normalize by log(9) since support is 1..9
    return float(entropy / math.log2(9))


def masked_bit_entropy(
    bitplanes: np.ndarray,
    valid_mask: np.ndarray,
) -> tuple[float | None, ...]:
    """Compute bit entropy per plane over valid cells only.

    Returns tuple of 4 values, one per plane.
    Each value is None if no valid cells exist.
    """
    if bitplanes.shape[0] != 4:
        raise ValueError(
            f"bitplanes must have 4 planes, got {bitplanes.shape[0]}"
        )

    results: list[float | None] = []

    for plane in range(4):
        valid_bits = bitplanes[plane][valid_mask > 0]

        if len(valid_bits) == 0:
            results.append(None)
            continue

        ones = np.sum(valid_bits)
        prob = float(ones) / len(valid_bits)
        results.append(_binary_entropy(prob))

    return tuple(results)


def masked_transition_rate(
    current_tokens: np.ndarray,
    current_mask: np.ndarray,
    previous_tokens: np.ndarray,
    previous_mask: np.ndarray,
    schema_digest_current: str,
    schema_digest_previous: str,
    normalizer_digest_current: str,
    normalizer_digest_previous: str,
) -> float | None:
    """Compute transition rate over valid cell overlaps.

    Numerator: cells where both masks are valid and tokens differ.
    Denominator: cells where both masks are valid.

    Returns None when:
    - denominator is zero
    - schema digest changed
    - normalizer digest changed
    - no valid previous frame exists
    """
    # Schema or normalizer changed -> undefined transition
    if schema_digest_current != schema_digest_previous:
        return None

    if normalizer_digest_current != normalizer_digest_previous:
        return None

    # Both masks valid
    overlap = (current_mask > 0) & (previous_mask > 0)

    if not np.any(overlap):
        return None

    denominator = int(np.sum(overlap))

    if denominator == 0:
        return None

    numerator = int(np.sum(
        overlap & (current_tokens != previous_tokens)
    ))

    return float(numerator / denominator)


def entropy_event_score(
    digit_entropy: float | None,
    transition_rate: float | None,
) -> float | None:
    """Compute entropy event score.

    Uses component metrics. Returns None when any required
    component is undefined.
    """
    if digit_entropy is None or transition_rate is None:
        return None

    # Deterministic formula: weighted combination
    score = 0.50 * digit_entropy + 0.50 * transition_rate

    return float(np.clip(score, 0.0, 1.0))


# ─── Legacy compatibility ───────────────────────────────────────────────

def measure_entropy(
    packet: GridPacket,
    previous: GridPacket | None,
) -> EntropyState:
    """Legacy entropy measurement for backward compatibility."""
    bit_entropy = _binary_entropy(float(packet.bits.mean()))
    digit_entropy = _categorical_entropy(packet.digits)

    transition_rate = 0.0

    if previous is not None:
        transition_rate = float(
            np.not_equal(packet.bits, previous.bits).mean()
        )

    temporal_gradient = float(
        np.abs(
            np.diff(packet.digits.astype(np.float32), axis=1)
        ).mean()
        / 9.0
    )

    event_score = float(
        np.clip(
            0.30 * bit_entropy
            + 0.25 * digit_entropy
            + 0.30 * transition_rate
            + 0.15 * temporal_gradient,
            0.0,
            1.0,
        )
    )

    return EntropyState(
        bit_entropy=bit_entropy,
        digit_entropy=digit_entropy,
        transition_rate=transition_rate,
        temporal_gradient=temporal_gradient,
        event_score=event_score,
    )


def _categorical_entropy(
    values: np.ndarray,
    classes: int = 10,
) -> float:
    counts = np.bincount(
        values.reshape(-1),
        minlength=classes,
    ).astype(np.float64)

    probabilities = counts / max(counts.sum(), 1.0)
    nonzero = probabilities > 0

    raw_entropy = -np.sum(
        probabilities[nonzero] * np.log2(probabilities[nonzero])
    )

    return float(raw_entropy / math.log2(classes))


_TOKEN_ALPHABET = (
    "0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
)


def state_token(
    entropy: EntropyState,
    forecast_anomaly: float,
) -> str:
    """Map measured system state to one visible token."""
    scalar = np.clip(
        0.78 * entropy.event_score + 0.22 * forecast_anomaly,
        0.0,
        1.0,
    )

    index = min(
        int(round(scalar * (len(_TOKEN_ALPHABET) - 1))),
        len(_TOKEN_ALPHABET) - 1,
    )

    return _TOKEN_ALPHABET[index]
