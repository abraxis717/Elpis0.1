from __future__ import annotations

import hashlib
import json

from elpis_grid81_semantics import canonical_bytes, canonical_digest, compute_orbit
from elpis_grid81_semantics.quarantine import (
    compute_quarantine_from_pair,
    compute_quarantine_identity,
)
from elpis_grid81_semantics.registry_contracts import default_structural_symbol_registry
from elpis_grid81_semantics.projection_contracts import GroupSelectionEvidenceV1


def test_canonical_bytes_ignore_dictionary_insertion_order():
    left = {"z": 3, "a": {"y": 2, "x": 1}, "m": [3, 2, 1]}
    right = {"m": [3, 2, 1], "a": {"x": 1, "y": 2}, "z": 3}
    assert canonical_bytes(left) == canonical_bytes(right)
    assert canonical_digest(left) == canonical_digest(right)


def test_canonical_digest_matches_sha256_of_canonical_bytes():
    payload = {"b": 2, "a": 1}
    assert canonical_bytes(payload) == b'{"a":1,"b":2}'
    assert canonical_digest(payload) == hashlib.sha256(b'{"a":1,"b":2}').hexdigest()


def test_same_process_orbit_repetition_is_exact(valid_pair_dict):
    baseline = compute_orbit(valid_pair_dict)
    for _ in range(10):
        assert compute_orbit(valid_pair_dict) == baseline


def test_orbit_ignores_input_dictionary_insertion_order(valid_pair_dict):
    reordered = {
        "schema_version": valid_pair_dict["schema_version"],
        "action": {
            "target_value": valid_pair_dict["action"]["target_value"],
            "kind": valid_pair_dict["action"]["kind"],
            "target_cell": valid_pair_dict["action"]["target_cell"],
        },
        "writable_mask81": valid_pair_dict["writable_mask81"],
        "schema_id": valid_pair_dict["schema_id"],
        "grid81": valid_pair_dict["grid81"],
    }
    assert compute_orbit(reordered) == compute_orbit(valid_pair_dict)


def test_orbit_digest_is_sensitive_to_declared_identity_parameters(valid_pair_dict):
    baseline = compute_orbit(valid_pair_dict)
    assert compute_orbit(valid_pair_dict, schema_id="alternate.schema").pair_orbit_digest != baseline.pair_orbit_digest
    assert compute_orbit(valid_pair_dict, schema_version="2.0").pair_orbit_digest != baseline.pair_orbit_digest
    assert compute_orbit(valid_pair_dict, registry_digest="alternate.registry").pair_orbit_digest != baseline.pair_orbit_digest


def test_default_registry_is_exactly_repeatable():
    first = default_structural_symbol_registry()
    second = default_structural_symbol_registry()
    assert first == second
    assert first.to_dict() == second.to_dict()
    assert first.registry_digest == second.registry_digest


def test_quarantine_canonical_digest_ignores_key_order(valid_pair_dict):
    reordered = dict(reversed(list(valid_pair_dict.items())))
    first = compute_quarantine_from_pair(valid_pair_dict)
    second = compute_quarantine_from_pair(reordered)
    assert first == second


def test_quarantine_raw_and_provenance_components_are_sensitive(valid_pair_dict):
    first = compute_quarantine_identity(valid_pair_dict, b"raw-A", "prov-A")
    raw_changed = compute_quarantine_identity(valid_pair_dict, b"raw-B", "prov-A")
    provenance_changed = compute_quarantine_identity(valid_pair_dict, b"raw-A", "prov-B")
    assert first.canonical_payload_digest == raw_changed.canonical_payload_digest
    assert first.canonical_payload_digest == provenance_changed.canonical_payload_digest
    assert first.raw_byte_sha256 != raw_changed.raw_byte_sha256
    assert first.provenance_root_digest != provenance_changed.provenance_root_digest


def test_evidence_set_serialization_is_hash_seed_independent_in_shape():
    evidence = GroupSelectionEvidenceV1(
        eligible_group_ids={"z", "a", "m"},
        ineligible_group_ids={"y", "b", "n"},
        supporting_motif_digests=["m2", "m1"],
        selection_policy_digest="s",
        status="EVIDENCE_ONLY",
    )
    encoded = json.dumps(evidence.to_dict(), sort_keys=True, separators=(",", ":"))
    assert encoded == (
        '{"eligible_group_ids":["a","m","z"],'
        '"ineligible_group_ids":["b","n","y"],'
        '"selection_policy_digest":"s",'
        '"status":"EVIDENCE_ONLY",'
        '"supporting_motif_digests":["m2","m1"]}'
    )
