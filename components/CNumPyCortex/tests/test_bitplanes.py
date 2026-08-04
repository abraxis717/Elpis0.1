"""Test bitplane encoding and decoding."""
from __future__ import annotations

import numpy as np

from c_numpy_cortex.encoding import encode_bitplanes, decode_bitplanes


def test_bitplane_exact_shape():
    tokens = np.arange(81, dtype=np.uint8).reshape(9, 9)
    tokens = np.clip(tokens, 0, 9)

    bits = encode_bitplanes(tokens)
    assert bits.shape == (4, 9, 9)
    assert bits.dtype == np.uint8


def test_bitplane_token_roundtrip():
    tokens = np.random.randint(0, 10, size=(9, 9)).astype(np.uint8)

    bits = encode_bitplanes(tokens)
    decoded = decode_bitplanes(bits)

    assert np.array_equal(decoded, tokens)


def test_token_zero_roundtrip():
    tokens = np.zeros((9, 9), dtype=np.uint8)

    bits = encode_bitplanes(tokens)
    decoded = decode_bitplanes(bits)

    assert np.array_equal(decoded, tokens)
    assert np.all(bits == 0)


def test_no_semantic_reinterpretation():
    """Individual bits carry no semantic meaning."""
    tokens = np.ones((9, 9), dtype=np.uint8) * 5
    bits = encode_bitplanes(tokens)

    # Bit 5 = 0b0101
    # Bit plane 0 should be all 1s (bit 0 of 5)
    assert np.all(bits[0] == 1)
    # Bit plane 1 should be all 0s (bit 1 of 5)
    assert np.all(bits[1] == 0)
    # Bit plane 2 should be all 1s (bit 2 of 5)
    assert np.all(bits[2] == 1)
    # Bit plane 3 should be all 0s (bit 3 of 5)
    assert np.all(bits[3] == 0)


def test_all_tokens_0_to_9_roundtrip():
    for val in range(10):
        tokens = np.full((9, 9), val, dtype=np.uint8)
        bits = encode_bitplanes(tokens)
        decoded = decode_bitplanes(bits)
        assert np.array_equal(decoded, tokens), f"Failed for token {val}"
