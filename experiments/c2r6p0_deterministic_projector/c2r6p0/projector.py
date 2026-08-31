"""C2R6-P0 deterministic Semantic-IR -> Grid81 projector (entry point).

project() is a pure function of (ProjectionInputV1, pinned ruleset). It
never touches the filesystem, environment, network, time, or any model.
Expected rejections are typed ProjectionResults (status + ProjectionError);
the only raised exceptions are programming errors (bad wrapper types).

Pipeline (each stage cites its rule identifiers in the trace):
  R0  canonicalize the semantic graph (order-insensitive view)
  R5  schedule graph analysis (topo order, components, roots, sinks)
  R15 capacity checks (lanes / ranks / loci) -> DECOMPOSITION_REQUIRED
  R6-R13 deterministic lane/rank allocation, roles, routes, memory,
          constraints, interfaces, terminal locus
  R14 frozen/writable masks (disjoint, covering; terminal frozen)
  R16 declared features + active residual via authoritative C2R7-C
      machinery (width 529, vocabulary identity pinned)
  R17 structural input fingerprint
  trace  proof-carrying replay record
"""
from __future__ import annotations

from elpis_p0.structural_residual import (
    CONTROL_LANE,
    GRID_SIZE,
    LaneBindingV1,
    StructuralSchemaV1,
    build_structural_schema,
    materialisable,
    residual as authority_residual,
    validate_transition,
)

from . import rules as R
from .allocator import VOID, allocate
from .canonicalize import CanonicalGraph, canonicalize, content_digest_of
from .contracts import (
    C2R6P0_SCHEMA_VERSION,
    PROJECTION_DOMAIN,
    ProjectionInputV1,
    ProjectionResultV1,
    ProjectionStatus,
    StructuralBindingV1,
    domain_digest,
    result_digest_payload,
)
from .graph import GraphAnalysis, analyze
from .residual import (
    build_fingerprint,
    build_masks,
    derive_residual_state,
)
from .rules import Ruleset, load_ruleset
from .trace import build_rejection_trace, build_trace

_RULES_CACHE: Ruleset | None = None


def _ruleset() -> Ruleset:
    global _RULES_CACHE
    if _RULES_CACHE is None:
        _RULES_CACHE = load_ruleset()
    return _RULES_CACHE


def _rejection_result(
    content_digest: str,
    ruleset: Ruleset,
    status: ProjectionStatus,
    error,
    trace_rule: str = R.R_CONTRACT_ACCEPT,
    trace_detail: dict | None = None,
) -> ProjectionResultV1:
    trace = build_rejection_trace(
        content_digest,
        ruleset.digest(),
        status.value,
        error,
        rule=trace_rule,
        detail=trace_detail,
    )
    return ProjectionResultV1(
        schema=C2R6P0_SCHEMA_VERSION,
        status=status.value,
        semantic_input_digest=content_digest,
        rule_set_digest=ruleset.digest(),
        grid81=tuple(VOID for _ in range(GRID_SIZE)),
        frozen_mask=tuple(0 for _ in range(GRID_SIZE)),
        writable_mask=tuple(1 for _ in range(GRID_SIZE)),
        bindings=StructuralBindingV1(
            op_bindings=(), entity_bindings=(), edge_bindings=(),
            output_entity_ids=(),
        ),
        invariants=(),
        lane_bindings=(),
        declared_features=tuple(0 for _ in range(ruleset.feature_width)),
        active_residual=tuple(0 for _ in range(ruleset.feature_width)),
        residual_ids=(),
        structural_input_fingerprint="",
        structural_schema=None,
        trace=trace,
        projection_digest="",
        error=error,
        # decomposition rejections carry the authoritative well-founded
        # capacity record (lanes/ranks/loci required); other rejections
        # do not.
        capacity=error.detail.get("capacity")
        if status is ProjectionStatus.DECOMPOSITION_REQUIRED
        else None,
    )


def _finalize_digest(result: ProjectionResultV1) -> ProjectionResultV1:
    from dataclasses import replace

    digest = domain_digest(
        PROJECTION_DOMAIN, result_digest_payload(result)
    )
    return replace(result, projection_digest=digest)


def project(
    pin: ProjectionInputV1,
    ruleset: Ruleset | None = None,
) -> ProjectionResultV1:
    """Project one explicit semantic graph into a Grid81 structural seed."""
    rules = ruleset if ruleset is not None else _ruleset()
    # Single identity space for all outcomes: the canonical content digest
    # (request_id excluded). It is computable for every input, valid or not.
    input_digest = content_digest_of(pin.semantic_graph)

    graph: CanonicalGraph
    graph, err = canonicalize(pin.semantic_graph, rules)
    if graph is None:
        assert err is not None
        return _finalize_digest(
            _rejection_result(
                input_digest, rules,
                ProjectionStatus(err.status),
                err, trace_rule=err.rule,
            )
        )

    analysis: GraphAnalysis
    analysis, err = analyze(graph.payload)
    if analysis is None:
        assert err is not None
        return _finalize_digest(
            _rejection_result(
                graph.content_digest, rules,
                ProjectionStatus.STRUCTURAL_CONTRADICTION,
                err, trace_rule=err.rule,
            )
        )
    assert analysis is not None

    placement, err, capacity = allocate(graph.payload, analysis, rules)
    if placement is None:
        assert err is not None
        return _finalize_digest(
            _rejection_result(
                graph.content_digest, rules,
                ProjectionStatus.DECOMPOSITION_REQUIRED,
                err,
                trace_rule=R.R_DECOMPOSITION_REQUIRED_TRACE,
                trace_detail={"capacity": capacity},
            )
        )
    assert placement is not None

    # ---- masks (R14)
    # Known-fact freeze (mission 13): the control lane is reserved for the
    # terminal RESOLUTION locus, and a lane with NO bound operation is a
    # known fact too (nothing may ever bind to it). Both are frozen, not
    # search space. This keeps the candidate's writable mask a SUBSET of
    # the authority schema's writable mask (which freezes all unbound
    # lanes), so every placement the candidate offers is also a legal
    # validate_transition move under r.structural_schema.
    bound_lanes = {b.lane for b in placement.op_bindings}
    frozen_cells = set(placement.frozen)
    for lane in range(GRID_SIZE // 9):
        if lane == CONTROL_LANE or lane not in bound_lanes:
            for rank in range(9):
                frozen_cells.add(rank * 9 + lane)
    frozen_mask, writable_mask = build_masks(frozen_cells, rules)

    # ---- authoritative schema (C2R7-C)
    lane_bindings = tuple(
        sorted(
            (
                LaneBindingV1(
                    lane=b.lane,
                    semantic_id=b.semantic_id,
                    role="operation",
                    operational_token=b.token,
                )
                for b in placement.op_bindings
            ),
            key=lambda b: b.lane,
        )
    )
    invariants = tuple(
        sorted(placement.invariants, key=lambda i: i.invariant_id)
    )
    grid = tuple(placement.grid)
    schema = build_structural_schema(
        semantic_request_digest=graph.content_digest,
        lane_bindings=lane_bindings,
        invariants=invariants,
    )
    # The authoritative schema is the degenerate seed; this projector is
    # strictly stronger (it places what the facts determine). The schema
    # object is carried so downstream refiners receive the same lane
    # bindings + invariants. Validate it.
    schema.validate()
    # Fail-closed: every cell the CANDIDATE offers as writable must also
    # be writable under the authority schema, so a refiner acting on
    # r.writable_mask can only make validate_transition-legal moves
    # (mission 13: validate mask semantics against existing authority).
    for i in range(GRID_SIZE):
        assert not (writable_mask[i] and schema.writable_mask[i] == 0), (
            f"projector bug: cell {i} writable but frozen by the "
            "authority schema"
        )

    # ---- residual + features (R16, authoritative machinery)
    residual_ids, declared, active = derive_residual_state(
        grid, invariants, rules
    )

    # ---- invariant self-checks (fail closed on projector bugs)
    # The residual is whatever the authoritative machinery reports; a
    # non-empty active residual is NOT a projector bug (mission 19: the
    # projector establishes the search problem, the refiner resolves it).
    # What IS a bug is a residual that disagrees with the recompute.
    assert authority_residual(grid, invariants) == residual_ids, (
        "projector bug: residual mismatch with derived residual"
    )
    assert materialisable(grid, schema), (
        "projector bug: seed is not materialisable under its own schema"
    )

    # ---- bindings (R18 sidecar)
    bindings = StructuralBindingV1(
        op_bindings=tuple(sorted(
            placement.op_bindings, key=lambda b: b.semantic_id)),
        entity_bindings=tuple(sorted(
            placement.entity_bindings, key=lambda b: b.semantic_id)),
        edge_bindings=tuple(sorted(
            placement.edge_bindings, key=lambda b: b.semantic_id)),
        output_entity_ids=graph.output_entity_ids,
    )

    # ---- fingerprint (R17)
    fingerprint = build_fingerprint(
        grid, frozen_mask, writable_mask, invariants, lane_bindings,
        declared, active, bindings,
    )

    # ---- trace
    trace = build_trace(
        graph.content_digest,
        graph.payload,
        placement.actions,
        invariants,
        declared,
        active,
        residual_ids,
        rules.digest(),
    )

    result = ProjectionResultV1(
        schema=C2R6P0_SCHEMA_VERSION,
        status=ProjectionStatus.PROJECTED.value,
        semantic_input_digest=graph.content_digest,
        rule_set_digest=rules.digest(),
        grid81=grid,
        frozen_mask=frozen_mask,
        writable_mask=writable_mask,
        bindings=bindings,
        invariants=invariants,
        lane_bindings=lane_bindings,
        declared_features=declared,
        active_residual=active,
        residual_ids=residual_ids,
        structural_input_fingerprint=fingerprint,
        structural_schema=schema,
        trace=trace,
        projection_digest="",
        error=None,
        capacity=capacity,
    )
    return _finalize_digest(result)


# Convenience: the frozen mask is the complement of writable by
# construction; expose the helper for tests.
def frozen_writable_disjoint(result: ProjectionResultV1) -> bool:
    for i in range(GRID_SIZE):
        if result.frozen_mask[i] and result.writable_mask[i]:
            return False
    return True
