from __future__ import annotations

from pathlib import Path
import glob
import hashlib
import json
import os

import numpy as np

from .contracts import PacketCommitManifest


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)

    return h.hexdigest()


def _fsync_file(fd: int) -> None:
    os.fsync(fd)


def _fsync_dir(path: str) -> None:
    fd = os.open(path, os.O_RDONLY)

    try:
        os.fsync(fd)
    except (OSError, AttributeError):
        pass

    os.close(fd)


def _atomic_rename(tmp_path: str, final_path: str) -> None:
    os.replace(tmp_path, final_path)


class AtomicPacketWriter:
    """Write generation packets atomically.

    Transaction sequence:
    1. Write grid81.g.npz.tmp, fsync, rename to grid81.g.npz
    2. Write state.g.json.tmp, fsync, rename to state.g.json
    3. Compute SHA-256 of both files
    4. Write commit_manifest.json.tmp, fsync, rename
    5. Fsync directory

    The manifest replacement is the sole commit point.
    """

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_generation(
        self,
        generation: int,
        digits: np.ndarray,
        valid_mask: np.ndarray,
        bitplanes: np.ndarray,
        metadata: dict,
        channel_schema_digest: str,
        created_monotonic_ns: int,
        fresh_until_monotonic_ns: int,
    ) -> PacketCommitManifest:
        npz_path = str(self.output_dir / f"grid81.{generation}.npz")
        json_path = str(self.output_dir / f"state.{generation}.json")

        # 1. Write NPZ atomically
        npz_tmp = npz_path + ".tmp"

        try:
            np.savez_compressed(
                npz_tmp,
                digits=digits,
                valid_mask=valid_mask,
                bitplanes=bitplanes,
            )
        finally:
            pass

        # np.savez_compressed may create npz_tmp.npz on some platforms
        # Handle both cases
        actual_tmp = npz_tmp + ".npz" if os.path.exists(npz_tmp + ".npz") else npz_tmp
        _atomic_rename(actual_tmp, npz_path)

        # Clean up the other tmp variant if it exists
        for candidate in [npz_tmp, npz_tmp + ".npz"]:
            if os.path.exists(candidate):
                try:
                    os.unlink(candidate)
                except OSError:
                    pass

        # 2. Write JSON atomically
        json_tmp = json_path + ".tmp"
        fd = os.open(json_tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)

        try:
            content = json.dumps(
                metadata,
                indent=2,
                sort_keys=True,
            )
            os.write(fd, content.encode())
            _fsync_file(fd)
        finally:
            os.close(fd)

        _atomic_rename(json_tmp, json_path)

        # 3. Compute digests
        packet_sha = _file_sha256(npz_path)
        metadata_sha = _file_sha256(json_path)

        # 4. Write manifest atomically
        manifest = PacketCommitManifest(
            abi_version="cnumpycortex.packet-set.v2",
            generation=generation,
            packet_file=npz_path,
            metadata_file=json_path,
            packet_sha256=packet_sha,
            metadata_sha256=metadata_sha,
            channel_schema_digest=channel_schema_digest,
            created_monotonic_ns=created_monotonic_ns,
            fresh_until_monotonic_ns=fresh_until_monotonic_ns,
        )

        manifest_path = str(
            self.output_dir / "commit_manifest.json"
        )
        manifest_tmp = manifest_path + ".tmp"
        fd = os.open(
            manifest_tmp,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o644,
        )

        try:
            manifest_json = json.dumps(
                {
                    "abi_version": manifest.abi_version,
                    "generation": manifest.generation,
                    "packet_file": manifest.packet_file,
                    "metadata_file": manifest.metadata_file,
                    "packet_sha256": manifest.packet_sha256,
                    "metadata_sha256": manifest.metadata_sha256,
                    "channel_schema_digest": (
                        manifest.channel_schema_digest
                    ),
                    "created_monotonic_ns": (
                        manifest.created_monotonic_ns
                    ),
                    "fresh_until_monotonic_ns": (
                        manifest.fresh_until_monotonic_ns
                    ),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            os.write(fd, manifest_json.encode())
            _fsync_file(fd)
        finally:
            os.close(fd)

        _atomic_rename(manifest_tmp, manifest_path)
        _fsync_dir(str(self.output_dir))

        return manifest


def read_manifest(output_dir: str) -> PacketCommitManifest | None:
    """Read the currently committed manifest."""
    manifest_path = Path(output_dir) / "commit_manifest.json"

    if not manifest_path.exists():
        return None

    with manifest_path.open() as f:
        data = json.load(f)

    return PacketCommitManifest(
        abi_version=data["abi_version"],
        generation=data["generation"],
        packet_file=data["packet_file"],
        metadata_file=data["metadata_file"],
        packet_sha256=data["packet_sha256"],
        metadata_sha256=data["metadata_sha256"],
        channel_schema_digest=data["channel_schema_digest"],
        created_monotonic_ns=data["created_monotonic_ns"],
        fresh_until_monotonic_ns=data["fresh_until_monotonic_ns"],
    )


def verify_generation(
    manifest: PacketCommitManifest,
) -> bool:
    """Verify checksums of packet and metadata files."""
    if not Path(manifest.packet_file).exists():
        return False

    if not Path(manifest.metadata_file).exists():
        return False

    actual_packet = _file_sha256(manifest.packet_file)

    if actual_packet != manifest.packet_sha256:
        return False

    actual_metadata = _file_sha256(manifest.metadata_file)

    if actual_metadata != manifest.metadata_sha256:
        return False

    return True


def crash_recovery(output_dir: str) -> None:
    """Recover from incomplete writes after crash.

    Steps:
    1. Read committed manifest if present
    2. Delete stale temporary files
    3. Remove generation files newer than committed manifest
    4. Preserve committed generation and up to 3 older ones
    """
    out = Path(output_dir)

    # Delete stale tmp files
    for tmp in out.glob("*.tmp"):
        try:
            tmp.unlink()
        except OSError:
            pass

    manifest = read_manifest(str(out))

    if manifest is None:
        # No manifest -> clean up all generation files
        for f in sorted(out.glob("grid81.*.npz")):
            try:
                f.unlink()
            except OSError:
                pass

        for f in sorted(out.glob("state.*.json")):
            try:
                f.unlink()
            except OSError:
                pass

        return

    # Remove generation files newer than committed manifest
    committed_gen = manifest.generation

    for f in sorted(out.glob("grid81.*.npz")):
        try:
            gen_str = f.stem.split(".")[-1]
            gen = int(gen_str)

            if gen > committed_gen:
                f.unlink()

                # Also remove paired state file
                state_file = out / f"state.{gen}.json"

                if state_file.exists():
                    state_file.unlink()

        except (ValueError, IndexError):
            pass


def retention_cleanup(
    output_dir: str,
    retention_count: int = 4,
) -> None:
    """Keep exactly N committed generations, delete older ones."""
    manifest = read_manifest(str(Path(output_dir)))

    if manifest is None:
        return

    current_gen = manifest.generation

    # Find all committed generations
    generations: list[int] = []

    for f in sorted(Path(output_dir).glob("grid81.*.npz")):
        # Skip tmp artifacts
        if ".tmp" in f.name:
            continue
        try:
            gen_str = f.stem.split(".")[-1]
            gen = int(gen_str)
            generations.append(gen)
        except (ValueError, IndexError):
            continue

    generations.sort()

    # Keep the last retention_count generations
    to_delete = generations[:-retention_count]

    for gen in to_delete:
        npz = Path(output_dir) / f"grid81.{gen}.npz"
        state = Path(output_dir) / f"state.{gen}.json"

        if npz.exists():
            try:
                npz.unlink()
            except OSError:
                pass

        if state.exists():
            try:
                state.unlink()
            except OSError:
                pass

    # Also clean up orphaned .tmp.npz files
    for f in Path(output_dir).glob("*.tmp.npz"):
        try:
            f.unlink()
        except OSError:
            pass
