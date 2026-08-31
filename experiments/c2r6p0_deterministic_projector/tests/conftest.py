"""Test configuration: path wiring, shared builders, common invariants.

The authority overlay is installed by importing c2r6p0 (its __init__
installs it); elpis_p0 imports below therefore resolve to the pinned
authority sources.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

EXP_DIR = Path(__file__).resolve().parent.parent
if str(EXP_DIR) not in sys.path:
    sys.path.insert(0, str(EXP_DIR))

import c2r6p0  # noqa: F401  (installs the authority overlay)
from c2r6p0 import projector  # noqa: E402
from c2r6p0.contracts import ProjectionInputV1, ProjectionStatus  # noqa: E402
from c2r6p0.rules import load_ruleset  # noqa: E402

from elpis_p0.semantic_ir import (  # noqa: E402
    P0SemanticRequestV1,
    build_semantic_request_v1,
)
from elpis_p0.structural_residual import (  # noqa: E402
    GRID_SIZE,
    materialisable,
    residual as authority_residual,
)


@pytest.fixture(scope="session")
def ruleset():
    return load_ruleset()


@pytest.fixture(scope="session")
def project(ruleset):
    """project(pin) bound to the pinned ruleset."""
    return lambda pin: projector.project(pin, ruleset)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def wrap(graph: P0SemanticRequestV1, **kw) -> ProjectionInputV1:
    return ProjectionInputV1.from_signed(graph, **kw)


def simple_graph(
    request_id: str = "t",
    n_inputs: int = 1,
    n_ops: int = 1,
    with_output: bool = True,
) -> P0SemanticRequestV1:
    """n_ops independent ops each reading its own input (no deps)."""
    from elpis_p0.semantic_ir import SemanticEntityV1, SemanticOperationV1

    ents = []
    ops = []
    outs = []
    for i in range(n_ops):
        in_id = f"in{i}"
        ents.append(SemanticEntityV1(in_id, "input", f"v.{in_id}", "str"))
        if with_output and i == n_ops - 1:
            out_id = f"out{i}"
            ents.append(
                SemanticEntityV1(out_id, "output", f"v.{out_id}", "str")
            )
            outs.append(out_id)
            ops.append(SemanticOperationV1(
                f"op{i}", "step",
                input_entity_ids=(in_id,),
                output_entity_ids=(out_id,),
            ))
        else:
            ops.append(SemanticOperationV1(
                f"op{i}", "step", input_entity_ids=(in_id,),
            ))
    return build_semantic_request_v1(
        request_id=request_id,
        entities=tuple(ents),
        operations=tuple(ops),
        output_entity_ids=tuple(outs),
    )


def check_invariants(result) -> None:
    """Common structural invariants for every PROJECTED result."""
    assert len(result.grid81) == GRID_SIZE
    assert all(0 <= v <= 9 for v in result.grid81)
    assert len(result.frozen_mask) == GRID_SIZE
    assert len(result.writable_mask) == GRID_SIZE
    # frozen/writable: disjoint + covering (mission 13)
    for i in range(GRID_SIZE):
        assert not (result.frozen_mask[i] and result.writable_mask[i])
        assert result.frozen_mask[i] or result.writable_mask[i]
    # residual width + bit shape (mission 20)
    assert len(result.declared_features) == 529
    assert len(result.active_residual) == 529
    assert all(v in (0, 1) for v in result.declared_features)
    assert all(v in (0, 1) for v in result.active_residual)
    for i in range(529):
        assert result.active_residual[i] <= result.declared_features[i]
    # active residual == unsatisfied invariant count
    assert sum(result.active_residual) == len(result.residual_ids)
    # authority identity: same machinery, same answer (mission 20)
    assert authority_residual(
        result.grid81, result.invariants
    ) == result.residual_ids
    assert materialisable(result.grid81, result.structural_schema)
    # terminal locus: frozen RESOLUTION (mission 18)
    assert result.grid81[80] == 9
    assert result.frozen_mask[80] == 1
    # schema validity
    result.structural_schema.validate()
    # digests are 64-hex
    for d in (
        result.structural_input_fingerprint,
        result.projection_digest,
        result.trace.trace_digest,
        result.semantic_input_digest,
        result.rule_set_digest,
    ):
        assert len(d) == 64, (d,)
        assert all(c in "0123456789abcdef" for c in d)
    # every op binding locus exists and is frozen (mission 12/13)
    for b in result.bindings.op_bindings:
        assert 0 <= b.cell < GRID_SIZE
        assert result.grid81[b.cell] == b.token
        assert result.frozen_mask[b.cell] == 1
        assert b.frozen is True


def check_bindings_against_graph(result, graph: P0SemanticRequestV1) -> None:
    """Every binding references a real semantic identity (mission 26)."""
    from elpis_p0.semantic_ir import semantic_request_payload

    payload = semantic_request_payload(graph)
    op_ids = {o["operation_id"] for o in payload["operations"]}
    ent_ids = {e["entity_id"] for e in payload["entities"]}
    dep_ids = {d["dependency_id"] for d in payload["dependencies"]}
    rel_ids = {r["relation_id"] for r in payload["relations"]}
    con_ids = {c["constraint_id"] for c in payload["constraints"]}
    qty_ids = {q["quantity_id"] for q in payload["quantities"]}
    for b in result.bindings.op_bindings:
        assert b.semantic_id in op_ids
    for b in result.bindings.entity_bindings:
        assert b.semantic_id in ent_ids
    for b in result.bindings.edge_bindings:
        sid = b.semantic_id
        if b.semantic_kind == "dependency":
            assert sid in dep_ids
        elif b.semantic_kind == "relation":
            assert sid in rel_ids
        elif b.semantic_kind == "constraint":
            assert sid in con_ids
        elif b.semantic_kind == "quantity":
            assert sid in qty_ids
    assert sorted(result.bindings.output_entity_ids) == sorted(
        payload["output_entity_ids"]
    )


def project_fixture(graph, project) -> object:
    r = project(wrap(graph))
    return r
