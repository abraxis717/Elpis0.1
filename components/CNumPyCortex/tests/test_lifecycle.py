"""Test lifecycle classification — all five values, no sixth."""
from __future__ import annotations

from c_numpy_cortex.contracts import (
    ChannelDescriptor,
    ChannelSchema,
    ObservedValue,
    ObservationValidity,
    PacketLifecycle,
    compute_schema_digest,
)
from c_numpy_cortex.lifecycle import classify_lifecycle


def _make_schema(required_count: int = 2) -> ChannelSchema:
    rows = []
    for i in range(9):
        rows.append(
            ChannelDescriptor(
                channel_id=f"ch_{i}",
                source_kind="psutil",
                unit="none",
                sampling_class="psutil",
                expected_period_ns=50_000_000,
                stale_after_ns=100_000_000,
                transform_id="robust_z",
                required=(i < required_count),
            )
        )
    digest = compute_schema_digest(tuple(rows))
    return ChannelSchema(
        schema_id="test", version="1.0", rows=tuple(rows), digest=digest
    )


def _make_values(
    schema: ChannelSchema,
    validity: ObservationValidity = ObservationValidity.FRESH,
    value: float = 1.0,
) -> dict[str, ObservedValue]:
    return {
        r.channel_id: ObservedValue(
            value=value if validity == ObservationValidity.FRESH else None,
            observed_monotonic_ns=1000,
            source_sequence=1,
            validity=validity,
            error_code=None,
        )
        for r in schema.rows
    }


def test_lifecycle_ready():
    schema = _make_schema(required_count=2)
    values = _make_values(schema, ObservationValidity.FRESH, 1.0)
    lifecycle, reasons = classify_lifecycle(
        schema, values, 1000, None,
    )
    assert lifecycle == PacketLifecycle.READY


def test_lifecycle_invalid_required_missing():
    schema = _make_schema(required_count=2)
    values = _make_values(schema)
    # Remove a required channel
    del values[schema.rows[0].channel_id]
    lifecycle, reasons = classify_lifecycle(
        schema, values, 1000, None,
    )
    assert lifecycle == PacketLifecycle.INVALID
    assert any("REQUIRED_MISSING" in r for r in reasons)


def test_lifecycle_invalid_required_invalid():
    schema = _make_schema(required_count=2)
    values = _make_values(schema)
    # Mark a required channel as INVALID
    req_id = schema.rows[0].channel_id
    values[req_id] = ObservedValue(
        value=None,
        observed_monotonic_ns=1000,
        source_sequence=1,
        validity=ObservationValidity.INVALID,
        error_code="sensor_fault",
    )
    lifecycle, reasons = classify_lifecycle(
        schema, values, 1000, None,
    )
    assert lifecycle == PacketLifecycle.INVALID


def test_lifecycle_stale_past_deadline():
    schema = _make_schema(required_count=2)
    values = _make_values(schema, ObservationValidity.FRESH, 1.0)
    lifecycle, reasons = classify_lifecycle(
        schema, values, now_monotonic_ns=5000,
        fresh_until_monotonic_ns=3000,
    )
    assert lifecycle == PacketLifecycle.STALE


def test_lifecycle_stale_required_stale():
    schema = _make_schema(required_count=2)
    values = _make_values(schema)
    # Mark a required channel as STALE
    req_id = schema.rows[0].channel_id
    values[req_id] = ObservedValue(
        value=1.0,
        observed_monotonic_ns=1000,
        source_sequence=1,
        validity=ObservationValidity.STALE,
        error_code=None,
    )
    lifecycle, reasons = classify_lifecycle(
        schema, values, 1000, None,
    )
    assert lifecycle == PacketLifecycle.STALE


def test_lifecycle_degraded_optional_stale():
    schema = _make_schema(required_count=2)
    values = _make_values(schema, ObservationValidity.FRESH, 1.0)
    # Mark an optional channel as STALE
    opt_id = schema.rows[2].channel_id
    values[opt_id] = ObservedValue(
        value=1.0,
        observed_monotonic_ns=1000,
        source_sequence=1,
        validity=ObservationValidity.STALE,
        error_code=None,
    )
    lifecycle, reasons = classify_lifecycle(
        schema, values, 1000, None,
    )
    assert lifecycle == PacketLifecycle.DEGRADED


def test_lifecycle_degraded_previous_fallback():
    schema = _make_schema(required_count=2)
    values = _make_values(schema, ObservationValidity.FRESH, 1.0)
    lifecycle, reasons = classify_lifecycle(
        schema, values, 1000, None,
        previous_fallback=True,
    )
    assert lifecycle == PacketLifecycle.DEGRADED
    assert "DEGRADED_READ_PREVIOUS_GENERATION" in reasons


def test_lifecycle_warming():
    """Warming is set by the compile path when < 9 samples exist."""
    # The classifier itself doesn't know about sample counts,
    # but the compile path sets WARMING for required rows with <9 samples.
    # We test this at the compile integration level.
    schema = _make_schema(required_count=2)
    values = _make_values(schema, ObservationValidity.FRESH, 1.0)
    lifecycle, reasons = classify_lifecycle(
        schema, values, 1000, None,
    )
    # Without warming flag, should be READY
    assert lifecycle == PacketLifecycle.READY


def test_no_sixth_lifecycle():
    """Exactly five lifecycle values, no sixth."""
    assert len(PacketLifecycle) == 5
    expected = {"WARMING", "READY", "DEGRADED", "STALE", "INVALID"}
    actual = {v.value for v in PacketLifecycle}
    assert actual == expected


def test_degraded_read_previous_generation_reason():
    schema = _make_schema(required_count=2)
    values = _make_values(schema, ObservationValidity.FRESH, 1.0)
    lifecycle, reasons = classify_lifecycle(
        schema, values, 1000, None,
        previous_fallback=True,
    )
    assert lifecycle == PacketLifecycle.DEGRADED
    assert "DEGRADED_READ_PREVIOUS_GENERATION" in reasons
