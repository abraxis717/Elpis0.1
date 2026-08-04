"""Test crash recovery and retention."""
from __future__ import annotations

import os
import tempfile
import json

import numpy as np
import pytest

from c_numpy_cortex.packets import (
    AtomicPacketWriter,
    crash_recovery,
    read_manifest,
    retention_cleanup,
)


def test_crash_recovery_deletes_stale_tmp():
    """Stale tmp files are deleted on recovery."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create stale tmp files
        open(os.path.join(tmp, "grid81.1.npz.tmp"), "w").close()
        open(os.path.join(tmp, "state.1.json.tmp"), "w").close()
        open(os.path.join(tmp, "commit_manifest.json.tmp"), "w").close()

        crash_recovery(tmp)

        remaining = os.listdir(tmp)
        assert "grid81.1.npz.tmp" not in remaining
        assert "state.1.json.tmp" not in remaining


def test_crash_recovery_removes_newer_generations():
    """Remove generation files newer than committed manifest."""
    with tempfile.TemporaryDirectory() as tmp:
        writer = AtomicPacketWriter(tmp)

        tokens = np.ones((9, 9), dtype=np.uint8) * 5
        mask = np.ones((9, 9), dtype=np.uint8)
        bits = np.zeros((4, 9, 9), dtype=np.uint8)

        # Write generation 1
        writer.write_generation(
            generation=1,
            digits=tokens,
            valid_mask=mask,
            bitplanes=bits,
            metadata={"gen": 1},
            channel_schema_digest="digest",
            created_monotonic_ns=1000,
            fresh_until_monotonic_ns=3000,
        )

        # Manually create generation 2 files (simulating crash mid-write)
        np.savez_compressed(
            os.path.join(tmp, "grid81.2.npz"),
            digits=tokens,
            valid_mask=mask,
            bitplanes=bits,
        )
        with open(os.path.join(tmp, "state.2.json"), "w") as f:
            json.dump({"gen": 2}, f)

        crash_recovery(tmp)

        # Gen 2 files should be gone
        assert not os.path.exists(os.path.join(tmp, "grid81.2.npz"))
        assert not os.path.exists(os.path.join(tmp, "state.2.json"))

        # Gen 1 should remain
        assert os.path.exists(os.path.join(tmp, "grid81.1.npz"))


def test_crash_recovery_no_manifest():
    """No manifest -> clean up all generation files."""
    with tempfile.TemporaryDirectory() as tmp:
        np.savez_compressed(
            os.path.join(tmp, "grid81.1.npz"),
            digits=np.zeros((9, 9), dtype=np.uint8),
            valid_mask=np.zeros((9, 9), dtype=np.uint8),
            bitplanes=np.zeros((4, 9, 9), dtype=np.uint8),
        )

        crash_recovery(tmp)

        remaining = [f for f in os.listdir(tmp) if f.startswith("grid81.")]
        assert len(remaining) == 0


def test_retention_keeps_four():
    """Retention keeps exactly 4 committed generations."""
    with tempfile.TemporaryDirectory() as tmp:
        writer = AtomicPacketWriter(tmp)
        tokens = np.ones((9, 9), dtype=np.uint8) * 5
        mask = np.ones((9, 9), dtype=np.uint8)
        bits = np.zeros((4, 9, 9), dtype=np.uint8)

        for gen in range(1, 7):
            writer.write_generation(
                generation=gen,
                digits=tokens,
                valid_mask=mask,
                bitplanes=bits,
                metadata={"gen": gen},
                channel_schema_digest="digest",
                created_monotonic_ns=gen * 1000,
                fresh_until_monotonic_ns=gen * 1000 + 2000,
            )
            retention_cleanup(tmp, retention_count=4)

        # Should have exactly 4 generations
        npz_files = [
            f for f in os.listdir(tmp)
            if f.startswith("grid81.") and f.endswith(".npz") and ".tmp" not in f
        ]
        assert len(npz_files) == 4

        # Should be generations 3,4,5,6
        for f in npz_files:
            gen_num = int(f.replace("grid81.", "").replace(".npz", ""))
            assert gen_num in (3, 4, 5, 6)


def test_retention_preserves_current():
    """Never delete the currently committed generation."""
    with tempfile.TemporaryDirectory() as tmp:
        writer = AtomicPacketWriter(tmp)
        tokens = np.ones((9, 9), dtype=np.uint8) * 5
        mask = np.ones((9, 9), dtype=np.uint8)
        bits = np.zeros((4, 9, 9), dtype=np.uint8)

        writer.write_generation(
            generation=1,
            digits=tokens,
            valid_mask=mask,
            bitplanes=bits,
            metadata={"gen": 1},
            channel_schema_digest="digest",
            created_monotonic_ns=1000,
            fresh_until_monotonic_ns=3000,
        )

        retention_cleanup(tmp, retention_count=4)

        assert os.path.exists(os.path.join(tmp, "grid81.1.npz"))
