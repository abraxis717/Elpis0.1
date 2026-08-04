from __future__ import annotations

import re

import pytest

from elpis_grid81_semantics import (
    ActionKindV1,
    D4,
    D4PairPayloadV1,
    Grid81ActionV1,
    GroupSelectionEvidenceV1,
    transform_coordinate,
)
from elpis_grid81_semantics.registry_contracts import StructuralSymbolRegistryV1


@pytest.mark.parametrize(
    ("kind", "cell", "value", "fragment"),
    [
        (ActionKindV1.NOOP, 0, None, "target_cell=None"),
        (ActionKindV1.NOOP, None, 0, "target_value=None"),
        (ActionKindV1.EDIT, None, 0, "target_cell set"),
        (ActionKindV1.EDIT, 0, None, "target_value set"),
        (ActionKindV1.EDIT, -1, 0, "out of [0,80]"),
        (ActionKindV1.EDIT, 81, 0, "out of [0,80]"),
        (ActionKindV1.EDIT, 0, -1, "out of [0,9]"),
        (ActionKindV1.EDIT, 0, 10, "out of [0,9]"),
        ("noop", None, None, "Unknown action kind"),
    ],
)
def test_action_rejects_each_explicit_invalid_branch(kind, cell, value, fragment):
    with pytest.raises(ValueError, match=re.escape(fragment)):
        Grid81ActionV1(kind, cell, value)


@pytest.mark.parametrize("kind", [None, "", "NOOP", "write", 1])
def test_action_from_dict_rejects_invalid_kind(kind):
    with pytest.raises(ValueError, match="Invalid action kind"):
        Grid81ActionV1.from_dict({"kind": kind})


def test_action_from_dict_rejects_missing_kind():
    with pytest.raises(ValueError, match="Invalid action kind"):
        Grid81ActionV1.from_dict({})


@pytest.mark.parametrize("length", [0, 80, 82])
def test_pair_rejects_wrong_grid_cardinality(length):
    with pytest.raises(ValueError, match="grid81 length"):
        D4PairPayloadV1(
            grid81=tuple([0] * length),
            writable_mask81=tuple([1] * 81),
            action=Grid81ActionV1(ActionKindV1.NOOP, None, None),
            schema_id="elpis.d4_pair_payload.v1",
            schema_version="1.0",
        )


@pytest.mark.parametrize("bad_value", [-1, 10])
def test_pair_rejects_out_of_domain_grid_value(bad_value):
    grid = [0] * 81
    grid[37] = bad_value
    with pytest.raises(ValueError, match=r"grid81\[37\].*out of \[0,9\]"):
        D4PairPayloadV1(
            grid81=tuple(grid),
            writable_mask81=tuple([1] * 81),
            action=Grid81ActionV1(ActionKindV1.NOOP, None, None),
            schema_id="elpis.d4_pair_payload.v1",
            schema_version="1.0",
        )


@pytest.mark.parametrize("length", [0, 80, 82])
def test_pair_rejects_wrong_mask_cardinality(length):
    with pytest.raises(ValueError, match="writable_mask81 length"):
        D4PairPayloadV1(
            grid81=tuple([0] * 81),
            writable_mask81=tuple([1] * length),
            action=Grid81ActionV1(ActionKindV1.NOOP, None, None),
            schema_id="elpis.d4_pair_payload.v1",
            schema_version="1.0",
        )


@pytest.mark.parametrize("bad_value", [-1, 2, 9])
def test_pair_rejects_nonbinary_mask_value(bad_value):
    mask = [1] * 81
    mask[24] = bad_value
    with pytest.raises(ValueError, match=r"writable_mask81\[24\].*not in"):
        D4PairPayloadV1(
            grid81=tuple([0] * 81),
            writable_mask81=tuple(mask),
            action=Grid81ActionV1(ActionKindV1.NOOP, None, None),
            schema_id="elpis.d4_pair_payload.v1",
            schema_version="1.0",
        )


def test_pair_rejects_edit_outside_writable_scope():
    with pytest.raises(ValueError, match="EDIT targets non-writable cell 40"):
        D4PairPayloadV1(
            grid81=tuple([0] * 81),
            writable_mask81=tuple([0] * 81),
            action=Grid81ActionV1(ActionKindV1.EDIT, 40, 6),
            schema_id="elpis.d4_pair_payload.v1",
            schema_version="1.0",
        )


@pytest.mark.parametrize("missing", ["grid81", "writable_mask81", "action"])
def test_pair_from_dict_fails_closed_on_missing_required_field(valid_pair_dict, missing):
    malformed = dict(valid_pair_dict)
    malformed.pop(missing)
    with pytest.raises(KeyError):
        D4PairPayloadV1.from_dict(malformed)


def test_pair_from_corpus_row_rejects_nonwritable_expansion(valid_corpus_row):
    row = dict(valid_corpus_row)
    row["input_mask"] = [0] * 81
    with pytest.raises(ValueError, match="EDIT targets non-writable cell 40"):
        D4PairPayloadV1.from_corpus_row(row)


def _registry(*, void_group, all_opcodes):
    return StructuralSymbolRegistryV1(
        registry_id="r",
        registry_version="1",
        structural_regime_id="s",
        symbols={},
        reserved_symbols=set(),
        primitive_groups={
            "void_group": set(void_group),
            "all_opcodes": set(all_opcodes),
        },
        symbol_to_group={},
        orientation_behavior="o",
        registry_digest="d",
        provenance_root="p",
    )


def test_registry_rejects_missing_void_symbol():
    with pytest.raises(ValueError, match="Symbol 0 must be in void_group"):
        _registry(void_group=set(), all_opcodes=set(range(10)))


@pytest.mark.parametrize("missing_symbol", range(1, 10))
def test_registry_rejects_each_missing_opcode(missing_symbol):
    opcodes = set(range(10)) - {missing_symbol}
    with pytest.raises(ValueError, match=f"Symbol {missing_symbol} must be in all_opcodes"):
        _registry(void_group={0}, all_opcodes=opcodes)


def test_group_selection_evidence_rejects_non_evidence_status():
    with pytest.raises(ValueError, match="status must be EVIDENCE_ONLY"):
        GroupSelectionEvidenceV1(
            eligible_group_ids=set(),
            ineligible_group_ids=set(),
            supporting_motif_digests=[],
            selection_policy_digest="s",
            status="ACTIVE",
        )


def test_transform_coordinate_rejects_unknown_d4_element():
    with pytest.raises(ValueError, match="Unknown D4 element"):
        transform_coordinate(0, 0, object())
