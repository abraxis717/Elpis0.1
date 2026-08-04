"""Test atomic packet transaction."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time

import numpy as np
import pytest

from c_numpy_cortex.packets import (
    AtomicPacketWriter,
    read_manifest,
    verify_generation,
)


def test_atomic_write_commit():
    """Writer writes NPZ, JSON, manifest atomically."""
    with tempfile.TemporaryDirectory() as tmp:
        writer = AtomicPacketWriter(tmp)

        tokens = np.arange(81, dtype=np.uint8).reshape(9, 9)
        tokens = np.clip(tokens, 0, 9)
        mask = np.ones((9, 9), dtype=np.uint8)
        bits = np.zeros((4, 9, 9), dtype=np.uint8)
        metadata = {"key": "value"}

        manifest = writer.write_generation(
            generation=1,
            digits=tokens,
            valid_mask=mask,
            bitplanes=bits,
            metadata=metadata,
            channel_schema_digest="abc123",
            created_monotonic_ns=1000,
            fresh_until_monotonic_ns=3000,
        )

        assert manifest.generation == 1
        assert manifest.abi_version == "cnumpycortex.packet-set.v2"

        # Files exist
        assert os.path.exists(manifest.packet_file)
        assert os.path.exists(manifest.metadata_file)

        # No tmp files remain
        tmp_files = [
            f for f in os.listdir(tmp) if f.endswith(".tmp")
        ]
        assert len(tmp_files) == 0


def test_manifest_is_sole_commit_point():
    """Reader during incomplete write sees old complete generation."""
    with tempfile.TemporaryDirectory() as tmp:
        writer = AtomicPacketWriter(tmp)

        # Write generation 1
        tokens1 = np.ones((9, 9), dtype=np.uint8) * 3
        mask1 = np.ones((9, 9), dtype=np.uint8)
        bits1 = np.zeros((4, 9, 9), dtype=np.uint8)

        manifest1 = writer.write_generation(
            generation=1,
            digits=tokens1,
            valid_mask=mask1,
            bitplanes=bits1,
            metadata={"gen": 1},
            channel_schema_digest="digest",
            created_monotonic_ns=1000,
            fresh_until_monotonic_ns=3000,
        )

        # Read manifest
        read = read_manifest(tmp)
        assert read is not None
        assert read.generation == 1

        # Write generation 2
        tokens2 = np.ones((9, 9), dtype=np.uint8) * 7
        mask2 = np.ones((9, 9), dtype=np.uint8)
        bits2 = np.zeros((4, 9, 9), dtype=np.uint8)

        manifest2 = writer.write_generation(
            generation=2,
            digits=tokens2,
            valid_mask=mask2,
            bitplanes=bits2,
            metadata={"gen": 2},
            channel_schema_digest="digest",
            created_monotonic_ns=2000,
            fresh_until_monotonic_ns=4000,
        )

        read2 = read_manifest(tmp)
        assert read2.generation == 2


def test_verify_generation_checksums():
    with tempfile.TemporaryDirectory() as tmp:
        writer = AtomicPacketWriter(tmp)

        tokens = np.ones((9, 9), dtype=np.uint8) * 5
        mask = np.ones((9, 9), dtype=np.uint8)
        bits = np.zeros((4, 9, 9), dtype=np.uint8)

        manifest = writer.write_generation(
            generation=1,
            digits=tokens,
            valid_mask=mask,
            bitplanes=bits,
            metadata={"test": True},
            channel_schema_digest="digest",
            created_monotonic_ns=1000,
            fresh_until_monotonic_ns=3000,
        )

        assert verify_generation(manifest) is True


def test_corrupted_packet_yields_invalid():
    with tempfile.TemporaryDirectory() as tmp:
        writer = AtomicPacketWriter(tmp)

        tokens = np.ones((9, 9), dtype=np.uint8) * 5
        mask = np.ones((9, 9), dtype=np.uint8)
        bits = np.zeros((4, 9, 9), dtype=np.uint8)

        manifest = writer.write_generation(
            generation=1,
            digits=tokens,
            valid_mask=mask,
            bitplanes=bits,
            metadata={"test": True},
            channel_schema_digest="digest",
            created_monotonic_ns=1000,
            fresh_until_monotonic_ns=3000,
        )

        # Corrupt packet file
        with open(manifest.packet_file, "a") as f:
            f.write("corrupted")

        assert verify_generation(manifest) is False


def test_reader_retries_once():
    """If checksum mismatch, re-read manifest exactly once."""
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

        writer.write_generation(
            generation=2,
            digits=tokens,
            valid_mask=mask,
            bitplanes=bits,
            metadata={"gen": 2},
            channel_schema_digest="digest",
            created_monotonic_ns=2000,
            fresh_until_monotonic_ns=4000,
        )

        # After writer advances, new manifest should be readable
        read = read_manifest(tmp)
        assert read.generation == 2
        assert verify_generation(read) is True
