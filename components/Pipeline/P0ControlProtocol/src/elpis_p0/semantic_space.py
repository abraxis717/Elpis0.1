"""Canonical P0 fixed-position Grid81 semantic schema.

P0 is not D4-semantic: row and column positions carry fixed meanings.
The generic structural Grid81 space remains a separate coarse refinement ABI.
"""
from __future__ import annotations

import hashlib
import json

from .contracts import BasisToken

P0_SEMANTIC_SPACE = "grid81.p0-semantic.v1"
P0_SEMANTIC_ABI_VERSION = "elpis.p0.semantic-grid.v1"
P0_SHAPE = (1, 81)
P0_DTYPE = "int64"
P0_VOCABULARY_SIZE = 10
P0_GENERIC_STRUCTURAL_BRIDGE = "grid81.structural.v1"
P0_ALLOWED_D4_ELEMENTS = ("IDENTITY",)

P0_SEMANTIC_ROWS = (
    "request_contract",
    "input_shape",
    "requested_transform",
    "output_shape",
    "constraints",
    "complexity_flags",
    "expert_interfaces",
    "validation_repair_loci",
    "resolution_control",
)

P0_COLUMN_ROLES = (
    (
        "request_input",
        "parameters_present",
        "route_contract",
        "transform_contract",
        "output_contract",
        "constraint_contract",
        "interface_contract",
        "resolution_contract",
        "reserved",
    ),
    (
        "parameter_slot_0",
        "parameter_slot_1",
        "parameter_slot_2",
        "parameter_slot_3",
        "json_input",
        "file_or_path_input",
        "stream_input",
        "input_constraint",
        "input_route",
    ),
    (
        "transform_slot_0",
        "transform_slot_1",
        "transform_slot_2",
        "class_transform",
        "async_interface",
        "recursive_expansion",
        "cache_or_memory",
        "transform_constraint",
        "transform_output",
    ),
    (
        "output_slot_0",
        "output_slot_1",
        "output_resolution",
        "json_output",
        "iterator_or_generator_output",
        "typed_output",
        "reserved",
        "output_constraint",
        "output_terminal_resolution",
    ),
    (
        "must",
        "never",
        "without",
        "validate",
        "safe",
        "deterministic",
        "typed",
        "test",
        "constraint_anchor",
    ),
    (
        "transform_anchor_0",
        "transform_anchor_1",
        "transform_anchor_2",
        "complexity_ge_5",
        "complexity_ge_7",
        "parallel_flag",
        "route_anchor",
        "constraint_anchor",
        "resolution_anchor",
    ),
    (
        "route_anchor",
        "interface_anchor_0",
        "interface_anchor_1",
        "test_interface",
        "typing_interface",
        "reserved_0",
        "reserved_1",
        "constraint_anchor",
        "resolution_anchor",
    ),
    (
        "syntax_error",
        "entrypoint_missing",
        "import_forbidden",
        "scope_mutation_forbidden",
        "banned_call",
        "language_mismatch",
        "reserved",
        "constraint_anchor",
        "resolution_anchor",
    ),
    (
        "route_anchor",
        "constraint_anchor_0",
        "resolution_anchor_0",
        "complexity_ge_8",
        "constraint_anchor_1",
        "interface_anchor",
        "output_anchor",
        "constraint_anchor_2",
        "resolution_anchor_1",
    ),
)

if len(P0_SEMANTIC_ROWS) != 9 or len(P0_COLUMN_ROLES) != 9:
    raise RuntimeError("P0 semantic schema must contain nine rows")
if any(len(row) != 9 for row in P0_COLUMN_ROLES):
    raise RuntimeError("every P0 semantic row must contain nine column roles")

P0_CELL_ROLES = tuple(
    f"{row_name}.{column_role}"
    for row_name, column_roles in zip(P0_SEMANTIC_ROWS, P0_COLUMN_ROLES)
    for column_role in column_roles
)
if len(P0_CELL_ROLES) != 81 or len(set(P0_CELL_ROLES)) != 81:
    raise RuntimeError("P0 semantic cell roles must be 81 globally unique identities")

P0_CELL_INDEX_BY_ROLE = {
    role: index
    for index, role in enumerate(P0_CELL_ROLES)
}

P0_VALIDATOR_FAILURE_ROLE_BY_KEY = {
    ("python.ast.v1", "SYNTAX_ERROR"):
        "validation_repair_loci.syntax_error",
    ("python.ast.v1", "ENTRYPOINT_MISSING"):
        "validation_repair_loci.entrypoint_missing",
    ("python.ast.v1", "IMPORT_FORBIDDEN"):
        "validation_repair_loci.import_forbidden",
    ("python.ast.v1", "SCOPE_MUTATION_FORBIDDEN"):
        "validation_repair_loci.scope_mutation_forbidden",
    ("python.ast.v1", "BANNED_CALL"):
        "validation_repair_loci.banned_call",
    ("python.ast.v1", "LANGUAGE_MISMATCH"):
        "validation_repair_loci.language_mismatch",
}


def basis_token_coarse_class(token: BasisToken) -> str:
    if token == BasisToken.VOID:
        return "void"
    if token == BasisToken.EXPANSION:
        return "expansion"
    return "terminal"


def semantic_space_payload() -> dict[str, object]:
    return {
        "abi_version": P0_SEMANTIC_ABI_VERSION,
        "allowed_d4_elements": list(P0_ALLOWED_D4_ELEMENTS),
        "coarse_structural_bridge": P0_GENERIC_STRUCTURAL_BRIDGE,
        "column_roles": [list(row) for row in P0_COLUMN_ROLES],
        "dtype": P0_DTYPE,
        "semantic_rows": list(P0_SEMANTIC_ROWS),
        "semantic_space": P0_SEMANTIC_SPACE,
        "shape": list(P0_SHAPE),
        "tokens": [
            {
                "coarse_class": basis_token_coarse_class(token),
                "id": int(token),
                "name": token.name,
            }
            for token in BasisToken
        ],
        "validator_failure_roles": [
            {
                "code": code,
                "role": role,
                "validator_id": validator_id,
            }
            for (validator_id, code), role
            in sorted(P0_VALIDATOR_FAILURE_ROLE_BY_KEY.items())
        ],
        "vocabulary_size": P0_VOCABULARY_SIZE,
    }


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def p0_semantic_space_digest() -> str:
    return hashlib.sha256(_canonical_bytes(semantic_space_payload())).hexdigest()


P0_SEMANTIC_SPACE_DIGEST = p0_semantic_space_digest()


def validator_failure_role(validator_id: str, code: str) -> str:
    try:
        return P0_VALIDATOR_FAILURE_ROLE_BY_KEY[(validator_id, code)]
    except KeyError as exc:
        raise ValueError(
            f"unsupported P0 validator failure locus: {validator_id}/{code}"
        ) from exc


def validator_failure_cell_index(validator_id: str, code: str) -> int:
    return P0_CELL_INDEX_BY_ROLE[validator_failure_role(validator_id, code)]


def validate_p0_projection_identity(projection) -> None:
    if projection.semantic_space != P0_SEMANTIC_SPACE:
        raise ValueError("P0 projection semantic_space mismatch")
    if projection.semantic_abi_version != P0_SEMANTIC_ABI_VERSION:
        raise ValueError("P0 projection semantic ABI mismatch")
    if projection.semantic_space_digest != P0_SEMANTIC_SPACE_DIGEST:
        raise ValueError("P0 projection semantic-space digest mismatch")
    if tuple(projection.semantic_rows) != P0_SEMANTIC_ROWS:
        raise ValueError("P0 projection semantic row schema mismatch")
