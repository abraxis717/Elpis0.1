from __future__ import annotations

from copy import deepcopy

from elpis_grid81_semantics import (
    D4,
    D4PairPayloadV1,
    Grid81GroupProjectionV1,
    GroupSelectionEvidenceV1,
    canonical_bytes,
    canonical_digest,
    compute_orbit,
    transform_action,
)
from elpis_grid81_semantics.d4 import transform_pair
from elpis_grid81_semantics.projection_contracts import audit_passive_contracts
from elpis_grid81_semantics.quarantine import (
    compute_quarantine_from_pair,
    compute_quarantine_identity,
)
from elpis_grid81_semantics.registry_contracts import default_structural_symbol_registry


def test_canonical_operations_do_not_mutate_nested_payload():
    payload = {"z": [3, {"b": 2, "a": 1}], "a": {"items": [4, 5]}}
    before = deepcopy(payload)
    canonical_bytes(payload)
    canonical_digest(payload)
    assert payload == before


def test_action_transform_does_not_mutate_input(edit_action):
    source = edit_action.to_dict()
    before = deepcopy(source)
    transformed = transform_action(source, D4.ROTATE_90)
    assert source == before
    assert transformed is not source


def test_pair_transform_does_not_mutate_or_alias_input(valid_pair_dict):
    before = deepcopy(valid_pair_dict)
    transformed = transform_pair(valid_pair_dict, D4.ROTATE_90)
    assert valid_pair_dict == before
    assert transformed is not valid_pair_dict
    assert transformed["grid81"] is not valid_pair_dict["grid81"]
    assert transformed["writable_mask81"] is not valid_pair_dict["writable_mask81"]
    assert transformed["action"] is not valid_pair_dict["action"]


def test_orbit_compilation_does_not_mutate_or_alias_input(valid_pair_dict):
    before = deepcopy(valid_pair_dict)
    orbit = compute_orbit(valid_pair_dict)
    assert valid_pair_dict == before
    assert orbit.canonical_representative is not valid_pair_dict
    assert orbit.canonical_representative["grid81"] is not valid_pair_dict["grid81"]
    assert orbit.canonical_representative["action"] is not valid_pair_dict["action"]


def test_pair_from_dict_does_not_mutate_input(valid_pair_dict):
    before = deepcopy(valid_pair_dict)
    pair = D4PairPayloadV1.from_dict(valid_pair_dict)
    assert valid_pair_dict == before
    exported = pair.to_dict()
    assert exported["grid81"] is not valid_pair_dict["grid81"]
    assert exported["writable_mask81"] is not valid_pair_dict["writable_mask81"]
    assert exported["action"] is not valid_pair_dict["action"]


def test_pair_from_corpus_row_does_not_mutate_input(valid_corpus_row):
    before = deepcopy(valid_corpus_row)
    D4PairPayloadV1.from_corpus_row(valid_corpus_row)
    assert valid_corpus_row == before


def test_quarantine_operations_do_not_mutate_payload(valid_pair_dict):
    before = deepcopy(valid_pair_dict)
    compute_quarantine_identity(valid_pair_dict, b"raw", "provenance")
    compute_quarantine_from_pair(valid_pair_dict)
    assert valid_pair_dict == before


def test_registry_serialization_does_not_mutate_registry():
    registry = default_structural_symbol_registry()
    before = deepcopy(registry)
    registry.to_dict()
    assert registry == before


def test_passive_contract_audit_does_not_mutate_inputs():
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
        eligible_group_ids={"g1"},
        ineligible_group_ids={"g2"},
        supporting_motif_digests=["m"],
        selection_policy_digest="s",
        status="EVIDENCE_ONLY",
    )
    projection_before = deepcopy(projection)
    evidence_before = deepcopy(evidence)
    audit_passive_contracts(projection, evidence)
    projection.to_dict()
    evidence.to_dict()
    assert projection == projection_before
    assert evidence == evidence_before


def test_projection_to_dict_preserves_observed_nested_aliases_without_mutating():
    per_cell = {0: ["void_group"]}
    per_factor = {"void_group": [0]}
    motifs = ["m"]
    counts = {"void_group": 1}
    projection = Grid81GroupProjectionV1(
        grid_digest="g",
        registry_digest="r",
        factor_topology_digest="f",
        per_cell_memberships=per_cell,
        per_factor_memberships=per_factor,
        motif_identities=motifs,
        group_counts=counts,
        projection_digest="p",
    )
    before = deepcopy((per_cell, per_factor, motifs, counts))
    exported = projection.to_dict()
    assert (per_cell, per_factor, motifs, counts) == before
    assert exported["per_cell_memberships"] is per_cell
    assert exported["per_factor_memberships"] is per_factor
    assert exported["motif_identities"] is motifs
    assert exported["group_counts"] is counts


def test_registry_to_dict_copies_group_sets_but_aliases_other_observed_fields():
    registry = default_structural_symbol_registry()
    exported = registry.to_dict()
    assert exported["symbols"] is registry.symbols
    assert exported["symbol_to_group"] is registry.symbol_to_group
    assert exported["primitive_groups"] is not registry.primitive_groups
    for name, values in registry.primitive_groups.items():
        assert exported["primitive_groups"][name] == sorted(values)
