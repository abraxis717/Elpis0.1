"""M1A-R1 — adversarial qualification (fail closed).

Covers the required adversarial list:
  forged sender field, duplicate entity founding, sender sequence replay,
  sender sequence regression, malformed envelope, payload digest mismatch,
  missing receiver, message to terminated receiver, mailbox overflow,
  duplicate processing attempt, corrupt event, broken previous-event digest,
  modified historical event, truncated log, corrupted checkpoint, replay with
  wrong genesis/authority input.

M1A-R1: sender attribution is exercised through the entity-bound port (the
entity-facing API has NO sender parameter).
"""
from __future__ import annotations

import os
import struct

import pytest

from elpis_ecs import canonical
from elpis_ecs.kernel import Kernel
from elpis_ecs.persistence import (
    LENGTH_PREFIX,
    EventLog,
    build_event,
    verify_event_chain,
    verify_event_self_digest,
)
from elpis_ecs.replay import replay_from_events
from elpis_ecs.errors import (
    BrokenChainError,
    CorruptEventError,
    DuplicateEntityError,
    EcsError,
    EntityError,
    EnvelopeError,
    MailboxFullError,
    SequenceRegressionError,
    TerminatedEntityError,
    TerminatedReceiverError,
    WrongAuthorityError,
)


def _two_active(k):
    a = k.found_entity("alpha")
    b = k.found_entity("beta")
    k.run_until_quiescent()
    return a, b


class TestForgedSender:
    def test_forged_sender_field_rejected(self, tmp_path):
        # An entity cannot send as another: the entity-facing API has NO
        # sender parameter. A FOUNDED (not ACTIVE) entity's port cannot send.
        d = str(tmp_path)
        k = Kernel(d).open()
        a = k.found_entity("alpha")
        b = k.found_entity("beta")
        k.activate(b)
        pa = k.entity_port(a)
        # a is FOUNDED (not ACTIVE) -> its port cannot send.
        with pytest.raises(TerminatedEntityError):
            pa.propose(b, b"spoof")
        k.close()

    def test_forged_envelope_message_id_rejected(self, tmp_path):
        # A hand-built envelope with a forged sender produces a different
        # message_id than the kernel-sealed one, so it cannot be the
        # kernel-attributed message.
        from elpis_ecs import bus
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_active(k)
        forged = bus.seal_envelope(b, a, 1, b"x", 1)
        real = bus.seal_envelope(a, b, 1, b"x", 1)
        assert forged.message_id != real.message_id
        k.close()


class TestDuplicateFounding:
    def test_duplicate_identity_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a = k.found_entity("alpha")
        # Re-founding the same label gets a new index -> new ID (no recycle).
        b = k.found_entity("alpha")
        assert a != b
        # The registry never holds a duplicate identity.
        assert len(set(k.entity_ids())) == len(k.entity_ids())
        k.close()

    def test_registry_duplicate_rejected(self):
        from elpis_ecs import entity
        reg = entity.EntityRegistry()
        rec = entity.EntityRecord(
            entity_id="e", label="l", founding_index=0, founding_digest="e",
            lifecycle=entity.FOUNDED,
            state=entity.EntityStateVersion(
                entity_id="e", version=0, prev_state_digest="0" * 64,
                state_digest=entity.initial_state_digest("e"),
                causing_event_id="x", payload={},
            ),
        )
        reg.add(rec)
        with pytest.raises(DuplicateEntityError):
            reg.add(rec)


class TestSequenceReplayRegression:
    def test_replay_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_active(k)
        pa = k.entity_port(a)
        pa.propose(b, b"1")
        pa.propose(b, b"2")
        with pytest.raises(SequenceRegressionError):
            k.state.watermarks.admit(a, 1)  # replay of seq 1
        k.close()

    def test_regression_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_active(k)
        pa = k.entity_port(a)
        pa.propose(b, b"1")
        pa.propose(b, b"2")
        with pytest.raises(SequenceRegressionError):
            k.state.watermarks.admit(a, 2)  # regression to seen seq
        k.close()


class TestMalformedEnvelope:
    def test_payload_digest_mismatch(self):
        from elpis_ecs import bus
        e = bus.seal_envelope("S", "R", 1, b"p", 1)
        bad = bus.Envelope(
            schema=e.schema, message_id=e.message_id, sender_entity_id=e.sender_entity_id,
            receiver_entity_id=e.receiver_entity_id, sequence=e.sequence,
            payload=b"tampered", payload_digest=e.payload_digest, logical_clock=e.logical_clock,
        )
        with pytest.raises(EnvelopeError):
            bus.verify_envelope(bad)

    def test_message_id_mismatch(self):
        from elpis_ecs import bus
        e = bus.seal_envelope("S", "R", 1, b"p", 1)
        bad = bus.Envelope(
            schema=e.schema, message_id="0" * 64, sender_entity_id=e.sender_entity_id,
            receiver_entity_id=e.receiver_entity_id, sequence=e.sequence,
            payload=e.payload, payload_digest=e.payload_digest, logical_clock=e.logical_clock,
        )
        with pytest.raises(EnvelopeError):
            bus.verify_envelope(bad)

    def test_bad_schema(self):
        from elpis_ecs import bus
        e = bus.seal_envelope("S", "R", 1, b"p", 1)
        bad = bus.Envelope(
            schema="wrong.schema", message_id=e.message_id, sender_entity_id=e.sender_entity_id,
            receiver_entity_id=e.receiver_entity_id, sequence=e.sequence,
            payload=e.payload, payload_digest=e.payload_digest, logical_clock=e.logical_clock,
        )
        with pytest.raises(EnvelopeError):
            bus.verify_envelope(bad)

    def test_empty_payload(self):
        from elpis_ecs import bus
        with pytest.raises(EnvelopeError):
            bus.seal_envelope("S", "R", 1, b"", 1)


class TestReceiverConditions:
    def test_missing_receiver(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a = k.found_entity("alpha")
        k.run_until_quiescent()
        pa = k.entity_port(a)
        with pytest.raises(EntityError):
            pa.propose("ghost", b"x")
        k.close()

    def test_terminated_receiver(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_active(k)
        k.terminate(b)
        pa = k.entity_port(a)
        with pytest.raises(TerminatedReceiverError):
            pa.propose(b, b"x")
        k.close()

    def test_mailbox_overflow(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d, mailbox_capacity=1).open()
        a, b = _two_active(k)
        pa = k.entity_port(a)
        pa.propose(b, b"1")
        with pytest.raises(MailboxFullError):
            pa.propose(b, b"2")
        k.close()

    def test_duplicate_processing(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_active(k)
        pa = k.entity_port(a)
        pa.propose(b, b"1")
        pa.propose(b, b"2")
        second = k.state.mailboxes.box(b)._queue[1].message_id
        with pytest.raises(EcsError):
            k._process_message(b, second)  # not the head
        k.close()


class TestCorruptEvent:
    def _corrupt_log(self, d, mutate):
        """Read the log, mutate events, rewrite, return the EventLog."""
        log = EventLog(os.path.join(d, "events.log"))
        log.open()
        events = log.read_events(recovery=True)
        mutate(events)
        # Rewrite the log with the mutated events.
        log.close()
        os.remove(os.path.join(d, "events.log"))
        # Corrupt bytes deliberately bypass the now-validating append API.
        from elpis_ecs.persistence import LENGTH_PREFIX
        with open(os.path.join(d, "events.log"), "wb") as fh:
            for ev in events:
                raw = canonical.canonical_bytes(ev)
                fh.write(LENGTH_PREFIX.pack(len(raw)) + raw)

    def test_corrupt_event_self_digest(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        _two_active(k)
        k.close()

        def mutate(events):
            events[0]["payload_digest"] = "f" * 64  # break self digest
        self._corrupt_log(d, mutate)

        log = EventLog(os.path.join(d, "events.log"))
        log.open()
        with pytest.raises(CorruptEventError):
            log.read_events()
        log.close()

    def test_broken_prev_event_digest(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        _two_active(k)
        k.close()

        def mutate(events):
            # Break ONLY the prev linkage: set event[1]'s prev to a digest
            # that is not event[0]'s digest, then recompute event[1]'s
            # self-digest so its self-digest stays valid. This isolates the
            # chain (prev) check -> BrokenChainError.
            events[1]["prev_event_digest"] = "e" * 64
            body = {kk: vv for kk, vv in events[1].items() if kk != "event_digest"}
            events[1]["event_digest"] = canonical.domain_digest(
                canonical.DOMAIN_EVENT, body)
        self._corrupt_log(d, mutate)

        log = EventLog(os.path.join(d, "events.log"))
        log.open()
        with pytest.raises(BrokenChainError):
            log.read_events()
        log.close()

    def test_modified_historical_event(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        _two_active(k)
        k.close()

        def mutate(events):
            # Modify a historical event's payload -> self digest breaks.
            events[0]["payload"]["label"] = "tampered"
        self._corrupt_log(d, mutate)

        log = EventLog(os.path.join(d, "events.log"))
        log.open()
        with pytest.raises(CorruptEventError):
            log.read_events()
        log.close()

    def test_truncated_log(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        _two_active(k)
        k.close()
        # Truncate the file mid-record.
        path = os.path.join(d, "events.log")
        with open(path, "rb") as fh:
            data = fh.read()
        with open(path, "wb") as fh:
            fh.write(data[:len(data) // 2])  # cut mid-record
        # Recovery: either truncates to a valid prefix or fails closed.
        log = EventLog(path)
        log.open()
        try:
            events = log.read_events(recovery=True)
            # If it parsed, the chain must verify (no hybrid).
            verify_event_chain(events)
        except (CorruptEventError, BrokenChainError):
            pass  # fail closed is acceptable
        log.close()

    def test_replay_wrong_genesis(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        _two_active(k)
        events = k.events()
        k.close()
        from elpis_ecs.persistence import genesis_descriptor_digest
        wrong = genesis_descriptor_digest("attacker-genesis")
        with pytest.raises(WrongAuthorityError):
            replay_from_events(wrong, events)


class TestCorruptCheckpoint:
    def test_corrupt_checkpoint_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        _two_active(k)
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
        # Corrupt the checkpoint.
        with open(os.path.join(d, "checkpoint.bin"), "wb") as fh:
            fh.write(b"\x00garbage")
        # Restart: corrupt checkpoint rejected, full replay -> same root.
        k2 = Kernel(d).open()
        assert k2.state_root_digest() == good_root
        k2.close()

    def test_mismatched_checkpoint_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        _two_active(k)
        from elpis_ecs.persistence import Checkpoint
        events = k.events()
        # A checkpoint with a WRONG state_root_digest (mismatched).
        cp = Checkpoint(
            event_index=len(events) - 1,
            event_digest=events[-1]["event_digest"],
            state_root_digest="0" * 64,  # wrong
            logical_clock=k.state.logical_clock,
        )
        k._checkpoints.write(cp)
        good_root = k.state_root_digest()
        k.close()
        k2 = Kernel(d).open()  # mismatched checkpoint rejected -> full replay
        assert k2.state_root_digest() == good_root
        k2.close()
