"""Test frozen contracts, enums, semantic identity."""
from __future__ import annotations

import numpy as np
import pytest

from c_numpy_cortex.contracts import (
    ChannelDescriptor,
    ChannelSchema,
    ForecastEvaluation,
    ForecastStatus,
    ForecastVintage,
    MISSING_CHANNEL,
    ObservationPacketV2,
    ObservationValidity,
    ObservedValue,
    PacketCommitManifest,
    PacketLifecycle,
    TensorSpaceIdentity,
    compute_schema_digest,
)


def test_observation_validity_vocabulary():
    assert ObservationValidity.FRESH.value == "FRESH"
    assert ObservationValidity.STALE.value == "STALE"
    assert ObservationValidity.INVALID.value == "INVALID"
    assert ObservationValidity.MISSING.value == "MISSING"
    assert len(ObservationValidity) == 4


def test_packet_lifecycle_vocabulary():
    assert PacketLifecycle.WARMING.value == "WARMING"
    assert PacketLifecycle.READY.value == "READY"
    assert PacketLifecycle.DEGRADED.value == "DEGRADED"
    assert PacketLifecycle.STALE.value == "STALE"
    assert PacketLifecycle.INVALID.value == "INVALID"
    assert len(PacketLifecycle) == 5


def test_forecast_status_vocabulary():
    assert ForecastStatus.OK.value == "OK"
    assert ForecastStatus.WARMING.value == "WARMING"
    assert ForecastStatus.NO_MATURE_VINTAGE.value == "NO_MATURE_VINTAGE"
    assert ForecastStatus.NO_REALIZATION.value == "NO_REALIZATION"
    assert ForecastStatus.MODEL_ERROR.value == "MODEL_ERROR"
    assert ForecastStatus.SCHEMA_MISMATCH.value == "SCHEMA_MISMATCH"
    assert ForecastStatus.STALE_FORECAST.value == "STALE_FORECAST"


def test_channel_descriptor_slots_and_frozen():
    cd = ChannelDescriptor(
        channel_id="cpu.total_pct",
        source_kind="psutil",
        unit="percent",
        sampling_class="psutil",
        expected_period_ns=50_000_000,
        stale_after_ns=100_000_000,
        transform_id="robust_z",
        required=True,
    )
    assert cd.required is True
    assert cd.source_kind == "psutil"
    assert cd.expected_period_ns > 0
    assert cd.stale_after_ns >= cd.expected_period_ns


def test_channel_descriptor_missing():
    assert MISSING_CHANNEL.required is False
    assert MISSING_CHANNEL.source_kind == "missing"


def test_observed_value_fresh():
    ov = ObservedValue(
        value=42.0,
        observed_monotonic_ns=100,
        source_sequence=1,
        validity=ObservationValidity.FRESH,
        error_code=None,
    )
    assert ov.value == 42.0
    assert ov.validity == ObservationValidity.FRESH


def test_observed_value_missing():
    ov = ObservedValue(
        value=None,
        observed_monotonic_ns=100,
        source_sequence=1,
        validity=ObservationValidity.MISSING,
        error_code="no_source",
    )
    assert ov.value is None
    assert ov.validity == ObservationValidity.MISSING


def test_observed_value_valid_zero():
    """A valid measured value may numerically equal zero."""
    ov = ObservedValue(
        value=0.0,
        observed_monotonic_ns=100,
        source_sequence=1,
        validity=ObservationValidity.FRESH,
        error_code=None,
    )
    assert ov.value == 0.0
    assert ov.validity == ObservationValidity.FRESH


def test_channel_schema_exactly_nine_rows():
    rows = tuple(
        ChannelDescriptor(
            channel_id=f"ch_{i}",
            source_kind="psutil",
            unit="none",
            sampling_class="psutil",
            expected_period_ns=50_000_000,
            stale_after_ns=100_000_000,
            transform_id="robust_z",
            required=(i < 2),
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
    assert len(schema.rows) == 9


def test_channel_schema_rejects_non_nine():
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
        for i in range(8)
    )
    digest = compute_schema_digest(rows)

    with pytest.raises(ValueError, match="exactly 9"):
        ChannelSchema(
            schema_id="bad",
            version="1.0",
            rows=rows,
            digest=digest,
        )


def test_channel_schema_rejects_duplicate_ids():
    rows = tuple(
        ChannelDescriptor(
            channel_id="same_id",
            source_kind="psutil",
            unit="none",
            sampling_class="psutil",
            expected_period_ns=50_000_000,
            stale_after_ns=100_000_000,
            transform_id="robust_z",
            required=False,
        )
        for _ in range(9)
    )
    digest = compute_schema_digest(rows)

    with pytest.raises(ValueError, match="Duplicate"):
        ChannelSchema(
            schema_id="dup",
            version="1.0",
            rows=rows,
            digest=digest,
        )


def test_channel_schema_rejects_invalid_period():
    rows = tuple(
        ChannelDescriptor(
            channel_id=f"ch_{i}",
            source_kind="psutil",
            unit="none",
            sampling_class="psutil",
            expected_period_ns=0,
            stale_after_ns=0,
            transform_id="robust_z",
            required=False,
        )
        for i in range(9)
    )
    digest = compute_schema_digest(rows)

    with pytest.raises(ValueError):
        ChannelSchema(
            schema_id="bad",
            version="1.0",
            rows=rows,
            digest=digest,
        )


def test_channel_schema_rejects_stale_less_than_period():
    rows = tuple(
        ChannelDescriptor(
            channel_id=f"ch_{i}",
            source_kind="psutil",
            unit="none",
            sampling_class="psutil",
            expected_period_ns=100,
            stale_after_ns=50,
            transform_id="robust_z",
            required=False,
        )
        for i in range(9)
    )
    digest = compute_schema_digest(rows)

    with pytest.raises(ValueError):
        ChannelSchema(
            schema_id="bad",
            version="1.0",
            rows=rows,
            digest=digest,
        )


def test_schema_digest_includes_required():
    rows_a = tuple(
        ChannelDescriptor(
            channel_id=f"ch_{i}",
            source_kind="psutil",
            unit="none",
            sampling_class="psutil",
            expected_period_ns=50_000_000,
            stale_after_ns=100_000_000,
            transform_id="robust_z",
            required=True,
        )
        for i in range(9)
    )
    rows_b = tuple(
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
    digest_a = compute_schema_digest(rows_a)
    digest_b = compute_schema_digest(rows_b)
    assert digest_a != digest_b


def test_tensor_space_identity_thermal():
    space = TensorSpaceIdentity.thermal(layout_digest="abc123")
    assert space.semantic_space == "grid81.thermal.ordinal.v1"
    assert space.shape == (9, 9)
    assert space.dtype == "uint8"
    assert space.vocabulary_size == 10


def test_tensor_space_identity_not_structural():
    space = TensorSpaceIdentity.thermal(layout_digest="abc123")
    assert space.semantic_space != "grid81.structural.v1"


def test_packet_commit_manifest():
    manifest = PacketCommitManifest(
        abi_version="cnumpycortex.packet-set.v2",
        generation=1,
        packet_file="grid81.1.npz",
        metadata_file="state.1.json",
        packet_sha256="a" * 64,
        metadata_sha256="b" * 64,
        channel_schema_digest="c" * 64,
        created_monotonic_ns=1000,
        fresh_until_monotonic_ns=3000,
    )
    assert manifest.abi_version == "cnumpycortex.packet-set.v2"
    assert manifest.generation == 1


def test_forecast_vintage():
    vintage = ForecastVintage(
        vintage_id="v1",
        base_generation=5,
        created_monotonic_ns=5000,
        resample_rule="200ms",
        target_monotonic_ns=(6000, 7000, 8000),
        channels=("ch_a", "ch_b"),
        q10=(0.0, 0.0),
        q50=(1.0, 1.0),
        q90=(2.0, 2.0),
        model_digest="md",
        context_digest="cd",
        channel_schema_digest="sd",
        normalizer_state_digest="nd",
    )
    assert vintage.base_generation == 5
    assert len(vintage.target_monotonic_ns) == 3


def test_forecast_evaluation_ok():
    ev = ForecastEvaluation(
        vintage_id="v1",
        status=ForecastStatus.OK,
        score=0.5,
        horizon_steps=3,
        channels_evaluated=2,
        reason_codes=(),
    )
    assert ev.score == 0.5
    assert ev.status == ForecastStatus.OK


def test_forecast_evaluation_no_score_when_not_ok():
    ev = ForecastEvaluation(
        vintage_id="v1",
        status=ForecastStatus.MODEL_ERROR,
        score=None,
        horizon_steps=0,
        channels_evaluated=0,
        reason_codes=("ERROR",),
    )
    assert ev.score is None


def test_observation_packet_v2():
    space = TensorSpaceIdentity.thermal(layout_digest="ld")
    pkt = ObservationPacketV2(
        generation=1,
        wall_time_ns=1000,
        monotonic_ns=500,
        lifecycle=PacketLifecycle.READY,
        lifecycle_reasons=(),
        space=space,
        channel_schema_digest="sd",
        normalizer_state_digest="nd",
        tokens_sha256="ts",
        bits_sha256="bs",
        digit_entropy=0.5,
        bit_entropy=(0.3, 0.4, 0.5, 0.6),
        entropy_event_score=0.4,
        transition_rate=0.1,
        valid_cell_count=81,
    )
    assert pkt.generation == 1
    assert pkt.lifecycle == PacketLifecycle.READY
    assert pkt.valid_cell_count == 81


def test_six_live_channels_produce_three_missing():
    live = [
        ChannelDescriptor(
            channel_id=f"live_{i}",
            source_kind="psutil",
            unit="none",
            sampling_class="psutil",
            expected_period_ns=50_000_000,
            stale_after_ns=100_000_000,
            transform_id="robust_z",
            required=(i < 2),
        )
        for i in range(6)
    ]
    from c_numpy_cortex.schema import propose_channel_schema
    import tempfile, os

    with tempfile.NamedTemporaryFile(
        suffix=".toml", delete=False
    ) as f:
        tmp = f.name

    try:
        schema = propose_channel_schema(live, tmp)
        missing_count = sum(
            1
            for r in schema.rows
            if r.source_kind == "missing"
        )
        assert missing_count == 3

        # Missing rows are optional
        for r in schema.rows:
            if r.source_kind == "missing":
                assert r.required is False

        # No channel duplication
        ids = [r.channel_id for r in schema.rows]
        live_ids = ids[:6]
        assert len(set(live_ids)) == 6
    finally:
        os.unlink(tmp)
