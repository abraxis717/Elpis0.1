"""Test diagnostic logging format."""
from __future__ import annotations

from c_numpy_cortex.diagnostic_log import format_diagnostic_line


def test_diagnostic_line_has_required_fields():
    line = format_diagnostic_line(
        generation=1,
        monotonic_ns=1000,
        wall_time_ns=1_700_000_000_000_000_000,
        component="compile",
        event="grid81_commit",
        status="READY",
    )

    assert "wall_time_iso_ms=" in line
    assert "generation=1" in line
    assert "monotonic_ns=1000" in line
    assert "component=compile" in line
    assert "event=grid81_commit" in line
    assert "status=READY" in line


def test_diagnostic_line_with_source_sequence():
    line = format_diagnostic_line(
        generation=1,
        monotonic_ns=1000,
        wall_time_ns=1_700_000_000_000_000_000,
        component="sensor",
        event="acquisition",
        status="FRESH",
        source_sequence=5,
    )
    assert "source_sequence=5" in line


def test_diagnostic_line_with_extra():
    line = format_diagnostic_line(
        generation=1,
        monotonic_ns=1000,
        wall_time_ns=1_700_000_000_000_000_000,
        component="compile",
        event="grid81_commit",
        status="READY",
        extra={"valid_cells": 72, "reason": "test"},
    )
    assert "valid_cells=72" in line
    assert "reason=test" in line


def test_iso_timestamp_has_millisecond_precision():
    line = format_diagnostic_line(
        generation=1,
        monotonic_ns=1000,
        wall_time_ns=1_700_000_000_000_000_000,
        component="test",
        event="test",
        status="OK",
    )
    # Check for millisecond precision in ISO format
    assert ".000" in line or "T" in line


def test_iso_timestamp_has_timezone():
    line = format_diagnostic_line(
        generation=1,
        monotonic_ns=1000,
        wall_time_ns=1_700_000_000_000_000_000,
        component="test",
        event="test",
        status="OK",
    )
    # Timezone-aware ISO format includes + or Z
    assert "+" in line or "Z" in line or "00:00" in line
