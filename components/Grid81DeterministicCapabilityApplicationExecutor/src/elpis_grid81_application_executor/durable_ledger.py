"""Explicit, file-backed application ledger; never writes canonical Grid81 state.

Use one instance per thread/process and close it (or use a context manager).
SQLite must reside on a filesystem supporting SQLite locks and durable fsync.
Lock contention waits up to 30 seconds, then raises sqlite3.OperationalError.
The ledger transaction does not cover any caller-owned state or publication.
"""

from contextlib import contextmanager
import os
import re
from pathlib import Path
import sqlite3

from .canonical import canonical_digest
from .ledger import LedgerEntry, ledger_head_digest


_SCHEMA_VERSION = 1
_APPLICATION_ID = 0x454C504C  # ELPL
_ENTRY_COLUMNS = "sequence, previous_head, receipt_digest, entry_digest"


# Write-once R0 declarations; also pin predicates/options absent from PRAGMAs.
_SCHEMA_SQL = {
    "ledger_entries": """
        CREATE TABLE ledger_entries (
            sequence INTEGER PRIMARY KEY CHECK(sequence > 0),
            previous_head TEXT NOT NULL,
            receipt_digest TEXT NOT NULL UNIQUE,
            entry_digest TEXT NOT NULL,
            artifact_digest TEXT NOT NULL,
            UNIQUE(sequence, receipt_digest, artifact_digest)
        )
    """,
    "unique_applied_artifact": """
        CREATE UNIQUE INDEX unique_applied_artifact
        ON ledger_entries(artifact_digest) WHERE artifact_digest != ''
    """,
    "applied_artifacts": """
        CREATE TABLE applied_artifacts (
            artifact_digest TEXT PRIMARY KEY NOT NULL
                CHECK(artifact_digest != ''),
            sequence INTEGER NOT NULL UNIQUE,
            receipt_digest TEXT NOT NULL UNIQUE,
            FOREIGN KEY(sequence, receipt_digest, artifact_digest)
                REFERENCES ledger_entries(
                    sequence, receipt_digest, artifact_digest)
        )
    """,
}


_COLUMNS = {
    "ledger_entries": (
        ("sequence", "INTEGER", 0, None, 1, 0),
        ("previous_head", "TEXT", 1, None, 0, 0),
        ("receipt_digest", "TEXT", 1, None, 0, 0),
        ("entry_digest", "TEXT", 1, None, 0, 0),
        ("artifact_digest", "TEXT", 1, None, 0, 0),
    ),
    "applied_artifacts": (
        ("artifact_digest", "TEXT", 1, None, 1, 0),
        ("sequence", "INTEGER", 1, None, 0, 0),
        ("receipt_digest", "TEXT", 1, None, 0, 0),
    ),
}
_INDEXES = {
    "ledger_entries": {
        (1, "u", 0, ("receipt_digest",)),
        (1, "u", 0, ("sequence", "receipt_digest", "artifact_digest")),
        (1, "c", 1, ("artifact_digest",)),
    },
    "applied_artifacts": {
        (1, "pk", 0, ("artifact_digest",)),
        (1, "u", 0, ("sequence",)),
        (1, "u", 0, ("receipt_digest",)),
    },
}
_SQL_TOKEN = re.compile(
    r"--[^\n]*(?:\n|$)|/\*[\s\S]*?\*/|'(?:''|[^'])*'|"
    r'"(?:""|[^"])*"|`(?:``|[^`])*`|\[[^\]]*\]|[A-Za-z_][A-Za-z_0-9]*|'
    r"!=|<>|>=|<=|[^\s]"
)


def _schema_tokens(statement):
    """Normalize formatting, comments, keyword case and identifier quoting.

    This supplements structural introspection for CHECK expressions, partial
    index predicates, conflict policies and FK deferrability, which SQLite does
    not fully expose via PRAGMAs. It is deliberately not a SQL equivalence
    engine: only the supported R0 declarations are accepted.
    """
    tokens = []
    for token in _SQL_TOKEN.findall(statement or ""):
        if token.startswith(("--", "/*")):
            continue
        if token.startswith("'"):
            tokens.append(token)  # Literal values are case sensitive.
        elif token.startswith(('"', '`', '[')):
            tokens.append(token[1:-1].replace(token[-1] * 2, token[-1]).lower())
        else:
            tokens.append(token.lower())
    if tokens and tokens[-1] == ";":
        tokens.pop()
    return tuple(tokens)


def _verify_schema(connection):
    """Authenticate R0 structure in the caller's transaction, without writes."""
    try:
        objects = connection.execute(
            "SELECT type, name, tbl_name, sql FROM main.sqlite_master"
        ).fetchall()
        declared = {}
        autoindexes = set()
        for kind, name, table, sql in objects:
            if kind == "index" and sql is None and table in _COLUMNS:
                # Internal indexes must also have the correct origin/structure
                # below; there is no blanket exemption for sqlite_ names.
                if not name.startswith(f"sqlite_autoindex_{table}_"):
                    return False, "schema_mismatch:objects"
                autoindexes.add(name)
            elif (name in _SCHEMA_SQL and table == (
                "ledger_entries" if name == "unique_applied_artifact" else name
            ) and kind == ("index" if name == "unique_applied_artifact" else "table")):
                declared[name] = sql
            else:
                return False, "schema_mismatch:objects"
        if set(declared) != set(_SCHEMA_SQL):
            return False, "schema_mismatch:objects"
        # TEMP objects could shadow unqualified queries on this connection.
        if connection.execute("SELECT 1 FROM sqlite_temp_master LIMIT 1").fetchone():
            return False, "schema_mismatch:objects"

        seen_autoindexes = set()
        for table, columns in _COLUMNS.items():
            actual = tuple(tuple(row)[1:] for row in connection.execute(
                f'PRAGMA main.table_xinfo("{table}")'
            ))
            if actual != columns:
                return False, "schema_mismatch:columns"
            indexes = []
            for _, name, unique, origin, partial in connection.execute(
                f'PRAGMA main.index_list("{table}")'
            ):
                if origin != "c":
                    seen_autoindexes.add(name)
                elif name != "unique_applied_artifact":
                    return False, "schema_mismatch:indexes"
                quoted_name = name.replace('"', '""')
                details = [tuple(row) for row in connection.execute(
                    f'PRAGMA main.index_xinfo("{quoted_name}")'
                )]
                keys = tuple(row[2] for row in details if row[5])
                column_ids = {column[0]: index for index, column in enumerate(columns)}
                expected_details = [
                    (index, column_ids.get(column), column, 0, "BINARY", 1)
                    for index, column in enumerate(keys)
                ] + [(len(keys), -1, None, 0, "BINARY", 0)]
                if details != expected_details:
                    return False, "schema_mismatch:indexes"
                indexes.append((unique, origin, partial, keys))
            if len(indexes) != len(_INDEXES[table]) or set(indexes) != _INDEXES[table]:
                return False, "schema_mismatch:indexes"
            foreign_keys = [tuple(row) for row in connection.execute(
                f'PRAGMA main.foreign_key_list("{table}")'
            )]
            expected_fks = [] if table == "ledger_entries" else [
                (0, index, "ledger_entries", column, column, "NO ACTION", "NO ACTION", "NONE")
                for index, column in enumerate(("sequence", "receipt_digest", "artifact_digest"))
            ]
            if sorted(foreign_keys) != expected_fks:
                return False, "schema_mismatch:foreign_keys"
        if seen_autoindexes != autoindexes:
            return False, "schema_mismatch:indexes"
        for name, statement in _SCHEMA_SQL.items():
            if _schema_tokens(declared[name]) != _schema_tokens(statement):
                return False, "schema_mismatch:declarations"
    except sqlite3.DatabaseError:
        return False, "schema_mismatch:introspection"
    return True, "valid"


class DurableApplicationLedger:
    """Durable CAS and replay exclusion with ApplicationLedger digest identity.

    Stale heads and duplicate identities raise ValueError. Corrupt/unsupported
    ledgers raise RuntimeError or sqlite3.DatabaseError on open or append;
    verify_chain returns a failed verification. Storage/locking errors propagate
    as sqlite3 errors. Every
    append verifies the full chain under its write lock (linear in chain size).

    Artifact associations are checked against their entry records but are not
    part of the historical entry hash. As with the in-memory hash chain, this
    is corruption detection, not authentication against an attacker rewriting
    the entire database or restoring an older, internally consistent database.
    """

    def __init__(self, path: str | os.PathLike[str]):
        raw_path = os.fspath(path)
        if not isinstance(raw_path, str) or raw_path in ("", ":memory:"):
            raise ValueError("A persistent database file path is required")
        database_path = Path(raw_path).resolve()
        if any(parent.name == "Grid81" and parent.parent.name == "Canonical"
               for parent in (database_path, *database_path.parents)):
            raise ValueError("Ledger database cannot reside inside Canonical/Grid81")
        self._pid = os.getpid()
        self._connection = sqlite3.connect(
            str(database_path), timeout=30.0, isolation_level=None,
        )
        self._connection.row_factory = sqlite3.Row
        try:
            # Rollback journaling with FULL synchronization makes successful
            # commits durable without relying on connection defaults.
            mode = self._connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
            if mode != "delete":
                raise RuntimeError("SQLite rollback journaling is required")
            self._connection.execute("PRAGMA synchronous = FULL")
            self._connection.execute("PRAGMA foreign_keys = ON")
            with self._transaction(write=True) as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                identity = connection.execute("PRAGMA application_id").fetchone()[0]
                objects = connection.execute("SELECT name FROM sqlite_master").fetchall()
                if version == 0 and identity == 0 and not objects:
                    for statement in _SCHEMA_SQL.values():
                        connection.execute(statement)
                    connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                    connection.execute(f"PRAGMA application_id = {_APPLICATION_ID}")
                self._require_valid(connection)
        except BaseException:
            self._connection.close()
            raise

    def _check_open(self):
        if os.getpid() != self._pid:
            raise RuntimeError("Open a new DurableApplicationLedger in each process")
        if self._connection is None:
            raise RuntimeError("Ledger is closed")

    @contextmanager
    def _transaction(self, *, write=False):
        self._check_open()
        connection = self._connection
        connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

    @staticmethod
    def _head(connection):
        row = connection.execute(
            "SELECT entry_digest FROM ledger_entries ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else ledger_head_digest([])

    @property
    def head(self) -> str:
        self._check_open()
        return self._head(self._connection)

    @property
    def is_empty(self) -> bool:
        self._check_open()
        return self._connection.execute(
            "SELECT 1 FROM ledger_entries LIMIT 1"
        ).fetchone() is None

    def has_receipt(self, artifact_digest: str) -> bool:
        """Query durable artifact consumption; no process-local replay cache."""
        self._check_open()
        return self._connection.execute(
            "SELECT 1 FROM applied_artifacts WHERE artifact_digest = ?",
            (artifact_digest,),
        ).fetchone() is not None

    def append(self, previous_head: str, receipt_digest: str,
               artifact_digest: str = "") -> LedgerEntry:
        """Atomically validate CAS/uniqueness and commit entry and association."""
        with self._transaction(write=True) as connection:
            self._require_valid(connection)
            head = self._head(connection)
            if previous_head != head:
                raise ValueError(
                    f"Stale ledger head: expected {head[:16]}..., got {previous_head[:16]}..."
                )
            if not isinstance(receipt_digest, str) or not isinstance(artifact_digest, str):
                raise TypeError("Receipt and artifact digests must be strings")
            if artifact_digest and connection.execute(
                "SELECT 1 FROM applied_artifacts WHERE artifact_digest = ?",
                (artifact_digest,),
            ).fetchone():
                raise ValueError("Duplicate artifact: already applied")
            if connection.execute(
                "SELECT 1 FROM ledger_entries WHERE receipt_digest = ?", (receipt_digest,),
            ).fetchone():
                raise ValueError("Duplicate receipt: already applied")
            sequence = connection.execute("SELECT COUNT(*) FROM ledger_entries").fetchone()[0] + 1
            payload = dict(sequence=sequence, previous_head=head, receipt_digest=receipt_digest)
            entry = LedgerEntry(**payload, entry_digest=canonical_digest(payload))
            connection.execute(
                "INSERT INTO ledger_entries VALUES (?, ?, ?, ?, ?)",
                (entry.sequence, entry.previous_head, entry.receipt_digest,
                 entry.entry_digest, artifact_digest),
            )
            if artifact_digest:
                connection.execute(
                    "INSERT INTO applied_artifacts VALUES (?, ?, ?)",
                    (artifact_digest, sequence, receipt_digest),
                )
            # Verify the resulting state before committing. A failure rolls back
            # every inserted record.
            self._require_valid(connection)
        return entry

    @staticmethod
    def _verify(connection) -> tuple[bool, str]:
        if (connection.execute("PRAGMA user_version").fetchone()[0] != _SCHEMA_VERSION
                or connection.execute("PRAGMA application_id").fetchone()[0] != _APPLICATION_ID):
            return False, "unsupported_ledger_schema"
        schema_ok, reason = _verify_schema(connection)
        if not schema_ok:
            return False, reason
        if [row[0] for row in connection.execute("PRAGMA integrity_check")] != ["ok"]:
            return False, "database_integrity_failure"
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            return False, "artifact_association_mismatch"
        previous_head = ledger_head_digest([])
        receipts = set()
        artifacts = set()
        expected_associations = set()
        count = 0
        for count, row in enumerate(connection.execute(
            "SELECT * FROM ledger_entries ORDER BY sequence"
        ), start=1):
            if row["sequence"] != count:
                return False, f"invalid_sequence:{row['sequence']}"
            if any(not isinstance(row[column], str) for column in (
                "previous_head", "receipt_digest", "entry_digest", "artifact_digest"
            )):
                return False, f"invalid_entry_types_at_sequence:{count}"
            if row["previous_head"] != previous_head:
                return False, f"chain_break_at_sequence:{count}"
            expected = canonical_digest({key: row[key] for key in (
                "sequence", "previous_head", "receipt_digest"
            )})
            if row["entry_digest"] != expected:
                return False, f"digest_mismatch_at_sequence:{count}"
            if row["receipt_digest"] in receipts:
                return False, f"duplicate_receipt_at_sequence:{count}"
            receipts.add(row["receipt_digest"])
            artifact = row["artifact_digest"]
            if artifact:
                if artifact in artifacts:
                    return False, f"duplicate_artifact_at_sequence:{count}"
                artifacts.add(artifact)
                expected_associations.add((artifact, count, row["receipt_digest"]))
            previous_head = expected
        associations = [tuple(row) for row in connection.execute(
            "SELECT artifact_digest, sequence, receipt_digest FROM applied_artifacts"
        )]
        if (len(associations) != len(expected_associations)
                or set(associations) != expected_associations):
            return False, "artifact_association_mismatch"
        return (True, "valid") if count else (True, "empty")

    @classmethod
    def _require_valid(cls, connection):
        ok, reason = cls._verify(connection)
        if not ok:
            raise RuntimeError(f"Invalid durable ledger: {reason}")

    def verify_chain(self) -> tuple[bool, str]:
        """Verify chain, replay uniqueness and artifact links in one snapshot."""
        self._check_open()
        try:
            with self._transaction() as connection:
                return self._verify(connection)
        except sqlite3.DatabaseError as error:
            return False, f"database_error:{error}"

    def to_dict(self) -> dict:
        """Return the same evidence shape as ApplicationLedger, from one snapshot."""
        with self._transaction() as connection:
            entries = [dict(row) for row in connection.execute(
                f"SELECT {_ENTRY_COLUMNS} FROM ledger_entries ORDER BY sequence"
            )]
            return dict(entries=entries, head=ledger_head_digest(entries), count=len(entries))

    def close(self):
        """Close this connection; safe to call more than once."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self):
        self._check_open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
