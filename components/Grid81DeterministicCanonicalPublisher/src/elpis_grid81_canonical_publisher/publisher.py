"""Grid81 atomic canonical snapshot publisher R0.

This module owns publication mechanics only.  It does not manufacture semantic
state, grant capability authority, or turn a promotion plan into permission.

A caller supplies:
  * the current canonical project root;
  * a separately prepared candidate project root containing Canonical/Grid81;
  * the expected current canonical digest;
  * an artifact digest naming the exact upstream publication object;
  * an expected durable-ledger head;
  * an explicit lock path outside Canonical/Grid81.

Publication order is recoverable rather than pretending SQLite and the
filesystem share one transaction:

    validate -> stage -> prove atomic-exchange support
    -> append exact publication receipt to durable ledger
    -> atomic directory exchange -> production-reader verification -> cleanup

If the process dies after durable ledger append but before directory exchange,
the exact same receipt is resume authority.  A different candidate is not.
"""

from __future__ import annotations

import ctypes
import fcntl
import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import stat
from typing import Any

from Grid81.canonical_reader import CanonicalReadError, load_current_grid81


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_AT_FDCWD = -100
_RENAME_EXCHANGE = 0x2


class PublicationError(RuntimeError):
    """Fail-closed publication rejection with a stable machine code."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}:{detail}")


@dataclass(frozen=True)
class CanonicalPublicationReceipt:
    status: str
    publication_receipt_digest: str
    artifact_digest: str
    previous_canonical_digest: str
    resulting_canonical_digest: str
    generation_number: int
    transaction_id: str
    capability_id: str
    resulting_ledger_head: str
    resumed: bool


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise PublicationError(code, detail)


def _require_hex64(value: str, code: str) -> None:
    _require(type(value) is str and _HEX64.fullmatch(value) is not None, code)


def _load_json(path: Path, code: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PublicationError(code) from exc
    _require(type(value) is dict, code)
    return value


def _reject_symlinks(root: Path) -> None:
    _require(root.is_dir(), "CANDIDATE_GRID81_MISSING")
    for current, dirs, files in os.walk(root, followlinks=False):
        base = Path(current)
        for name in (*dirs, *files):
            path = base / name
            if path.is_symlink():
                raise PublicationError("CANDIDATE_SYMLINK", str(path))


def _fsync_tree(root: Path) -> None:
    """Flush staged bytes and directory entries before authority is consumed."""
    files: list[Path] = []
    dirs: list[Path] = []
    for current, child_dirs, child_files in os.walk(root):
        base = Path(current)
        dirs.append(base)
        files.extend(base / name for name in child_files)
        child_dirs.sort()
        child_files.sort()

    for path in sorted(files):
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    for path in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_exchange(left: Path, right: Path) -> None:
    """Linux/POSIX directory exchange; never degrade to a two-rename gap."""
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise PublicationError("ATOMIC_EXCHANGE_UNSUPPORTED")

    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int

    rc = renameat2(
        _AT_FDCWD,
        os.fsencode(left),
        _AT_FDCWD,
        os.fsencode(right),
        _RENAME_EXCHANGE,
    )
    if rc != 0:
        err = ctypes.get_errno()
        raise PublicationError("ATOMIC_EXCHANGE_FAILED", str(err))


def _commit_exchange(left: Path, right: Path) -> None:
    """Separate seam so crash-window recovery can be tested without weakening probe."""
    _atomic_exchange(left, right)


def _exchange_probe(parent: Path, token: str) -> None:
    """Prove same-parent directory exchange works before consuming ledger authority."""
    a = parent / f".grid81.exchange-probe-a.{token}"
    b = parent / f".grid81.exchange-probe-b.{token}"
    for path in (a, b):
        if path.exists():
            shutil.rmtree(path)

    a.mkdir()
    b.mkdir()
    (a / "A").write_bytes(b"A")
    (b / "B").write_bytes(b"B")

    try:
        _atomic_exchange(a, b)
        _require((a / "B").is_file() and (b / "A").is_file(),
                 "ATOMIC_EXCHANGE_PROBE_FAILED")
        _atomic_exchange(a, b)
        _require((a / "A").is_file() and (b / "B").is_file(),
                 "ATOMIC_EXCHANGE_PROBE_FAILED")
    finally:
        shutil.rmtree(a, ignore_errors=True)
        shutil.rmtree(b, ignore_errors=True)
        _fsync_dir(parent)


@contextmanager
def _exclusive_lock(lock_path: Path):
    lock_path = lock_path.absolute()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    _require("Canonical/Grid81" not in lock_path.as_posix(),
             "LOCK_INSIDE_CANONICAL_GRID81")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _ledger_snapshot(ledger: Any) -> dict:
    try:
        ok, reason = ledger.verify_chain()
        snapshot = ledger.to_dict()
    except Exception as exc:
        raise PublicationError("LEDGER_UNREADABLE") from exc
    _require(ok is True, "LEDGER_INVALID", str(reason))
    _require(type(snapshot) is dict and type(snapshot.get("entries")) is list,
             "LEDGER_SERIALIZATION_INVALID")
    return snapshot


def _exact_reserved_entry(
    snapshot: dict,
    *,
    receipt_digest: str,
    expected_previous_head: str,
) -> dict | None:
    matches = [
        entry for entry in snapshot["entries"]
        if entry.get("receipt_digest") == receipt_digest
        and entry.get("previous_head") == expected_previous_head
    ]
    _require(len(matches) <= 1, "LEDGER_DUPLICATE_RECEIPT")
    return matches[0] if matches else None


def _publication_payload(
    *,
    artifact_digest: str,
    previous_canonical_digest: str,
    candidate: Any,
    expected_ledger_head: str,
) -> dict:
    return {
        "schema": "elpis.grid81.atomic-publication-receipt.v1",
        "artifact_digest": artifact_digest,
        "previous_canonical_digest": previous_canonical_digest,
        "resulting_canonical_digest": candidate.canonical_digest,
        "generation_number": candidate.generation_number,
        "generation_file_sha256": candidate.generation_raw_sha256,
        "generation_semantic_digest": candidate.generation_semantic_digest,
        "transaction_id": candidate.transaction_id,
        "capability_id": candidate.capability_id,
        "expected_ledger_head": expected_ledger_head,
    }


def _validate_candidate_sidecars(candidate_root: Path, candidate: Any) -> None:
    grid = candidate_root / "Canonical" / "Grid81"
    head_path = grid / "HEAD.json"
    consumed_path = grid / ".consumed_capability.json"
    receipt_path = grid / ".consumption_receipt.json"

    head = _load_json(head_path, "CANDIDATE_HEAD_INVALID")
    consumed = _load_json(consumed_path, "CANDIDATE_CONSUMED_CAPABILITY_INVALID")
    receipt = _load_json(receipt_path, "CANDIDATE_CONSUMPTION_RECEIPT_INVALID")

    _require(head.get("append_only") is True, "CANDIDATE_NOT_APPEND_ONLY")
    _require(head.get("transaction_id") == candidate.transaction_id,
             "CANDIDATE_HEAD_TRANSACTION_MISMATCH")
    _require(head.get("capability_id") == candidate.capability_id,
             "CANDIDATE_HEAD_CAPABILITY_MISMATCH")

    _require(consumed.get("capability_id") == candidate.capability_id,
             "CANDIDATE_CONSUMED_CAPABILITY_MISMATCH")
    lifecycle = consumed.get("lifecycle", {})
    _require(type(lifecycle) is dict, "CANDIDATE_LIFECYCLE_INVALID")
    _require(lifecycle.get("consumed") is True
             and lifecycle.get("consumption_count") == 1
             and lifecycle.get("replay_permitted") is False,
             "CANDIDATE_LIFECYCLE_INVALID")
    target = consumed.get("target_bindings", {})
    txn = consumed.get("transaction_binding", {})
    _require(type(target) is dict and target.get("generation") == candidate.generation_number,
             "CANDIDATE_TARGET_GENERATION_MISMATCH")
    _require(type(txn) is dict and txn.get("transaction_id") == candidate.transaction_id,
             "CANDIDATE_CONSUMED_TRANSACTION_MISMATCH")

    _require(receipt.get("commit_status") == "COMMITTED",
             "CANDIDATE_RECEIPT_NOT_COMMITTED")
    _require(receipt.get("capability_id") == candidate.capability_id,
             "CANDIDATE_RECEIPT_CAPABILITY_MISMATCH")
    _require(receipt.get("transaction_id") == candidate.transaction_id,
             "CANDIDATE_RECEIPT_TRANSACTION_MISMATCH")
    _require(receipt.get("generation_file_sha256") == candidate.generation_raw_sha256,
             "CANDIDATE_RECEIPT_GENERATION_HASH_MISMATCH")
    _require(receipt.get("head_file_sha256") == _sha256_file(head_path),
             "CANDIDATE_RECEIPT_HEAD_HASH_MISMATCH")
    _require(receipt.get("consumed_capability_sha256") == _sha256_file(consumed_path),
             "CANDIDATE_RECEIPT_CONSUMED_HASH_MISMATCH")


def _validate_successor(
    project_root: Path,
    candidate_root: Path,
    current: Any,
    candidate: Any,
) -> None:
    expected_generation = current.generation_number + 1
    _require(candidate.generation_number == expected_generation,
             "GENERATION_NOT_IMMEDIATE_SUCCESSOR")

    expected_rel = f"Canonical/Grid81/generations/{expected_generation:06d}.json"
    _require(candidate.generation_path == expected_rel,
             "GENERATION_PATH_MISMATCH")

    current_grid = project_root / "Canonical" / "Grid81"
    candidate_grid = candidate_root / "Canonical" / "Grid81"
    _reject_symlinks(candidate_grid)

    current_generations = current_grid / "generations"
    candidate_generations = candidate_grid / "generations"
    _require(current_generations.is_dir() and candidate_generations.is_dir(),
             "GENERATIONS_DIRECTORY_MISSING")

    old_names = sorted(
        p.name for p in current_generations.iterdir()
        if p.is_file()
    )
    candidate_names = sorted(
        p.name for p in candidate_generations.iterdir()
        if p.is_file()
    )
    expected_names = sorted((*old_names, f"{expected_generation:06d}.json"))
    _require(candidate_names == expected_names, "GENERATION_SET_MISMATCH")

    for name in old_names:
        old = current_generations / name
        new = candidate_generations / name
        _require(not old.is_symlink() and not new.is_symlink(),
                 "GENERATION_SYMLINK")
        _require(old.read_bytes() == new.read_bytes(),
                 "HISTORICAL_GENERATION_MUTATED", name)

    next_gen = _load_json(
        candidate_generations / f"{expected_generation:06d}.json",
        "CANDIDATE_GENERATION_INVALID",
    )
    _require(
        next_gen.get("prior_generation_binding")
        == current.generation_semantic_digest,
        "PRIOR_GENERATION_BINDING_MISMATCH",
    )

    head = _load_json(candidate_grid / "HEAD.json", "CANDIDATE_HEAD_INVALID")
    _require(
        head.get("previous_generation_binding")
        == current.generation_semantic_digest,
        "HEAD_PREVIOUS_GENERATION_BINDING_MISMATCH",
    )

    _validate_candidate_sidecars(candidate_root, candidate)


def publish_candidate(
    *,
    project_root: Path | str,
    candidate_root: Path | str,
    ledger: Any,
    artifact_digest: str,
    expected_current_canonical_digest: str,
    expected_ledger_head: str,
    lock_path: Path | str,
) -> CanonicalPublicationReceipt:
    """Atomically publish one pre-qualified immediate successor snapshot.

    The canonical repository state itself is never used as a staging workspace.
    The candidate root is read-only input.  A private sibling staging directory
    is copied, fsynced, and exchanged atomically with Canonical/Grid81.
    """
    project_root = Path(project_root).absolute()
    candidate_root = Path(candidate_root).absolute()
    lock_path = Path(lock_path).absolute()

    _require_hex64(artifact_digest, "ARTIFACT_DIGEST_INVALID")
    _require_hex64(expected_current_canonical_digest,
                   "EXPECTED_CANONICAL_DIGEST_INVALID")
    _require_hex64(expected_ledger_head, "EXPECTED_LEDGER_HEAD_INVALID")

    target = project_root / "Canonical" / "Grid81"
    candidate_grid = candidate_root / "Canonical" / "Grid81"
    _require(target.is_dir(), "CURRENT_GRID81_MISSING")
    _require(candidate_grid.is_dir(), "CANDIDATE_GRID81_MISSING")
    _require(target.parent == project_root / "Canonical",
             "CURRENT_LAYOUT_INVALID")

    with _exclusive_lock(lock_path):
        try:
            current = load_current_grid81(project_root)
            candidate = load_current_grid81(candidate_root)
        except CanonicalReadError as exc:
            raise PublicationError("CANONICAL_READER_REJECTED", exc.code) from exc

        _require_hex64(candidate.transaction_id, "CANDIDATE_TRANSACTION_ID_INVALID")
        _require_hex64(candidate.capability_id, "CANDIDATE_CAPABILITY_ID_INVALID")

        payload = _publication_payload(
            artifact_digest=artifact_digest,
            previous_canonical_digest=expected_current_canonical_digest,
            candidate=candidate,
            expected_ledger_head=expected_ledger_head,
        )
        receipt_digest = _digest(payload)
        token = receipt_digest[:20]
        stage = target.parent / f".Grid81.stage.{token}"

        snapshot = _ledger_snapshot(ledger)
        existing = _exact_reserved_entry(
            snapshot,
            receipt_digest=receipt_digest,
            expected_previous_head=expected_ledger_head,
        )
        artifact_seen = bool(ledger.has_receipt(artifact_digest))

        # Crash/retry after a successful exchange: verify the exact reservation,
        # clean the old exchanged directory if it remains, and return idempotently.
        if current.canonical_digest == candidate.canonical_digest:
            _validate_candidate_sidecars(candidate_root, candidate)
            _require(artifact_seen and existing is not None,
                     "CANONICAL_WITHOUT_EXACT_LEDGER_RECEIPT")
            if stage.exists():
                shutil.rmtree(stage)
                _fsync_dir(target.parent)
            return CanonicalPublicationReceipt(
                status="ALREADY_COMMITTED",
                publication_receipt_digest=receipt_digest,
                artifact_digest=artifact_digest,
                previous_canonical_digest=expected_current_canonical_digest,
                resulting_canonical_digest=candidate.canonical_digest,
                generation_number=candidate.generation_number,
                transaction_id=candidate.transaction_id,
                capability_id=candidate.capability_id,
                resulting_ledger_head=ledger.head,
                resumed=True,
            )

        _require(
            current.canonical_digest == expected_current_canonical_digest,
            "STALE_CANONICAL_HEAD",
        )
        _validate_successor(project_root, candidate_root, current, candidate)

        if artifact_seen:
            _require(existing is not None, "ARTIFACT_LEDGER_CONFLICT")
            _require(
                existing.get("entry_digest") == ledger.head,
                "LEDGER_ADVANCED_AFTER_RESERVATION",
            )
            resumed = True
        else:
            _require(existing is None, "LEDGER_RECEIPT_WITHOUT_ARTIFACT")
            _require(ledger.head == expected_ledger_head, "STALE_LEDGER_HEAD")
            resumed = False

        # Build and flush the exact candidate snapshot before consuming authority.
        if stage.exists():
            shutil.rmtree(stage)
        shutil.copytree(candidate_grid, stage, symlinks=False)
        _reject_symlinks(stage)
        _fsync_tree(stage)
        _fsync_dir(target.parent)

        # Prove the kernel/filesystem can exchange directories atomically before
        # the durable ledger reservation is appended.
        _exchange_probe(target.parent, token)

        if not resumed:
            try:
                entry = ledger.append(
                    expected_ledger_head,
                    receipt_digest,
                    artifact_digest,
                )
            except ValueError as exc:
                raise PublicationError("STALE_LEDGER_HEAD") from exc
            reserved_head = entry.entry_digest
        else:
            reserved_head = existing["entry_digest"]

        try:
            _commit_exchange(stage, target)
            _fsync_dir(target.parent)
        except Exception as exc:
            # The exact durable reservation intentionally remains so retry can
            # resume the same candidate without consuming authority twice.
            if isinstance(exc, PublicationError):
                raise
            raise PublicationError("ATOMIC_EXCHANGE_FAILED") from exc

        try:
            committed = load_current_grid81(project_root)
            _require(
                committed.canonical_digest == candidate.canonical_digest,
                "POST_COMMIT_CANONICAL_DIGEST_MISMATCH",
            )
            _require(
                committed.generation_number == candidate.generation_number,
                "POST_COMMIT_GENERATION_MISMATCH",
            )
        except Exception as verification_error:
            try:
                _commit_exchange(stage, target)
                _fsync_dir(target.parent)
            except Exception as rollback_error:
                raise PublicationError("ROLLBACK_FAILED") from rollback_error
            if isinstance(verification_error, PublicationError):
                raise verification_error
            if isinstance(verification_error, CanonicalReadError):
                raise PublicationError(
                    "POST_COMMIT_READER_REJECTED",
                    verification_error.code,
                ) from verification_error
            raise PublicationError("POST_COMMIT_VERIFICATION_FAILED") from verification_error

        # stage now contains the previous canonical snapshot.
        shutil.rmtree(stage)
        _fsync_dir(target.parent)

        return CanonicalPublicationReceipt(
            status="COMMITTED",
            publication_receipt_digest=receipt_digest,
            artifact_digest=artifact_digest,
            previous_canonical_digest=expected_current_canonical_digest,
            resulting_canonical_digest=candidate.canonical_digest,
            generation_number=candidate.generation_number,
            transaction_id=candidate.transaction_id,
            capability_id=candidate.capability_id,
            resulting_ledger_head=reserved_head,
            resumed=resumed,
        )
