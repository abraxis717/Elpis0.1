from __future__ import annotations

import inspect
from enum import EnumMeta
from pathlib import Path

import elpis_grid81_semantics as semantics


EXPECTED_EXPORTS = [
    "Grid81ActionV1",
    "ActionKindV1",
    "canonical_bytes",
    "canonical_digest",
    "D4",
    "transform_coordinate",
    "transform_index",
    "transform_grid81",
    "transform_mask81",
    "transform_action",
    "compose",
    "inverse",
    "D4PairPayloadV1",
    "D4OrbitMemberV1",
    "D4PairOrbitV1",
    "compute_orbit",
    "QuarantineIdentityV1",
    "StructuralSymbolRegistryV1",
    "Grid81GroupProjectionV1",
    "GroupSelectionEvidenceV1",
]


def test_declared_root_exports_are_exact_and_ordered():
    assert semantics.__all__ == EXPECTED_EXPORTS


def test_every_declared_export_resolves():
    for name in EXPECTED_EXPORTS:
        assert hasattr(semantics, name), name


def test_export_categories_match_contract():
    enum_names = {"ActionKindV1", "D4"}
    class_names = {
        "Grid81ActionV1",
        "D4PairPayloadV1",
        "D4OrbitMemberV1",
        "D4PairOrbitV1",
        "QuarantineIdentityV1",
        "StructuralSymbolRegistryV1",
        "Grid81GroupProjectionV1",
        "GroupSelectionEvidenceV1",
    }
    function_names = set(EXPECTED_EXPORTS) - enum_names - class_names

    for name in enum_names:
        assert isinstance(getattr(semantics, name), EnumMeta)
    for name in class_names:
        assert inspect.isclass(getattr(semantics, name))
    for name in function_names:
        assert inspect.isfunction(getattr(semantics, name))


def test_exports_originate_from_promoted_package_boundary():
    for name in EXPECTED_EXPORTS:
        module_name = getattr(getattr(semantics, name), "__module__", "")
        assert module_name.startswith("elpis_grid81_semantics"), (name, module_name)


def test_no_private_name_is_declared_as_root_abi():
    assert not [name for name in semantics.__all__ if name.startswith("_")]


def test_public_submodule_helpers_and_constants_are_available():
    from elpis_grid81_semantics import actions, canonical, d4
    from elpis_grid81_semantics import projection_contracts, quarantine, registry_contracts

    assert canonical.SCHEMA_ID == "elpis.d4_pair_payload.v1"
    assert canonical.SCHEMA_VERSION == "1.0"
    assert d4.N == 9
    assert d4.D4_ELEMENTS == list(d4.D4)
    assert callable(actions.make_noop)
    assert callable(actions.make_edit)
    assert callable(canonical.pair_orbit_digest)
    assert callable(d4.transform_pair)
    assert callable(d4.build_composition_table)
    assert callable(d4.build_inverse_table)
    assert callable(quarantine.compute_quarantine_identity)
    assert callable(quarantine.compute_quarantine_from_pair)
    assert callable(registry_contracts.default_structural_symbol_registry)
    assert callable(projection_contracts.audit_passive_contracts)
