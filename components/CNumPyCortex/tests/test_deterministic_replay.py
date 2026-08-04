"""Test deterministic replay evidence."""
from __future__ import annotations

import numpy as np

from c_numpy_cortex.contracts import (
    ChannelDescriptor,
    ChannelSchema,
    ObservedValue,
    ObservationValidity,
    compute_schema_digest,
)
from c_numpy_cortex.encoding import (
    compile_thermal_frame,
    compute_quantizer_state,
    compute_normalizer_digest,
    encode_bitplanes,
)
from c_numpy_cortex.ring import ChronologicalRing
from c_numpy_cortex.contracts import PacketLifecycle


def _make_test_schema() -> ChannelSchema:
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
    return ChannelSchema(
        schema_id="test",
        version="1.0",
        rows=rows,
        digest=digest,
    )


def test_deterministic_replay_identical():
    """Replay the same stream twice, get identical results."""
    schema = _make_test_schema()

    # Generate deterministic synthetic stream
    stream: list[ObservedValue] = []
    seq = 0

    for t in range(100):
        for ch_idx, row in enumerate(schema.rows):
            seq += 1
            stream.append(
                ObservedValue(
                    value=float(t * 10 + ch_idx),
                    observed_monotonic_ns=t * 50_000_000,
                    source_sequence=seq,
                    validity=ObservationValidity.FRESH,
                    error_code=None,
                )
            )

    def replay():
        ring = ChronologicalRing(schema, capacity=256)
        quant_states = {}

        for obs in stream:
            for row in schema.rows:
                if obs.value == float(
                    (obs.observed_monotonic_ns // 50_000_000) * 10
                    + schema.rows.index(row)
                ):
                    ring.append_for(row.channel_id, obs)
                    break

        for row in schema.rows:
            history = ring.get_valid_history(
                row.channel_id, max_count=256
            )
            quant_states[row.channel_id] = compute_quantizer_state(history)

        normalizer_digest = compute_normalizer_digest(
            schema, quant_states
        )

        ring_data = {}
        for row in schema.rows:
            ring_data[row.channel_id] = ring.get_chronological(
                row.channel_id, count=9
            )

        tokens, mask, bits, cell_meta = compile_thermal_frame(
            schema,
            ring_data,
            quant_states,
            generation=1,
            wall_time_ns=1_700_000_000_000_000_000,
            monotonic_ns=1000,
            lifecycle=PacketLifecycle.WARMING,
            lifecycle_reasons=(),
        )

        return tokens, mask, bits, normalizer_digest

    t1, m1, b1, nd1 = replay()
    t2, m2, b2, nd2 = replay()

    assert np.array_equal(t1, t2), "Token grids differ"
    assert np.array_equal(m1, m2), "Validity masks differ"
    assert np.array_equal(b1, b2), "Bitplanes differ"
    assert nd1 == nd2, "Normalizer digests differ"


def test_deterministic_schema_artifact():
    """Schema artifact bytes are deterministic."""
    schema1 = _make_test_schema()
    schema2 = _make_test_schema()

    assert schema1.digest == schema2.digest
    assert schema1.schema_id == schema2.schema_id


def test_deterministic_bitplane_encoding():
    """Bitplane encoding is deterministic."""
    tokens = np.full((9, 9), 5, dtype=np.uint8)
    b1 = encode_bitplanes(tokens)
    b2 = encode_bitplanes(tokens)
    assert np.array_equal(b1, b2)
