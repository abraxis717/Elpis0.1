"""Test ObservedValue, freshness, and multi-rate."""
from __future__ import annotations

from c_numpy_cortex.contracts import (
    ObservedValue,
    ObservationValidity,
)


def test_source_sequence_monotonic():
    vals = [
        ObservedValue(
            value=float(i),
            observed_monotonic_ns=1000 + i * 50_000_000,
            source_sequence=i,
            validity=ObservationValidity.FRESH,
            error_code=None,
        )
        for i in range(10)
    ]
    for i in range(1, len(vals)):
        assert vals[i].source_sequence > vals[i-1].source_sequence


def test_fresh_requires_finite():
    ov = ObservedValue(
        value=42.0,
        observed_monotonic_ns=100,
        source_sequence=1,
        validity=ObservationValidity.FRESH,
        error_code=None,
    )
    assert ov.value == 42.0


def test_stale_retains_value():
    ov = ObservedValue(
        value=42.0,
        observed_monotonic_ns=100,
        source_sequence=1,
        validity=ObservationValidity.STALE,
        error_code=None,
    )
    assert ov.value == 42.0
    assert ov.validity == ObservationValidity.STALE


def test_invalid_uses_none():
    ov = ObservedValue(
        value=None,
        observed_monotonic_ns=100,
        source_sequence=1,
        validity=ObservationValidity.INVALID,
        error_code="sensor_error",
    )
    assert ov.value is None
    assert ov.validity == ObservationValidity.INVALID


def test_missing_uses_none():
    ov = ObservedValue(
        value=None,
        observed_monotonic_ns=100,
        source_sequence=1,
        validity=ObservationValidity.MISSING,
        error_code="no_source",
    )
    assert ov.value is None


def test_valid_zero_distinct_from_missing():
    valid_zero = ObservedValue(
        value=0.0,
        observed_monotonic_ns=100,
        source_sequence=1,
        validity=ObservationValidity.FRESH,
        error_code=None,
    )
    missing = ObservedValue(
        value=None,
        observed_monotonic_ns=100,
        source_sequence=1,
        validity=ObservationValidity.MISSING,
        error_code="no_source",
    )
    assert valid_zero.value == 0.0
    assert missing.value is None
    assert valid_zero.validity != missing.validity
