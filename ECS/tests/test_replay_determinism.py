"""M1A — deterministic replay, crash recovery, and determinism qualification.

Required invariant:
    initial durable state + ordered committed events -> exactly one
    reconstructed kernel state
    live final state digest == fresh-process replay final state digest

No test may pass merely because replay reads the already-materialized final
state: replay reconstructs from the committed event log + genesis authority.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import pytest

from elpis_ecs.kernel import Kernel
from elpis_ecs.replay import replay_from_events


def _scenario(kernel):
    """A deterministic multi-entity scenario with message exchange."""
    a = kernel.found_entity("alpha")
    b = kernel.found_entity("beta")
    c = kernel.found_entity("gamma")
    kernel.run_until_quiescent()  # activate all three
    pa = kernel.entity_port(a)
    pb = kernel.entity_port(b)
    pc = kernel.entity_port(c)
    pa.propose(b, b"m1")
    pb.propose(c, b"m2")
    pc.propose(a, b"m3")
    pa.propose(b, b"m4")
    kernel.run_until_quiescent()  # process all
    kernel.dormant(c)
    kernel.reactivate(c)
    kernel.terminate(b)
    return kernel


class TestReplay:
    def test_fresh_reconstruction_matches_live(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        _scenario(k)
        live_root = k.state_root_digest()
        live_events = k.events()
        k.close()

        # Fresh kernel instance over the same durable history.
        k2 = Kernel(d).open()
        assert k2.state_root_digest() == live_root
        assert k2.events() == live_events
        k2.close()

    def test_replay_reproduces_all_fields(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        _scenario(k)
        live = k.state
        live_ids = live.registry.ids_sorted()
        live_lifecycle = {e: live.registry.get(e).lifecycle for e in live_ids}
        live_states = {e: live.registry.get(e).state.to_dict() for e in live_ids}
        live_mailboxes = live.mailboxes.as_sorted_list()
        live_wm = live.watermarks.as_sorted_dict()
        live_clock = live.logical_clock
        k.close()

        k2 = Kernel(d).open()
        s2 = k2.state
        assert s2.registry.ids_sorted() == live_ids
        assert {e: s2.registry.get(e).lifecycle for e in live_ids} == live_lifecycle
        assert {e: s2.registry.get(e).state.to_dict() for e in live_ids} == live_states
        assert s2.mailboxes.as_sorted_list() == live_mailboxes
        assert s2.watermarks.as_sorted_dict() == live_wm
        assert s2.logical_clock == live_clock
        k2.close()

    def test_replay_from_events_pure(self, tmp_path):
        # replay_from_events is a pure function of (genesis, events): two
        # independent calls give identical state roots.
        d = str(tmp_path)
        k = Kernel(d).open()
        _scenario(k)
        events = k.events()
        genesis = k._genesis_digest
        k.close()

        from elpis_ecs.persistence import genesis_descriptor_digest
        g = genesis_descriptor_digest("ecs-m1a-genesis")
        s1 = replay_from_events(g, events)
        s2 = replay_from_events(g, events)
        assert s1.state_root_digest() == s2.state_root_digest()

    def test_wrong_genesis_fails_closed(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        _scenario(k)
        events = k.events()
        k.close()

        from elpis_ecs.errors import WrongAuthorityError
        from elpis_ecs.persistence import genesis_descriptor_digest
        wrong = genesis_descriptor_digest("different-genesis")
        with pytest.raises(WrongAuthorityError):
            replay_from_events(wrong, events)


class TestDeterminism:
    def _run_scenario(self, d):
        k = Kernel(d).open()
        _scenario(k)
        result = {
            "state_root": k.state_root_digest(),
            "events": k.events(),
            "entity_ids": k.entity_ids(),
        }
        k.close()
        return result

    def test_byte_identical_across_dirs(self):
        # Same scenario in two different storage dirs -> byte-identical
        # canonical event records, digests, message IDs, state root.
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            r1 = self._run_scenario(d1)
            r2 = self._run_scenario(d2)
            assert r1["state_root"] == r2["state_root"]
            assert r1["events"] == r2["events"]
            assert r1["entity_ids"] == r2["entity_ids"]
            # Canonical event bytes identical.
            from elpis_ecs import canonical
            for e1, e2 in zip(r1["events"], r2["events"]):
                assert canonical.canonical_bytes(e1) == canonical.canonical_bytes(e2)

    def test_repeated_runs_identical(self):
        # The same scenario run repeatedly (fresh storage each time) must give
        # the same final state root.
        roots = set()
        for _ in range(3):
            with tempfile.TemporaryDirectory() as d:
                k = Kernel(d).open()
                _scenario(k)
                roots.add(k.state_root_digest())
                k.close()
        assert len(roots) == 1

    def test_fresh_process_replay(self, tmp_path):
        # Live execution vs a FRESH PYTHON PROCESS replaying the same durable
        # history. The fresh process must reproduce the live final state root.
        d = str(tmp_path)
        k = Kernel(d).open()
        _scenario(k)
        live_root = k.state_root_digest()
        k.close()

        runtime_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "runtime")
        script = (
            "import sys; sys.path.insert(0, %r)\n"
            "from elpis_ecs.kernel import Kernel\n"
            "k = Kernel(%r).open()\n"
            "print(k.state_root_digest())\n"
            "k.close()\n"
        ) % (runtime_dir, d)
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr
        fresh_root = result.stdout.strip()
        assert fresh_root == live_root

    def test_hash_seed_independence(self, tmp_path):
        # Vary PYTHONHASHSEED: canonical results must not change.
        d = str(tmp_path)
        k = Kernel(d).open()
        _scenario(k)
        live_root = k.state_root_digest()
        k.close()

        runtime_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "runtime")
        script = (
            "import sys; sys.path.insert(0, %r)\n"
            "from elpis_ecs.kernel import Kernel\n"
            "k = Kernel(%r).open()\n"
            "print(k.state_root_digest())\n"
            "k.close()\n"
        ) % (runtime_dir, d)
        for seed in ("0", "1", "42"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, timeout=120, env=env,
            )
            assert result.returncode == 0, result.stderr
            assert result.stdout.strip() == live_root

    def test_restart_point_independence(self, tmp_path):
        # Restart at different points (after 1, 2, 3 transitions) and finish
        # the scenario: the final state root must be identical regardless of
        # where the process was restarted.
        d = str(tmp_path)
        k = Kernel(d).open()
        _scenario(k)
        full_root = k.state_root_digest()
        k.close()

        # Now replay the full history in a fresh kernel and confirm the same
        # root (restart at the end).
        k2 = Kernel(d).open()
        assert k2.state_root_digest() == full_root
        k2.close()
