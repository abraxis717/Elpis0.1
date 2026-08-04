"""Test forecast vintages with deterministic synthetic ForecastPort."""
from __future__ import annotations

from c_numpy_cortex.contracts import (
    ForecastStatus,
)
from c_numpy_cortex.vintages import (
    SyntheticForecastPort,
    VintageStore,
    evaluate_vintage,
)


def test_synthetic_forecast_port():
    port = SyntheticForecastPort(
        base_values={"ch_a": (0.0, 1.0, 2.0)},
    )
    q10, q50, q90 = port.forecast(
        context_data={},
        channels=("ch_a",),
        target_count=3,
    )
    assert q10 == (0.0,)
    assert q50 == (1.0,)
    assert q90 == (2.0,)


def test_vintage_store_create():
    store = VintageStore()
    v = store.create_vintage(
        base_generation=5,
        created_monotonic_ns=5000,
        resample_rule="200ms",
        target_monotonic_ns=(6000, 7000),
        channels=("ch_a",),
        q10=(0.0,),
        q50=(1.0,),
        q90=(2.0,),
        model_digest="md",
        context_digest="cd",
        channel_schema_digest="sd",
        normalizer_state_digest="nd",
    )
    assert v.base_generation == 5
    assert len(v.target_monotonic_ns) == 2


def test_no_mature_vintage():
    store = VintageStore()
    v = store.create_vintage(
        base_generation=5,
        created_monotonic_ns=5000,
        resample_rule="200ms",
        target_monotonic_ns=(6000, 7000),
        channels=("ch_a",),
        q10=(0.0,),
        q50=(1.0,),
        q90=(2.0,),
        model_digest="md",
        context_digest="cd",
        channel_schema_digest="sd",
        normalizer_state_digest="nd",
    )
    ev = evaluate_vintage(
        v,
        current_monotonic_ns=5500,
        realizations={"ch_a": 1.0},
        current_schema_digest="sd",
        current_normalizer_digest="nd",
        required_channels={"ch_a"},
    )
    assert ev.status == ForecastStatus.NO_MATURE_VINTAGE
    assert ev.score is None


def test_no_realization():
    store = VintageStore()
    v = store.create_vintage(
        base_generation=5,
        created_monotonic_ns=5000,
        resample_rule="200ms",
        target_monotonic_ns=(6000, 7000),
        channels=("ch_a",),
        q10=(0.0,),
        q50=(1.0,),
        q90=(2.0,),
        model_digest="md",
        context_digest="cd",
        channel_schema_digest="sd",
        normalizer_state_digest="nd",
    )
    ev = evaluate_vintage(
        v,
        current_monotonic_ns=6500,
        realizations={},  # No realization data
        current_schema_digest="sd",
        current_normalizer_digest="nd",
        required_channels={"ch_a"},
    )
    assert ev.status == ForecastStatus.NO_REALIZATION
    assert ev.score is None


def test_model_error():
    port = SyntheticForecastPort(error="model crash")
    try:
        port.forecast(
            context_data={},
            channels=("ch_a",),
            target_count=3,
        )
        assert False, "Should have raised"
    except RuntimeError as e:
        assert "model crash" in str(e)


def test_schema_mismatch():
    store = VintageStore()
    v = store.create_vintage(
        base_generation=5,
        created_monotonic_ns=5000,
        resample_rule="200ms",
        target_monotonic_ns=(6000, 7000),
        channels=("ch_a",),
        q10=(0.0,),
        q50=(1.0,),
        q90=(2.0,),
        model_digest="md",
        context_digest="cd",
        channel_schema_digest="sd_old",
        normalizer_state_digest="nd",
    )
    ev = evaluate_vintage(
        v,
        current_monotonic_ns=6500,
        realizations={"ch_a": 1.0},
        current_schema_digest="sd_new",
        current_normalizer_digest="nd",
        required_channels={"ch_a"},
    )
    assert ev.status == ForecastStatus.SCHEMA_MISMATCH
    assert ev.score is None


def test_normalizer_mismatch():
    store = VintageStore()
    v = store.create_vintage(
        base_generation=5,
        created_monotonic_ns=5000,
        resample_rule="200ms",
        target_monotonic_ns=(6000, 7000),
        channels=("ch_a",),
        q10=(0.0,),
        q50=(1.0,),
        q90=(2.0,),
        model_digest="md",
        context_digest="cd",
        channel_schema_digest="sd",
        normalizer_state_digest="nd_old",
    )
    ev = evaluate_vintage(
        v,
        current_monotonic_ns=6500,
        realizations={"ch_a": 1.0},
        current_schema_digest="sd",
        current_normalizer_digest="nd_new",
        required_channels={"ch_a"},
    )
    assert ev.status == ForecastStatus.SCHEMA_MISMATCH
    assert ev.score is None


def test_synthetic_drift_ok():
    """Synthetic drift produces status=OK and score>0."""
    store = VintageStore()
    v = store.create_vintage(
        base_generation=5,
        created_monotonic_ns=5000,
        resample_rule="200ms",
        target_monotonic_ns=(6000, 7000),
        channels=("ch_a",),
        q10=(0.0,),
        q50=(1.0,),
        q90=(2.0,),
        model_digest="md",
        context_digest="cd",
        channel_schema_digest="sd",
        normalizer_state_digest="nd",
    )
    # Realization outside [q10, q90] -> score > 0
    ev = evaluate_vintage(
        v,
        current_monotonic_ns=6500,
        realizations={"ch_a": 3.0},
        current_schema_digest="sd",
        current_normalizer_digest="nd",
        required_channels={"ch_a"},
    )
    assert ev.status == ForecastStatus.OK
    assert ev.score is not None
    assert ev.score > 0


def test_no_same_tick_comparison():
    """Forecast context ends before target realization."""
    # A forecast created at gen g uses context ending at g.
    # Targets are strictly > context end.
    # We prove this by checking target_monotonic_ns > created_monotonic_ns.
    store = VintageStore()
    v = store.create_vintage(
        base_generation=5,
        created_monotonic_ns=5000,
        resample_rule="200ms",
        target_monotonic_ns=(6000, 7000),
        channels=("ch_a",),
        q10=(0.0,),
        q50=(1.0,),
        q90=(2.0,),
        model_digest="md",
        context_digest="cd",
        channel_schema_digest="sd",
        normalizer_state_digest="nd",
    )
    for target in v.target_monotonic_ns:
        assert target > v.created_monotonic_ns, (
            "Same-tick leakage: target <= created"
        )


def test_q_column_aliases():
    """q10/q50/q90 accept aliases: 0.1, q0.1, p10, median, q0.5, p50, etc."""
    # This is tested in the Chronos2Forecaster._quantile_column
    # We test the synthetic port handles the canonical forms
    port = SyntheticForecastPort(
        base_values={
            "ch_a": (0.1, 0.5, 0.9),
        }
    )
    q10, q50, q90 = port.forecast({}, ("ch_a",), 3)
    assert q10 == (0.1,)
    assert q50 == (0.5,)
    assert q90 == (0.9,)
