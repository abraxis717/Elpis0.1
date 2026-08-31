"""Deterministic canonicalizer for the supported Semantic IR subset.

The canonicalizer converts an authoritative P0SemanticRequestV1 into a
CanonicalGraph (a frozen, order-independent view) or a typed rejection.
It never mutates or repairs the input: malformed IR is rejected, not fixed.

Rejection taxonomy (mission 8, 30):
  INVALID_SEMANTIC_IR        — authority-level or reference violations
  UNSUPPORTED_SEMANTIC_SHAPE — valid IR outside the supported structural subset
  AMBIGUOUS_BINDING          — an explicit fact admits two structural readings
  STRUCTURAL_CONTRADICTION   — explicit facts cannot hold in one Grid81

Declaration-order insensitivity: the authoritative payload function already
sorts node/edge lists by id; every downstream stage consumes sorted views
only. Argument order inside an operation is material (authoritative
semantic_ir treats it as material) and is preserved verbatim.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from elpis_p0.semantic_ir import (
    P0_SEMANTIC_REQUEST_DIGEST_DOMAIN,
    P0_SEMANTIC_REQUEST_SCHEMA,
    P0SemanticRequestContractError,
    P0SemanticRequestV1,
    semantic_request_payload,
)

from .contracts import (
    ErrorCode,
    ProjectionError,
    ProjectionStatus,
    canonical_bytes,
    domain_digest,
    sha256_hex,
)
from . import rules as R
from .rules import Ruleset
from .taxonomy import (
    QUANTITY_ARITY_PREDICATES,
    SUPPORTED_DEPENDENCY_KINDS,
    SUPPORTED_ENTITY_KINDS,
)

_ARITY_COMPARATORS = frozenset({"eq", "ne", "lt", "le", "gt", "ge"})


def _canonical_bytes(payload: object) -> bytes:
    return canonical_bytes(payload)


def _authority_digest(payload: object) -> str:
    """Recompute the authoritative signed digest (same formula, public
    constants only — no private imports)."""
    return hashlib.sha256(
        P0_SEMANTIC_REQUEST_DIGEST_DOMAIN.encode("utf-8")
        + b"\x00"
        + _canonical_bytes(payload)
    ).hexdigest()


@dataclass(frozen=True)
class CanonicalGraph:
    """Order-independent view of a supported semantic graph."""

    payload: dict[str, Any]              # authoritative payload, sans request_id
    request_id: str
    content_digest: str                   # semantic_input_digest
    op_ids: tuple[str, ...]               # sorted operation ids
    entity_ids: tuple[str, ...]            # sorted entity ids
    output_entity_ids: tuple[str, ...]     # sorted declared outputs


def content_digest_of(request: P0SemanticRequestV1) -> str:
    """Canonical semantic input identity.

    The graph's request_id is a request-scoped label; the semantic content
    identity covers the content fields only, so relabeling a request never
    changes the projection identity (mission 5).
    """
    payload = semantic_request_payload(request)
    content = {k: v for k, v in payload.items() if k != "request_id"}
    return domain_digest(
        "elpis.c2r6p0.semantic-input-canonical.v1", content
    )


def _reject(
    status: ProjectionStatus,
    code: ErrorCode,
    rule: str,
    detail: dict[str, Any],
    identity: str = "",
) -> ProjectionError:
    return ProjectionError(
        status=status.value,
        code=code.value,
        rule=rule,
        detail=detail,
        semantic_identity=identity,
    )


# ---------------------------------------------------------------------------
# Field-shape checks (directly constructed dataclasses may carry bad shapes)
# ---------------------------------------------------------------------------


def _check_field_shapes(payload: dict[str, Any]) -> ProjectionError | None:
    for key in ("entities", "operations", "constraints", "relations",
                "dependencies", "quantities"):
        items = payload.get(key)
        if not isinstance(items, list):
            return _reject(
                ProjectionStatus.INVALID_SEMANTIC_IR,
                ErrorCode.INVALID_SEMANTIC_IR,
                R.R_CONTRACT_ACCEPT,
                {"field": key, "reason": "not_a_list"},
            )
    for entity in payload["entities"]:
        for fname in ("entity_id", "kind", "identity"):
            if not isinstance(entity.get(fname), str) or not entity[fname]:
                return _reject(
                    ProjectionStatus.INVALID_SEMANTIC_IR,
                    ErrorCode.INVALID_SEMANTIC_IR,
                    R.R_CONTRACT_ACCEPT,
                    {"entity": entity.get("entity_id"), "field": fname},
                    str(entity.get("entity_id", "")),
                )
        if not isinstance(entity.get("data_type", ""), str):
            return _reject(
                ProjectionStatus.INVALID_SEMANTIC_IR,
                ErrorCode.INVALID_SEMANTIC_IR,
                R.R_CONTRACT_ACCEPT,
                {"entity": entity.get("entity_id"), "field": "data_type"},
                str(entity.get("entity_id", "")),
            )
    for op in payload["operations"]:
        if not isinstance(op.get("operation_id"), str) or not op["operation_id"]:
            return _reject(
                ProjectionStatus.INVALID_SEMANTIC_IR,
                ErrorCode.INVALID_SEMANTIC_IR,
                R.R_CONTRACT_ACCEPT,
                {"operation": str(op.get("operation_id", ""))},
            )
        if not isinstance(op.get("operator"), str) or not op["operator"]:
            return _reject(
                ProjectionStatus.INVALID_SEMANTIC_IR,
                ErrorCode.INVALID_SEMANTIC_IR,
                R.R_CONTRACT_ACCEPT,
                {"operation": op.get("operation_id"), "field": "operator"},
                str(op.get("operation_id", "")),
            )
        for fld in ("input_entity_ids", "output_entity_ids"):
            if not isinstance(op.get(fld), list):
                return _reject(
                    ProjectionStatus.INVALID_SEMANTIC_IR,
                    ErrorCode.INVALID_SEMANTIC_IR,
                    R.R_CONTRACT_ACCEPT,
                    {"operation": op.get("operation_id"), "field": fld},
                    str(op.get("operation_id", "")),
                )
            if any(not isinstance(x, str) for x in op[fld]):
                return _reject(
                    ProjectionStatus.INVALID_SEMANTIC_IR,
                    ErrorCode.INVALID_SEMANTIC_IR,
                    R.R_CONTRACT_ACCEPT,
                    {"operation": op.get("operation_id"),
                     "field": fld, "reason": "non_string_id"},
                    str(op.get("operation_id", "")),
                )
    outputs = payload.get("output_entity_ids")
    if not isinstance(outputs, list) or any(
        not isinstance(x, str) for x in outputs
    ):
        return _reject(
            ProjectionStatus.INVALID_SEMANTIC_IR,
            ErrorCode.INVALID_SEMANTIC_IR,
            R.R_CONTRACT_ACCEPT,
            {"field": "output_entity_ids", "reason": "malformed"},
        )
    return None


# ---------------------------------------------------------------------------
# Duplicate identity analysis (incompatible duplicates are classified before
# the authority's generic global-uniqueness rejection)
# ---------------------------------------------------------------------------


def _duplicate_incompatible_identity(
    payload: dict[str, Any]
) -> ProjectionError | None:
    """Same node id declared twice with differing attributes."""
    sections = (
        ("entities", "entity_id"),
        ("operations", "operation_id"),
        ("constraints", "constraint_id"),
        ("relations", "relation_id"),
        ("dependencies", "dependency_id"),
        ("quantities", "quantity_id"),
    )
    for section, id_field in sections:
        by_id: dict[str, dict[str, Any]] = {}
        for item in payload[section]:
            ident = item.get(id_field)
            if not isinstance(ident, str):
                continue
            if ident in by_id and by_id[ident] != item:
                return _reject(
                    ProjectionStatus.INVALID_SEMANTIC_IR,
                    ErrorCode.INVALID_SEMANTIC_IR,
                    R.R_DUPLICATE_ID,
                    {
                        "section": section,
                        "identity": ident,
                        "reason": "duplicate_incompatible_identity",
                        "first": by_id[ident],
                        "second": item,
                    },
                    ident,
                )
            by_id.setdefault(ident, item)
    return None


# ---------------------------------------------------------------------------
# Projector-level semantic checks (authority does not cover these)
# ---------------------------------------------------------------------------


def _check_supported_subset(
    payload: dict[str, Any]
) -> ProjectionError | None:
    entity_kinds = {
        e["entity_id"]: e["kind"] for e in payload["entities"]
    }
    for entity in payload["entities"]:
        if entity["kind"] not in SUPPORTED_ENTITY_KINDS:
            return _reject(
                ProjectionStatus.UNSUPPORTED_SEMANTIC_SHAPE,
                ErrorCode.UNSUPPORTED_SHAPE,
                R.R_UNSUPPORTED_KIND,
                {
                    "entity": entity["entity_id"],
                    "kind": entity["kind"],
                    "supported": sorted(SUPPORTED_ENTITY_KINDS),
                    "reason": "unsupported_entity_kind",
                },
                entity["entity_id"],
            )
    for dep in payload["dependencies"]:
        if dep["kind"] not in SUPPORTED_DEPENDENCY_KINDS:
            return _reject(
                ProjectionStatus.UNSUPPORTED_SEMANTIC_SHAPE,
                ErrorCode.UNSUPPORTED_SHAPE,
                R.R_UNSUPPORTED_KIND,
                {
                    "dependency": dep["dependency_id"],
                    "kind": dep["kind"],
                    "supported": sorted(SUPPORTED_DEPENDENCY_KINDS),
                    "reason": "unsupported_dependency_kind",
                },
                dep["dependency_id"],
            )
    # duplicate entity reference inside one operation (malformed shape)
    for op in payload["operations"]:
        for fld in ("input_entity_ids", "output_entity_ids"):
            ids = op[fld]
            if len(ids) != len(set(ids)):
                dup = sorted({x for x in ids if ids.count(x) > 1})
                return _reject(
                    ProjectionStatus.UNSUPPORTED_SEMANTIC_SHAPE,
                    ErrorCode.UNSUPPORTED_SHAPE,
                    R.R_UNSUPPORTED_KIND,
                    {
                        "operation": op["operation_id"],
                        "field": fld,
                        "duplicates": dup,
                        "reason": "duplicate_entity_reference",
                    },
                    op["operation_id"],
                )
    return None


def _producer_consumers(
    payload: dict[str, Any]
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    producers: dict[str, list[str]] = {}
    consumers: dict[str, list[str]] = {}
    for op in payload["operations"]:
        for e in op["output_entity_ids"]:
            producers.setdefault(e, []).append(op["operation_id"])
        for e in op["input_entity_ids"]:
            consumers.setdefault(e, []).append(op["operation_id"])
    for m in (producers, consumers):
        for k in m:
            m[k] = sorted(set(m[k]))
    return producers, consumers


def _check_references(
    payload: dict[str, Any],
) -> ProjectionError | None:
    """Dangling structural references the authority does not check."""
    producers, _ = _producer_consumers(payload)
    # declared outputs must have a producer (missing binding)
    for out in payload["output_entity_ids"]:
        if out not in producers:
            return _reject(
                ProjectionStatus.INVALID_SEMANTIC_IR,
                ErrorCode.INVALID_SEMANTIC_IR,
                R.R_DANGLING_REF,
                {
                    "entity": out,
                    "reason": "declared_output_without_producer",
                },
                out,
            )
    return None


def _check_relations(
    payload: dict[str, Any],
) -> ProjectionError | None:
    """Interface / route / state_feeds / mutates structural relations."""
    from .taxonomy import (
        INTERFACE_PREDICATE,
        MUTATES_PREDICATE,
        ROUTE_PREDICATE,
        STATE_FEEDS_PREDICATE,
    )

    op_ids = {o["operation_id"] for o in payload["operations"]}
    entity_ids = {e["entity_id"] for e in payload["entities"]}
    producers, _ = _producer_consumers(payload)

    interface_sources: dict[str, set[str]] = {}
    for rel in payload["relations"]:
        pred = rel["predicate"]
        src, tgt = rel["source_id"], rel["target_id"]
        rid = rel["relation_id"]
        if pred == ROUTE_PREDICATE:
            if src not in op_ids or tgt not in op_ids:
                return _reject(
                    ProjectionStatus.INVALID_SEMANTIC_IR,
                    ErrorCode.INVALID_SEMANTIC_IR,
                    R.R_ROUTE_DANGLING,
                    {
                        "relation": rid,
                        "source": src,
                        "target": tgt,
                        "reason": "route_endpoints_must_be_operations",
                    },
                    rid,
                )
            if src == tgt:
                return _reject(
                    ProjectionStatus.INVALID_SEMANTIC_IR,
                    ErrorCode.INVALID_SEMANTIC_IR,
                    R.R_ROUTE_DANGLING,
                    {
                        "relation": rid,
                        "source": src,
                        "reason": "route_self_endpoint",
                    },
                    rid,
                )
        elif pred == INTERFACE_PREDICATE:
            if tgt not in op_ids:
                return _reject(
                    ProjectionStatus.INVALID_SEMANTIC_IR,
                    ErrorCode.INVALID_SEMANTIC_IR,
                    R.R_AMBIGUOUS_INTERFACE,
                    {
                        "relation": rid,
                        "target": tgt,
                        "reason": "interface_must_target_operation",
                    },
                    rid,
                )
            if src not in entity_ids:
                return _reject(
                    ProjectionStatus.INVALID_SEMANTIC_IR,
                    ErrorCode.INVALID_SEMANTIC_IR,
                    R.R_AMBIGUOUS_INTERFACE,
                    {
                        "relation": rid,
                        "source": src,
                        "reason": "interface_source_must_be_entity",
                    },
                    rid,
                )
            interface_sources.setdefault(src, set()).add(tgt)
        elif pred == STATE_FEEDS_PREDICATE:
            if src not in op_ids or tgt not in op_ids:
                return _reject(
                    ProjectionStatus.INVALID_SEMANTIC_IR,
                    ErrorCode.INVALID_SEMANTIC_IR,
                    R.R_MEMORY_PLACE,
                    {
                        "relation": rid,
                        "reason": "state_feeds_endpoints_must_be_operations",
                    },
                    rid,
                )
            if src == tgt:
                # The 529 vocabulary has no self-span signature; the
                # supported subset rejects rather than under-represent.
                return _reject(
                    ProjectionStatus.UNSUPPORTED_SEMANTIC_SHAPE,
                    ErrorCode.UNSUPPORTED_SHAPE,
                    R.R_MEMORY_PLACE,
                    {
                        "relation": rid,
                        "source": src,
                        "reason": "state_feeds_self_recurrence_unexpressible",
                    },
                    rid,
                )
        elif pred == MUTATES_PREDICATE:
            if src not in op_ids:
                return _reject(
                    ProjectionStatus.INVALID_SEMANTIC_IR,
                    ErrorCode.INVALID_SEMANTIC_IR,
                    R.R_AMBIGUOUS_INTERFACE,
                    {
                        "relation": rid,
                        "source": src,
                        "reason": "mutates_source_must_be_operation",
                    },
                    rid,
                )
            if tgt not in entity_ids:
                return _reject(
                    ProjectionStatus.INVALID_SEMANTIC_IR,
                    ErrorCode.INVALID_SEMANTIC_IR,
                    R.R_AMBIGUOUS_INTERFACE,
                    {
                        "relation": rid,
                        "target": tgt,
                        "reason": "mutates_target_must_be_entity",
                    },
                    rid,
                )
            # state ownership must be unambiguous
            if len(producers.get(tgt, ())) > 1:
                return _reject(
                    ProjectionStatus.AMBIGUOUS_BINDING,
                    ErrorCode.AMBIGUOUS,
                    R.R_AMBIGUOUS_INTERFACE,
                    {
                        "relation": rid,
                        "entity": tgt,
                        "producers": producers[tgt],
                        "reason": "mutated_entity_has_multiple_producers",
                    },
                    tgt,
                )
    # ambiguous interface: one interface entity exposed by two operations
    for src, tgts in sorted(interface_sources.items()):
        if len(tgts) > 1:
            return _reject(
                ProjectionStatus.AMBIGUOUS_BINDING,
                ErrorCode.AMBIGUOUS,
                R.R_AMBIGUOUS_INTERFACE,
                {
                    "entity": src,
                    "targets": sorted(tgts),
                    "reason": "interface_entity_bound_to_multiple_operations",
                },
                src,
            )
    return None


def _compare_arity(comparator: str, actual: int, value: int) -> bool:
    if comparator == "eq":
        return actual == value
    if comparator == "ne":
        return actual != value
    if comparator == "lt":
        return actual < value
    if comparator == "le":
        return actual <= value
    if comparator == "gt":
        return actual > value
    if comparator == "ge":
        return actual >= value
    return False


def _check_contradictions(
    payload: dict[str, Any],
) -> ProjectionError | None:
    """Explicit facts that cannot simultaneously hold."""
    ops = {o["operation_id"]: o for o in payload["operations"]}
    # arity quantities vs declared arity
    for q in payload["quantities"]:
        if q["predicate"] not in QUANTITY_ARITY_PREDICATES:
            continue
        op = ops.get(q["subject_id"])
        if op is None:
            continue  # entity-subject arity quantities are data facts
        actual = (
            len(op["input_entity_ids"])
            if q["predicate"] == "input_arity"
            else len(op["output_entity_ids"])
        )
        if not _compare_arity(q["comparator"], actual, q["value"]):
            return _reject(
                ProjectionStatus.STRUCTURAL_CONTRADICTION,
                ErrorCode.CONTRADICTION,
                R.R_ARITY_VIOLATION,
                {
                    "quantity": q["quantity_id"],
                    "subject": q["subject_id"],
                    "predicate": q["predicate"],
                    "comparator": q["comparator"],
                    "declared": q["value"],
                    "actual": actual,
                    "reason": "arity_fact_violated",
                },
                q["quantity_id"],
            )
    # contradictory hard constraint pairs
    by_key: dict[tuple, dict[str, Any]] = {}
    for c in payload["constraints"]:
        if not c["hard"]:
            continue
        key = (c["subject_id"], c["predicate"], c["object_id"])
        other = by_key.get(key)
        if other is not None and other["negated"] != c["negated"]:
            return _reject(
                ProjectionStatus.STRUCTURAL_CONTRADICTION,
                ErrorCode.CONTRADICTION,
                R.R_CONSTRAINT_CONTRA,
                {
                    "constraints": sorted(
                        [other["constraint_id"], c["constraint_id"]]
                    ),
                    "key": {"subject": key[0], "predicate": key[1],
                             "object": key[2]},
                    "reason": "opposing_hard_constraints",
                },
                c["constraint_id"],
            )
        by_key.setdefault(key, c)
    return None


def _schedule_dag_edges(
    payload: dict[str, Any],
) -> list[tuple[str, str, int]]:
    """Schedule DAG edges: (src, dst, min_rank_gap).

    precedes: gap 1. route (S->T): value crosses S's lane to T's, so T must
    sit at least two ranks below S's consumer... the CROSS_LANE_ROUTE
    invariant needs a ROUTE locus strictly between producer and consumer
    ranks: gap 2. state_feeds (A->B): MEMORY_SPAN needs a MEMORY locus in
    A's lane between the ranks: gap 2.
    """
    from .taxonomy import (
        ROUTE_PREDICATE,
        STATE_FEEDS_PREDICATE,
    )

    edges: list[tuple[str, str, int]] = []
    for dep in payload["dependencies"]:
        edges.append(
            (dep["predecessor_operation_id"],
             dep["successor_operation_id"], 1)
        )
    for rel in payload["relations"]:
        if rel["predicate"] == ROUTE_PREDICATE:
            edges.append((rel["source_id"], rel["target_id"], 2))
        elif rel["predicate"] == STATE_FEEDS_PREDICATE:
            edges.append((rel["source_id"], rel["target_id"], 2))
    return edges


def _check_schedule_acyclic(
    payload: dict[str, Any],
) -> ProjectionError | None:
    """A cycle in the schedule DAG means explicit facts cannot hold in one
    grid (e.g. A precedes B plus B state_feeds A)."""
    ops = {o["operation_id"] for o in payload["operations"]}
    edges = [(s, d) for s, d, _ in _schedule_dag_edges(payload)]
    indeg = {op: 0 for op in ops}
    out: dict[str, list[str]] = {op: [] for op in ops}
    seen_pairs: set[tuple[str, str]] = set()
    for s, d in edges:
        if (s, d) in seen_pairs:
            continue
        seen_pairs.add((s, d))
        out[s].append(d)
        indeg[d] += 1
    ready = sorted(op for op in ops if indeg[op] == 0)
    visited = 0
    while ready:
        node = ready.pop(0)
        visited += 1
        for t in out[node]:
            indeg[t] -= 1
            if indeg[t] == 0:
                ready.append(t)
        ready.sort()
    if visited != len(ops):
        cyclic = sorted(op for op in ops if indeg[op] > 0)
        return _reject(
            ProjectionStatus.STRUCTURAL_CONTRADICTION,
            ErrorCode.CONTRADICTION,
            R.R_CYCLE_REJECT,
            {
                "operations": cyclic,
                "reason": "schedule_dag_cycle",
            },
            ",".join(cyclic),
        )
    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def canonicalize(
    request: P0SemanticRequestV1,
    ruleset: Ruleset,
) -> tuple[CanonicalGraph | None, ProjectionError | None]:
    """Canonicalize a semantic graph. Returns (graph, None) or (None, error)."""
    # 1) canonical payload + field-shape checks (a directly constructed
    #    dataclass may carry bad field types the authority would not)
    payload = semantic_request_payload(request)
    err = _check_field_shapes(payload)
    if err is not None:
        return None, err

    # 2) incompatible duplicate identities (classified before authority)
    err = _duplicate_incompatible_identity(payload)
    if err is not None:
        return None, err

    # 3) authoritative validation (schema, ids, references, uniqueness,
    #    dependency acyclicity, digest)
    try:
        request.validate()
    except P0SemanticRequestContractError as exc:
        detail = {"authority_message": str(exc)}
        msg = str(exc)
        if "acyclic" in msg:
            detail = {
                "reason": "dependency_cycle",
                "detail": "a dependency cycle is not a legitimate state "
                          "recurrence; state recurrence is represented by "
                          "state_feeds relations",
            }
            rule = R.R_CYCLE_REJECT
        elif "globally unique" in msg:
            detail = {"reason": "duplicate_identity"}
            rule = R.R_DUPLICATE_ID
        elif "unknown" in msg or "dangling" in msg:
            detail = {"reason": "dangling_reference", "message": msg}
            rule = R.R_DANGLING_REF
        else:
            rule = R.R_CONTRACT_ACCEPT
        return None, _reject(
            ProjectionStatus.INVALID_SEMANTIC_IR,
            ErrorCode.INVALID_SEMANTIC_IR,
            rule,
            detail,
        )
    except Exception as exc:  # malformed field types surface here
        return None, _reject(
            ProjectionStatus.INVALID_SEMANTIC_IR,
            ErrorCode.INVALID_SEMANTIC_IR,
            R.R_CONTRACT_ACCEPT,
            {"reason": "authority_validation_error",
             "message": str(exc)},
        )

    # 4) projector-level supported-subset + reference + relation checks
    for checker in (
        _check_supported_subset,
        _check_references,
        _check_relations,
        _check_contradictions,
        _check_schedule_acyclic,
    ):
        err = checker(payload)
        if err is not None:
            return None, err

    # 5) canonical graph view
    #    output_entity_ids is a SET of declared outputs: declaration order
    #    is not semantic, so the canonical content sorts it (the authority
    #    payload keeps declaration order; canonicalization is the
    #    projector's job, mission 8).
    content = {k: v for k, v in payload.items() if k != "request_id"}
    content["output_entity_ids"] = sorted(payload["output_entity_ids"])
    digest = domain_digest(
        "elpis.c2r6p0.semantic-input-canonical.v1", content
    )
    graph = CanonicalGraph(
        payload=content,
        request_id=request.request_id,
        content_digest=digest,
        op_ids=tuple(sorted(
            o["operation_id"] for o in payload["operations"]
        )),
        entity_ids=tuple(sorted(
            e["entity_id"] for e in payload["entities"]
        )),
        output_entity_ids=tuple(sorted(payload["output_entity_ids"])),
    )
    return graph, None
