"""M1A — message envelope, kernel-owned sender attribution, watermark, mailbox."""

from __future__ import annotations

import pytest

from elpis_ecs import bus
from elpis_ecs.errors import (
    EnvelopeError,
    MailboxFullError,
    SequenceRegressionError,
)


class TestEnvelope:
    def test_seal_deterministic(self):
        e1 = bus.seal_envelope("S", "R", 1, b"payload", 5)
        e2 = bus.seal_envelope("S", "R", 1, b"payload", 5)
        assert e1.message_id == e2.message_id
        assert e1.payload_digest == e2.payload_digest

    def test_message_id_identifies_content(self):
        # Same sender/seq/receiver/payload -> same ID.
        e1 = bus.seal_envelope("S", "R", 1, b"p", 0)
        e2 = bus.seal_envelope("S", "R", 1, b"p", 0)
        assert e1.message_id == e2.message_id
        # Different payload -> different ID.
        e3 = bus.seal_envelope("S", "R", 1, b"q", 0)
        assert e1.message_id != e3.message_id
        # Different sequence -> different ID.
        e4 = bus.seal_envelope("S", "R", 2, b"p", 0)
        assert e1.message_id != e4.message_id

    def test_verify_envelope_ok(self):
        e = bus.seal_envelope("S", "R", 1, b"p", 0)
        bus.verify_envelope(e)  # no raise

    def test_verify_payload_digest_mismatch(self):
        e = bus.seal_envelope("S", "R", 1, b"p", 0)
        bad = bus.Envelope(
            schema=e.schema, message_id=e.message_id, sender_entity_id=e.sender_entity_id,
            receiver_entity_id=e.receiver_entity_id, sequence=e.sequence,
            payload=b"tampered", payload_digest=e.payload_digest, logical_clock=e.logical_clock,
        )
        with pytest.raises(EnvelopeError):
            bus.verify_envelope(bad)

    def test_verify_message_id_mismatch(self):
        e = bus.seal_envelope("S", "R", 1, b"p", 0)
        bad = bus.Envelope(
            schema=e.schema, message_id="0" * 64, sender_entity_id=e.sender_entity_id,
            receiver_entity_id=e.receiver_entity_id, sequence=e.sequence,
            payload=e.payload, payload_digest=e.payload_digest, logical_clock=e.logical_clock,
        )
        with pytest.raises(EnvelopeError):
            bus.verify_envelope(bad)

    def test_invalid_sequence(self):
        with pytest.raises(EnvelopeError):
            bus.seal_envelope("S", "R", 0, b"p", 0)

    def test_invalid_clock(self):
        with pytest.raises(EnvelopeError):
            bus.seal_envelope("S", "R", 1, b"p", -1)

    def test_non_bytes_payload(self):
        with pytest.raises(EnvelopeError):
            bus.seal_envelope("S", "R", 1, "not-bytes", 0)


class TestWatermark:
    def test_next_expected_starts_at_one(self):
        wm = bus.SequenceWatermark()
        assert wm.next_expected("S") == 1

    def test_admit_advances(self):
        wm = bus.SequenceWatermark()
        wm.admit("S", 1)
        assert wm.get("S") == 1
        assert wm.next_expected("S") == 2

    def test_replay_rejected(self):
        wm = bus.SequenceWatermark()
        wm.admit("S", 1)
        with pytest.raises(SequenceRegressionError):
            wm.admit("S", 1)  # replay of seq 1

    def test_regression_rejected(self):
        wm = bus.SequenceWatermark()
        wm.admit("S", 1)
        wm.admit("S", 2)
        wm.admit("S", 3)
        with pytest.raises(SequenceRegressionError):
            wm.admit("S", 2)  # regression to an already-seen sequence

    def test_skip_rejected(self):
        wm = bus.SequenceWatermark()
        wm.admit("S", 1)
        with pytest.raises(SequenceRegressionError):
            wm.admit("S", 3)  # gap (seq 2 missing)

    def test_independent_senders(self):
        wm = bus.SequenceWatermark()
        wm.admit("A", 1)
        wm.admit("B", 1)
        assert wm.next_expected("A") == 2
        assert wm.next_expected("B") == 2

    def test_as_sorted_dict(self):
        wm = bus.SequenceWatermark()
        wm.admit("b", 1)
        wm.admit("a", 1)
        assert list(wm.as_sorted_dict()) == ["a", "b"]


class TestMailbox:
    def test_push_pop_fifo(self):
        mb = bus.Mailbox("R", 4)
        mb.push(bus.seal_envelope("S", "R", 1, b"a", 0))
        mb.push(bus.seal_envelope("S", "R", 2, b"b", 0))
        first = mb.pop()
        assert first.payload == b"a"
        second = mb.pop()
        assert second.payload == b"b"

    def test_full_rejects(self):
        mb = bus.Mailbox("R", 2)
        mb.push(bus.seal_envelope("S", "R", 1, b"a", 0))
        mb.push(bus.seal_envelope("S", "R", 2, b"b", 0))
        assert mb.is_full()
        with pytest.raises(MailboxFullError):
            mb.push(bus.seal_envelope("S", "R", 3, b"c", 0))

    def test_wrong_receiver_rejected(self):
        mb = bus.Mailbox("R", 4)
        with pytest.raises(EnvelopeError):
            mb.push(bus.seal_envelope("S", "OTHER", 1, b"a", 0))

    def test_pop_empty_raises(self):
        mb = bus.Mailbox("R", 4)
        with pytest.raises(EnvelopeError):
            mb.pop()

    def test_contents_sorted(self):
        mb = bus.Mailbox("R", 4)
        mb.push(bus.seal_envelope("S", "R", 1, b"a", 0))
        contents = mb.contents_sorted()
        assert len(contents) == 1
        assert contents[0]["payload_hex"] == b"a".hex()


class TestReceiverDeliverable:
    def test_active_ok(self):
        bus.check_receiver_deliverable("ACTIVE")

    def test_dormant_ok(self):
        bus.check_receiver_deliverable("DORMANT")

    def test_terminated_rejected(self):
        from elpis_ecs.errors import TerminatedReceiverError
        with pytest.raises(TerminatedReceiverError):
            bus.check_receiver_deliverable("TERMINATED")

    def test_missing_rejected(self):
        from elpis_ecs.errors import MissingReceiverError
        with pytest.raises(MissingReceiverError):
            bus.check_receiver_deliverable("BOGUS")
