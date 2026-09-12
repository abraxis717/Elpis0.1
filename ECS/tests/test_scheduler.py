"""M1A — deterministic scheduler (explicit ordering tuple, no semantic authority)."""

from __future__ import annotations

from elpis_ecs import scheduler


def _item(rank, eid, idx, mid, kind="PROCESS_MESSAGE"):
    return scheduler.ReadyItem(rank=rank, entity_id=eid, mailbox_index=idx,
                               message_id=mid, kind=kind, ref=mid)


class TestOrdering:
    def test_rank_first(self):
        a = _item(scheduler.RANK_ENQUEUE, "z", 0, "m1")
        b = _item(scheduler.RANK_ACTIVATE, "a", 0, "m2")
        ordered = scheduler.order_ready([b, a])
        assert ordered[0].rank == scheduler.RANK_ENQUEUE

    def test_entity_id_second(self):
        a = _item(0, "b", 0, "m1")
        b = _item(0, "a", 0, "m2")
        ordered = scheduler.order_ready([a, b])
        assert ordered[0].entity_id == "a"

    def test_mailbox_index_third(self):
        a = _item(0, "x", 1, "m1")
        b = _item(0, "x", 0, "m2")
        ordered = scheduler.order_ready([a, b])
        assert ordered[0].mailbox_index == 0

    def test_message_id_fourth(self):
        a = _item(0, "x", 0, "m2")
        b = _item(0, "x", 0, "m1")
        ordered = scheduler.order_ready([a, b])
        assert ordered[0].message_id == "m1"

    def test_input_order_independent(self):
        items = [_item(0, "c", 0, "m3"), _item(0, "a", 0, "m1"), _item(0, "b", 0, "m2")]
        o1 = [i.message_id for i in scheduler.order_ready(items)]
        o2 = [i.message_id for i in scheduler.order_ready(list(reversed(items)))]
        assert o1 == o2 == ["m1", "m2", "m3"]

    def test_total_order_unique(self):
        # No two distinct items share an ordering key.
        items = [_item(0, "a", 0, "m1"), _item(0, "a", 1, "m1"), _item(0, "a", 0, "m2")]
        keys = [i.ordering_key() for i in items]
        assert len(set(keys)) == len(keys)


class TestRun:
    def test_runs_all_in_order(self):
        seen = []
        items = [_item(0, "b", 0, "m2"), _item(0, "a", 0, "m1")]
        n = scheduler.run_deterministic(items, lambda it: seen.append(it.message_id))
        assert n == 2
        assert seen == ["m1", "m2"]

    def test_max_steps_bound(self):
        seen = []
        items = [_item(0, "a", i, f"m{i}") for i in range(5)]
        n = scheduler.run_deterministic(items, lambda it: seen.append(it.message_id), max_steps=3)
        assert n == 3
        assert len(seen) == 3

    def test_empty(self):
        assert scheduler.run_deterministic([], lambda it: None) == 0
