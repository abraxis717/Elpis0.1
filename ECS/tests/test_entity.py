"""M1A — deterministic entity identity, lifecycle, canonical state."""

from __future__ import annotations

import pytest

from elpis_ecs import entity
from elpis_ecs.errors import (
    DuplicateEntityError,
    EntityError,
    InvalidTransitionError,
    TerminatedEntityError,
)

GENESIS = "0" * 64


class TestFounding:
    def test_entity_id_deterministic(self):
        r1 = entity.founding_record(0, "alpha", GENESIS)
        r2 = entity.founding_record(0, "alpha", GENESIS)
        assert entity.entity_id_from_founding(r1) == entity.entity_id_from_founding(r2)

    def test_entity_id_is_64hex(self):
        r = entity.founding_record(0, "alpha", GENESIS)
        assert len(entity.entity_id_from_founding(r)) == 64

    def test_different_index_different_id(self):
        a = entity.entity_id_from_founding(entity.founding_record(0, "x", GENESIS))
        b = entity.entity_id_from_founding(entity.founding_record(1, "x", GENESIS))
        assert a != b

    def test_different_label_different_id(self):
        a = entity.entity_id_from_founding(entity.founding_record(0, "x", GENESIS))
        b = entity.entity_id_from_founding(entity.founding_record(0, "y", GENESIS))
        assert a != b

    def test_different_genesis_different_id(self):
        a = entity.entity_id_from_founding(entity.founding_record(0, "x", GENESIS))
        b = entity.entity_id_from_founding(entity.founding_record(0, "x", "1" * 64))
        assert a != b

    def test_invalid_index(self):
        with pytest.raises(EntityError):
            entity.founding_record(-1, "x", GENESIS)

    def test_invalid_label(self):
        with pytest.raises(EntityError):
            entity.founding_record(0, "", GENESIS)

    def test_invalid_genesis(self):
        with pytest.raises(EntityError):
            entity.founding_record(0, "x", "short")


class TestLifecycle:
    def test_founded_to_active(self):
        assert entity.validate_transition(entity.FOUNDED, entity.ACTIVE) == "ENTITY_ACTIVATED"

    def test_active_to_dormant(self):
        assert entity.validate_transition(entity.ACTIVE, entity.DORMANT) == "ENTITY_DORMANT"

    def test_dormant_to_active(self):
        assert entity.validate_transition(entity.DORMANT, entity.ACTIVE) == "ENTITY_REACTIVATED"

    def test_active_to_terminated(self):
        assert entity.validate_transition(entity.ACTIVE, entity.TERMINATED) == "ENTITY_TERMINATED"

    def test_dormant_to_terminated(self):
        assert entity.validate_transition(entity.DORMANT, entity.TERMINATED) == "ENTITY_TERMINATED"

    def test_founded_to_dormant_illegal(self):
        with pytest.raises(InvalidTransitionError):
            entity.validate_transition(entity.FOUNDED, entity.DORMANT)

    def test_founded_to_terminated_illegal(self):
        with pytest.raises(InvalidTransitionError):
            entity.validate_transition(entity.FOUNDED, entity.TERMINATED)

    def test_active_to_active_illegal(self):
        with pytest.raises(InvalidTransitionError):
            entity.validate_transition(entity.ACTIVE, entity.ACTIVE)

    def test_terminated_is_terminal(self):
        for target in (entity.FOUNDED, entity.ACTIVE, entity.DORMANT, entity.TERMINATED):
            with pytest.raises(TerminatedEntityError):
                entity.validate_transition(entity.TERMINATED, target)

    def test_unknown_state(self):
        with pytest.raises(InvalidTransitionError):
            entity.validate_transition("BOGUS", entity.ACTIVE)


class TestStateVersions:
    def test_state_digest_deterministic(self):
        d1 = entity.state_digest("e", 1, {"k": "v"})
        d2 = entity.state_digest("e", 1, {"k": "v"})
        assert d1 == d2

    def test_version_monotonic_in_digest(self):
        d1 = entity.state_digest("e", 1, {})
        d2 = entity.state_digest("e", 2, {})
        assert d1 != d2

    def test_make_state_version_binds_fields(self):
        v = entity.make_state_version("e", 1, "prev", "evt", {"k": "v"})
        assert v.entity_id == "e"
        assert v.version == 1
        assert v.prev_state_digest == "prev"
        assert v.causing_event_id == "evt"
        assert v.state_digest == entity.state_digest("e", 1, {"k": "v"})

    def test_make_state_version_invalid_version(self):
        with pytest.raises(EntityError):
            entity.make_state_version("e", 0, "prev", "evt", {})

    def test_initial_state_digest(self):
        assert entity.initial_state_digest("e") == entity.state_digest("e", 0, {})


class TestRegistry:
    def _record(self, eid="e1", lifecycle=entity.FOUNDED):
        return entity.EntityRecord(
            entity_id=eid, label="l", founding_index=0, founding_digest=eid,
            lifecycle=lifecycle,
            state=entity.EntityStateVersion(
                entity_id=eid, version=0, prev_state_digest="0" * 64,
                state_digest=entity.initial_state_digest(eid),
                causing_event_id="evt", payload={},
            ),
        )

    def test_add_and_get(self):
        reg = entity.EntityRegistry()
        reg.add(self._record("e1"))
        assert "e1" in reg
        assert reg.get("e1").entity_id == "e1"

    def test_duplicate_rejected(self):
        reg = entity.EntityRegistry()
        reg.add(self._record("e1"))
        with pytest.raises(DuplicateEntityError):
            reg.add(self._record("e1"))

    def test_get_missing_raises(self):
        reg = entity.EntityRegistry()
        with pytest.raises(EntityError):
            reg.get("nope")

    def test_ids_sorted(self):
        reg = entity.EntityRegistry()
        reg.add(self._record("c"))
        reg.add(self._record("a"))
        reg.add(self._record("b"))
        assert reg.ids_sorted() == ["a", "b", "c"]

    def test_state_root_projection_binds_identity_excludes_causing_event_cycle(self):
        reg = entity.EntityRegistry()
        reg.add(self._record("e1"))
        proj = reg.state_root_projection()[0]
        assert "label" in proj
        assert "founding_index" in proj
        assert "causing_event_id" not in proj
        assert "entity_id" in proj
        assert "lifecycle" in proj
        assert "state_version" in proj
        assert "state_digest" in proj
