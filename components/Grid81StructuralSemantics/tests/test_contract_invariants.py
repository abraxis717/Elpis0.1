from __future__ import annotations

import hashlib
import json

import pytest

from elpis_grid81_semantics import (
    ActionKindV1,
    D4,
    D4PairPayloadV1,
    Grid81ActionV1,
    Grid81GroupProjectionV1,
    GroupSelectionEvidenceV1,
    canonical_bytes,
    compose,
    compute_orbit,
    inverse,
    transform_action,
    transform_coordinate,
    transform_grid81,
    transform_index,
    transform_mask81,
)
from elpis_grid81_semantics.d4 import D4_ELEMENTS, transform_pair
from elpis_grid81_semantics.projection_contracts import audit_passive_contracts
from elpis_grid81_semantics.quarantine import (
    compute_quarantine_from_pair,
    compute_quarantine_identity,
)
from elpis_grid81_semantics.registry_contracts import (
    default_structural_symbol_registry,
)


def test_action_noop_round_trip_is_canonical(noop_action):
    assert noop_action.to_dict() == {
        "kind": "noop",
        "target_cell": None,
        "target_value": None,
    }
    assert noop_action.to_json() == '{"kind":"noop","target_cell":null,"target_value":null}'
    assert Grid81ActionV1.from_dict(noop_action.to_dict()) == noop_action


@pytest.mark.parametrize(
    ("cell", "value"),
    [(0, 0), (80, 9), (40, 6)],
)
def test_action_edit_accepts_closed_boundaries(cell, value):
    action = Grid81ActionV1(ActionKindV1.EDIT, cell, value)
    assert action.to_dict() == {
        "kind": "edit",
        "target_cell": cell,
        "target_value": value,
    }


def test_action_from_dict_accepts_documented_action_alias():
    action = Grid81ActionV1.from_dict(
        {"action": "edit", "target_cell": 80, "target_value": 9}
    )
    assert action == Grid81ActionV1(ActionKindV1.EDIT, 80, 9)


def test_pair_round_trip_preserves_contract(valid_pair_payload):
    rebuilt = D4PairPayloadV1.from_dict(valid_pair_payload.to_dict())
    assert rebuilt == valid_pair_payload
    assert rebuilt.to_dict() == valid_pair_payload.to_dict()


def test_pair_from_dict_supplies_documented_schema_defaults(valid_pair_dict):
    source = dict(valid_pair_dict)
    source.pop("schema_id")
    source.pop("schema_version")
    rebuilt = D4PairPayloadV1.from_dict(source)
    assert rebuilt.schema_id == "elpis.d4_pair_payload.v1"
    assert rebuilt.schema_version == "1.0"


def test_pair_from_corpus_row_builds_noop_when_no_expansion(valid_corpus_row):
    row = dict(valid_corpus_row)
    row["expansion_targets"] = []
    pair = D4PairPayloadV1.from_corpus_row(row)
    assert pair.action == Grid81ActionV1(ActionKindV1.NOOP, None, None)


@pytest.mark.parametrize(
    ("rationale", "expected"),
    [
        (["VOID_RESOLUTION"], 0),
        (["ACTIVE_EXPANSION"], 6),
        (["UNKNOWN_DIAGNOSTIC"], 0),
        (["VOID_RESOLUTION", "ACTIVE_EXPANSION"], 0),
    ],
)
def test_pair_from_corpus_row_maps_rationale_to_target_value(
    valid_corpus_row, rationale, expected
):
    row = dict(valid_corpus_row)
    row["rationale_codes"] = rationale
    pair = D4PairPayloadV1.from_corpus_row(row)
    assert pair.action.kind is ActionKindV1.EDIT
    assert pair.action.target_cell == 40
    assert pair.action.target_value == expected


def test_d4_element_order_and_cardinality_are_frozen():
    assert D4_ELEMENTS == list(D4)
    assert [element.name for element in D4] == [
        "IDENTITY",
        "ROTATE_90",
        "ROTATE_180",
        "ROTATE_270",
        "REFLECT_HORIZONTAL",
        "REFLECT_VERTICAL",
        "REFLECT_MAIN_DIAGONAL",
        "REFLECT_ANTI_DIAGONAL",
    ]


def test_d4_coordinate_rules_on_asymmetric_coordinate():
    expected = {
        D4.IDENTITY: (1, 2),
        D4.ROTATE_90: (2, 7),
        D4.ROTATE_180: (7, 6),
        D4.ROTATE_270: (6, 1),
        D4.REFLECT_HORIZONTAL: (7, 2),
        D4.REFLECT_VERTICAL: (1, 6),
        D4.REFLECT_MAIN_DIAGONAL: (2, 1),
        D4.REFLECT_ANTI_DIAGONAL: (6, 7),
    }
    assert {
        element: transform_coordinate(1, 2, element)
        for element in D4
    } == expected


@pytest.mark.parametrize("element", list(D4))
def test_each_d4_index_transform_is_a_bijection(element):
    transformed = [transform_index(index, element) for index in range(81)]
    assert sorted(transformed) == list(range(81))


def test_d4_composition_matches_sequential_application_exhaustively():
    for left in D4:
        for right in D4:
            composed = compose(left, right)
            for index in range(81):
                assert transform_index(index, composed) == transform_index(
                    transform_index(index, right), left
                )


@pytest.mark.parametrize("element", list(D4))
def test_d4_inverse_is_two_sided(element):
    inv = inverse(element)
    assert compose(element, inv) is D4.IDENTITY
    assert compose(inv, element) is D4.IDENTITY


def test_grid_and_mask_transforms_follow_position_permutation():
    grid = tuple(range(81))
    mask = tuple(1 if index in {0, 8, 72, 80} else 0 for index in range(81))
    for element in D4:
        transformed_grid = transform_grid81(grid, element)
        transformed_mask = transform_mask81(mask, element)
        for index in range(81):
            destination = transform_index(index, element)
            assert transformed_grid[destination] == grid[index]
            assert transformed_mask[destination] == mask[index]


def test_noop_action_is_d4_invariant(noop_action):
    for element in D4:
        assert transform_action(noop_action.to_dict(), element) == noop_action.to_dict()


def test_edit_action_transforms_cell_but_not_value(edit_action):
    for element in D4:
        transformed = transform_action(edit_action.to_dict(), element)
        assert transformed["kind"] == "edit"
        assert transformed["target_cell"] == transform_index(40, element)
        assert transformed["target_value"] == 6


def test_pair_transform_has_exact_semantic_fields(valid_pair_dict):
    transformed = transform_pair(valid_pair_dict, D4.ROTATE_90)
    assert list(transformed) == ["grid81", "writable_mask81", "action"]
    assert len(transformed["grid81"]) == 81
    assert len(transformed["writable_mask81"]) == 81


def test_symmetric_pair_has_orbit_one_and_stabilizer_eight():
    pair = {
        "grid81": [0] * 81,
        "writable_mask81": [1] * 81,
        "action": {"kind": "noop", "target_cell": None, "target_value": None},
    }
    orbit = compute_orbit(pair)
    assert orbit.orbit_size == 1
    assert orbit.stabilizer_size == 8
    assert orbit.orbit_size * orbit.stabilizer_size == 8
    assert len(orbit.members) == 8
    assert len(orbit.unique_member_digests) == 1


def test_asymmetric_pair_obeys_orbit_stabilizer(valid_pair_dict):
    orbit = compute_orbit(valid_pair_dict)
    assert orbit.orbit_size in {1, 2, 4, 8}
    assert orbit.orbit_size * orbit.stabilizer_size == 8
    assert len(orbit.members) == 8
    assert len(orbit.unique_member_digests) == orbit.orbit_size


def test_orbit_canonical_representative_bytes_are_bound(valid_pair_dict):
    orbit = compute_orbit(valid_pair_dict)
    decoded = bytes.fromhex(orbit.canonical_representative_bytes_hex)
    assert decoded == canonical_bytes(orbit.canonical_representative)
    assert hashlib.sha256(decoded).hexdigest() in orbit.unique_member_digests


def test_orbit_identity_is_d4_invariant(valid_pair_dict):
    baseline = compute_orbit(valid_pair_dict)
    for element in D4:
        transformed_pair = transform_pair(valid_pair_dict, element)
        candidate = compute_orbit(transformed_pair)
        assert candidate.pair_orbit_digest == baseline.pair_orbit_digest
        assert candidate.canonical_representative_bytes_hex == (
            baseline.canonical_representative_bytes_hex
        )


def test_quarantine_identity_keeps_three_digests_separate(valid_pair_dict):
    raw = b"noncanonical raw source bytes"
    result = compute_quarantine_identity(valid_pair_dict, raw, "source-A")
    assert result.canonical_payload_digest == hashlib.sha256(
        canonical_bytes(valid_pair_dict)
    ).hexdigest()
    assert result.raw_byte_sha256 == hashlib.sha256(raw).hexdigest()
    assert result.provenance_root_digest == hashlib.sha256(b"source-A").hexdigest()
    assert len({
        result.canonical_payload_digest,
        result.raw_byte_sha256,
        result.provenance_root_digest,
    }) == 3


def test_quarantine_from_pair_uses_canonical_bytes_as_raw(valid_pair_dict):
    result = compute_quarantine_from_pair(valid_pair_dict)
    empty_provenance = hashlib.sha256(b"").hexdigest()
    assert result.canonical_payload_digest == result.raw_byte_sha256
    assert result.provenance_root_digest == empty_provenance


def test_default_registry_encodes_required_symbol_domains():
    registry = default_structural_symbol_registry()
    assert registry.registry_id == "grid81.structural.v1"
    assert registry.registry_version == "1.0"
    assert registry.structural_regime_id == "grid81.structural.v1"
    assert registry.primitive_groups["void_group"] == {0}
    assert registry.primitive_groups["expansion_group"] == {6}
    assert registry.primitive_groups["all_opcodes"] == set(range(10))
    assert registry.reserved_symbols == set(range(10))
    assert registry.symbols["0"]["canonical_name"] == "VOID"
    assert registry.symbols["6"]["canonical_name"] == "EXPANSION"


def test_default_registry_digest_binds_declared_content():
    registry = default_structural_symbol_registry()
    bound = {
        "registry_id": "grid81.structural.v1",
        "symbols": registry.symbols,
        "primitive_groups": {
            key: sorted(value)
            for key, value in registry.primitive_groups.items()
        },
    }
    expected = hashlib.sha256(
        json.dumps(bound, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert registry.registry_digest == expected


def test_projection_contract_is_passive():
    projection = Grid81GroupProjectionV1(
        grid_digest="g",
        registry_digest="r",
        factor_topology_digest="f",
        per_cell_memberships={0: ["void_group"]},
        per_factor_memberships={"void_group": [0]},
        motif_identities=["m"],
        group_counts={"void_group": 1},
        projection_digest="p",
    )
    evidence = GroupSelectionEvidenceV1(
        eligible_group_ids={"g2", "g1"},
        ineligible_group_ids={"g4", "g3"},
        supporting_motif_digests=["m2", "m1"],
        selection_policy_digest="s",
        status="EVIDENCE_ONLY",
    )
    assert projection.audit_forbidden() == []
    assert evidence.audit_forbidden() == []
    assert audit_passive_contracts(projection, evidence) == []
    assert evidence.to_dict()["eligible_group_ids"] == ["g1", "g2"]
    assert evidence.to_dict()["ineligible_group_ids"] == ["g3", "g4"]


def test_action_factories_delegate_to_canonical_contract():
    from elpis_grid81_semantics.actions import make_edit, make_noop

    assert make_noop() == Grid81ActionV1(ActionKindV1.NOOP, None, None)
    assert make_edit(80, 9) == Grid81ActionV1(ActionKindV1.EDIT, 80, 9)


def test_pair_orbit_digest_helper_matches_orbit_compiler(valid_pair_dict):
    from elpis_grid81_semantics.canonical import pair_orbit_digest

    orbit = compute_orbit(valid_pair_dict)
    canonical_rep = bytes.fromhex(orbit.canonical_representative_bytes_hex)
    assert pair_orbit_digest(
        canonical_rep,
        orbit.schema_id,
        orbit.schema_version,
        orbit.registry_digest,
    ) == orbit.pair_orbit_digest


def test_named_composition_and_inverse_tables_match_public_operations():
    from elpis_grid81_semantics.d4 import build_composition_table, build_inverse_table

    composition = build_composition_table()
    inverses = build_inverse_table()
    assert set(composition) == {element.name for element in D4}
    assert set(inverses) == {element.name for element in D4}
    for left in D4:
        for right in D4:
            assert composition[left.name][right.name] == compose(left, right).name
        assert inverses[left.name] == inverse(left).name


def test_frozen_records_reject_attribute_rebinding(valid_pair_payload):
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        valid_pair_payload.schema_version = "2.0"
