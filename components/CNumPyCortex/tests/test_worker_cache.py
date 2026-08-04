"""Test worker cache immutability."""
from __future__ import annotations

from c_numpy_cortex.cache import WorkerCache
from c_numpy_cortex.contracts import (
    ObservedValue,
    ObservationValidity,
)


def test_cache_snapshot_is_immutable():
    cache = WorkerCache()
    cache.publish({
        "ch_a": ObservedValue(
            value=1.0,
            observed_monotonic_ns=100,
            source_sequence=1,
            validity=ObservationValidity.FRESH,
            error_code=None,
        ),
    })

    snap1, ver1 = cache.snapshot()

    cache.publish({
        "ch_a": ObservedValue(
            value=2.0,
            observed_monotonic_ns=200,
            source_sequence=2,
            validity=ObservationValidity.FRESH,
            error_code=None,
        ),
    })

    snap2, ver2 = cache.snapshot()

    assert ver2 > ver1
    assert snap1["ch_a"].value == 1.0
    assert snap2["ch_a"].value == 2.0


def test_cache_publish_updates():
    cache = WorkerCache()

    ov1 = ObservedValue(
        value=1.0,
        observed_monotonic_ns=100,
        source_sequence=1,
        validity=ObservationValidity.FRESH,
        error_code=None,
    )
    ov2 = ObservedValue(
        value=2.0,
        observed_monotonic_ns=200,
        source_sequence=1,
        validity=ObservationValidity.FRESH,
        error_code=None,
    )

    cache.publish({"ch_a": ov1})
    cache.publish({"ch_b": ov2})

    snap, _ = cache.snapshot()
    assert "ch_a" in snap
    assert "ch_b" in snap
    assert snap["ch_a"].value == 1.0
    assert snap["ch_b"].value == 2.0
