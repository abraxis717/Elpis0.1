"""Independent spawned writers/readers and bounded deterministic crash schedules."""
from __future__ import annotations

import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
import random
import sys
import time

import pytest

from Grid81.canonical_reader import load_current_grid81, canonical_namespace_lock
from elpis_grid81_application_executor import DurableApplicationLedger as Ledger
from elpis_grid81_canonical_publisher import PublicationError, publication_lock_path
import elpis_grid81_canonical_publisher.publisher as publisher

spec = importlib.util.spec_from_file_location(
    "publisher_fixtures", Path(__file__).with_name("test_publisher.py"))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

CTX = mp.get_context("spawn")
POINTS = (
    "before_lock", "after_lock", "after_live_validation", "after_staging",
    "after_probe", "before_append", "after_append", "before_exchange",
    "after_exchange", "before_verification", "after_verification", "during_cleanup",
)


def setup(base, writers=2, same=False):
    root = f._copy_root(base, "live")
    db = base / "ledger.db"
    jobs = []
    with Ledger(db) as ledger:
        for i in range(writers):
            if same and jobs:
                jobs.append(jobs[0]); continue
            cap = f._issue(root, ledger, approval=str(i), artifact=f._h(str(i)))
            candidate, state = f._candidate(base, root, cap, f"candidate{i}")
            jobs.append((candidate, cap, state.canonical_digest))
    return root, db, jobs


def call(root, db, job, **kw):
    with Ledger(db) as ledger:
        return publisher.publish_candidate(project_root=root, candidate_root=job[0],
            promotion_capability=job[1], ledger=ledger, **kw)


def worker(root, db, job, result, *, crash=None, gate=None, delay=0,
           pause=None, reached=None, release=None, lock=None, attempted=None):
    def checkpoint(name):
        if name == "before_lock" and attempted is not None:
            attempted.set()
        if name == "before_cleanup" and crash == "during_cleanup":
            unlink = os.unlink
            def die_after_first_unlink(*args, **kwargs):
                unlink(*args, **kwargs)
                os._exit(77)
            os.unlink = die_after_first_unlink
        if name == "before_lock" and gate is not None:
            gate.wait(30); time.sleep(delay)
        if name == pause:
            reached.set(); assert release.wait(30)
        if name == crash and crash != "during_cleanup":
            os._exit(77)
    publisher._checkpoint = checkpoint
    started = time.perf_counter()
    try:
        receipt = call(root, db, job, lock_path=lock)
        result.send((receipt.status, receipt.resumed, receipt.publication_receipt_digest,
                     time.perf_counter() - started))
    except Exception as exc:
        result.send((getattr(exc, "code", type(exc).__name__), str(exc)))


def start(root, db, job, **kw):
    receive, send = CTX.Pipe(False)
    process = CTX.Process(target=worker, args=(root, db, job, send), kwargs=kw)
    process.start()
    return process, receive


def finish(pair, expected=0):
    process, result = pair
    process.join(30)
    if process.is_alive():
        process.terminate(); process.join(); pytest.fail("writer deadlock")
    assert process.exitcode == expected
    return result.recv() if expected == 0 else None


def verify(root, db, jobs):
    state = load_current_grid81(root)
    assert state.generation_number == 2
    assert state.canonical_digest in {j[2] for j in jobs}
    grid = root / "Canonical/Grid81"
    assert sorted(p.name for p in (grid / "generations").iterdir()) == ["000001.json", "000002.json"]
    assert (grid / "generations/000001.json").read_bytes() == (f.SOURCE_GRID81 / "generations/000001.json").read_bytes()
    with Ledger(db) as ledger:
        assert ledger.verify_chain() == (True, "valid")
        entries = ledger.to_dict()["entries"]
        assert len(entries) == len({e["receipt_digest"] for e in entries}) == 1
    journal = json.loads((root / "Canonical/.Grid81.publisher-r1.json").read_text())
    assert journal["receipt_digest"] == entries[0]["receipt_digest"]
    assert journal["payload"]["resulting_canonical_digest"] == state.canonical_digest
    return state


@pytest.mark.parametrize("writers", [2, 4, 8])
@pytest.mark.parametrize("same", [False, True])
@pytest.mark.parametrize("seed", range(10))
def test_seeded_process_contention(tmp_path, writers, same, seed):
    root, db, jobs = setup(tmp_path, writers, same)
    gate = CTX.Barrier(writers)
    rng = random.Random(seed)
    pairs = [start(root, db, job, gate=gate, delay=rng.random() / 100) for job in jobs]
    results = [finish(pair) for pair in pairs]
    assert sum(r[0] == "COMMITTED" for r in results) == 1
    if same:
        assert sum(r[0] == "ALREADY_COMMITTED" and r[1] for r in results) == writers - 1
        assert len({r[2] for r in results}) == 1
    else:
        assert sum(r[0] == "PUBLICATION_RESERVATION_CONFLICT" for r in results) == writers - 1
    state = verify(root, db, jobs)
    winner = next(j for j in jobs if j[2] == state.canonical_digest)
    replay = call(root, db, winner)
    assert replay.resumed and replay.status == "ALREADY_COMMITTED"
    assert not list((root / "Canonical").glob(".Grid81.stage.*"))


@pytest.mark.parametrize("point", POINTS)
@pytest.mark.parametrize("retry", ["exact", "conflicting"])
def test_process_death_recovery(tmp_path, point, retry):
    root, db, jobs = setup(tmp_path)
    finish(start(root, db, jobs[0], crash=point), expected=77)
    pending = POINTS.index(point) >= POINTS.index("before_append")
    reserved = POINTS.index(point) >= POINTS.index("after_append")
    visible = POINTS.index(point) >= POINTS.index("after_exchange")
    assert load_current_grid81(root).generation_number == (2 if visible else 1)
    with Ledger(db) as ledger:
        assert ledger.to_dict()["count"] == int(reserved)
    if retry == "conflicting":
        result = finish(start(root, db, jobs[1]))
        if pending:
            assert result[0] == "PUBLICATION_RESERVATION_CONFLICT"
        else:
            assert result[0] == "COMMITTED"
            assert finish(start(root, db, jobs[0]))[0] == "PUBLICATION_RESERVATION_CONFLICT"
            verify(root, db, jobs)
            return
    result = finish(start(root, db, jobs[0]))
    assert result[:2] == ("ALREADY_COMMITTED" if visible else "COMMITTED", reserved)
    state = verify(root, db, jobs)
    assert state.canonical_digest == jobs[0][2]
    assert call(root, db, jobs[0]).status == "ALREADY_COMMITTED"


@pytest.mark.parametrize("same_lock", [True, False])
def test_controlled_lock_order_and_wrong_domain(tmp_path, same_lock):
    root, db, jobs = setup(tmp_path)
    reached, release, b_reached = CTX.Event(), CTX.Event(), CTX.Event()
    a = start(root, db, jobs[0], pause="after_live_validation", reached=reached, release=release)
    assert reached.wait(30)
    attempted = CTX.Event()
    b = start(root, db, jobs[1], pause="after_lock", reached=b_reached, release=release, attempted=attempted,
              lock=publication_lock_path(root) if same_lock else tmp_path / "alternate.lock")
    if same_lock:
        assert attempted.wait(30)
    assert not b_reached.wait(.2)
    if not same_lock:
        assert finish(b)[0] == "WRONG_LOCK_DOMAIN"
    release.set()
    assert finish(a)[0] == "COMMITTED"
    if same_lock:
        assert finish(b)[0] == "PUBLICATION_RESERVATION_CONFLICT"
    verify(root, db, jobs)


def test_ledger_ahead_new_capability_cannot_reserve_second_successor(tmp_path):
    root, db, jobs = setup(tmp_path)
    finish(start(root, db, jobs[0], crash="after_append"), expected=77)
    with Ledger(db) as ledger:
        cap = f._issue(root, ledger, approval="ledger-ahead", artifact=f._h("new artifact"))
        candidate, state = f._candidate(tmp_path, root, cap, "ledger-ahead")
    b = (candidate, cap, state.canonical_digest)
    assert finish(start(root, db, b))[0] == "PUBLICATION_RESERVATION_CONFLICT"
    assert finish(start(root, db, jobs[0]))[:2] == ("COMMITTED", True)
    verify(root, db, jobs)


@pytest.mark.parametrize("alias", ["relative", "dot", "dotdot", "symlink"])
def test_root_aliases_share_domain(tmp_path, alias):
    root, db, jobs = setup(tmp_path)
    if alias == "relative": other = Path(os.path.relpath(root))
    elif alias == "dot": other = str(root) + "/."
    elif alias == "dotdot": other = root / "Canonical/.."
    else:
        other = tmp_path / "alias"; other.symlink_to(root, target_is_directory=True)
    assert publication_lock_path(other) == publication_lock_path(root)
    reached, release = CTX.Event(), CTX.Event()
    a = start(root, db, jobs[0], pause="after_lock", reached=reached, release=release)
    assert reached.wait(30)
    b_reached = CTX.Event()
    attempted = CTX.Event()
    b = start(other, db, jobs[1], pause="after_lock", reached=b_reached, release=release, attempted=attempted)
    assert attempted.wait(30)
    assert not b_reached.wait(.2)
    release.set()
    assert finish(a)[0] == "COMMITTED"
    assert finish(b)[0] == "PUBLICATION_RESERVATION_CONFLICT"
    verify(root, db, jobs)


def test_unrelated_roots_do_not_block(tmp_path):
    root, db, jobs = setup(tmp_path / "a")
    other, odb, ojobs = setup(tmp_path / "b")
    reached, release = CTX.Event(), CTX.Event()
    a = start(root, db, jobs[0], pause="after_lock", reached=reached, release=release)
    assert reached.wait(30)
    assert finish(start(other, odb, ojobs[0]))[0] == "COMMITTED"
    release.set(); assert finish(a)[0] == "COMMITTED"


def test_ledger_substitution_is_rejected(tmp_path):
    root, db, jobs = setup(tmp_path)
    finish(start(root, db, jobs[0], crash="after_append"), expected=77)
    assert finish(start(root, tmp_path / "other.db", jobs[0]))[0] == "PUBLICATION_LEDGER_MISMATCH"
    assert call(root, db, jobs[0]).resumed


def test_future_successor_cannot_leapfrog(tmp_path):
    root, db, jobs = setup(tmp_path)
    with Ledger(db) as ledger:
        cap = f._issue(jobs[0][0], ledger, approval="future", artifact=f._h("future"))
        candidate = tmp_path / "future"
        import shutil
        shutil.copytree(jobs[0][0], candidate)
        state = f._make_candidate(jobs[0][0], candidate, cap)
    assert finish(start(root, db, (candidate, cap, state.canonical_digest)))[0] == "STALE_CANONICAL_HEAD"
    with Ledger(db) as ledger: assert ledger.is_empty


@pytest.mark.parametrize("kind", ["symlink_lock", "symlink_parent", "file_parent", "fifo_parent"])
def test_lock_object_hardening(tmp_path, kind):
    root, db, jobs = setup(tmp_path)
    lock = None
    if kind == "symlink_lock":
        lock = tmp_path / "link"; lock.symlink_to(root / "Canonical", target_is_directory=True)
    else:
        parent = root / "Canonical"; parent.rename(root / "saved")
        if kind == "symlink_parent": parent.symlink_to(root / "saved", target_is_directory=True)
        elif kind == "file_parent": parent.write_text("invalid")
        else: os.mkfifo(parent)
    result = finish(start(root, db, jobs[0], lock=lock))
    assert result[0] in {"WRONG_LOCK_DOMAIN", "PUBLICATION_LOCK_UNAVAILABLE", "CURRENT_GRID81_MISSING"}
    with Ledger(db) as ledger: assert ledger.is_empty


def test_parent_replacement_between_open_and_flock_is_detected(tmp_path, monkeypatch):
    import Grid81.canonical_reader as reader
    root, db, jobs = setup(tmp_path)
    original = reader.fcntl.flock
    def replacement(fd, operation):
        (root / "Canonical").rename(root / "old-parent")
        (root / "Canonical").mkdir()
        return original(fd, operation)
    monkeypatch.setattr(reader.fcntl, "flock", replacement)
    with pytest.raises(Exception, match="CANONICAL_LOCK_REPLACED"):
        call(root, db, jobs[0])
    with Ledger(db) as ledger: assert ledger.is_empty


def reader_process(root, stop, ready, result):
    seen = []; errors = []
    ready.set()
    while not stop.is_set():
        try:
            state = load_current_grid81(root)
            seen.append((state.generation_number, state.canonical_digest))
        except Exception as exc:
            errors.append(str(exc))
    result.send((seen, errors))


def paused_reader(root, reached, release, result):
    import Grid81.canonical_reader as reader
    original = reader._load_json
    def pause(path):
        value = original(path)
        if path.name == "HEAD.json":
            reached.set(); assert release.wait(30)
        return value
    reader._load_json = pause
    result.send(reader.load_current_grid81(root).generation_number)


def test_reader_head_to_sidecars_is_one_snapshot(tmp_path):
    root, db, jobs = setup(tmp_path)
    reached, release, writer_reached = CTX.Event(), CTX.Event(), CTX.Event()
    recv, send = CTX.Pipe(False)
    reader = CTX.Process(target=paused_reader, args=(root, reached, release, send))
    reader.start(); assert reached.wait(30)
    attempted = CTX.Event()
    writer = start(root, db, jobs[0], pause="after_lock", reached=writer_reached, release=release, attempted=attempted)
    assert attempted.wait(30)
    assert not writer_reached.wait(.2)
    release.set()
    assert recv.recv() == 1
    reader.join(30); assert reader.exitcode == 0
    assert finish(writer)[0] == "COMMITTED"
    assert load_current_grid81(root).generation_number == 2


def test_post_exchange_verification_failure_never_reverses_visibility(tmp_path, monkeypatch):
    root, db, jobs = setup(tmp_path)
    def fault(point):
        if point == "before_verification":
            raise RuntimeError("injected verification failure")
    monkeypatch.setattr(publisher, "_checkpoint", fault)
    with pytest.raises(PublicationError, match="POST_COMMIT_VERIFICATION_FAILED"):
        call(root, db, jobs[0])
    assert load_current_grid81(root).canonical_digest == jobs[0][2]
    monkeypatch.setattr(publisher, "_checkpoint", lambda point: None)
    monkeypatch.setattr(publisher, "_commit_exchange", lambda *a: pytest.fail("retry exchanged backward"))
    assert call(root, db, jobs[0]).status == "ALREADY_COMMITTED"


def test_corrupt_stage_is_inert_and_exact_retry_rebuilds_it(tmp_path):
    root, db, jobs = setup(tmp_path)
    finish(start(root, db, jobs[0], crash="after_append"), expected=77)
    stage = next((root / "Canonical").glob(".Grid81.stage.*"))
    (stage / "HEAD.json").write_text("damaged")
    before = (stage / "HEAD.json").read_bytes()
    assert finish(start(root, db, jobs[1]))[0] == "PUBLICATION_RESERVATION_CONFLICT"
    assert (stage / "HEAD.json").read_bytes() == before
    assert call(root, db, jobs[0]).resumed
    verify(root, db, jobs)


def test_reserved_candidate_can_move_but_not_change(tmp_path):
    import shutil
    root, db, jobs = setup(tmp_path)
    finish(start(root, db, jobs[0], crash="after_append"), expected=77)
    moved = tmp_path / "moved"
    shutil.copytree(jobs[0][0], moved)
    assert call(root, db, (moved, *jobs[0][1:])).resumed
    (moved / "Canonical/Grid81/generations/000001.json").write_bytes(b"different history")
    with pytest.raises(PublicationError, match="PUBLICATION_RESERVATION_CONFLICT"):
        call(root, db, (moved, *jobs[0][1:]))


def test_deleted_lock_file_cannot_split_directory_lock(tmp_path):
    root, db, jobs = setup(tmp_path)
    old_lock = tmp_path / "caller.lock"
    old_lock.write_text("")
    reached, release, second = CTX.Event(), CTX.Event(), CTX.Event()
    a = start(root, db, jobs[0], pause="after_lock", reached=reached, release=release)
    assert reached.wait(30)
    old_lock.unlink(); old_lock.write_text("replacement inode")
    # There is no publisher lock file to unlink: the nonempty directory cannot
    # be removed, and writers do not rename/replace it.
    with pytest.raises(OSError): (root / "Canonical").rmdir()
    attempted = CTX.Event()
    b = start(root, db, jobs[1], pause="after_lock", reached=second, release=release, attempted=attempted)
    assert attempted.wait(30)
    assert not second.wait(.2)
    release.set()
    assert finish(a)[0] == "COMMITTED"
    assert finish(b)[0] == "PUBLICATION_RESERVATION_CONFLICT"


def test_legacy_exact_reservation_can_bootstrap_r1(tmp_path):
    root, db, jobs = setup(tmp_path)
    cap = jobs[0][1]
    candidate = load_current_grid81(jobs[0][0])
    with Ledger(db) as ledger:
        payload = publisher._publication_payload(artifact_digest=cap["source_bindings"]["artifact_digest"],
            promotion_capability_digest=cap["capability_digest"],
            previous_canonical_digest=cap["target_bindings"]["source_canonical_digest"],
            candidate=candidate, expected_ledger_head=ledger.head)
        ledger.append(ledger.head, publisher._digest(payload), cap["source_bindings"]["artifact_digest"])
    assert call(root, db, jobs[0]).resumed
    verify(root, db, jobs)


def test_opaque_legacy_nonempty_ledger_cannot_bootstrap_fresh_authority(tmp_path):
    root, db, jobs = setup(tmp_path)
    with Ledger(db) as ledger:
        ledger.append(ledger.head, f._h("opaque receipt"), f._h("other artifact"))
        cap = f._issue(root, ledger, approval="fresh", artifact=f._h("fresh artifact"))
        candidate, state = f._candidate(tmp_path, root, cap, "fresh")
    with pytest.raises(PublicationError, match="UNBOUND_PUBLICATION_LEDGER"):
        call(root, db, (candidate, cap, state.canonical_digest))


def test_in_memory_ledger_cannot_claim_recoverable_publication(tmp_path):
    from elpis_grid81_application_executor.ledger import ApplicationLedger
    root, db, jobs = setup(tmp_path)
    with pytest.raises(PublicationError, match="DURABLE_LEDGER_REQUIRED"):
        publisher.publish_candidate(project_root=root, candidate_root=jobs[0][0],
            promotion_capability=jobs[0][1], ledger=ApplicationLedger())


def test_ledger_storage_identity_and_replacement_detection(tmp_path):
    db = tmp_path / "original.db"
    with Ledger(db) as original:
        alias = tmp_path / "alias.db"; alias.symlink_to(db)
        with Ledger(alias) as aliased:
            assert original.storage_identity == aliased.storage_identity
        with Ledger(tmp_path / "replacement.db") as replacement:
            assert original.storage_identity != replacement.storage_identity
        os.replace(tmp_path / "replacement.db", db)
        with pytest.raises(RuntimeError, match="Ledger database was replaced"):
            original.storage_identity


@pytest.mark.parametrize("mutation", ["bad_json", "payload", "tree", "identity"])
def test_corrupt_recovery_record_fails_before_mutation(tmp_path, mutation):
    root, db, jobs = setup(tmp_path)
    finish(start(root, db, jobs[0], crash="after_append"), expected=77)
    path = root / "Canonical/.Grid81.publisher-r1.json"
    original = path.read_bytes()
    record = json.loads(original)
    if mutation == "payload": record["payload"] = {}; record["receipt_digest"] = publisher._digest({})
    elif mutation == "tree": record["tree_digest"] = 42
    elif mutation == "identity": record["ledger_identity"] = "invalid"
    path.write_text("{" if mutation == "bad_json" else json.dumps(record))
    assert finish(start(root, db, jobs[0]))[0] == "INVALID_RECOVERY_STATE"
    with Ledger(db) as ledger: assert ledger.to_dict()["count"] == 1
    assert load_current_grid81(root).generation_number == 1
    path.write_bytes(original)
    assert call(root, db, jobs[0]).resumed


def test_visible_exact_retry_reports_original_reserved_head(tmp_path):
    root, db, jobs = setup(tmp_path)
    committed = call(root, db, jobs[0])
    with Ledger(db) as ledger:
        ledger.append(ledger.head, f._h("unrelated receipt"), f._h("unrelated artifact"))
    replay = call(root, db, jobs[0])
    assert replay.resulting_ledger_head == committed.resulting_ledger_head
    assert replay.publication_receipt_digest == committed.publication_receipt_digest


def test_old_visible_reservation_rejects_advanced_ledger(tmp_path):
    root, db, jobs = setup(tmp_path)
    finish(start(root, db, jobs[0], crash="after_append"), expected=77)
    with Ledger(db) as ledger:
        ledger.append(ledger.head, f._h("unrelated receipt"), f._h("unrelated artifact"))
    assert finish(start(root, db, jobs[0]))[0] == "LEDGER_ADVANCED_AFTER_RESERVATION"
    assert load_current_grid81(root).generation_number == 1


def model_states(identities):
    """Explore two writers, one crash/restart each, without filesystem details.

    pc: acquire, validate, prepare, reserve, expose, verify, close, done.
    The record excludes a different identity even before SQLite reservation.
    """
    initial = ((0, 0), (0, 0), -1, -1, -1, -1)
    seen = {initial}; pending = [initial]
    while pending:
        pcs, crashes, owner, record, reservation, visible = pending.pop()
        assert reservation == -1 or reservation == record
        assert visible == -1 or visible == reservation
        for i, identity in enumerate(identities):
            pc = pcs[i]
            if pc == 7: continue
            successors = []
            if owner == i and crashes[i] == 0:
                c = list(crashes); c[i] += 1
                q = list(pcs); q[i] = 0
                successors.append((tuple(q), tuple(c), -1, record, reservation, visible))
            if pc == 0 and owner == -1:
                q = list(pcs); q[i] = 1
                successors.append((tuple(q), crashes, i, record, reservation, visible))
            elif owner == i:
                q = list(pcs); q[i] += 1
                r, a, v, lock = record, reservation, visible, owner
                if pc == 1:
                    if r not in (-1, identity): q[i] = 7; lock = -1
                    elif v == identity: q[i] = 6
                elif pc == 2: r = identity
                elif pc == 3: a = identity
                elif pc == 4: v = identity
                elif pc == 6: lock = -1
                successors.append((tuple(q), crashes, lock, r, a, v))
            for state in successors:
                assert visible == -1 or state[-1] == visible
                if state not in seen: seen.add(state); pending.append(state)
    return seen


@pytest.mark.parametrize("identities", [(0, 0), (0, 1)])
def test_bounded_state_model(identities):
    states = model_states(identities)
    assert len(states) > 100
    assert any(state[0] == (7, 7) for state in states)
    # Compare the implementation's observed crash boundaries with the abstract
    # no-reservation / prepared / reserved / visible states explored above.
    triples = {state[-3:] for state in states}
    for point in POINTS:
        prepared = POINTS.index(point) >= POINTS.index("before_append")
        reserved = POINTS.index(point) >= POINTS.index("after_append")
        visible = POINTS.index(point) >= POINTS.index("after_exchange")
        assert (0 if prepared else -1, 0 if reserved else -1, 0 if visible else -1) in triples
    print("model states", identities, len(states))


@pytest.mark.parametrize("seed", range(3))
def test_production_readers_during_successive_publications(tmp_path, seed):
    root, db, jobs = setup(tmp_path)
    stop = CTX.Event(); readers = []
    old = load_current_grid81(root)
    allowed = {(1, old.canonical_digest)}
    for _ in range(3):
        recv, send = CTX.Pipe(False); ready = CTX.Event()
        process = CTX.Process(target=reader_process, args=(root, stop, ready, send))
        process.start(); assert ready.wait(30); readers.append((process, recv))
    rng = random.Random(seed)
    import shutil
    for generation in range(2, 12):
        with Ledger(db) as ledger:
            cap = f._issue(root, ledger, approval=str(generation), artifact=f._h(str(generation)))
            candidate = tmp_path / f"generation{generation}"
            shutil.copytree(root, candidate)
            state = f._make_candidate(root, candidate, cap)
        history = {p.name: p.read_bytes() for p in (root / "Canonical/Grid81/generations").iterdir()}
        allowed.add((generation, state.canonical_digest))
        time.sleep(rng.random() / 1000)
        assert finish(start(root, db, (candidate, cap, state.canonical_digest)))[0] == "COMMITTED"
        assert all((root / "Canonical/Grid81/generations" / n).read_bytes() == b for n, b in history.items())
    stop.set()
    sample_count = 0
    for process, recv in readers:
        seen, errors = recv.recv(); process.join(30)
        sample_count += len(seen)
        assert process.exitcode == 0 and not errors and seen
        assert set(seen) <= allowed
        assert [n for n, _ in seen] == sorted(n for n, _ in seen)
    with Ledger(db) as ledger:
        assert ledger.verify_chain() == (True, "valid")
        assert ledger.to_dict()["count"] == 10
    assert load_current_grid81(root).generation_number == 11
    print("reader samples", seed, sample_count)
