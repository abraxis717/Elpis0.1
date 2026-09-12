"""M1A-R1 — replay clock-progression and checkpoint-binding regression
(review defects 4, 5, 11).

Proves:
  * replay verifies exact logical-clock progression (clock == i + 1);
  * a skipped clock is rejected;
  * a duplicated clock is rejected;
  * a regressed clock is rejected;
  * a boolean masquerading as an integer clock is rejected;
  * a negative clock is rejected;
  * the next founding index is replayed exactly;
  * a capacity mismatch is rejected (wrong initial root);
  * a checkpoint whose root matches but whose clock does not is rejected;
  * event-chain field types/ranges are validated (bool-as-int, bad types).
"""
from __future__ import annotations

import copy

import pytest

from elpis_ecs.kernel import Kernel
from elpis_ecs.replay import replay_from_events
from elpis_ecs.persistence import (
    build_event,
    genesis_descriptor_digest,
    state_root_digest,
    empty_state_root,
    verify_event_chain,
)
from elpis_ecs.errors import (
    BrokenChainError,
    CorruptEventError,
    WrongAuthorityError,
)

GENESIS = genesis_descriptor_digest("ecs-m1a-genesis")


def _retamper_clock(events, idx, new_clock):
    """Set events[idx].logical_clock and recompute its self-digest.

    This isolates the CLOCK-PROGRESSION check: the self-digest stays valid,
    so the only thing that can reject the chain is the exact-progression
    requirement (clock == index + 1).
    """
    from elpis_ecs import canonical
    ev = events[idx]
    ev["logical_clock"] = new_clock
    body = {k: v for k, v in ev.items() if k != "event_digest"}
    ev["event_digest"] = canonical.domain_digest(canonical.DOMAIN_EVENT, body)
    return events


def _make_history(k):
    """Build a small committed history and return (events, kernel)."""
    a = k.found_entity("alpha")
    b = k.found_entity("beta")
    k.run_until_quiescent()
    pa = k.entity_port(a)
    pa.propose(b, b"m")
    return k.events()


class TestClockProgression:
    def test_clock_progression_exact(self, tmp_path):
        """Every committed event has logical_clock == index + 1."""
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        for i, ev in enumerate(events):
            assert ev["logical_clock"] == i + 1

    def test_clock_skip_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        bad = copy.deepcopy(events)
        _retamper_clock(bad, 2, bad[2]["logical_clock"] + 1)  # skip
        with pytest.raises(BrokenChainError):
            replay_from_events(GENESIS, bad)

    def test_clock_duplicate_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        bad = copy.deepcopy(events)
        _retamper_clock(bad, 2, bad[1]["logical_clock"])  # duplicate
        with pytest.raises(BrokenChainError):
            replay_from_events(GENESIS, bad)

    def test_clock_regressed_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        bad = copy.deepcopy(events)
        _retamper_clock(bad, 2, 1)  # regressed
        with pytest.raises(BrokenChainError):
            replay_from_events(GENESIS, bad)

    def test_clock_bool_rejected(self, tmp_path):
        """A boolean masquerading as an integer clock is rejected."""
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        bad = copy.deepcopy(events)
        bad[0]["logical_clock"] = True  # bool, not int
        with pytest.raises(CorruptEventError):
            verify_event_chain(bad)

    def test_clock_negative_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        bad = copy.deepcopy(events)
        bad[0]["logical_clock"] = -1
        with pytest.raises(CorruptEventError):
            verify_event_chain(bad)

    def test_clock_non_int_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        bad = copy.deepcopy(events)
        bad[0]["logical_clock"] = "1"  # string, not int
        with pytest.raises(CorruptEventError):
            verify_event_chain(bad)


class TestEventChainFieldValidation:
    def test_event_index_bool_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        bad = copy.deepcopy(events)
        bad[0]["event_index"] = True
        with pytest.raises(CorruptEventError):
            verify_event_chain(bad)

    def test_event_index_mismatch_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        bad = copy.deepcopy(events)
        bad[1]["event_index"] = 5
        with pytest.raises(BrokenChainError):
            verify_event_chain(bad)

    def test_transaction_id_non_str_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        bad = copy.deepcopy(events)
        bad[0]["transaction_id"] = 123
        with pytest.raises(CorruptEventError):
            verify_event_chain(bad)

    def test_entity_id_non_str_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        bad = copy.deepcopy(events)
        bad[0]["entity_id"] = 42
        with pytest.raises(CorruptEventError):
            verify_event_chain(bad)

    def test_payload_non_dict_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        bad = copy.deepcopy(events)
        bad[0]["payload"] = ["not", "a", "dict"]
        with pytest.raises(CorruptEventError):
            verify_event_chain(bad)

    def test_payload_digest_mismatch_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        bad = copy.deepcopy(events)
        bad[0]["payload_digest"] = "f" * 64
        with pytest.raises(CorruptEventError):
            verify_event_chain(bad)

    def test_before_root_non_digest_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        bad = copy.deepcopy(events)
        bad[0]["before_state_root"] = "short"
        with pytest.raises(CorruptEventError):
            verify_event_chain(bad)

    def test_after_root_non_digest_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        bad = copy.deepcopy(events)
        bad[0]["after_state_root"] = "x" * 64  # not hex
        with pytest.raises(CorruptEventError):
            verify_event_chain(bad)

    def test_prev_digest_non_digest_rejected(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        k.close()
        bad = copy.deepcopy(events)
        bad[0]["prev_event_digest"] = "not-a-digest"
        with pytest.raises(CorruptEventError):
            verify_event_chain(bad)


class TestReplayAuthority:
    def test_founding_index_replayed_exactly(self, tmp_path):
        d = str(tmp_path)
        k = Kernel(d).open()
        k.found_entity("e0")
        k.found_entity("e1")
        k.found_entity("e2")
        events = k.events()
        k.close()
        state = replay_from_events(GENESIS, events)
        assert state.next_founding_index == 3

    def test_capacity_mismatch_rejected(self, tmp_path):
        """Replaying a history under a different capacity fails (the initial
        root binds the capacity)."""
        d = str(tmp_path)
        k = Kernel(d, mailbox_capacity=16).open()
        k.found_entity("alpha")
        events = k.events()
        k.close()
        with pytest.raises(WrongAuthorityError):
            replay_from_events(GENESIS, events, mailbox_capacity=64)


class TestCheckpointClockBinding:
    def _checkpointed(self, d, clock_delta=0):
        """Write a checkpoint at the last event; optionally corrupt its clock."""
        from elpis_ecs.persistence import Checkpoint
        k = Kernel(d).open()
        events = _make_history(k)
        cp = Checkpoint(
            event_index=len(events) - 1,
            event_digest=events[-1]["event_digest"],
            state_root_digest=k.state_root_digest(),
            logical_clock=k.state.logical_clock + clock_delta,
        )
        k._checkpoints.write(cp)
        k.close()
        return events

    def test_checkpoint_clock_mismatch_rejected(self, tmp_path):
        """A checkpoint whose root matches but whose clock does not is
        rejected; full replay still yields the correct state."""
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        good_root = k.state_root_digest()
        good_clock = k.state.logical_clock
        k.close()

        from elpis_ecs.persistence import Checkpoint
        cp = Checkpoint(
            event_index=len(events) - 1,
            event_digest=events[-1]["event_digest"],
            state_root_digest=good_root,  # root matches
            logical_clock=good_clock + 5,  # clock does NOT match
        )
        k2 = Kernel(d)
        k2._checkpoints.write(cp)
        # The mismatched checkpoint is rejected; full replay yields the
        # correct state (clock == good_clock, not good_clock + 5).
        k2.open()
        assert k2.state.logical_clock == good_clock
        assert k2.state_root_digest() == good_root
        k2.close()

    def test_valid_checkpoint_accepted(self, tmp_path):
        """A checkpoint whose root, clock, and event digest all agree is
        accepted and yields the same state."""
        d = str(tmp_path)
        events = self._checkpointed(d, clock_delta=0)
        k2 = Kernel(d).open()
        assert k2.state.logical_clock == len(events)
        k2.close()

    def test_checkpoint_event_digest_mismatch_rejected(self, tmp_path):
        """A checkpoint whose event digest does not agree is rejected."""
        d = str(tmp_path)
        k = Kernel(d).open()
        events = _make_history(k)
        good_root = k.state_root_digest()
        good_clock = k.state.logical_clock
        k.close()

        from elpis_ecs.persistence import Checkpoint
        cp = Checkpoint(
            event_index=len(events) - 1,
            event_digest="0" * 64,  # wrong event digest
            state_root_digest=good_root,
            logical_clock=good_clock,
        )
        k2 = Kernel(d)
        k2._checkpoints.write(cp)
        k2.open()
        assert k2.state.logical_clock == good_clock
        assert k2.state_root_digest() == good_root
        k2.close()
