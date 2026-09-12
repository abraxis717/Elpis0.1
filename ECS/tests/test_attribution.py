"""M1A-R1 — sender-attribution regression (review defect 1).

Proves the entity-facing API cannot select another entity as sender:
  * an A-bound port emits only A-attributed messages;
  * a B-bound port emits B-attributed messages;
  * the entity-facing propose has NO sender parameter;
  * a stale port (after close/reopen) is rejected;
  * a cross-kernel port is rejected;
  * a port for a dormant/terminated entity cannot send;
  * manually constructing/mutating envelope data does not bypass attribution.

The trusted host API is Kernel.entity_port(entity_id); the entity-facing API
is EntityPort.propose(receiver_entity_id, payload) (no sender parameter).
"""
from __future__ import annotations

import inspect

import pytest

from elpis_ecs.kernel import Kernel
from elpis_ecs.port import EntityPort
from elpis_ecs.errors import (
    PortKernelMismatchError,
    StalePortError,
    TerminatedEntityError,
)


def _two_active(k):
    a = k.found_entity("alpha")
    b = k.found_entity("beta")
    k.run_until_quiescent()
    return a, b


def _envelope_sender(k, receiver):
    """The sender_entity_id of the (single) enqueued message to receiver."""
    ev = [e for e in k.events() if e["event_kind"] == "MESSAGE_ENQUEUED"]
    assert ev, "no MESSAGE_ENQUEUED event committed"
    return ev[-1]["payload"]["envelope"]["sender_entity_id"]


class TestAttribution:
    def test_a_bound_port_emits_only_a(self, tmp_path):
        """All messages sent through an A-bound port are attributed to A."""
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_active(k)
        pa = k.entity_port(a)
        pa.propose(b, b"m1")
        pa.propose(b, b"m2")
        pa.propose(b, b"m3")
        # Every committed envelope is attributed to A.
        for e in k.events():
            if e["event_kind"] == "MESSAGE_ENQUEUED":
                assert e["payload"]["envelope"]["sender_entity_id"] == a
        k.close()

    def test_b_bound_port_emits_b(self, tmp_path):
        """A B-bound port attributes its messages to B (not A)."""
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_active(k)
        pb = k.entity_port(b)
        pb.propose(a, b"from-b")
        assert _envelope_sender(k, a) == b
        k.close()

    def test_no_sender_parameter_on_entity_facing_propose(self):
        """The entity-facing propose has NO sender parameter."""
        sig = inspect.signature(EntityPort.propose)
        params = list(sig.parameters)
        # self + receiver + payload only. No sender of any name.
        assert params == ["self", "receiver_entity_id", "payload"], params
        assert not any("sender" in p for p in params), params

    def test_a_bound_port_cannot_emit_b(self, tmp_path):
        """There is no API parameter by which an A-bound port selects B."""
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_active(k)
        pa = k.entity_port(a)
        # The only entity-facing call is propose(receiver, payload). There is
        # no way to pass b as the sender. The result is attributed to a.
        pa.propose(b, b"cannot-be-b")
        assert _envelope_sender(k, b) == a
        # And the watermark advanced for a, not b.
        assert k.state.watermarks.get(a) == 1
        assert k.state.watermarks.get(b) == 0
        k.close()

    def test_stale_port_after_reopen_rejected(self, tmp_path):
        """A port issued before a close/reopen is stale and rejected."""
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_active(k)
        stale = k.entity_port(a)
        k.close()
        k.open()  # new epoch
        with pytest.raises(StalePortError):
            stale.propose(b, b"stale")
        # A fresh port issued under the new epoch works.
        fresh = k.entity_port(a)
        fresh.propose(b, b"fresh")
        assert _envelope_sender(k, b) == a
        k.close()

    def test_cross_kernel_port_rejected(self, tmp_path):
        """A port issued by one kernel instance is rejected by another.

        The public API structurally routes a port to its issuing kernel
        (port.propose -> port._kernel), so cross-kernel use is impossible
        through the entity-facing surface. This white-box test exercises the
        guard directly: a foreign port passed to a different kernel's
        transition method is rejected.
        """
        d1 = str(tmp_path / "k1")
        d2 = str(tmp_path / "k2")
        k1 = Kernel(d1).open()
        k2 = Kernel(d2).open()
        a, b = _two_active(k1)
        c, dd = _two_active(k2)
        foreign = k1.entity_port(a)
        # Using k1's port against k2 is rejected (kernel identity mismatch).
        with pytest.raises(PortKernelMismatchError):
            k2._propose_from_port(foreign, c, b"cross")
        k1.close()
        k2.close()

    def test_dormant_sender_cannot_send(self, tmp_path):
        """A port for a DORMANT entity cannot send."""
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_active(k)
        pa = k.entity_port(a)
        k.dormant(a)
        with pytest.raises(TerminatedEntityError):
            pa.propose(b, b"dormant-sender")
        k.close()

    def test_terminated_sender_cannot_send(self, tmp_path):
        """A port for a TERMINATED entity cannot send."""
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_active(k)
        pa = k.entity_port(a)
        k.terminate(a)
        with pytest.raises(TerminatedEntityError):
            pa.propose(b, b"terminated-sender")
        k.close()

    def test_founded_sender_cannot_send(self, tmp_path):
        """A port for a FOUNDED (not yet ACTIVE) entity cannot send."""
        d = str(tmp_path)
        k = Kernel(d).open()
        a = k.found_entity("alpha")  # stays FOUNDED
        b = k.found_entity("beta")
        k.activate(b)
        pa = k.entity_port(a)
        with pytest.raises(TerminatedEntityError):
            pa.propose(b, b"founded-sender")
        k.close()

    def test_manual_envelope_cannot_bypass_attribution(self, tmp_path):
        """Manually constructing/mutating envelope data does not bypass the
        kernel's attribution: the entity-facing API takes no envelope, and the
        kernel only seals envelopes with the bound sender."""
        from elpis_ecs import bus
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_active(k)
        pa = k.entity_port(a)
        # The entity-facing API accepts only (receiver, payload) — there is no
        # envelope injection point.
        sig = inspect.signature(EntityPort.propose)
        assert "envelope" not in sig.parameters
        # A hand-forged envelope claiming sender=b is NOT what the kernel
        # commits: the kernel seals with the bound sender a.
        forged = bus.seal_envelope(b, a, 1, b"spoof", 1)
        pa.propose(b, b"real")
        committed = _envelope_sender(k, b)
        assert committed == a
        # The forged envelope's message id differs from the committed one, so
        # it cannot be the kernel-attributed message.
        committed_mid = [
            e for e in k.events() if e["event_kind"] == "MESSAGE_ENQUEUED"
        ][-1]["payload"]["envelope"]["message_id"]
        assert forged.message_id != committed_mid
        k.close()

    def test_port_is_process_local_not_a_token(self, tmp_path):
        """No port token appears in canonical events (replay is unaffected)."""
        d = str(tmp_path)
        k = Kernel(d).open()
        a, b = _two_active(k)
        pa = k.entity_port(a)
        pa.propose(b, b"x")
        # No event field references the port object or any port token.
        for e in k.events():
            for v in e.values():
                assert not isinstance(v, EntityPort)
        k.close()
