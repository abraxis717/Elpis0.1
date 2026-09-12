"""Enumerated behavior-field census, not a clock-only proxy for entity state."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from elpis_ecs import canonical
from elpis_ecs.kernel import Kernel
from elpis_ecs.limits import PROTOCOL
from elpis_ecs.persistence import genesis_descriptor_digest
from test_integration_hardening import setup


FIELDS = [
    "genesis_digest", "history_digest", "logical_clock", "next_founding_index",
    "mailbox_capacity", "mailbox_default_capacity", "registry_key", "entity_id",
    "label", "founding_index", "founding_digest", "lifecycle", "state_entity_id",
    "version", "prev_state_digest", "state_digest", "payload", "mailbox_key",
    "mailbox_receiver", "box_capacity", "queue_order", "queue_contents", "watermark",
    "envelope_schema", "message_id", "sender_entity_id", "receiver_entity_id",
    "sequence", "envelope_payload", "payload_digest", "envelope_clock",
]


@pytest.mark.parametrize("field", FIELDS)
def test_individual_state_field_changes_root(tmp_path, field):
    with Kernel(str(tmp_path)) as k:
        a, b = setup(k)
        k.entity_port(a).propose(b, b"one")
        k.entity_port(a).propose(b, b"two")
        s = k.state
        root = s.state_root_digest()
        rec, box = s.registry.get(a), s.mailboxes._boxes[b]
        if field in {"genesis_digest", "history_digest"}:
            setattr(s, field, "f" * 64)
        elif field in {"logical_clock", "next_founding_index", "mailbox_capacity"}:
            setattr(s, field, getattr(s, field) + 1)
        elif field == "mailbox_default_capacity":
            s.mailboxes.capacity += 1
        elif field == "registry_key":
            s.registry._by_id["f" * 64] = s.registry._by_id.pop(a)
        elif field in {"entity_id", "founding_digest"}:
            setattr(rec, field, "f" * 64)
        elif field == "label":
            rec.label = "changed"
        elif field == "founding_index":
            rec.founding_index += 1
        elif field == "lifecycle":
            rec.lifecycle = "DORMANT"
        elif field in {"state_entity_id", "version", "prev_state_digest", "state_digest", "payload"}:
            key = "entity_id" if field == "state_entity_id" else field
            value = {"delivered": 1} if key == "payload" else rec.state.version + 1 if key == "version" else "f" * 64
            rec.state = replace(rec.state, **{key: value})
        elif field == "mailbox_key":
            s.mailboxes._boxes["f" * 64] = s.mailboxes._boxes.pop(b)
        elif field == "mailbox_receiver":
            box.receiver_entity_id = "f" * 64
        elif field == "box_capacity":
            box.capacity += 1
        elif field == "queue_order":
            box._queue.reverse()
        elif field == "queue_contents":
            box._queue.pop()
        elif field == "watermark":
            s.watermarks._wm[a] += 1
        else:
            key = {"envelope_schema": "schema", "envelope_payload": "payload", "envelope_clock": "logical_clock"}.get(field, field)
            env = box._queue[0]
            value = b"changed" if key == "payload" else getattr(env, key) + 1 if key in {"sequence", "logical_clock"} else "f" * 64
            box._queue[0] = replace(env, **{key: value})
        assert s.state_root_digest() != root, field


@pytest.mark.parametrize("field", list(PROTOCOL))
def test_each_protocol_value_is_genesis_bound(monkeypatch, field):
    original = genesis_descriptor_digest("g")
    # Fault injection into protocol implementation, not a runtime config API.
    value = PROTOCOL[field]
    monkeypatch.setitem(PROTOCOL, field, value + 1 if type(value) is int else value + ".changed")
    assert genesis_descriptor_digest("g") != original


def test_distinct_histories_cannot_share_root_with_different_future_event_head(tmp_path):
    roots, heads = [], []
    for i in range(2):
        with Kernel(str(tmp_path / str(i))) as k:
            a, b = setup(k)
            for eid in ([a, b] if i == 0 else [b, a]):
                k.dormant(eid)
                k.reactivate(eid)
            roots.append(k.state_root_digest())
            heads.append(k.snapshot()["event_digest"])
    assert heads[0] != heads[1]
    assert roots[0] != roots[1]
