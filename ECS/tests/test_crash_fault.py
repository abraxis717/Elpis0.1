"""M1A — crash / fault injection around the persistence boundary.

After restart, each fault must deterministically yield either the
pre-transition or the post-transition committed state — never a hybrid.

Fault points:
  * before event append            -> pre-transition state
  * during attempted txn (pre-commit) -> pre-transition state
  * immediately after commit, before in-memory projection update
                                          -> post-transition state
  * after projection update          -> post-transition state
  * during checkpoint creation       -> post-transition state (checkpoint
                                          rejected, full replay)
  * truncated log (incomplete trailing record) -> pre-transition state
"""

from __future__ import annotations

import os
import struct

import pytest

from elpis_ecs.kernel import Kernel
from elpis_ecs.persistence import LENGTH_PREFIX, EventLog
from elpis_ecs import canonical
from elpis_ecs.errors import EcsError


class CrashSimulated(Exception):
    """Simulates a process crash at a specific fault point."""


def _setup_two_entities(k):
    a = k.found_entity("alpha")
    b = k.found_entity("beta")
    k.run_until_quiescent()
    return a, b


def _faulted_append(log, write: bool):
    """Replace log.append_event with a faulting version.

    write=True  -> the durable append completes (fsync), THEN the process
                   crashes (simulating power loss after commit, before the
                   in-memory projection update).
    write=False -> the process crashes BEFORE the durable append (no write).
    """
    def faulted(event):
        if write:
            # Complete the real durable append (single write + fsync).
            fd = log.open()
            payload = canonical.canonical_bytes(dict(event))
            framed = LENGTH_PREFIX.pack(len(payload)) + payload
            w = 0
            while w < len(framed):
                w += os.write(fd, framed[w:])
            os.fsync(fd)
        raise CrashSimulated("crash")
    log.append_event = faulted


class TestCrashBeforeAppend:
    def test_yields_pre_transition_state(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _setup_two_entities(k)
        pre_root = k.state_root_digest()
        pre_events = len(k.events())
        pa = k.entity_port(a)
        # Crash BEFORE the durable append of the enqueue.
        _faulted_append(k._log, write=False)
        with pytest.raises(CrashSimulated):
            pa.propose(b, b"crash-before")
        k.close()

        # Restart: must yield the pre-transition state (no hybrid).
        k2 = Kernel(d).open()
        assert k2.state_root_digest() == pre_root
        assert len(k2.events()) == pre_events
        assert k2.mailbox_size(b) == 0
        k2.close()


class TestCrashAfterCommitBeforeProjection:
    def test_yields_post_transition_state(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _setup_two_entities(k)
        # Crash AFTER the durable append (fsync) but BEFORE the in-memory
        # projection update.
        pa = k.entity_port(a)
        _faulted_append(k._log, write=True)
        with pytest.raises(CrashSimulated):
            pa.propose(b, b"crash-after-commit")
        k.close()

        # Restart: the committed event is durable, so replay yields the
        # post-transition state (the message is in the mailbox). The event
        # count is unchanged (the commit already happened before the crash).
        k2 = Kernel(d).open()
        assert k2.mailbox_size(b) == 1
        assert len(k2.events()) == 5
        k2.close()


class TestCrashAfterProjection:
    def test_yields_post_transition_state(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _setup_two_entities(k)
        # Normal commit (append + projection both complete), then crash.
        pa = k.entity_port(a)
        pa.propose(b, b"crash-after-projection")
        post_root = k.state_root_digest()
        post_events = len(k.events())
        k.close()  # process exits (crash) after projection update

        # Restart: post-transition state.
        k2 = Kernel(d).open()
        assert k2.state_root_digest() == post_root
        assert len(k2.events()) == post_events
        assert k2.mailbox_size(b) == 1
        k2.close()


class TestCrashDuringConsumption:
    def test_crash_before_process_commit_yields_pre(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _setup_two_entities(k)
        pa = k.entity_port(a)
        pa.propose(b, b"msg")
        assert k.mailbox_size(b) == 1
        pre_root = k.state_root_digest()
        # Crash before the MESSAGE_PROCESSED commit.
        _faulted_append(k._log, write=False)
        with pytest.raises(CrashSimulated):
            k._process_message(b, k.state.mailboxes.box(b)._queue[0].message_id)
        k.close()

        k2 = Kernel(d).open()
        assert k2.state_root_digest() == pre_root
        assert k2.mailbox_size(b) == 1  # message still queued
        k2.close()

    def test_crash_after_process_commit_yields_post(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _setup_two_entities(k)
        pa = k.entity_port(a)
        pa.propose(b, b"msg")
        mid = k.state.mailboxes.box(b)._queue[0].message_id
        # Crash after the MESSAGE_PROCESSED durable commit.
        _faulted_append(k._log, write=True)
        with pytest.raises(CrashSimulated):
            k._process_message(b, mid)
        k.close()

        k2 = Kernel(d).open()
        assert k2.mailbox_size(b) == 0  # message consumed
        assert k2.state.registry.get(b).state.payload == {"delivered": 1}
        k2.close()


class TestTruncatedLog:
    def test_incomplete_trailing_record_truncated(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _setup_two_entities(k)
        pa = k.entity_port(a)
        pa.propose(b, b"committed")
        pre_root = k.state_root_digest()
        pre_events = len(k.events())
        k.close()

        # Simulate a crash mid-append: append a partial framed record.
        with open(os.path.join(d, "events.log"), "ab") as fh:
            fh.write(LENGTH_PREFIX.pack(500))  # length header
            fh.write(b"partial-payload-bytes")  # incomplete payload
        # The partial record claims 500 bytes but only 23 are present.

        k2 = Kernel(d).open()
        # Recovery truncates the incomplete trailing record -> pre-transition.
        assert k2.state_root_digest() == pre_root
        assert len(k2.events()) == pre_events
        assert k2.mailbox_size(b) == 1
        k2.close()

    def test_truncated_then_new_commit(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _setup_two_entities(k)
        pa = k.entity_port(a)
        pa.propose(b, b"committed")
        k.close()

        with open(os.path.join(d, "events.log"), "ab") as fh:
            fh.write(LENGTH_PREFIX.pack(300))
            fh.write(b"xyz")
        k2 = Kernel(d).open()
        # After truncation, a new commit appends cleanly.
        p2 = k2.entity_port(a)
        p2.propose(b, b"next")
        assert k2.mailbox_size(b) == 2
        k2.close()


class TestCheckpointFault:
    def test_corrupt_checkpoint_rejected_full_replay(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _setup_two_entities(k)
        pa = k.entity_port(a)
        pa.propose(b, b"msg")
        k.run_until_quiescent()
        good_root = k.state_root_digest()
        # Write a valid checkpoint, then corrupt it.
        from elpis_ecs.persistence import Checkpoint
        events = k.events()
        cp = Checkpoint(
            event_index=len(events) - 1,
            event_digest=events[-1]["event_digest"],
            state_root_digest=good_root,
            logical_clock=k.state.logical_clock,
        )
        k._checkpoints.write(cp)
        k.close()

        # Corrupt the checkpoint file.
        with open(os.path.join(d, "checkpoint.bin"), "wb") as fh:
            fh.write(b"\x00\x01\x02\x03corrupt-checkpoint-bytes")

        # Restart: corrupt checkpoint rejected, full replay yields the same
        # state root.
        k2 = Kernel(d).open()
        assert k2.state_root_digest() == good_root
        k2.close()

    def test_checkpoint_speeds_replay_same_result(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _setup_two_entities(k)
        pa = k.entity_port(a)
        pa.propose(b, b"msg")
        k.run_until_quiescent()
        good_root = k.state_root_digest()
        from elpis_ecs.persistence import Checkpoint
        events = k.events()
        cp = Checkpoint(
            event_index=len(events) - 1,
            event_digest=events[-1]["event_digest"],
            state_root_digest=good_root,
            logical_clock=k.state.logical_clock,
        )
        k._checkpoints.write(cp)
        k.close()

        k2 = Kernel(d).open()  # uses the valid checkpoint
        assert k2.state_root_digest() == good_root
        k2.close()
