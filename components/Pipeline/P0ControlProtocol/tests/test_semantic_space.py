from __future__ import annotations

from dataclasses import replace

import pytest

from elpis_fractal_spine.structural_semantics import StructuralOpcode
from elpis_p0.contracts import BasisToken, RequestContext
from elpis_p0.projector import DeterministicPythonProjector
from elpis_p0.semantic_space import (
    P0_ALLOWED_D4_ELEMENTS,
    P0_CELL_INDEX_BY_ROLE,
    P0_SEMANTIC_ABI_VERSION,
    P0_SEMANTIC_ROWS,
    P0_SEMANTIC_SPACE,
    P0_SEMANTIC_SPACE_DIGEST,
    P0_VALIDATOR_FAILURE_ROLE_BY_KEY,
    basis_token_coarse_class,
    semantic_space_payload,
    validate_p0_projection_identity,
    validator_failure_cell_index,
)


def test_p0_semantic_space_is_not_generic_structural_space():
    assert P0_SEMANTIC_SPACE == "grid81.p0-semantic.v1"
    assert P0_SEMANTIC_SPACE != "grid81.structural.v1"
    assert P0_ALLOWED_D4_ELEMENTS == ("IDENTITY",)
    assert len(P0_SEMANTIC_SPACE_DIGEST) == 64
    int(P0_SEMANTIC_SPACE_DIGEST, 16)


def test_schema_digest_payload_binds_token_and_position_meaning():
    payload = semantic_space_payload()
    assert payload["semantic_space"] == P0_SEMANTIC_SPACE
    assert payload["semantic_rows"] == list(P0_SEMANTIC_ROWS)
    assert len(payload["column_roles"]) == 9
    assert len(payload["tokens"]) == 10
    assert {row["name"] for row in payload["tokens"]} == {
        token.name for token in BasisToken
    }
    assert payload["allowed_d4_elements"] == ["IDENTITY"]


def test_basis_token_specialization_preserves_generic_coarse_classes():
    generic = {int(token): token for token in StructuralOpcode}
    for token in BasisToken:
        other = generic[int(token)]
        expected = (
            "void"
            if other == StructuralOpcode.VOID
            else "expansion"
            if other == StructuralOpcode.EXPANSION
            else "terminal"
        )
        assert basis_token_coarse_class(token) == expected


def test_canonical_projector_emits_bound_p0_identity():
    projection = DeterministicPythonProjector().project(
        RequestContext(
            request_id="semantic-space",
            prompt="write deterministic python",
        )
    )
    assert projection.semantic_space == P0_SEMANTIC_SPACE
    assert projection.semantic_abi_version == P0_SEMANTIC_ABI_VERSION
    assert projection.semantic_space_digest == P0_SEMANTIC_SPACE_DIGEST
    validate_p0_projection_identity(projection)

    with pytest.raises(ValueError, match="semantic_space mismatch"):
        validate_p0_projection_identity(
            replace(projection, semantic_space="grid81.structural.v1")
        )


def test_every_validator_failure_has_one_distinct_nonvoid_repair_cell():
    projection = DeterministicPythonProjector().project(
        RequestContext(request_id="repair-loci", prompt="x")
    )
    cells = []
    for validator_id, code in sorted(P0_VALIDATOR_FAILURE_ROLE_BY_KEY):
        cell = validator_failure_cell_index(validator_id, code)
        cells.append(cell)
        assert P0_CELL_INDEX_BY_ROLE[
            P0_VALIDATOR_FAILURE_ROLE_BY_KEY[(validator_id, code)]
        ] == cell
        assert 63 <= cell <= 68
        assert projection.grid81[cell] != int(BasisToken.VOID)
    assert len(cells) == len(set(cells)) == 6
