"""Test masked entropy, transition rate."""
from __future__ import annotations

import numpy as np

from c_numpy_cortex.entropy import (
    masked_digit_entropy,
    masked_bit_entropy,
    masked_transition_rate,
    entropy_event_score,
)
from c_numpy_cortex.encoding import encode_bitplanes


def test_masked_digit_entropy_valid_cells():
    """Use valid cells only, token support 1..9."""
    tokens = np.full((9, 9), 5, dtype=np.uint8)
    mask = np.ones((9, 9), dtype=np.uint8)

    # All valid, all same token -> entropy should be 0
    ent = masked_digit_entropy(tokens, mask)
    assert ent is not None
    assert ent == pytest.approx(0.0, abs=1e-9)


def test_masked_digit_entropy_no_valid_cells():
    tokens = np.zeros((9, 9), dtype=np.uint8)
    mask = np.zeros((9, 9), dtype=np.uint8)

    ent = masked_digit_entropy(tokens, mask)
    assert ent is None


def test_masked_bit_entropy_per_plane():
    tokens = np.full((9, 9), 5, dtype=np.uint8)
    mask = np.ones((9, 9), dtype=np.uint8)
    bits = encode_bitplanes(tokens)

    entropies = masked_bit_entropy(bits, mask)
    assert len(entropies) == 4
    for e in entropies:
        assert e is not None


def test_masked_entropy_valid_cells_only():
    """Masked cells do not affect entropy."""
    tokens = np.full((9, 9), 5, dtype=np.uint8)
    tokens[0, 0] = 0  # Absent cell
    mask = np.ones((9, 9), dtype=np.uint8)
    mask[0, 0] = 0  # Mark as invalid

    ent = masked_digit_entropy(tokens, mask)
    assert ent is not None
    # With 80 valid cells all token=5, entropy should be 0
    assert ent == pytest.approx(0.0, abs=1e-9)


def test_transition_none_when_schema_changes():
    tokens = np.full((9, 9), 5, dtype=np.uint8)
    mask = np.ones((9, 9), dtype=np.uint8)

    rate = masked_transition_rate(
        tokens, mask,
        tokens, mask,
        "digest_a",
        "digest_b",
        "norm_digest",
        "norm_digest",
    )
    assert rate is None


def test_transition_none_when_normalizer_changes():
    tokens = np.full((9, 9), 5, dtype=np.uint8)
    mask = np.ones((9, 9), dtype=np.uint8)

    rate = masked_transition_rate(
        tokens, mask,
        tokens, mask,
        "same_schema",
        "same_schema",
        "norm_a",
        "norm_b",
    )
    assert rate is None


def test_transition_none_with_zero_valid_overlap():
    tokens = np.full((9, 9), 5, dtype=np.uint8)
    mask = np.zeros((9, 9), dtype=np.uint8)

    rate = masked_transition_rate(
        tokens, mask,
        tokens, mask,
        "digest",
        "digest",
        "norm",
        "norm",
    )
    assert rate is None


def test_transition_rate_same_tokens():
    tokens = np.full((9, 9), 5, dtype=np.uint8)
    mask = np.ones((9, 9), dtype=np.uint8)

    rate = masked_transition_rate(
        tokens, mask,
        tokens, mask,
        "digest", "digest",
        "norm", "norm",
    )
    assert rate is not None
    assert rate == pytest.approx(0.0, abs=1e-9)


def test_transition_rate_different_tokens():
    current = np.full((9, 9), 5, dtype=np.uint8)
    previous = np.full((9, 9), 3, dtype=np.uint8)
    mask = np.ones((9, 9), dtype=np.uint8)

    rate = masked_transition_rate(
        current, mask,
        previous, mask,
        "digest", "digest",
        "norm", "norm",
    )
    assert rate is not None
    assert rate == pytest.approx(1.0, abs=1e-9)


def test_entropy_event_score_with_values():
    score = entropy_event_score(0.5, 0.3)
    assert score is not None
    assert 0.0 <= score <= 1.0


def test_entropy_event_score_none_when_missing():
    assert entropy_event_score(None, 0.3) is None
    assert entropy_event_score(0.5, None) is None


# pytest is a fixture used above, need the import
import pytest
