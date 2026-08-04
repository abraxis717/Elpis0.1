"""Test retention specifically."""
from __future__ import annotations

import os
import tempfile
import numpy as np

from c_numpy_cortex.packets import (
    AtomicPacketWriter,
    retention_cleanup,
)


def test_retention_exactly_four():
    """Retention keeps exactly four committed generations."""
    with tempfile.TemporaryDirectory() as tmp:
        writer = AtomicPacketWriter(tmp)
        tokens = np.ones((9, 9), dtype=np.uint8) * 5
        mask = np.ones((9, 9), dtype=np.uint8)
        bits = np.zeros((4, 9, 9), dtype=np.uint8)

        for gen in range(1, 11):
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

        npz_files = [
            f for f in os.listdir(tmp)
            if f.startswith("grid81.") and f.endswith(".npz") and ".tmp" not in f
        ]
        assert len(npz_files) == 4
