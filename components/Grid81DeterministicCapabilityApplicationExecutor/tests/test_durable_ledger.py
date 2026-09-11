"""Persistence, digest compatibility, rollback and corruption detection."""

import sqlite3

import pytest

from elpis_grid81_application_executor import DurableApplicationLedger
from elpis_grid81_application_executor.canonical import canonical_digest
from elpis_grid81_application_executor.ledger import ApplicationLedger


def database_rows(path):
    with sqlite3.connect(path) as connection:
        return (
            connection.execute("SELECT * FROM ledger_entries ORDER BY sequence").fetchall(),
            connection.execute("SELECT * FROM applied_artifacts ORDER BY sequence").fetchall(),
        )


def test_empty_and_multi_entry_digest_parity(tmp_path):
    memory = ApplicationLedger()
    with DurableApplicationLedger(tmp_path / "ledger.sqlite") as durable:
        assert durable.is_empty
        assert durable.head == memory.head
        assert durable.to_dict() == memory.to_dict()
        assert durable.verify_chain() == (True, "empty")
        assert not durable.has_receipt("")
        for index, artifact in enumerate(("", "artifact1", "", "artifact3", "artifact4")):
            receipt = canonical_digest({"receipt": index})
            assert durable.append(durable.head, receipt, artifact) == memory.append(
                memory.head, receipt, artifact
            )
            assert durable.to_dict() == memory.to_dict()
        assert not durable.is_empty
        assert durable.verify_chain() == (True, "valid")
        # Returned evidence is detached from persistent state.
        evidence = durable.to_dict()
        evidence["entries"][0]["entry_digest"] = "changed"
        assert durable.to_dict() == memory.to_dict()


def test_reopen_and_duplicate_exclusion(tmp_path):
    path = tmp_path / "ledger.sqlite"
    with DurableApplicationLedger(path) as ledger:
        ledger.append(ledger.head, "receipt1", "artifact1")
        expected = ledger.to_dict()
    with DurableApplicationLedger(path) as ledger:
        assert ledger.to_dict() == expected
        assert ledger.has_receipt("artifact1")
        before = database_rows(path)
        with pytest.raises(ValueError, match="Duplicate artifact"):
            ledger.append(ledger.head, "receipt2", "artifact1")
        with pytest.raises(ValueError, match="Duplicate receipt"):
            ledger.append(ledger.head, "receipt1", "artifact2")
        assert database_rows(path) == before
        assert not ledger.has_receipt("artifact2")
        assert ledger.verify_chain() == (True, "valid")
        ledger.append(ledger.head, "receipt2", "artifact2")


def test_stale_head_has_zero_durable_mutation(tmp_path):
    path = tmp_path / "ledger.sqlite"
    with DurableApplicationLedger(path) as first, DurableApplicationLedger(path) as second:
        stale = second.head
        committed = first.append(first.head, "receipt1", "artifact1")
        assert second.head == committed.entry_digest
        assert second.has_receipt("artifact1")
        before = database_rows(path)
        with pytest.raises(ValueError, match="Stale ledger head"):
            second.append(stale, "receipt2", "artifact2")
        assert database_rows(path) == before
        assert not second.has_receipt("artifact2")
        assert second.to_dict() == first.to_dict()


@pytest.mark.parametrize("failure", ["insert", "post_insert"])
def test_rollback_after_entry_insert(tmp_path, monkeypatch, failure):
    class InsertFailureConnection(sqlite3.Connection):
        fail_insert = False
        reached_fault = False

        def execute(self, sql, parameters=()):
            if self.fail_insert and sql.startswith("INSERT INTO applied_artifacts"):
                self.fail_insert = False
                self.reached_fault = True
                assert self.execute("SELECT COUNT(*) FROM ledger_entries").fetchone()[0] == 2
                if failure == "post_insert":
                    super().execute(sql, parameters)
                    assert self.execute("SELECT COUNT(*) FROM applied_artifacts").fetchone()[0] == 2
                raise sqlite3.IntegrityError("injected insertion failure")
            return super().execute(sql, parameters)

    original_connect = sqlite3.connect

    def connect(*args, **kwargs):
        return original_connect(*args, **kwargs, factory=InsertFailureConnection)

    monkeypatch.setattr(sqlite3, "connect", connect)
    path = tmp_path / "ledger.sqlite"
    with DurableApplicationLedger(path) as ledger:
        ledger.append(ledger.head, "receipt1", "artifact1")
        before = database_rows(path)
        ledger._connection.fail_insert = True
        with pytest.raises(sqlite3.IntegrityError, match="injected insertion failure"):
            ledger.append(ledger.head, "receipt2", "artifact2")
        assert ledger._connection.reached_fault
        assert database_rows(path) == before
        assert not ledger.has_receipt("artifact2")
        # Retry identical identities: rollback must remove every marker.
        ledger.append(ledger.head, "receipt2", "artifact2")
    with DurableApplicationLedger(path) as reopened:
        assert reopened.to_dict()["count"] == 2
        assert reopened.has_receipt("artifact2")
        assert reopened.verify_chain() == (True, "valid")


def test_commit_error_rolls_back_both_records(tmp_path, monkeypatch):
    class CommitFailureConnection(sqlite3.Connection):
        fail_commit = False

        def commit(self):
            if self.fail_commit:
                self.fail_commit = False
                raise sqlite3.OperationalError("injected commit failure")
            return super().commit()

    original_connect = sqlite3.connect

    def connect(*args, **kwargs):
        return original_connect(*args, **kwargs, factory=CommitFailureConnection)

    monkeypatch.setattr(sqlite3, "connect", connect)
    path = tmp_path / "ledger.sqlite"
    with DurableApplicationLedger(path) as ledger:
        before = database_rows(path)
        ledger._connection.fail_commit = True
        with pytest.raises(sqlite3.OperationalError, match="injected commit failure"):
            ledger.append(ledger.head, "receipt1", "artifact1")
        assert not ledger._connection.in_transaction
        assert database_rows(path) == before
        assert not ledger.has_receipt("artifact1")
        ledger.append(ledger.head, "receipt1", "artifact1")
    with DurableApplicationLedger(path) as reopened:
        assert reopened.has_receipt("artifact1")
        assert reopened.verify_chain() == (True, "valid")


@pytest.mark.parametrize("sql", [
    "UPDATE ledger_entries SET entry_digest = 'tampered' WHERE sequence = 1",
    "UPDATE ledger_entries SET previous_head = 'tampered' WHERE sequence = 1",
    "UPDATE ledger_entries SET previous_head = 'tampered' WHERE sequence = 2",
    "UPDATE ledger_entries SET sequence = 7 WHERE sequence = 2",
    "DELETE FROM applied_artifacts WHERE sequence = 1",
    "UPDATE applied_artifacts SET artifact_digest = 'tampered' WHERE sequence = 1",
    "UPDATE applied_artifacts SET receipt_digest = 'tampered' WHERE sequence = 1",
    "UPDATE ledger_entries SET artifact_digest = 'tampered' WHERE sequence = 1",
    "INSERT INTO applied_artifacts VALUES ('orphan', 42, 'orphan_receipt')",
    "PRAGMA user_version = 99",
    "PRAGMA application_id = 0",
    "DROP TABLE applied_artifacts",
])
def test_tampering_detected_and_append_fails_closed(tmp_path, sql):
    path = tmp_path / "ledger.sqlite"
    with DurableApplicationLedger(path) as ledger:
        ledger.append(ledger.head, "receipt1", "artifact1")
        ledger.append(ledger.head, "receipt2", "artifact2")
        head = ledger.head
        with sqlite3.connect(path) as connection:
            connection.execute(sql)
        assert ledger.verify_chain()[0] is False
        with pytest.raises((RuntimeError, sqlite3.DatabaseError)):
            ledger.append(head, "receipt3", "artifact3")
    with pytest.raises((RuntimeError, sqlite3.DatabaseError)):
        DurableApplicationLedger(path)


@pytest.mark.parametrize("duplicate", ["receipt", "artifact"])
def test_uniqueness_recomputed_even_if_schema_tampered(tmp_path, monkeypatch, duplicate):
    path = tmp_path / "ledger.sqlite"
    with DurableApplicationLedger(path) as ledger:
        first = ledger.append(ledger.head, "receipt1", "artifact1")
        with sqlite3.connect(path) as connection:
            # Remove SQL constraints to simulate offline database corruption.
            connection.execute("DROP TABLE applied_artifacts")
            connection.execute("""
                CREATE TABLE applied_artifacts (
                    artifact_digest TEXT, sequence INTEGER, receipt_digest TEXT)
            """)
            connection.execute("CREATE TABLE forged AS SELECT * FROM ledger_entries")
            connection.execute("DROP TABLE ledger_entries")
            connection.execute("ALTER TABLE forged RENAME TO ledger_entries")
            receipt = "receipt1" if duplicate == "receipt" else "receipt2"
            artifact = "artifact1" if duplicate == "artifact" else "artifact2"
            payload = dict(sequence=2, previous_head=first.entry_digest, receipt_digest=receipt)
            connection.execute("INSERT INTO ledger_entries VALUES (?, ?, ?, ?, ?)",
                               (2, first.entry_digest, receipt, canonical_digest(payload), artifact))
        assert ledger.verify_chain() == (False, "schema_mismatch:objects")
        # Independently retain coverage of logical duplicate detection, even
        # though public verification now rejects this fixture's schema first.
        from elpis_grid81_application_executor import durable_ledger
        monkeypatch.setattr(durable_ledger, "_verify_schema", lambda connection: (True, "valid"))
        assert ledger.verify_chain() == (False, f"duplicate_{duplicate}_at_sequence:2")


def test_database_level_uniqueness(tmp_path):
    path = tmp_path / "ledger.sqlite"
    with DurableApplicationLedger(path) as ledger:
        ledger.append(ledger.head, "receipt1", "artifact1")
        with sqlite3.connect(path) as connection:
            for receipt, artifact in (("receipt1", "artifact2"), ("receipt2", "artifact1")):
                with pytest.raises(sqlite3.IntegrityError):
                    connection.execute("INSERT INTO ledger_entries VALUES (?, ?, ?, ?, ?)",
                                       (2, ledger.head, receipt, "digest", artifact))
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO applied_artifacts VALUES (?, ?, ?)",
                                   ("artifact1", 2, "receipt2"))
        assert ledger.verify_chain() == (True, "valid")


def test_schema_marker_is_required_and_unrelated_database_is_rejected(tmp_path):
    path = tmp_path / "unrelated.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")
    with pytest.raises(RuntimeError, match="unsupported_ledger_schema"):
        DurableApplicationLedger(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert connection.execute("SELECT name FROM sqlite_master").fetchall() == [("unrelated",)]


def test_lifecycle_and_explicit_durability(tmp_path):
    path = tmp_path / "ledger.sqlite"
    with pytest.raises(LookupError):
        with DurableApplicationLedger(path) as ledger:
            assert ledger._connection.execute("PRAGMA synchronous").fetchone()[0] == 2
            assert ledger._connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
            assert ledger._connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            ledger.append(ledger.head, "receipt1")
            raise LookupError("caller failure after a committed append")
    ledger.close()
    with pytest.raises(RuntimeError, match="closed"):
        ledger.to_dict()
    with DurableApplicationLedger(path) as reopened:
        assert reopened.to_dict()["count"] == 1


@pytest.mark.parametrize("path", ["", ":memory:"])
def test_reject_nonpersistent_paths(path):
    with pytest.raises(ValueError, match="persistent"):
        DurableApplicationLedger(path)


def test_reject_canonical_database_location(tmp_path):
    canonical = tmp_path / "Canonical" / "Grid81"
    with pytest.raises(ValueError, match="Canonical/Grid81"):
        DurableApplicationLedger(canonical / "ledger.sqlite")
    assert not canonical.exists()


def recreate_table(connection, table, old, new):
    """Change only a table declaration, retaining all legitimate row values."""
    statement = connection.execute(
        "SELECT sql FROM sqlite_master WHERE name = ?", (table,)
    ).fetchone()[0]
    assert old in statement
    indexes = [row[0] for row in connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL",
        (table,),
    )]
    columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
    rows = connection.execute(f'SELECT * FROM "{table}"').fetchall()
    connection.execute(f'DROP TABLE "{table}"')
    connection.execute(statement.replace(old, new, 1))
    column_list = ", ".join(f'"{column}"' for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    connection.executemany(
        f'INSERT INTO "{table}" ({column_list}) VALUES ({placeholders})', rows
    )
    for index in indexes:
        connection.execute(index)


@pytest.mark.parametrize("mutation, reason", [
    (("DROP INDEX unique_applied_artifact",), "objects"),
    (("CREATE TABLE unexpected (value TEXT)",), "objects"),
    (("CREATE TRIGGER unexpected AFTER INSERT ON ledger_entries BEGIN SELECT 1; END",), "objects"),
    (("CREATE VIEW unexpected AS SELECT * FROM ledger_entries",), "objects"),
    (("CREATE INDEX unexpected ON ledger_entries(previous_head)",), "objects"),
    (("applied_artifacts", "TEXT PRIMARY KEY NOT NULL", "TEXT NOT NULL"), "columns"),
    (("applied_artifacts", "sequence INTEGER NOT NULL UNIQUE", "sequence INTEGER NOT NULL"), "indexes"),
    (("applied_artifacts", "receipt_digest TEXT NOT NULL UNIQUE", "receipt_digest TEXT NOT NULL"), "indexes"),
    (("ledger_entries", "receipt_digest TEXT NOT NULL UNIQUE", "receipt_digest TEXT NOT NULL"), "indexes"),
    (("ledger_entries", "UNIQUE(sequence, receipt_digest, artifact_digest)", "CHECK(sequence > 0)"), "indexes"),
    (("ledger_entries", "entry_digest TEXT NOT NULL", "entry_digest BLOB NOT NULL"), "columns"),
    (("ledger_entries", "entry_digest TEXT NOT NULL", "entry_digest TEXT"), "columns"),
    (("ledger_entries", "sequence INTEGER PRIMARY KEY", "sequence INTEGER"), "columns"),
    (("ledger_entries", "previous_head TEXT NOT NULL", "extra TEXT, previous_head TEXT NOT NULL"), "columns"),
    (("applied_artifacts", "sequence INTEGER NOT NULL", "sequence INTEGER"), "columns"),
    (("applied_artifacts", "sequence INTEGER NOT NULL", "sequence INT NOT NULL"), "columns"),
    (("applied_artifacts", "receipt_digest TEXT NOT NULL", "extra TEXT, receipt_digest TEXT NOT NULL"), "columns"),
    (("ledger_entries", "CHECK(sequence > 0)", "CHECK(sequence >= 0)"), "declarations"),
    (("applied_artifacts", "CHECK(artifact_digest != '')", "CHECK(1)"), "declarations"),
    (("ledger_entries", "TEXT NOT NULL UNIQUE", "TEXT NOT NULL UNIQUE ON CONFLICT REPLACE"), "declarations"),
    (("applied_artifacts", "REFERENCES ledger_entries(", "REFERENCES wrong_parent("), "foreign_keys"),
])
def test_structural_schema_authority(tmp_path, mutation, reason):
    path = tmp_path / "ledger.sqlite"
    with DurableApplicationLedger(path) as ledger:
        ledger.append(ledger.head, "receipt1", "artifact1")
        ledger.append(ledger.head, "receipt2", "artifact2")
        evidence = ledger.to_dict()
        with sqlite3.connect(path) as connection:
            if len(mutation) == 1:
                connection.execute(mutation[0])
            else:
                recreate_table(connection, *mutation)
        # The fixture changed schema only; its ledger and replay rows still agree.
        assert ledger.to_dict() == evidence
        assert ledger.has_receipt("artifact1") and ledger.has_receipt("artifact2")
        assert_schema_rejected(path, ledger, reason)


def assert_schema_rejected(path, ledger, reason):
    expected = f"schema_mismatch:{reason}"
    before_bytes = path.read_bytes()
    before_rows = database_rows(path)
    assert ledger.verify_chain() == (False, expected)
    with pytest.raises(RuntimeError, match=expected):
        ledger.append(ledger.head, "new_receipt", "new_artifact")
    assert database_rows(path) == before_rows
    assert path.read_bytes() == before_bytes
    assert not ledger._connection.in_transaction
    ledger.close()
    with pytest.raises(RuntimeError, match=expected):
        DurableApplicationLedger(path)
    assert database_rows(path) == before_rows
    assert path.read_bytes() == before_bytes


@pytest.mark.parametrize("replacement", [
    "CREATE INDEX unique_applied_artifact ON ledger_entries(artifact_digest) WHERE artifact_digest != ''",
    "CREATE UNIQUE INDEX unique_applied_artifact ON ledger_entries(artifact_digest)",
    "CREATE UNIQUE INDEX unique_applied_artifact ON ledger_entries(receipt_digest) WHERE artifact_digest != ''",
    "CREATE UNIQUE INDEX unique_applied_artifact ON ledger_entries(artifact_digest COLLATE NOCASE) WHERE artifact_digest != ''",
    "CREATE UNIQUE INDEX unique_applied_artifact ON ledger_entries(artifact_digest) WHERE artifact_digest = ''",
    "CREATE UNIQUE INDEX unique_applied_artifact ON ledger_entries(artifact_digest) WHERE artifact_digest != '' AND sequence > 100",
])
def test_replaced_artifact_index_is_rejected(tmp_path, replacement):
    path = tmp_path / "ledger.sqlite"
    with DurableApplicationLedger(path) as ledger:
        ledger.append(ledger.head, "receipt1", "artifact1")
        before = database_rows(path)
        with sqlite3.connect(path) as connection:
            connection.execute("DROP INDEX unique_applied_artifact")
            connection.execute(replacement)
        assert database_rows(path) == before
        reason = "declarations" if ("artifact_digest = ''" in replacement or "AND sequence" in replacement) else "indexes"
        assert_schema_rejected(path, ledger, reason)


@pytest.mark.parametrize("retained_constraints", ["none", "uniqueness_only"])
def test_recreated_associations_preserve_rows_but_lose_constraints(tmp_path, retained_constraints):
    path = tmp_path / "ledger.sqlite"
    with DurableApplicationLedger(path) as ledger:
        ledger.append(ledger.head, "receipt1", "artifact1")
        before = database_rows(path)
        with sqlite3.connect(path) as connection:
            rows = connection.execute("SELECT * FROM applied_artifacts").fetchall()
            connection.execute("DROP TABLE applied_artifacts")
            if retained_constraints == "none":
                connection.execute("""
                    CREATE TABLE applied_artifacts (
                        artifact_digest TEXT NOT NULL, sequence INTEGER NOT NULL,
                        receipt_digest TEXT NOT NULL)
                """)
            else:
                connection.execute("""
                    CREATE TABLE applied_artifacts (
                        artifact_digest TEXT PRIMARY KEY NOT NULL CHECK(artifact_digest != ''),
                        sequence INTEGER NOT NULL UNIQUE, receipt_digest TEXT NOT NULL UNIQUE)
                """)
            connection.executemany("INSERT INTO applied_artifacts VALUES (?, ?, ?)", rows)
        assert database_rows(path) == before
        reason = "columns" if retained_constraints == "none" else "foreign_keys"
        assert_schema_rejected(path, ledger, reason)


def test_schema_formatting_is_not_identity(tmp_path):
    path = tmp_path / "ledger.sqlite"
    with DurableApplicationLedger(path) as ledger:
        ledger.append(ledger.head, "receipt1", "artifact1")
        evidence = ledger.to_dict()
        with sqlite3.connect(path) as connection:
            recreate_table(connection, "applied_artifacts", "CREATE TABLE applied_artifacts",
                           'create /* formatting only */ table "applied_artifacts"')
            connection.execute("DROP INDEX unique_applied_artifact")
            connection.execute("""
                create unique index "unique_applied_artifact"
                on "ledger_entries" ( "artifact_digest" )
                where "artifact_digest" != '' -- formatting only
            """)
        assert ledger.verify_chain() == (True, "valid")
        assert ledger.to_dict() == evidence
    with DurableApplicationLedger(path) as reopened:
        assert reopened.to_dict() == evidence
        reopened.append(reopened.head, "receipt2", "artifact2")
