"""C2R6-P0 projector contracts: input wrapper, result, bindings, trace.

These types define the public surface of the deterministic Semantic-IR to
Grid81 projector. The projector is a pure function of (explicit semantic
input, pinned rules). Request/debug identifiers are carried by the wrapper
but never enter the canonical semantic digest or the structural
fingerprint.

Authority reuse (no redefinition):
  * BasisToken, P0SemanticRequestV1, semantic IR dataclasses  -> elpis_p0
  * LaneBindingV1, StructuralInvariantV1, StructuralSchemaV1,
    residual, is_resolved, materialisable, validate_transition,
    DecompositionRequired                                   -> elpis_p0.structural_residual
    (frozen C2R7-C source copy)
  * FEATURE_WIDTH (529), VOCABULARY_DIGEST, encode_constraint_state
    -> structural_trm_features (C2R7-C probe)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ..elpis_p0.contracts import BasisToken
from ..elpis_p0.semantic_ir import P0SemanticRequestV1
from ..elpis_p0.structural_residual import (
    GRID_SIZE,
    LaneBindingV1,
    StructuralInvariantV1,
    StructuralSchemaV1,
)

# ---------------------------------------------------------------------------
# Canonical helpers (local; identical formula to authority _canonical_bytes)
# ---------------------------------------------------------------------------

C2R6P0_SCHEMA_VERSION = "c2r6p0.projection.v1"
SEMANTIC_CANONICAL_DOMAIN = "elpis.c2r6p0.semantic-input-canonical.v1"
FINGERPRINT_DOMAIN = "elpis.c2r6p0.structural-input-fingerprint.v1"
PROJECTION_DOMAIN = "elpis.c2r6p0.projection-result.v1"
TRACE_DOMAIN = "elpis.c2r6p0.projection-trace.v1"
RULESET_DOMAIN = "elpis.c2r6p0.ruleset.v1"


def canonical_bytes(obj: Any) -> bytes:
    """Canonical JSON: sorted keys, compact separators, no NaN."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def domain_digest(domain: str, payload: Any) -> str:
    return sha256_hex(domain.encode("utf-8") + b"\x00" + canonical_bytes(payload))


def grid_digest(grid: tuple[int, ...]) -> str:
    """Running structural digest used by trace events.

    Same payload shape as elpis_fractal_spine.structural_refinement's
    private _compute_grid_digest so the two stay comparable.
    """
    return sha256_hex(canonical_bytes({"grid81": list(grid)}))


# ---------------------------------------------------------------------------
# Statuses and errors (typed; no free-form exceptions at the API boundary)
# ---------------------------------------------------------------------------


class ProjectionStatus(str, Enum):
    PROJECTED = "PROJECTED"
    INVALID_SEMANTIC_IR = "INVALID_SEMANTIC_IR"
    UNSUPPORTED_SEMANTIC_SHAPE = "UNSUPPORTED_SEMANTIC_SHAPE"
    DECOMPOSITION_REQUIRED = "DECOMPOSITION_REQUIRED"
    AMBIGUOUS_BINDING = "AMBIGUOUS_BINDING"
    STRUCTURAL_CONTRADICTION = "STRUCTURAL_CONTRADICTION"


class ErrorCode(str, Enum):
    """Centralized error codes. Each carries a rule identifier."""

    OK = "OK"
    INVALID_SEMANTIC_IR = "ERR.INVALID_SEMANTIC_IR"
    UNSUPPORTED_SHAPE = "ERR.UNSUPPORTED_SEMANTIC_SHAPE"
    DECOMPOSITION = "ERR.DECOMPOSITION_REQUIRED"
    AMBIGUOUS = "ERR.AMBIGUOUS_BINDING"
    CONTRADICTION = "ERR.STRUCTURAL_CONTRADICTION"


@dataclass(frozen=True)
class ProjectionError:
    """Deterministic typed rejection detail. No exception reprs."""

    status: str
    code: str
    rule: str
    detail: dict[str, Any]
    semantic_identity: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "code": self.code,
            "rule": self.rule,
            "detail": self.detail,
            "semantic_identity": self.semantic_identity,
        }


# ---------------------------------------------------------------------------
# Supported-subset taxonomy lives in c2r6p0.taxonomy (single source).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ProjectionInputV1 — canonical experimental wrapper around Semantic IR
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectionInputV1:
    """Explicit semantic input to the projector.

    ``request_id`` and ``debug_tag`` are request/debug identifiers: they must
    not affect projection identity (mission 5). The semantic graph must
    contain only explicit semantic facts already represented by the
    authoritative Semantic IR types.
    """

    schema: str = "c2r6p0.projection-input.v1"
    semantic_graph: P0SemanticRequestV1 = field(default=None)  # type: ignore[assignment]
    request_id: str = ""
    debug_tag: str = ""

    def __post_init__(self) -> None:
        if self.schema != "c2r6p0.projection-input.v1":
            raise ValueError(f"unsupported ProjectionInputV1 schema {self.schema!r}")
        if not isinstance(self.semantic_graph, P0SemanticRequestV1):
            raise ValueError("semantic_graph must be a P0SemanticRequestV1")
        for name in ("request_id", "debug_tag"):
            value = getattr(self, name)
            if not isinstance(value, str) or "\x00" in value or len(value) > 128:
                raise ValueError(f"{name} must be a short NUL-free string")

    @staticmethod
    def from_signed(
        graph: P0SemanticRequestV1,
        request_id: str = "",
        debug_tag: str = "",
    ) -> "ProjectionInputV1":
        """Wrap an already-signed (digest-bearing) semantic graph."""
        return ProjectionInputV1(
            semantic_graph=graph,
            request_id=request_id,
            debug_tag=debug_tag,
        )


# ---------------------------------------------------------------------------
# StructuralBindingV1 — the semantic sidecar (identity authority)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OpBinding:
    """One structural lane bound to one explicit semantic operation."""

    binding_id: str
    semantic_id: str            # operation_id — the identity authority
    semantic_kind: str           # "operation"
    operator: str
    input_entity_ids: tuple[str, ...]
    output_entity_ids: tuple[str, ...]
    lane: int
    rank: int
    cell: int
    token: int                    # BasisToken int (INPUT/TRANSFORM/OUTPUT)
    frozen: bool                  # True => the locus is a frozen fact
    data_types: tuple[tuple[str, str], ...] = ()  # (entity_id, data_type) of declared outputs


@dataclass(frozen=True)
class EntityBinding:
    """One explicit semantic entity preserved by projection."""

    binding_id: str
    semantic_id: str
    semantic_kind: str           # the entity's declared kind
    identity: str
    data_type: str
    producer_ops: tuple[str, ...]
    consumer_ops: tuple[str, ...]
    declared_output: bool


@dataclass(frozen=True)
class EdgeBinding:
    """One explicit semantic relation/dependency/constraint/quantity.

    ``structural_kind`` records how the fact was compiled:
      * dependency: "precedes" | "state_feeds"
      * constraint: "CONSTRAINT_AFTER" | "preserved"
      * relation: the predicate (route/interface/mutates/preserved)
      * quantity: the predicate ("arity_checked" | "preserved")
    ``lanes`` are the structural loci the fact maps to (empty when the fact
    is preserved without structural effect). ``discharged`` says whether the
    associated invariant is satisfied by the seed.
    """

    binding_id: str
    semantic_id: str
    semantic_kind: str            # "dependency" | "constraint" | "relation" | "quantity"
    structural_kind: str
    lanes: tuple[int, ...]
    discharged: bool
    payload: dict[str, Any]        # canonical-JSON-able explicit fields


@dataclass(frozen=True)
class StructuralBindingV1:
    """The complete semantic sidecar of a projection."""

    op_bindings: tuple[OpBinding, ...]
    entity_bindings: tuple[EntityBinding, ...]
    edge_bindings: tuple[EdgeBinding, ...]
    output_entity_ids: tuple[str, ...]

    def op_by_semantic_id(self) -> dict[str, OpBinding]:
        return {b.semantic_id: b for b in self.op_bindings}

    def entity_by_semantic_id(self) -> dict[str, EntityBinding]:
        return {b.semantic_id: b for b in self.entity_bindings}


def binding_payload(b: StructuralBindingV1) -> dict[str, Any]:
    """Canonical binding payload (fingerprint scope)."""
    return {
        "op_bindings": [
            {
                "semantic_id": x.semantic_id,
                "semantic_kind": x.semantic_kind,
                "operator": x.operator,
                "input_entity_ids": list(x.input_entity_ids),
                "output_entity_ids": list(x.output_entity_ids),
                "lane": x.lane,
                "rank": x.rank,
                "cell": x.cell,
                "token": x.token,
                "frozen": x.frozen,
                "data_types": [list(t) for t in x.data_types],
            }
            for x in sorted(b.op_bindings, key=lambda x: x.semantic_id)
        ],
        "entity_bindings": [
            {
                "semantic_id": x.semantic_id,
                "semantic_kind": x.semantic_kind,
                "identity": x.identity,
                "data_type": x.data_type,
                "producer_ops": list(x.producer_ops),
                "consumer_ops": list(x.consumer_ops),
                "declared_output": x.declared_output,
            }
            for x in sorted(b.entity_bindings, key=lambda x: x.semantic_id)
        ],
        "edge_bindings": [
            {
                "semantic_id": x.semantic_id,
                "semantic_kind": x.semantic_kind,
                "structural_kind": x.structural_kind,
                "lanes": list(x.lanes),
                "discharged": x.discharged,
                "payload": x.payload,
            }
            for x in sorted(b.edge_bindings, key=lambda x: x.semantic_id)
        ],
        "output_entity_ids": sorted(b.output_entity_ids),
    }


# ---------------------------------------------------------------------------
# ProjectionTraceV1 — proof-carrying deterministic derivation trace
# ---------------------------------------------------------------------------

# Event types (mission 7). Centralized here.
EV_SEMANTIC_NODE_ACCEPTED = "SEMANTIC_NODE_ACCEPTED"
EV_DEPENDENCY_ACCEPTED = "DEPENDENCY_ACCEPTED"
EV_TYPE_RELATION_ACCEPTED = "TYPE_RELATION_ACCEPTED"
EV_LANE_ASSIGNED = "LANE_ASSIGNED"
EV_ROLE_PLACED = "ROLE_PLACED"
EV_ROUTE_INSERTED = "ROUTE_INSERTED"
EV_MEMORY_RELATION_ENCODED = "MEMORY_RELATION_ENCODED"
EV_CONSTRAINT_ENCODED = "CONSTRAINT_ENCODED"
EV_INTERFACE_ENCODED = "INTERFACE_ENCODED"
EV_FROZEN_LOCUS_DECLARED = "FROZEN_LOCUS_DECLARED"
EV_WRITABLE_LOCUS_DECLARED = "WRITABLE_LOCUS_DECLARED"
EV_DECLARED_FEATURE_DERIVED = "DECLARED_FEATURE_DERIVED"
EV_ACTIVE_RESIDUAL_DERIVED = "ACTIVE_RESIDUAL_DERIVED"
EV_DECOMPOSITION_REQUIRED = "DECOMPOSITION_REQUIRED"
EV_UNRESOLVED_LOCUS_DECLARED = "UNRESOLVED_LOCUS_DECLARED"
EV_REJECTION = "REJECTION"


@dataclass(frozen=True)
class ProjectionTraceEvent:
    seq: int
    event_type: str
    rule_id: str
    semantic_ids: tuple[str, ...]
    loci: tuple[int, ...]
    before_digest: str
    after_digest: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "event_type": self.event_type,
            "rule_id": self.rule_id,
            "semantic_ids": list(self.semantic_ids),
            "loci": list(self.loci),
            "before_digest": self.before_digest,
            "after_digest": self.after_digest,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ProjectionTraceV1:
    schema: str
    events: tuple[ProjectionTraceEvent, ...]
    trace_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "events": [e.to_dict() for e in self.events],
            "trace_digest": self.trace_digest,
        }

    def to_canonical_bytes(self) -> bytes:
        """Canonical byte form (mission 7: the trace must be canonically
        serializable and hashable). Identical traces -> identical bytes."""
        return canonical_bytes(self.to_dict())


# ---------------------------------------------------------------------------
# ProjectionResultV1
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectionResultV1:
    schema: str
    status: str
    # identity
    semantic_input_digest: str
    rule_set_digest: str
    # structural state
    grid81: tuple[int, ...]
    frozen_mask: tuple[int, ...]
    writable_mask: tuple[int, ...]
    bindings: StructuralBindingV1
    invariants: tuple[StructuralInvariantV1, ...]
    lane_bindings: tuple[LaneBindingV1, ...]
    # residual side (authoritative C2R7-C machinery)
    declared_features: tuple[int, ...]
    active_residual: tuple[int, ...]
    residual_ids: tuple[str, ...]
    # digests
    structural_input_fingerprint: str
    structural_schema: StructuralSchemaV1 | None
    trace: ProjectionTraceV1
    projection_digest: str
    error: ProjectionError | None = None
    # capacity record (always present; meaningful on PROJECTED/DECOMPOSITION)
    capacity: dict[str, int] | None = None

    def is_projected(self) -> bool:
        return self.status == ProjectionStatus.PROJECTED.value

    def to_dict(self) -> dict[str, Any]:
        schema = self.structural_schema
        return {
            "schema": self.schema,
            "status": self.status,
            "semantic_input_digest": self.semantic_input_digest,
            "rule_set_digest": self.rule_set_digest,
            "grid81": list(self.grid81),
            "frozen_mask": list(self.frozen_mask),
            "writable_mask": list(self.writable_mask),
            "bindings": binding_payload(self.bindings),
            "invariants": [
                {
                    "invariant_id": i.invariant_id,
                    "kind": i.kind,
                    "lanes": list(i.lanes),
                }
                for i in self.invariants
            ],
            "lane_bindings": [
                {
                    "lane": b.lane,
                    "semantic_id": b.semantic_id,
                    "role": b.role,
                    "operational_token": b.operational_token,
                }
                for b in self.lane_bindings
            ],
            "declared_features": list(self.declared_features),
            "active_residual": list(self.active_residual),
            "residual_ids": list(self.residual_ids),
            "structural_input_fingerprint": self.structural_input_fingerprint,
            "structural_schema_digest": (
                schema.schema_digest if schema is not None else ""
            ),
            "trace": self.trace.to_dict(),
            "projection_digest": self.projection_digest,
            "error": self.error.to_dict() if self.error is not None else None,
            "capacity": self.capacity,
        }

    def to_canonical_bytes(self) -> bytes:
        return canonical_bytes(self.to_dict())


def result_digest_payload(result: "ProjectionResultV1") -> dict[str, Any]:
    """Canonical payload bound by projection_digest (everything but itself)."""
    d = result.to_dict()
    d.pop("projection_digest", None)
    return d
