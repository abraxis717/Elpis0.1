"""Grid81 serialized, recoverable canonical snapshot publisher R1.

This module owns publication mechanics only.  It does not manufacture semantic
state, grant capability authority, or turn a promotion plan into permission.

A caller supplies:
  * the current canonical project root;
  * a separately prepared candidate project root containing Canonical/Grid81;
  * the expected current canonical digest;
  * an artifact digest naming the exact upstream publication object;
  * an expected durable-ledger head;
  * optionally, an assertion of the publisher-derived Canonical parent lock.

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

from Grid81.canonical_reader import (
    CanonicalReadError, load_current_grid81, canonical_namespace_lock,
    _load_current_grid81_locked,
)
from elpis_grid81_application_executor import DurableApplicationLedger
from elpis_grid81_promotion_authority import (
    PromotionAuthorityError,
    require_promotion_capability,
)


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
    promotion_capability_digest: str
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
def _exclusive_lock(project_root: Path):
    acquired = False
    try:
        with canonical_namespace_lock(project_root, exclusive=True):
            acquired = True
            yield
    except CanonicalReadError as exc:
        raise PublicationError("PUBLICATION_LOCK_INVALID", exc.code) from exc
    except OSError as exc:
        raise PublicationError("PUBLICATION_IO_FAILED" if acquired else "PUBLICATION_LOCK_UNAVAILABLE") from exc


def publication_lock_path(project_root: Path | str) -> Path:
    """Physical directory lock; aliases of the project root resolve identically."""
    return Path(project_root).resolve(strict=True) / "Canonical"


def _checkpoint(name: str) -> None:
    """No-op fault-injection seam. Tests may kill the process at this boundary."""


def _tree_identity(grid: Path) -> str:
    _reject_symlinks(grid)
    inventory = []
    for path in sorted(grid.rglob("*")):
        mode = path.lstat().st_mode
        _require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), "CANDIDATE_FILE_TYPE")
        inventory.append([path.relative_to(grid).as_posix(),
                          _sha256_file(path) if stat.S_ISREG(mode) else None])
    return _digest(inventory)


def _read_recovery(path: Path) -> dict | None:
    if not path.exists() and not path.is_symlink():
        return None
    _require(not path.is_symlink() and path.is_file(), "INVALID_RECOVERY_STATE")
    record = _load_json(path, "INVALID_RECOVERY_STATE")
    _require(set(record) == {"schema", "payload", "receipt_digest", "tree_digest", "ledger_identity"}
             and record.get("schema") == "elpis.grid81.publication-recovery.v1"
             and type(record.get("payload")) is dict,
             "INVALID_RECOVERY_STATE")
    _require(_digest(record["payload"]) == record["receipt_digest"], "INVALID_RECOVERY_STATE")
    _require_hex64(record["tree_digest"], "INVALID_RECOVERY_STATE")
    payload = record["payload"]
    digest_fields = {
        "artifact_digest", "promotion_capability_digest", "previous_canonical_digest",
        "resulting_canonical_digest", "generation_file_sha256", "generation_semantic_digest",
        "transaction_id", "capability_id", "expected_ledger_head",
    }
    _require(set(payload) == digest_fields | {"schema", "generation_number"}
             and payload.get("schema") == "elpis.grid81.atomic-publication-receipt.v1"
             and type(payload.get("generation_number")) is int
             and payload["generation_number"] > 0, "INVALID_RECOVERY_STATE")
    for field in digest_fields:
        _require_hex64(payload[field], "INVALID_RECOVERY_STATE")
    identity = record["ledger_identity"]
    _require(type(identity) is list and len(identity) == 2
             and all(type(n) is int and n >= 0 for n in identity), "INVALID_RECOVERY_STATE")
    return record


def _write_recovery(path: Path, record: dict) -> None:
    # The fixed temporary name is safe under the namespace lock. Interrupted
    # writes are never authority; only the fsynced, replaced record is read.
    temp = path.with_suffix(".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(_canonical_bytes(record))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    _fsync_dir(path.parent)


def _cleanup(stage: Path) -> None:
    _checkpoint("before_cleanup")
    if stage.exists() or stage.is_symlink():
        _require(not stage.is_symlink() and stage.is_dir(), "CORRUPTED_STAGING_STATE")
        shutil.rmtree(stage)
    _checkpoint("during_cleanup")
    _fsync_dir(stage.parent)


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
    promotion_capability_digest: str,
    previous_canonical_digest: str,
    candidate: Any,
    expected_ledger_head: str,
) -> dict:
    return {
        "schema": "elpis.grid81.atomic-publication-receipt.v1",
        "artifact_digest": artifact_digest,
        "promotion_capability_digest": promotion_capability_digest,
        "previous_canonical_digest": previous_canonical_digest,
        "resulting_canonical_digest": candidate.canonical_digest,
        "generation_number": candidate.generation_number,
        "generation_file_sha256": candidate.generation_raw_sha256,
        "generation_semantic_digest": candidate.generation_semantic_digest,
        "transaction_id": candidate.transaction_id,
        "capability_id": candidate.capability_id,
        "expected_ledger_head": expected_ledger_head,
    }


def _validate_candidate_sidecars(
    candidate_root: Path,
    candidate: Any,
    promotion_capability: dict,
) -> None:
    grid = candidate_root / "Canonical" / "Grid81"
    head_path = grid / "HEAD.json"
    consumed_path = grid / ".consumed_capability.json"
    receipt_path = grid / ".consumption_receipt.json"

    head = _load_json(head_path, "CANDIDATE_HEAD_INVALID")
    consumed = _load_json(consumed_path, "CANDIDATE_CONSUMED_CAPABILITY_INVALID")
    receipt = _load_json(receipt_path, "CANDIDATE_CONSUMPTION_RECEIPT_INVALID")
    generation = _load_json(
        candidate_root / candidate.generation_path,
        "CANDIDATE_GENERATION_INVALID",
    )

    _require(head.get("append_only") is True, "CANDIDATE_NOT_APPEND_ONLY")
    _require(head.get("transaction_id") == candidate.transaction_id,
             "CANDIDATE_HEAD_TRANSACTION_MISMATCH")
    _require(head.get("capability_id") == candidate.capability_id,
             "CANDIDATE_HEAD_CAPABILITY_MISMATCH")

    expected_consumed = json.loads(json.dumps(promotion_capability))
    expected_consumed["lifecycle"] = {
        "state": "CONSUMED",
        "consumed": True,
        "consumption_count": 1,
        "replay_permitted": False,
    }
    _require(
        consumed == expected_consumed,
        "CANDIDATE_CONSUMED_CAPABILITY_PROJECTION_MISMATCH",
    )

    _require(
        generation.get("source_capability_digest")
        == promotion_capability["capability_digest"],
        "CANDIDATE_GENERATION_CAPABILITY_DIGEST_MISMATCH",
    )

    _require(receipt.get("commit_status") == "COMMITTED",
             "CANDIDATE_RECEIPT_NOT_COMMITTED")
    _require(receipt.get("capability_id") == candidate.capability_id,
             "CANDIDATE_RECEIPT_CAPABILITY_MISMATCH")
    _require(
        receipt.get("capability_digest")
        == promotion_capability["capability_digest"],
        "CANDIDATE_RECEIPT_CAPABILITY_DIGEST_MISMATCH",
    )
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
    promotion_capability: dict,
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

    _validate_candidate_sidecars(
        candidate_root,
        candidate,
        promotion_capability,
    )


def _validate_candidate_promotion_bindings(
    promotion_capability: dict,
    candidate: Any,
) -> None:
    source = promotion_capability["source_bindings"]
    target = promotion_capability["target_bindings"]

    _require(
        target["target_generation"] == candidate.generation_number,
        "PROMOTION_TARGET_GENERATION_MISMATCH",
    )
    _require(
        target["generation_target"] == candidate.generation_path,
        "PROMOTION_GENERATION_PATH_MISMATCH",
    )
    _require(
        target["head_target"] == "Canonical/Grid81/HEAD.json",
        "PROMOTION_HEAD_PATH_MISMATCH",
    )
    _require(
        target["transaction_id"] == candidate.transaction_id,
        "PROMOTION_TRANSACTION_ID_MISMATCH",
    )
    _require(
        promotion_capability["capability_id"] == candidate.capability_id,
        "PROMOTION_CAPABILITY_ID_MISMATCH",
    )
    _require_hex64(
        source["artifact_digest"],
        "PROMOTION_ARTIFACT_DIGEST_INVALID",
    )


def _validate_live_source_promotion_bindings(
    promotion_capability: dict,
    current: Any,
) -> None:
    target = promotion_capability["target_bindings"]

    _require(
        target["source_generation"] == current.generation_number,
        "PROMOTION_SOURCE_GENERATION_MISMATCH",
    )
    _require(
        target["source_canonical_digest"] == current.canonical_digest,
        "PROMOTION_SOURCE_CANONICAL_DIGEST_MISMATCH",
    )
    _require(
        target["source_generation_semantic_digest"]
        == current.generation_semantic_digest,
        "PROMOTION_SOURCE_SEMANTIC_DIGEST_MISMATCH",
    )


def publish_candidate(
    *,
    project_root: Path | str,
    candidate_root: Path | str,
    ledger: Any,
    promotion_capability: dict,
    lock_path: Path | str | None = None,
) -> CanonicalPublicationReceipt:
    """Atomically publish one pre-qualified immediate successor snapshot.

    The canonical repository state itself is never used as a staging workspace.
    The candidate root is read-only input.  A private sibling staging directory
    is copied, fsynced, and exchanged atomically with Canonical/Grid81.
    """
    project_root = Path(project_root).resolve(strict=True)
    candidate_root = Path(candidate_root).resolve(strict=True)
    derived_lock = publication_lock_path(project_root)
    if lock_path is not None:
        supplied = Path(os.path.abspath(lock_path))
        _require(not supplied.is_symlink() and supplied.resolve() == derived_lock,
                 "WRONG_LOCK_DOMAIN")
    _require(isinstance(ledger, DurableApplicationLedger), "DURABLE_LEDGER_REQUIRED")

    try:
        promotion_capability = require_promotion_capability(
            promotion_capability
        )
    except PromotionAuthorityError as exc:
        raise PublicationError(
            "PROMOTION_CAPABILITY_INVALID",
            exc.detail or exc.code,
        ) from exc

    source_binding = promotion_capability["source_bindings"]
    target_binding = promotion_capability["target_bindings"]
    artifact_digest = source_binding["artifact_digest"]
    promotion_capability_digest = promotion_capability["capability_digest"]
    expected_current_canonical_digest = target_binding[
        "source_canonical_digest"
    ]
    expected_ledger_head = target_binding[
        "expected_publication_ledger_head"
    ]

    target = project_root / "Canonical" / "Grid81"
    candidate_grid = candidate_root / "Canonical" / "Grid81"
    _require(target.is_dir(), "CURRENT_GRID81_MISSING")
    _require(candidate_grid.is_dir(), "CANDIDATE_GRID81_MISSING")
    _require(target.parent == project_root / "Canonical",
             "CURRENT_LAYOUT_INVALID")

    _checkpoint("before_lock")
    with _exclusive_lock(project_root):
        _checkpoint("after_lock")
        _require(not target.is_symlink(), "CURRENT_LAYOUT_INVALID")
        _require(candidate_root != project_root and not candidate_root.is_relative_to(project_root),
                 "CANDIDATE_ROOT_INSIDE_PROJECT_ROOT")
        tree_digest = _tree_identity(candidate_grid)
        try:
            current = _load_current_grid81_locked(project_root)
            candidate = load_current_grid81(candidate_root)
        except CanonicalReadError as exc:
            raise PublicationError("CANONICAL_READER_REJECTED", exc.code) from exc

        _require_hex64(candidate.transaction_id, "CANDIDATE_TRANSACTION_ID_INVALID")
        _require_hex64(candidate.capability_id, "CANDIDATE_CAPABILITY_ID_INVALID")
        _validate_candidate_promotion_bindings(
            promotion_capability,
            candidate,
        )

        payload = _publication_payload(
            artifact_digest=artifact_digest,
            promotion_capability_digest=promotion_capability_digest,
            previous_canonical_digest=expected_current_canonical_digest,
            candidate=candidate,
            expected_ledger_head=expected_ledger_head,
        )
        receipt_digest = _digest(payload)
        token = receipt_digest
        stage = target.parent / f".Grid81.stage.{token}"

        snapshot = _ledger_snapshot(ledger)
        existing = _exact_reserved_entry(
            snapshot,
            receipt_digest=receipt_digest,
            expected_previous_head=expected_ledger_head,
        )
        artifact_seen = bool(ledger.has_receipt(artifact_digest))
        journal_path = target.parent / ".Grid81.publisher-r1.json"
        record = {
            "schema": "elpis.grid81.publication-recovery.v1",
            "payload": payload,
            "receipt_digest": receipt_digest,
            "tree_digest": tree_digest,
            "ledger_identity": list(ledger.storage_identity),
        }
        previous = _read_recovery(journal_path)
        if previous is not None:
            _require(previous["ledger_identity"] == record["ledger_identity"],
                     "PUBLICATION_LEDGER_MISMATCH")
            if previous != record:
                prior = previous["payload"]
                _require(prior.get("resulting_canonical_digest") == current.canonical_digest
                         and prior.get("previous_canonical_digest") != expected_current_canonical_digest,
                         "PUBLICATION_RESERVATION_CONFLICT")
                _require(_exact_reserved_entry(snapshot,
                         receipt_digest=previous["receipt_digest"],
                         expected_previous_head=prior.get("expected_ledger_head")) is not None,
                         "INVALID_RECOVERY_STATE")
                _require(_tree_identity(target) == previous["tree_digest"],
                         "INVALID_RECOVERY_STATE")

        # Crash/retry after a successful exchange: verify the exact reservation,
        # clean the old exchanged directory if it remains, and return idempotently.
        if current.canonical_digest == candidate.canonical_digest:
            _require(_tree_identity(target) == tree_digest, "INVALID_RECOVERY_STATE")
            _validate_candidate_sidecars(
                candidate_root,
                candidate,
                promotion_capability,
            )
            _require(artifact_seen and existing is not None,
                     "CANONICAL_WITHOUT_EXACT_LEDGER_RECEIPT")
            _require(previous in (None, record), "INVALID_RECOVERY_STATE")
            if previous is None:
                _write_recovery(journal_path, record)
            # A previous process may have died immediately after renameat2,
            # before syncing the parent. Persist visibility before deleting
            # any old-generation recovery material.
            _fsync_dir(target.parent)
            _cleanup(stage)
            return CanonicalPublicationReceipt(
                status="ALREADY_COMMITTED",
                publication_receipt_digest=receipt_digest,
                artifact_digest=artifact_digest,
                promotion_capability_digest=promotion_capability_digest,
                previous_canonical_digest=expected_current_canonical_digest,
                resulting_canonical_digest=candidate.canonical_digest,
                generation_number=candidate.generation_number,
                transaction_id=candidate.transaction_id,
                capability_id=candidate.capability_id,
                resulting_ledger_head=existing["entry_digest"],
                resumed=True,
            )

        _require(
            current.canonical_digest == expected_current_canonical_digest,
            "STALE_CANONICAL_HEAD",
        )
        _validate_live_source_promotion_bindings(
            promotion_capability,
            current,
        )
        _validate_successor(
            project_root,
            candidate_root,
            current,
            candidate,
            promotion_capability,
        )

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
            # Nonempty legacy ledgers have opaque source bindings. Bootstrap
            # only an exact known reservation, or a fresh empty ledger.
            _require(previous is not None or snapshot["count"] == 0,
                     "UNBOUND_PUBLICATION_LEDGER")
            resumed = False

        _checkpoint("after_live_validation")

        # Build and flush the exact candidate snapshot before consuming authority.
        if stage.exists() or stage.is_symlink():
            _require(not stage.is_symlink() and stage.is_dir(), "CORRUPTED_STAGING_STATE")
            shutil.rmtree(stage)
        shutil.copytree(candidate_grid, stage, symlinks=False)
        _reject_symlinks(stage)
        _fsync_tree(stage)
        _fsync_dir(target.parent)
        _require(_tree_identity(stage) == tree_digest
                 and _tree_identity(candidate_grid) == tree_digest,
                 "CORRUPTED_STAGING_STATE")
        _checkpoint("after_staging")

        # Prove the kernel/filesystem can exchange directories atomically before
        # the durable ledger reservation is appended.
        _exchange_probe(target.parent, token)
        _checkpoint("after_probe")

        if previous != record:
            _write_recovery(journal_path, record)
        _checkpoint("before_append")

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
        _checkpoint("after_append")

        try:
            _checkpoint("before_exchange")
            _commit_exchange(stage, target)
            _checkpoint("after_exchange")
            _fsync_dir(target.parent)
        except Exception as exc:
            # The exact durable reservation intentionally remains so retry can
            # resume the same candidate without consuming authority twice.
            if isinstance(exc, PublicationError):
                raise
            raise PublicationError("ATOMIC_EXCHANGE_FAILED") from exc

        try:
            _checkpoint("before_verification")
            committed = _load_current_grid81_locked(project_root)
            _require(
                committed.canonical_digest == candidate.canonical_digest,
                "POST_COMMIT_CANONICAL_DIGEST_MISMATCH",
            )
            _require(
                committed.generation_number == candidate.generation_number,
                "POST_COMMIT_GENERATION_MISMATCH",
            )
        except Exception as verification_error:
            # Never reverse visibility. Retain reservation and old stage for
            # an exact verifying retry, including failures after exchange.
            if isinstance(verification_error, PublicationError):
                raise verification_error
            if isinstance(verification_error, CanonicalReadError):
                raise PublicationError(
                    "POST_COMMIT_READER_REJECTED",
                    verification_error.code,
                ) from verification_error
            raise PublicationError("POST_COMMIT_VERIFICATION_FAILED") from verification_error

        # stage now contains the previous canonical snapshot.
        _checkpoint("after_verification")
        _cleanup(stage)

        return CanonicalPublicationReceipt(
            status="COMMITTED",
            publication_receipt_digest=receipt_digest,
            artifact_digest=artifact_digest,
            promotion_capability_digest=promotion_capability_digest,
            previous_canonical_digest=expected_current_canonical_digest,
            resulting_canonical_digest=candidate.canonical_digest,
            generation_number=candidate.generation_number,
            transaction_id=candidate.transaction_id,
            capability_id=candidate.capability_id,
            resulting_ledger_head=reserved_head,
            resumed=resumed,
        )
