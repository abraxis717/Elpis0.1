"""M1A-R1 — concurrency regression (review defect 7).

The kernel serializes every state transition with one process-local mutation
lock. This test proves that concurrent proposals/founding operations
serialize: event indices remain contiguous, clocks remain contiguous, the
event chain remains valid, and a fresh replay equals the live final root.
"""
from __future__ import annotations

import threading

import pytest

from elpis_ecs.kernel import Kernel
from elpis_ecs.persistence import verify_event_chain


class TestConcurrency:
    def test_concurrent_proposals_serialize(self, tmp_path):
        """Many threads proposing concurrently: indices/clocks contiguous,
        chain valid, fresh replay == live final root."""
        d = str(tmp_path)
        k = Kernel(d, mailbox_capacity=64).open()
        a = k.found_entity("alpha")
        b = k.found_entity("beta")
        k.run_until_quiescent()
        pa = k.entity_port(a)

        n_senders = 4
        msgs_per_sender = 5
        errors = []

        def worker(sender_port, tag):
            try:
                for i in range(msgs_per_sender):
                    sender_port.propose(b, f"{tag}-{i}".encode())
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        # Each worker uses its OWN bound port (a distinct sender). All target
        # the same receiver b. The mutation lock serializes the transitions.
        ports = [k.entity_port(a) for _ in range(n_senders)]
        threads = [
            threading.Thread(target=worker, args=(ports[j], f"s{j}"))
            for j in range(n_senders)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, errors
        total_msgs = n_senders * msgs_per_sender
        # All messages committed (the receiver mailbox may have overflowed;
        # use a large capacity so all are accepted).
        events = k.events()
        enq = [e for e in events if e["event_kind"] == "MESSAGE_ENQUEUED"]
        assert len(enq) == total_msgs, (len(enq), total_msgs)

        # Event indices contiguous.
        indices = [e["event_index"] for e in events]
        assert indices == list(range(len(events))), indices

        # Clocks contiguous (clock == index + 1).
        for i, e in enumerate(events):
            assert e["logical_clock"] == i + 1

        # Chain valid.
        verify_event_chain(events)

        live_root = k.state_root_digest()
        k.close()

        # Fresh replay equals the live final root. The fresh kernel must use
        # the SAME capacity (capacity is operator-supplied configuration; the
        # reconciliation rejects a mismatched capacity).
        k2 = Kernel(d, mailbox_capacity=64).open()
        assert k2.state_root_digest() == live_root
        k2.close()

    def test_concurrent_founding_serialize(self, tmp_path):
        """Concurrent founding operations: no duplicate identities, founding
        indices contiguous, chain valid."""
        d = str(tmp_path)
        k = Kernel(d).open()
        n = 8
        ids = []
        lock = threading.Lock()
        errors = []

        def worker(j):
            try:
                eid = k.found_entity(f"e{j}")
                with lock:
                    ids.append(eid)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(j,)) for j in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, errors
        # No duplicate identities.
        assert len(set(ids)) == n, ids
        # Founding indices contiguous 0..n-1.
        fidx = sorted(k.state.registry.get(e).founding_index for e in ids)
        assert fidx == list(range(n)), fidx
        # Chain valid.
        verify_event_chain(k.events())
        k.close()

    def test_concurrent_mixed_serialize(self, tmp_path):
        """Mixed concurrent founding + proposing: chain valid, indices
        contiguous, fresh replay == live root."""
        d = str(tmp_path)
        k = Kernel(d, mailbox_capacity=64).open()
        a = k.found_entity("alpha")
        b = k.found_entity("beta")
        k.run_until_quiescent()
        pa = k.entity_port(a)
        errors = []

        def founder(j):
            try:
                k.found_entity(f"mix{j}")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def sender(i):
            try:
                pa.propose(b, f"m{i}".encode())
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = []
        for j in range(4):
            threads.append(threading.Thread(target=founder, args=(j,)))
        for i in range(6):
            threads.append(threading.Thread(target=sender, args=(i,)))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, errors
        events = k.events()
        indices = [e["event_index"] for e in events]
        assert indices == list(range(len(events))), indices
        verify_event_chain(events)
        live_root = k.state_root_digest()
        k.close()
        k2 = Kernel(d, mailbox_capacity=64).open()
        assert k2.state_root_digest() == live_root
        k2.close()
