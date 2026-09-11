"""Real spawned processes contend on durable CAS without timing-based sleeps."""

import multiprocessing
import os
import sqlite3

import pytest

from elpis_grid81_application_executor import DurableApplicationLedger
from elpis_grid81_application_executor.ledger import ApplicationLedger


def race_writer(path, barrier, results, identity):
    with DurableApplicationLedger(path) as ledger:
        previous = ledger.head
        barrier.wait(timeout=30)
        try:
            entry = ledger.append(previous, f"receipt{identity}", f"artifact{identity}")
        except ValueError as error:
            results.put((os.getpid(), identity, "rejected", str(error), ledger.to_dict()))
        else:
            results.put((os.getpid(), identity, "committed", entry.entry_digest, ledger.to_dict()))


def inspect_in_new_process(path, results, winner, loser):
    with DurableApplicationLedger(path) as ledger:
        before = ledger.to_dict()
        assert ledger.has_receipt(f"artifact{winner}")
        assert not ledger.has_receipt(f"artifact{loser}")
        with pytest.raises(ValueError, match="Duplicate artifact"):
            ledger.append(ledger.head, "third_receipt", f"artifact{winner}")
        with pytest.raises(ValueError, match="Duplicate receipt"):
            ledger.append(ledger.head, f"receipt{winner}", "third_artifact")
        assert ledger.to_dict() == before
        with sqlite3.connect(path) as connection:
            entries = connection.execute("SELECT receipt_digest FROM ledger_entries").fetchall()
            artifacts = connection.execute("SELECT artifact_digest FROM applied_artifacts").fetchall()
        results.put((os.getpid(), before, ledger.verify_chain(), entries, artifacts))


@pytest.mark.parametrize("preexisting", [False, True])
def test_process_race_exactly_one_commit_and_no_partial_state(tmp_path, preexisting):
    path = str(tmp_path / "ledger.sqlite")
    expected = ApplicationLedger()
    if preexisting:
        with DurableApplicationLedger(path) as ledger:
            ledger.append(ledger.head, "seed_receipt", "seed_artifact")
        expected.append(expected.head, "seed_receipt", "seed_artifact")
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    results = context.Queue()
    processes = [context.Process(target=race_writer, args=(path, barrier, results, i))
                 for i in range(2)]
    observer = None
    try:
        for process in processes:
            process.start()
        outcomes = [results.get(timeout=40) for _ in processes]
        for process in processes:
            process.join(timeout=40)
            assert process.exitcode == 0
        assert len({outcome[0] for outcome in outcomes} | {os.getpid()}) == 3
        committed = [outcome for outcome in outcomes if outcome[2] == "committed"]
        rejected = [outcome for outcome in outcomes if outcome[2] == "rejected"]
        assert len(committed) == len(rejected) == 1
        winner, loser = committed[0][1], rejected[0][1]
        assert rejected[0][3].startswith("Stale ledger head:")
        entry = expected.append(expected.head, f"receipt{winner}", f"artifact{winner}")
        assert committed[0][3] == entry.entry_digest
        assert committed[0][4] == rejected[0][4] == expected.to_dict()

        observer = context.Process(target=inspect_in_new_process,
                                   args=(path, results, winner, loser))
        observer.start()
        pid, snapshot, verification, entries, artifacts = results.get(timeout=40)
        observer.join(timeout=40)
        assert observer.exitcode == 0
        assert pid not in {outcome[0] for outcome in outcomes} | {os.getpid()}
        assert snapshot == expected.to_dict()
        assert verification == (True, "valid")
        assert sorted(entries) == sorted(
            [(f"receipt{winner}",)] + ([("seed_receipt",)] if preexisting else [])
        )
        assert sorted(artifacts) == sorted(
            [(f"artifact{winner}",)] + ([("seed_artifact",)] if preexisting else [])
        )
        with DurableApplicationLedger(path) as reopened:
            # Both losing identities remain available for a later valid append.
            reopened.append(reopened.head, f"receipt{loser}", f"artifact{loser}")
            assert reopened.verify_chain() == (True, "valid")
    finally:
        for process in processes + ([observer] if observer is not None else []):
            if process.is_alive():
                process.terminate()
            if process.pid is not None:
                process.join(timeout=5)
        results.close()
        results.join_thread()
