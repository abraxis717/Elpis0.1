"""M1A-R1 — persistence / crash-recovery regression (review defect 6).

Proves the recoverable framed append semantics (NOT a syscall-level atomic
claim):
  * a partial framed append is recoverably truncated to the last complete
    valid event prefix;
  * a complete-but-corrupt frame fails closed;
  * the zero-byte write path fails closed (os.write returning 0 ->
    PersistenceError, not an infinite loop);
  * the docs/tests no longer claim a syscall-level atomic write guarantee
    (the module docstring uses the precise terminology).
"""
from __future__ import annotations

import os
from unittest import mock

import pytest

from elpis_ecs.kernel import Kernel
from elpis_ecs.persistence import LENGTH_PREFIX, EventLog
from elpis_ecs.errors import PersistenceError, CorruptEventError


def _two_entities(k):
    a = k.found_entity("alpha")
    b = k.found_entity("beta")
    k.run_until_quiescent()
    return a, b


class TestPartialFrameRecovery:
    def test_partial_trailing_frame_truncated(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_entities(k)
        pa = k.entity_port(a)
        pa.propose(b, b"committed")
        pre_root = k.state_root_digest()
        pre_events = len(k.events())
        k.close()

        # Simulate a crash mid-append: a partial framed record.
        with open(os.path.join(d, "events.log"), "ab") as fh:
            fh.write(LENGTH_PREFIX.pack(500))
            fh.write(b"partial-bytes")  # incomplete payload
        k2 = Kernel(d).open()
        # Recovery truncates the incomplete trailing record -> pre-transition.
        assert k2.state_root_digest() == pre_root
        assert len(k2.events()) == pre_events
        assert k2.mailbox_size(b) == 1
        k2.close()

    def test_partial_length_prefix_truncated(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_entities(k)
        pa = k.entity_port(a)
        pa.propose(b, b"committed")
        pre_root = k.state_root_digest()
        pre_events = len(k.events())
        k.close()

        # Incomplete length prefix (fewer than 8 bytes).
        with open(os.path.join(d, "events.log"), "ab") as fh:
            fh.write(b"\x00\x00\x00")
        k2 = Kernel(d).open()
        assert k2.state_root_digest() == pre_root
        assert len(k2.events()) == pre_events
        k2.close()

    def test_no_hybrid_logical_transition(self, tmp_path):
        """Recovery yields either the pre- or post-transition state, never a
        hybrid: the event count is a clean prefix and the chain verifies."""
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_entities(k)
        pa = k.entity_port(a)
        pa.propose(b, b"one")
        pa.propose(b, b"two")
        full_events = len(k.events())
        k.close()

        # Truncate mid-second-record.
        path = os.path.join(d, "events.log")
        with open(path, "rb") as fh:
            data = fh.read()
        with open(path, "wb") as fh:
            fh.write(data[: len(data) * 3 // 4])
        k2 = Kernel(d).open()
        # Either the full prefix (2 events) or a shorter valid prefix; the
        # chain must verify (no hybrid).
        from elpis_ecs.persistence import verify_event_chain
        verify_event_chain(k2.events())
        assert len(k2.events()) <= full_events
        k2.close()


class TestCompleteCorruptFrame:
    def test_complete_corrupt_frame_fails_closed(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_entities(k)
        k.close()

        # Append a COMPLETE frame whose JSON is malformed.
        with open(os.path.join(d, "events.log"), "ab") as fh:
            payload = b"not-valid-json{{{"
            fh.write(LENGTH_PREFIX.pack(len(payload)))
            fh.write(payload)
        k2 = Kernel(d)
        with pytest.raises(CorruptEventError):
            k2.open()
        k2.close()


class TestZeroByteWrite:
    def test_zero_byte_write_fails_closed(self, tmp_path):
        """If os.write returns 0, the append fails closed (no infinite loop)."""
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_entities(k)
        pa = k.entity_port(a)

        real_write = os.write

        def fake_zero(fd, buf):
            return 0

        with mock.patch("os.write", side_effect=fake_zero):
            with pytest.raises(PersistenceError):
                pa.propose(b, b"should-fail")
        k.close()

    def test_zero_byte_write_no_partial_state(self, tmp_path):
        """A zero-byte write failure leaves the state unchanged (fail closed)."""
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_entities(k)
        pa = k.entity_port(a)
        pre_root = k.state_root_digest()
        pre_events = len(k.events())

        def fake_zero(fd, buf):
            return 0

        with mock.patch("os.write", side_effect=fake_zero):
            with pytest.raises(PersistenceError):
                pa.propose(b, b"should-fail")
        # State unchanged (the transition was not committed).
        assert k.state_root_digest() == pre_root
        assert len(k.events()) == pre_events
        k.close()


class TestTerminology:
    def test_no_syscall_atomic_claim_in_docs(self):
        """The persistence module docstring uses precise recoverable-append
        terminology and does NOT claim a syscall-level atomic transaction."""
        from elpis_ecs import persistence
        doc = (persistence.__doc__ or "").lower()
        assert "recoverable framed append" in doc
        assert "complete-frame recovery" in doc
        # The overclaim phrases must be gone.
        assert "provably atomic" not in doc
        assert "single write + fsync" not in doc
        assert "single-write transaction" not in doc

    def test_append_docstring_precise(self):
        from elpis_ecs.persistence import EventLog
        doc = EventLog.append_event.__doc__ or ""
        assert "recoverable framed append" in doc
        assert "syscall-atomicity" in doc  # explicitly disclaimed
