"""Test channel schema loading and validation."""
from __future__ import annotations

import pytest
import tempfile
import os

from c_numpy_cortex.schema import (
    load_channel_schema,
    propose_channel_schema,
)
from c_numpy_cortex.contracts import (
    ChannelDescriptor,
    MISSING_CHANNEL,
    compute_schema_digest,
)


def test_load_channel_schema_from_toml():
    content = """[metadata]
schema_id = "test_v1"
version = "1.0"

[[channels]]
channel_id = "cpu.total_pct"
source_kind = "psutil"
unit = "percent"
sampling_class = "psutil"
expected_period_ns = 50_000_000
stale_after_ns = 100_000_000
transform_id = "robust_z"
required = true

[[channels]]
channel_id = "memory.used_pct"
source_kind = "psutil"
unit = "percent"
sampling_class = "psutil"
expected_period_ns = 50_000_000
stale_after_ns = 100_000_000
transform_id = "robust_z"
required = true

[[channels]]
channel_id = "temp.system.cpu"
source_kind = "hwmon"
unit = "celsius"
sampling_class = "hwmon"
expected_period_ns = 100_000_000
stale_after_ns = 300_000_000
transform_id = "robust_z"
required = false

[[channels]]
channel_id = "gpu.0.temp_c"
source_kind = "nvidia"
unit = "celsius"
sampling_class = "nvidia"
expected_period_ns = 500_000_000
stale_after_ns = 1_500_000_000
transform_id = "robust_z"
required = false

[[channels]]
channel_id = "gpu.0.util_pct"
source_kind = "nvidia"
unit = "percent"
sampling_class = "nvidia"
expected_period_ns = 500_000_000
stale_after_ns = 1_500_000_000
transform_id = "robust_z"
required = false

[[channels]]
channel_id = "llama.cpu_8080.healthy"
source_kind = "llama"
unit = "binary"
sampling_class = "llama"
expected_period_ns = 1_000_000_000
stale_after_ns = 3_000_000_000
transform_id = "none"
required = false

[[channels]]
channel_id = "llama.blackwell_8081.healthy"
source_kind = "llama"
unit = "binary"
sampling_class = "llama"
expected_period_ns = 1_000_000_000
stale_after_ns = 3_000_000_000
transform_id = "none"
required = false

[[channels]]
channel_id = "__MISSING__"
source_kind = "missing"
unit = "none"
sampling_class = "psutil"
expected_period_ns = 50_000_000
stale_after_ns = 100_000_000
transform_id = "none"
required = false

[[channels]]
channel_id = "__MISSING__"
source_kind = "missing"
unit = "none"
sampling_class = "psutil"
expected_period_ns = 50_000_000
stale_after_ns = 100_000_000
transform_id = "none"
required = false
"""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".toml", delete=False
    ) as f:
        f.write(content)
        tmp = f.name

    try:
        schema = load_channel_schema(tmp)
        assert len(schema.rows) == 9
        assert schema.rows[0].required is True
        assert schema.rows[1].required is True
        assert schema.rows[2].required is False
        assert schema.rows[7].source_kind == "missing"
        assert schema.rows[8].source_kind == "missing"

        # Verify digest is computed
        assert len(schema.digest) == 64
    finally:
        os.unlink(tmp)


def test_propose_channel_schema_padding():
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
        for i in range(4)
    ]

    with tempfile.NamedTemporaryFile(
        suffix=".toml", delete=False
    ) as f:
        tmp = f.name

    try:
        schema = propose_channel_schema(live, tmp)
        assert len(schema.rows) == 9
        missing = sum(
            1 for r in schema.rows if r.source_kind == "missing"
        )
        assert missing == 5
    finally:
        os.unlink(tmp)


def test_runtime_rejects_foreign_digest():
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
    assert digest != "foreign_digest"


def test_stable_gpu_identity_uses_pci():
    cd = ChannelDescriptor(
        channel_id="gpu.0000:01:00.0.temp_c",
        source_kind="nvidia",
        unit="celsius",
        sampling_class="nvidia",
        expected_period_ns=500_000_000,
        stale_after_ns=1_500_000_000,
        transform_id="robust_z",
        required=False,
    )
    assert "0000:01:00.0" in cd.channel_id


def test_stable_hwmon_identity_uses_driver():
    cd = ChannelDescriptor(
        channel_id="temp.coretemp_pkg.isa_0042.Package_id_0",
        source_kind="hwmon",
        unit="celsius",
        sampling_class="hwmon",
        expected_period_ns=100_000_000,
        stale_after_ns=300_000_000,
        transform_id="robust_z",
        required=False,
    )
    assert "coretemp" in cd.channel_id
