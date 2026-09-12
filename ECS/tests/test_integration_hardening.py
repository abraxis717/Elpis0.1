"""Adversarial integration qualification: synchronized races and hostile records."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import os
from pathlib import Path
import threading

import pytest

from elpis_ecs import canonical
from elpis_ecs.bus import verify_envelope, seal_envelope
from elpis_ecs.errors import EcsError, CorruptEventError, PersistenceError
from elpis_ecs.kernel import Kernel
from elpis_ecs.limits import MAX_FRAME_BYTES, MAX_INT, MAX_PAYLOAD_BYTES, MAX_STRING_BYTES
from elpis_ecs.persistence import LENGTH_PREFIX, _parse_records, Checkpoint, verify_event_chain
from elpis_ecs.port import EntityPort
from elpis_ecs.replay import replay_from_events, replay_with_checkpoint


def setup(k):
    a, b = k.found_entity("alpha"), k.found_entity("beta")
    k.run_until_quiescent()
    return a, b


def reseal(ev):
    ev["payload_digest"] = canonical.digest(ev["payload"])
    ev["event_digest"] = canonical.domain_digest(
        canonical.DOMAIN_EVENT, {k: v for k, v in ev.items() if k != "event_digest"})


class ObservedLock:
    """Signal an actual acquire attempt, before blocking on the real lock."""
    def __init__(self, lock, attempted):
        self.lock, self.attempted = lock, attempted
    def __enter__(self):
        if threading.current_thread().name == "reader":
            self.attempted.set()
        self.lock.acquire()
    def __exit__(self, *exc):
        self.lock.release()


@pytest.mark.parametrize("read", ["events", "snapshot", "state", "state_root_digest", "ready_items", "entity_ids", "mailbox_size", "checkpoint", "log"])
def test_live_reader_cannot_truncate_live_append(tmp_path, monkeypatch, read):
    with Kernel(str(tmp_path)) as k:
        a, b = setup(k)
        header, release, attempted, done = (threading.Event() for _ in range(4))
        original = os.write
        fd = k._log._fd
        size = Path(k.log_path).stat().st_size
        def paused_write(target, data):
            if target == fd and not header.is_set():
                n = original(target, data[:8])
                header.set()
                assert release.wait(10)
                return n
            return original(target, data)
        monkeypatch.setattr(os, "write", paused_write)
        owner = k._log if read == "log" else k
        name = "_lock" if read == "log" else "_mutation_lock"
        monkeypatch.setattr(owner, name, ObservedLock(getattr(owner, name), attempted))
        def reader():
            threading.current_thread().name = "reader"
            try:
                if read == "log":
                    return k._log.read_events()
                if read == "state":
                    return k.state
                if read == "mailbox_size":
                    return k.mailbox_size(b)
                return getattr(k, read)()
            finally:
                done.set()
        with ThreadPoolExecutor(2) as pool:
            writer = pool.submit(k.entity_port(a).propose, b, b"live-race")
            assert header.wait(10)
            future = pool.submit(reader)
            try:
                assert attempted.wait(10)
                assert not done.is_set()
                assert Path(k.log_path).stat().st_size == size + 8
            finally:
                release.set()
            writer.result(10)
            future.result(10)
        root, events = k.state_root_digest(), k.events()
        assert events[-1]["after_state_root"] == root
    with Kernel(str(tmp_path)) as reopened:
        assert reopened.state_root_digest() == root
        assert reopened.events() == events


TOP_CORRUPTIONS = {
    "schema": "ecs.event.unknown", "event_index": 0, "logical_clock": True,
    "transaction_id": "forged", "event_kind": "GENESIS", "entity_id": "f" * 64,
    "payload": {}, "payload_digest": "a" * 64, "before_state_root": "b" * 64,
    "after_state_root": "c" * 64, "prev_event_digest": "d" * 64, "event_digest": "e" * 64,
    "unknown": 0,
}


@pytest.mark.parametrize("field", TOP_CORRUPTIONS)
@pytest.mark.parametrize("seal", [False, True])
def test_checkpoint_tail_top_level_matrix(tmp_path, field, seal):
    with Kernel(str(tmp_path)) as k:
        a, b = setup(k)
        cp = k.checkpoint().to_dict()
        k.entity_port(a).propose(b, b"tail")
        events = k.events()
        bad = deepcopy(events)
        bad[-1][field] = TOP_CORRUPTIONS[field]
        # Independent content digests should not hide schema/link/semantic errors.
        if seal and field not in {"payload_digest", "event_digest"}:
            reseal(bad[-1])
        for marker in [None, cp]:
            with pytest.raises(EcsError):
                replay_with_checkpoint(k._genesis_digest, bad, marker)
        # Exercise real reopen through the checkpoint path as well.
        path = Path(k.log_path)
    path.write_bytes(b"".join(LENGTH_PREFIX.pack(len(raw)) + raw
                             for raw in map(canonical.canonical_bytes, bad)))
    before = path.read_bytes()
    with pytest.raises(EcsError):
        Kernel(str(tmp_path)).open()
    assert path.read_bytes() == before


@pytest.mark.parametrize("field", ["schema", "event_index", "logical_clock", "transaction_id", "event_kind", "entity_id", "payload", "payload_digest", "before_state_root", "after_state_root", "prev_event_digest", "event_digest"])
def test_missing_event_field_rejected(tmp_path, field):
    with Kernel(str(tmp_path)) as k:
        k.found_entity("a")
        events = k.events()
        del events[0][field]
        with pytest.raises(EcsError):
            replay_from_events(k._genesis_digest, events)


ENVELOPE_CORRUPTIONS = [
    ("schema", "bad"), ("message_id", "f" * 64), ("sender_entity_id", "f" * 64),
    ("receiver_entity_id", "f" * 64), ("sequence", True), ("sequence", 0),
    ("sequence", 2), ("sequence", MAX_INT + 1), ("payload_hex", "AB"),
    ("payload_hex", "ab "), ("payload_hex", "a"), ("payload_hex", ""),
    ("payload_hex", "aa" * (MAX_PAYLOAD_BYTES + 1)), ("payload_digest", "f" * 64),
    ("logical_clock", True), ("logical_clock", -1), ("logical_clock", 1), ("extra", 1),
]


@pytest.mark.parametrize("field,value", ENVELOPE_CORRUPTIONS)
def test_checkpoint_tail_envelope_matrix(tmp_path, field, value):
    with Kernel(str(tmp_path)) as k:
        a, b = setup(k)
        cp = k.checkpoint().to_dict()
        k.entity_port(a).propose(b, b"tail")
        events = k.events()
        events[-1]["payload"]["envelope"][field] = value
        reseal(events[-1])
        with pytest.raises(EcsError):
            replay_with_checkpoint(k._genesis_digest, events, cp)


@pytest.mark.parametrize("value", [-1, True, False, 0, 2, 1.0, MAX_INT + 1, "1", None])
def test_exact_clock_hostile_values(tmp_path, value):
    with Kernel(str(tmp_path)) as k:
        k.found_entity("a")
        events = k.events()
        events[0]["logical_clock"] = value
        reseal(events[0])
        with pytest.raises(EcsError):
            replay_from_events(k._genesis_digest, events)


@pytest.mark.parametrize("payload", [
    b"{} ", b'{"a":1,"a":2}', b'[]', b'{"x":NaN}', b'{"x":Infinity}',
    b'{"x":1e999}', b'\xff', b'{"x":"\\ud800"}', b'null', b'not JSON',
    b'{"a":' + b'[' * 2000 + b']' * 2000 + b'}',
])
def test_complete_malformed_records_preserved(tmp_path, payload):
    path = tmp_path / "events.log"
    with Kernel(str(tmp_path)) as k:
        k.found_entity("a")
    with path.open("ab") as stream:
        stream.write(LENGTH_PREFIX.pack(len(payload)) + payload)
    before = path.read_bytes()
    with pytest.raises(EcsError):
        Kernel(str(tmp_path)).open()
    assert path.read_bytes() == before


@pytest.mark.parametrize("length", [0, MAX_FRAME_BYTES + 1, MAX_INT, (1 << 64) - 1])
def test_hostile_length_does_not_allocate_or_truncate(tmp_path, monkeypatch, length):
    path = tmp_path / "events.log"
    path.write_bytes(LENGTH_PREFIX.pack(length))
    real = os.pread
    def bounded(fd, size, offset):
        assert size <= MAX_FRAME_BYTES
        return real(fd, size, offset)
    monkeypatch.setattr(os, "pread", bounded)
    with pytest.raises(CorruptEventError):
        Kernel(str(tmp_path)).open()
    assert path.read_bytes() == LENGTH_PREFIX.pack(length)


@pytest.mark.parametrize("tail", [b"junk", b"\xff", b"\0\0\1", LENGTH_PREFIX.pack(0), LENGTH_PREFIX.pack(MAX_FRAME_BYTES + 1)])
def test_impossible_crash_debris_is_corruption(tmp_path, tail):
    with Kernel(str(tmp_path)) as k:
        k.found_entity("a")
    path = tmp_path / "events.log"
    with path.open("ab") as stream:
        stream.write(tail)
    before = path.read_bytes()
    with pytest.raises(CorruptEventError):
        Kernel(str(tmp_path)).open()
    assert path.read_bytes() == before


@pytest.mark.parametrize("cut", range(1, 9))
def test_all_partial_header_boundaries_recover_and_append(tmp_path, cut):
    with Kernel(str(tmp_path)) as k:
        k.found_entity("a")
        root = k.state_root_digest()
    path = tmp_path / "events.log"
    size = path.stat().st_size
    with path.open("ab") as stream:
        stream.write(LENGTH_PREFIX.pack(100)[:cut])
    with Kernel(str(tmp_path)) as k:
        assert k.state_root_digest() == root
        assert path.stat().st_size == size
        k.found_entity("b")
        root = k.state_root_digest()
    with Kernel(str(tmp_path)) as k:
        assert k.state_root_digest() == root


@pytest.mark.parametrize("field,value", [("founding_index", True), ("founding_index", 2), ("founding_digest", "f" * 64), ("label", ""), ("label", "x" * (MAX_STRING_BYTES + 1)), ("extra", 1)])
def test_founding_payload_semantics(tmp_path, field, value):
    with Kernel(str(tmp_path)) as k:
        k.found_entity("a")
        events = k.events()
        events[-1]["payload"][field] = value
        reseal(events[-1])
        with pytest.raises(EcsError):
            replay_from_events(k._genesis_digest, events)


@pytest.mark.parametrize("field,value", [("from", "DORMANT"), ("to", "TERMINATED"), ("extra", 1)])
def test_lifecycle_payload_semantics(tmp_path, field, value):
    with Kernel(str(tmp_path)) as k:
        a = k.found_entity("a")
        k.activate(a)
        events = k.events()
        events[-1]["payload"][field] = value
        reseal(events[-1])
        with pytest.raises(EcsError):
            replay_from_events(k._genesis_digest, events)


def test_corrupt_semantic_prefix_plus_partial_tail_never_truncates(tmp_path):
    with Kernel(str(tmp_path)) as k:
        k.found_entity("a")
        ev = k.events()[0]
    ev["payload"]["founding_index"] = 3
    reseal(ev)
    raw = canonical.canonical_bytes(ev)
    path = tmp_path / "events.log"
    data = LENGTH_PREFIX.pack(len(raw)) + raw + LENGTH_PREFIX.pack(100) + b"short"
    path.write_bytes(data)
    with pytest.raises(EcsError):
        Kernel(str(tmp_path)).open()
    assert path.read_bytes() == data
    # Failure released descriptor/ownership: repeated opens fail on corruption.
    with pytest.raises(EcsError):
        Kernel(str(tmp_path)).open()


def test_second_owner_and_alias_rejected(tmp_path):
    path = tmp_path / "history"
    with Kernel(str(path)) as k:
        k.found_entity("a")
        alias = tmp_path / "alias"
        alias.symlink_to(path, target_is_directory=True)
        for location in [path, alias]:
            with pytest.raises((OSError, PersistenceError)):
                Kernel(str(location)).open()
        k.found_entity("b")


def test_port_and_state_cannot_be_rebound(tmp_path):
    with Kernel(str(tmp_path)) as k:
        a, b = setup(k)
        port = k.entity_port(a)
        for name, value in [("entity_id", b), ("_entity_id", b), ("_epoch", 123), ("_kernel", None)]:
            with pytest.raises(AttributeError):
                setattr(port, name, value)
            with pytest.raises(AttributeError):
                delattr(port, name)
        with pytest.raises(TypeError):
            EntityPort(k, k._epoch, b)
        before = k.snapshot()
        detached = k.state
        detached.logical_clock = 999
        detached.registry.get(a).lifecycle = "TERMINATED"
        detached.mailboxes.capacity = 1
        assert k.snapshot() == before
        for attr in ["state", "mailbox_capacity", "genesis_label"]:
            with pytest.raises(AttributeError):
                setattr(k, attr, None)
        port.propose(b, b"still-a")
        assert k.events()[-1]["payload"]["envelope"]["sender_entity_id"] == a


def test_dormant_queues_pause_and_terminal_queues_remain_inert(tmp_path):
    with Kernel(str(tmp_path)) as k:
        a, b = setup(k)
        port = k.entity_port(a)
        k.dormant(b)
        port.propose(b, b"queued")
        assert k.step() == 0
        assert k.mailbox_size(b) == 1
        k.reactivate(b)
        assert k.step() == 1
        port.propose(b, b"terminal-retained")
        k.terminate(b)
        assert k.step() == 0
        assert k.mailbox_size(b) == 1
        root = k.state_root_digest()
    with Kernel(str(tmp_path)) as k:
        assert k.state_root_digest() == root
        assert k.step() == 0


@pytest.mark.parametrize("field", ["sequence", "logical_clock"])
def test_envelope_bool_is_not_integer(field):
    env = seal_envelope("a" * 64, "b" * 64, 1, b"x", 1)
    with pytest.raises(EcsError):
        verify_envelope(replace(env, **{field: True}))


def test_concurrent_mixed_operations_and_introspection(tmp_path):
    with Kernel(str(tmp_path), mailbox_capacity=128) as k:
        a, b = setup(k)
        port = k.entity_port(a)
        barrier = threading.Barrier(6)
        def founder():
            barrier.wait()
            for i in range(12):
                eid = k.found_entity(f"new-{i}")
                # Scheduler may have activated it already; own lifecycle uses
                # a separate entity preactivated before concurrent rounds.
        c = k.found_entity("lifecycle")
        k.activate(c)
        def lifecycle():
            barrier.wait()
            for _ in range(12):
                k.dormant(c)
                k.reactivate(c)
        def sender():
            barrier.wait()
            for i in range(24):
                port.propose(b, str(i).encode())
        def processor():
            barrier.wait()
            for _ in range(40):
                k.step()
        def reader():
            barrier.wait()
            for _ in range(24):
                snap = k.snapshot()
                assert snap["event_count"] == snap["state_root"]["logical_clock"]
                assert canonical.domain_digest(canonical.DOMAIN_STATE_ROOT, snap["state_root"]) == snap["state_root_digest"]
                verify_event_chain(k.events())
        def checkpoint():
            barrier.wait()
            for _ in range(12):
                cp = k.checkpoint()
                assert cp.logical_clock == cp.event_index + 1
        with ThreadPoolExecutor(6) as pool:
            futures = [pool.submit(f) for f in [founder, lifecycle, sender, processor, reader, checkpoint]]
            for future in futures:
                future.result(30)
        k.run_until_quiescent()
        events, root = k.events(), k.state_root_digest()
        verify_event_chain(events)
        assert k.state.registry.get(b).state.payload == {"delivered": 24}
        assert replay_from_events(k._genesis_digest, events, 128).state_root_digest() == root
    with Kernel(str(tmp_path), mailbox_capacity=128) as k:
        assert k.state_root_digest() == root


@pytest.mark.parametrize("field,value", [
    ("schema", "unknown"), ("event_index", True), ("event_index", MAX_INT + 1),
    ("event_index", -1), ("logical_clock", True), ("logical_clock", -1),
    ("logical_clock", 99), ("event_digest", "f" * 64),
    ("state_root_digest", "f" * 64), ("checkpoint_digest", "f" * 64), ("extra", 1),
])
def test_checkpoint_record_corruption_falls_back(tmp_path, field, value):
    from elpis_ecs.persistence import checkpoint_digest
    with Kernel(str(tmp_path)) as k:
        setup(k)
        cp = k.checkpoint().to_dict()
        root = k.state_root_digest()
        path = Path(k.cp_path)
    cp[field] = value
    if field != "checkpoint_digest":
        cp["checkpoint_digest"] = checkpoint_digest(cp)
    raw = canonical.canonical_bytes(cp)
    path.write_bytes(LENGTH_PREFIX.pack(len(raw)) + raw)
    with Kernel(str(tmp_path)) as k:
        assert k.state_root_digest() == root


@pytest.mark.parametrize("digest", ["A" * 64, "+" + "0" * 63, " " + "0" * 63, "0" * 63, "０" * 64])
def test_digest_format_is_exact_lowercase_hex(tmp_path, digest):
    with Kernel(str(tmp_path)) as k:
        k.found_entity("a")
        events = k.events()
        events[0]["prev_event_digest"] = digest
        reseal(events[0])
        with pytest.raises(EcsError):
            replay_from_events(k._genesis_digest, events)


def test_ambiguous_scheduler_keys_rejected():
    from elpis_ecs.scheduler import ReadyItem, order_ready
    from elpis_ecs.errors import SchedulerError
    item = ReadyItem(0, "a", 0, "m", "PROCESS_MESSAGE", "m")
    with pytest.raises(SchedulerError):
        order_ready([item, item])


def test_invalid_first_record_rejected_before_reading_remaining_file(tmp_path, monkeypatch):
    path = tmp_path / "events.log"
    frame = LENGTH_PREFIX.pack(2) + b"{}"
    path.write_bytes(frame * 10000)
    read = os.pread
    def first_frame_only(fd, count, offset):
        assert offset < len(frame), "parser accumulated corrupt records before validation"
        return read(fd, count, offset)
    monkeypatch.setattr(os, "pread", first_frame_only)
    with pytest.raises(CorruptEventError):
        Kernel(str(tmp_path)).open()
    assert path.stat().st_size == len(frame) * 10000
