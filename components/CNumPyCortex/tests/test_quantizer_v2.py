"""Test quantizer behavior with golden bin boundaries."""
from __future__ import annotations

import math

import numpy as np
import pytest

from c_numpy_cortex.encoding import (
    compute_quantizer_state,
    quantize_value,
    compute_normalizer_digest,
)
from c_numpy_cortex.contracts import (
    ObservedValue,
    ObservationValidity,
    ChannelDescriptor,
    ChannelSchema,
    compute_schema_digest,
)


def test_z_zero_maps_to_token_5():
    """z=0 must map exactly to token 5."""
    # Constant valid channel: all values equal -> MAD < 1e-6 -> scale=1.0
    history = tuple([5.0] * 64)
    state = compute_quantizer_state(history)

    token, mask = quantize_value(5.0, state, ObservationValidity.FRESH)
    assert token == 5, f"z=0 should map to token 5, got {token}"
    assert mask == 1


def test_constant_valid_channel_token_5():
    """Constant valid channel maps to token 5 with mask 1."""
    history = tuple([10.0] * 64)
    state = compute_quantizer_state(history)

    token, mask = quantize_value(10.0, state, ObservationValidity.FRESH)
    assert token == 5
    assert mask == 1


def test_missing_maps_to_token_0_mask_0():
    history = tuple([float(i) for i in range(64)])
    state = compute_quantizer_state(history)

    ov = ObservedValue(
        value=None,
        observed_monotonic_ns=100,
        source_sequence=1,
        validity=ObservationValidity.MISSING,
        error_code="no_source",
    )

    token, mask = quantize_value(
        0.0, state, ObservationValidity.MISSING
    )
    assert token == 0
    assert mask == 0


def test_stale_maps_to_token_0_mask_0():
    history = tuple([float(i) for i in range(64)])
    state = compute_quantizer_state(history)

    token, mask = quantize_value(
        5.0, state, ObservationValidity.STALE
    )
    assert token == 0
    assert mask == 0


def test_invalid_maps_to_token_0_mask_0():
    history = tuple([float(i) for i in range(64)])
    state = compute_quantizer_state(history)

    token, mask = quantize_value(
        5.0, state, ObservationValidity.INVALID
    )
    assert token == 0
    assert mask == 0


def test_nan_maps_to_token_0_mask_0():
    history = tuple([float(i) for i in range(64)])
    state = compute_quantizer_state(history)

    token, mask = quantize_value(
        float("nan"), state, ObservationValidity.FRESH
    )
    assert token == 0
    assert mask == 0


def test_inf_maps_to_token_0_mask_0():
    history = tuple([float(i) for i in range(64)])
    state = compute_quantizer_state(history)

    token, mask = quantize_value(
        float("inf"), state, ObservationValidity.FRESH
    )
    assert token == 0
    assert mask == 0


def test_support_below_32_maps_to_warmup():
    """Warm-up: support below 32 -> token=0, mask=0."""
    history = tuple([float(i) for i in range(10)])
    state = compute_quantizer_state(history)

    token, mask = quantize_value(
        5.0, state, ObservationValidity.FRESH
    )
    assert token == 0
    assert mask == 0


def test_golden_bin_boundaries():
    """Verify golden bin boundaries with known quantizer state."""
    # Create history with known median and scale
    history = tuple([0.0] * 32 + [10.0] * 32)
    state = compute_quantizer_state(history)
    assert state.support == 64

    # The median of [0]*32 + [10]*32 is 5.0 (or close)
    # MAD would be 5.0, scale = 1.4826 * 5.0 = 7.413
    # For value = median, z = 0 -> token 5
    token, mask = quantize_value(
        state.median, state, ObservationValidity.FRESH
    )
    assert token == 5
    assert mask == 1


def test_normalizer_digest_changes_with_state():
    """Normalizer digest must change when normalizer state changes."""
    rows = tuple(
        ChannelDescriptor(
            channel_id=f"ch_{i}",
            source_kind="psutil",
            unit="none",
            sampling_class="psutil",
            expected_period_ns=50_000_000,
            stale_after_ns=100_000_000,
            transform_id="robust_z",
            required=False,
        )
        for i in range(9)
    )
    digest = compute_schema_digest(rows)
    schema = ChannelSchema(
        schema_id="test",
        version="1.0",
        rows=rows,
        digest=digest,
    )

    states1 = {}
    states2 = {}

    for i, row in enumerate(rows):
        h1 = tuple([float(i * 10)] * 40)
        h2 = tuple([float(i * 10 + 5)] * 40)
        states1[row.channel_id] = compute_quantizer_state(h1)
        states2[row.channel_id] = compute_quantizer_state(h2)

    d1 = compute_normalizer_digest(schema, states1)
    d2 = compute_normalizer_digest(schema, states2)
    assert d1 != d2


def test_normalizer_digest_deterministic():
    """Normalizer digest must be deterministic."""
    rows = tuple(
        ChannelDescriptor(
            channel_id=f"ch_{i}",
            source_kind="psutil",
            unit="none",
            sampling_class="psutil",
            expected_period_ns=50_000_000,
            stale_after_ns=100_000_000,
            transform_id="robust_z",
            required=False,
        )
        for i in range(9)
    )
    digest = compute_schema_digest(rows)
    schema = ChannelSchema(
        schema_id="test",
        version="1.0",
        rows=rows,
        digest=digest,
    )

    states = {}

    for i, row in enumerate(rows):
        h = tuple([float(i * 10)] * 40)
        states[row.channel_id] = compute_quantizer_state(h)

    d1 = compute_normalizer_digest(schema, states)
    d2 = compute_normalizer_digest(schema, states)
    assert d1 == d2
