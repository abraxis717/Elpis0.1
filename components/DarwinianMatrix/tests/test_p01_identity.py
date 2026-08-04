from __future__ import annotations

from pathlib import Path

import pytest

from DarwinianMatrix.trm.p01_identity import (
    P01ArtifactIdentity,
)


def write_pair(
    root: Path,
    *,
    checkpoint_bytes: bytes = b"checkpoint",
    adapter_bytes: bytes = b"adapter",
):
    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    checkpoint = root / "trm_hermes_best.pt"
    adapter = root / "grid_refiner.py"

    checkpoint.write_bytes(checkpoint_bytes)
    adapter.write_bytes(adapter_bytes)

    return checkpoint, adapter


def test_identity_hashes_opaque_artifacts(tmp_path):
    checkpoint, adapter = write_pair(
        tmp_path / "first"
    )

    identity = P01ArtifactIdentity.from_files(
        checkpoint_path=checkpoint,
        adapter_path=adapter,
    )

    assert identity.checkpoint_size == len(
        b"checkpoint"
    )
    assert identity.adapter_size == len(
        b"adapter"
    )
    assert len(identity.checkpoint_sha256) == 64
    assert len(identity.adapter_sha256) == 64
    assert identity.fallback_allowed is False


def test_identity_is_portable_across_filesystem_paths(
    tmp_path,
):
    first_checkpoint, first_adapter = write_pair(
        tmp_path / "first"
    )

    second_checkpoint, second_adapter = write_pair(
        tmp_path / "second"
    )

    first = P01ArtifactIdentity.from_files(
        checkpoint_path=first_checkpoint,
        adapter_path=first_adapter,
    )

    second = P01ArtifactIdentity.from_files(
        checkpoint_path=second_checkpoint,
        adapter_path=second_adapter,
    )

    assert first.digest() == second.digest()
    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )


def test_checkpoint_change_changes_identity(tmp_path):
    first_checkpoint, first_adapter = write_pair(
        tmp_path / "first",
        checkpoint_bytes=b"checkpoint-a",
    )

    second_checkpoint, second_adapter = write_pair(
        tmp_path / "second",
        checkpoint_bytes=b"checkpoint-b",
    )

    first = P01ArtifactIdentity.from_files(
        checkpoint_path=first_checkpoint,
        adapter_path=first_adapter,
    )

    second = P01ArtifactIdentity.from_files(
        checkpoint_path=second_checkpoint,
        adapter_path=second_adapter,
    )

    assert first.digest() != second.digest()


def test_adapter_change_changes_identity(tmp_path):
    first_checkpoint, first_adapter = write_pair(
        tmp_path / "first",
        adapter_bytes=b"adapter-a",
    )

    second_checkpoint, second_adapter = write_pair(
        tmp_path / "second",
        adapter_bytes=b"adapter-b",
    )

    first = P01ArtifactIdentity.from_files(
        checkpoint_path=first_checkpoint,
        adapter_path=first_adapter,
    )

    second = P01ArtifactIdentity.from_files(
        checkpoint_path=second_checkpoint,
        adapter_path=second_adapter,
    )

    assert first.digest() != second.digest()


def test_canonical_identity_excludes_absolute_paths(
    tmp_path,
):
    checkpoint, adapter = write_pair(
        tmp_path / "absolute" / "location"
    )

    identity = P01ArtifactIdentity.from_files(
        checkpoint_path=checkpoint,
        adapter_path=adapter,
    )

    payload_text = str(
        identity.canonical_payload()
    )

    assert str(tmp_path) not in payload_text
    assert (
        identity.checkpoint_filename
        == "trm_hermes_best.pt"
    )
    assert (
        identity.adapter_filename
        == "grid_refiner.py"
    )


def test_missing_checkpoint_is_rejected(tmp_path):
    _, adapter = write_pair(
        tmp_path / "files"
    )

    with pytest.raises(FileNotFoundError):
        P01ArtifactIdentity.from_files(
            checkpoint_path=(
                tmp_path / "missing.pt"
            ),
            adapter_path=adapter,
        )


def test_missing_adapter_is_rejected(tmp_path):
    checkpoint, _ = write_pair(
        tmp_path / "files"
    )

    with pytest.raises(FileNotFoundError):
        P01ArtifactIdentity.from_files(
            checkpoint_path=checkpoint,
            adapter_path=(
                tmp_path / "missing.py"
            ),
        )
