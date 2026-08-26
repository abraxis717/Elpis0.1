"""Canonical relational semantic request graph for P0.

C2R7-A establishes an explicit task-representation contract independent of
Grid81. It does not parse natural language and does not map the graph into the
81-cell control lattice. The legacy keyword projector must reject a context
carrying this graph until an explicit binding gate is qualified.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Iterable

P0_SEMANTIC_REQUEST_SCHEMA = "elpis.p0.semantic-request-graph.v1"
P0_SEMANTIC_REQUEST_DIGEST_DOMAIN = (
    "elpis.p0.semantic-request-graph.c2r7a.v1"
)

_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
_COMPARATORS = frozenset({"eq", "ne", "lt", "le", "gt", "ge"})


class P0SemanticRequestContractError(ValueError):
    pass


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(payload: object) -> str:
    return hashlib.sha256(
        P0_SEMANTIC_REQUEST_DIGEST_DOMAIN.encode("utf-8")
        + b"\x00"
        + _canonical_bytes(payload)
    ).hexdigest()


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise P0SemanticRequestContractError(
            f"{name} must be a non-empty string"
        )
    if value != value.strip():
        raise P0SemanticRequestContractError(
            f"{name} must not contain leading/trailing whitespace"
        )
    if "\x00" in value:
        raise P0SemanticRequestContractError(
            f"{name} must not contain NUL"
        )


def _require_id(name: str, value: str) -> None:
    _require_text(name, value)
    if _ID.fullmatch(value) is None:
        raise P0SemanticRequestContractError(
            f"{name} is not a canonical semantic identifier"
        )


@dataclass(frozen=True, slots=True)
class SemanticEntityV1:
    entity_id: str
    kind: str
    identity: str
    data_type: str = ""


@dataclass(frozen=True, slots=True)
class SemanticOperationV1:
    operation_id: str
    operator: str
    input_entity_ids: tuple[str, ...] = ()
    output_entity_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticConstraintV1:
    constraint_id: str
    predicate: str
    subject_id: str
    object_id: str = ""
    negated: bool = False
    hard: bool = True


@dataclass(frozen=True, slots=True)
class SemanticRelationV1:
    relation_id: str
    source_id: str
    predicate: str
    target_id: str
    negated: bool = False


@dataclass(frozen=True, slots=True)
class SemanticDependencyV1:
    dependency_id: str
    predecessor_operation_id: str
    successor_operation_id: str
    kind: str = "precedes"


@dataclass(frozen=True, slots=True)
class SemanticQuantityV1:
    quantity_id: str
    subject_id: str
    predicate: str
    comparator: str
    value: int
    unit: str = ""


@dataclass(frozen=True, slots=True)
class P0SemanticRequestV1:
    request_id: str
    entities: tuple[SemanticEntityV1, ...]
    operations: tuple[SemanticOperationV1, ...]
    constraints: tuple[SemanticConstraintV1, ...] = ()
    relations: tuple[SemanticRelationV1, ...] = ()
    dependencies: tuple[SemanticDependencyV1, ...] = ()
    quantities: tuple[SemanticQuantityV1, ...] = ()
    output_entity_ids: tuple[str, ...] = ()
    schema: str = P0_SEMANTIC_REQUEST_SCHEMA
    digest: str = ""

    def validate(self) -> None:
        _validate_request(self)
        expected = _digest(semantic_request_payload(self))
        if self.digest != expected:
            raise P0SemanticRequestContractError(
                "semantic request digest mismatch"
            )


def _sorted_by_id(values: Iterable[object], attr: str) -> list[object]:
    return sorted(values, key=lambda value: getattr(value, attr))


def semantic_request_payload(
    request: P0SemanticRequestV1,
) -> dict[str, object]:
    return {
        "schema": request.schema,
        "request_id": request.request_id,
        "entities": [
            {
                "entity_id": item.entity_id,
                "kind": item.kind,
                "identity": item.identity,
                "data_type": item.data_type,
            }
            for item in _sorted_by_id(request.entities, "entity_id")
        ],
        "operations": [
            {
                "operation_id": item.operation_id,
                "operator": item.operator,
                "input_entity_ids": list(item.input_entity_ids),
                "output_entity_ids": list(item.output_entity_ids),
            }
            for item in _sorted_by_id(
                request.operations, "operation_id"
            )
        ],
        "constraints": [
            {
                "constraint_id": item.constraint_id,
                "predicate": item.predicate,
                "subject_id": item.subject_id,
                "object_id": item.object_id,
                "negated": item.negated,
                "hard": item.hard,
            }
            for item in _sorted_by_id(
                request.constraints, "constraint_id"
            )
        ],
        "relations": [
            {
                "relation_id": item.relation_id,
                "source_id": item.source_id,
                "predicate": item.predicate,
                "target_id": item.target_id,
                "negated": item.negated,
            }
            for item in _sorted_by_id(
                request.relations, "relation_id"
            )
        ],
        "dependencies": [
            {
                "dependency_id": item.dependency_id,
                "predecessor_operation_id": (
                    item.predecessor_operation_id
                ),
                "successor_operation_id": (
                    item.successor_operation_id
                ),
                "kind": item.kind,
            }
            for item in _sorted_by_id(
                request.dependencies, "dependency_id"
            )
        ],
        "quantities": [
            {
                "quantity_id": item.quantity_id,
                "subject_id": item.subject_id,
                "predicate": item.predicate,
                "comparator": item.comparator,
                "value": item.value,
                "unit": item.unit,
            }
            for item in _sorted_by_id(
                request.quantities, "quantity_id"
            )
        ],
        "output_entity_ids": list(request.output_entity_ids),
    }


def build_semantic_request_v1(
    *,
    request_id: str,
    entities: tuple[SemanticEntityV1, ...],
    operations: tuple[SemanticOperationV1, ...],
    constraints: tuple[SemanticConstraintV1, ...] = (),
    relations: tuple[SemanticRelationV1, ...] = (),
    dependencies: tuple[SemanticDependencyV1, ...] = (),
    quantities: tuple[SemanticQuantityV1, ...] = (),
    output_entity_ids: tuple[str, ...] = (),
) -> P0SemanticRequestV1:
    unsigned = P0SemanticRequestV1(
        request_id=request_id,
        entities=entities,
        operations=operations,
        constraints=constraints,
        relations=relations,
        dependencies=dependencies,
        quantities=quantities,
        output_entity_ids=output_entity_ids,
    )
    _validate_request(unsigned)
    request = P0SemanticRequestV1(
        request_id=unsigned.request_id,
        entities=unsigned.entities,
        operations=unsigned.operations,
        constraints=unsigned.constraints,
        relations=unsigned.relations,
        dependencies=unsigned.dependencies,
        quantities=unsigned.quantities,
        output_entity_ids=unsigned.output_entity_ids,
        schema=unsigned.schema,
        digest=_digest(semantic_request_payload(unsigned)),
    )
    request.validate()
    return request


def _validate_request(request: P0SemanticRequestV1) -> None:
    if request.schema != P0_SEMANTIC_REQUEST_SCHEMA:
        raise P0SemanticRequestContractError(
            "semantic request schema mismatch"
        )
    _require_id("request_id", request.request_id)
    if not request.operations:
        raise P0SemanticRequestContractError(
            "semantic request requires at least one operation"
        )

    all_ids: list[str] = []

    for item in request.entities:
        _require_id("entity_id", item.entity_id)
        _require_text("entity.kind", item.kind)
        _require_text("entity.identity", item.identity)
        if item.data_type:
            _require_text("entity.data_type", item.data_type)
        all_ids.append(item.entity_id)

    entity_ids = {item.entity_id for item in request.entities}

    for item in request.operations:
        _require_id("operation_id", item.operation_id)
        _require_text("operation.operator", item.operator)
        for entity_id in (
            item.input_entity_ids + item.output_entity_ids
        ):
            _require_id("operation.entity_id", entity_id)
            if entity_id not in entity_ids:
                raise P0SemanticRequestContractError(
                    "operation references unknown entity"
                )
        all_ids.append(item.operation_id)

    operation_ids = {
        item.operation_id for item in request.operations
    }

    for item in request.constraints:
        _require_id("constraint_id", item.constraint_id)
        _require_text("constraint.predicate", item.predicate)
        _require_id("constraint.subject_id", item.subject_id)
        if not isinstance(item.negated, bool):
            raise P0SemanticRequestContractError(
                "constraint.negated must be bool"
            )
        if not isinstance(item.hard, bool):
            raise P0SemanticRequestContractError(
                "constraint.hard must be bool"
            )
        if item.object_id:
            _require_id("constraint.object_id", item.object_id)
        all_ids.append(item.constraint_id)

    for item in request.quantities:
        _require_id("quantity_id", item.quantity_id)
        _require_id("quantity.subject_id", item.subject_id)
        _require_text("quantity.predicate", item.predicate)
        if item.comparator not in _COMPARATORS:
            raise P0SemanticRequestContractError(
                "quantity comparator is unsupported"
            )
        if isinstance(item.value, bool) or not isinstance(
            item.value, int
        ):
            raise P0SemanticRequestContractError(
                "quantity value must be int"
            )
        if item.unit:
            _require_text("quantity.unit", item.unit)
        all_ids.append(item.quantity_id)

    if len(all_ids) != len(set(all_ids)):
        raise P0SemanticRequestContractError(
            "semantic node identifiers must be globally unique"
        )

    node_ids = set(all_ids)

    for item in request.constraints:
        if item.subject_id not in node_ids:
            raise P0SemanticRequestContractError(
                "constraint subject is unknown"
            )
        if item.object_id and item.object_id not in node_ids:
            raise P0SemanticRequestContractError(
                "constraint object is unknown"
            )
        if item.subject_id == item.constraint_id:
            raise P0SemanticRequestContractError(
                "constraint cannot target itself"
            )
        if item.object_id == item.constraint_id:
            raise P0SemanticRequestContractError(
                "constraint cannot target itself"
            )

    for item in request.quantities:
        if item.subject_id not in (
            entity_ids | operation_ids
        ):
            raise P0SemanticRequestContractError(
                "quantity subject must be entity or operation"
            )

    edge_ids: list[str] = []

    relation_keys: set[tuple[str, str, str, bool]] = set()
    for item in request.relations:
        _require_id("relation_id", item.relation_id)
        _require_id("relation.source_id", item.source_id)
        _require_text("relation.predicate", item.predicate)
        _require_id("relation.target_id", item.target_id)
        if not isinstance(item.negated, bool):
            raise P0SemanticRequestContractError(
                "relation.negated must be bool"
            )
        if item.source_id not in node_ids:
            raise P0SemanticRequestContractError(
                "relation source is unknown"
            )
        if item.target_id not in node_ids:
            raise P0SemanticRequestContractError(
                "relation target is unknown"
            )
        key = (
            item.source_id,
            item.predicate,
            item.target_id,
            item.negated,
        )
        if key in relation_keys:
            raise P0SemanticRequestContractError(
                "duplicate semantic relation"
            )
        relation_keys.add(key)
        edge_ids.append(item.relation_id)

    dependency_pairs: set[tuple[str, str, str]] = set()
    for item in request.dependencies:
        _require_id("dependency_id", item.dependency_id)
        _require_id(
            "dependency.predecessor_operation_id",
            item.predecessor_operation_id,
        )
        _require_id(
            "dependency.successor_operation_id",
            item.successor_operation_id,
        )
        _require_text("dependency.kind", item.kind)
        if item.predecessor_operation_id not in operation_ids:
            raise P0SemanticRequestContractError(
                "dependency predecessor is unknown"
            )
        if item.successor_operation_id not in operation_ids:
            raise P0SemanticRequestContractError(
                "dependency successor is unknown"
            )
        if (
            item.predecessor_operation_id
            == item.successor_operation_id
        ):
            raise P0SemanticRequestContractError(
                "dependency cannot self-loop"
            )
        key = (
            item.predecessor_operation_id,
            item.successor_operation_id,
            item.kind,
        )
        if key in dependency_pairs:
            raise P0SemanticRequestContractError(
                "duplicate semantic dependency"
            )
        dependency_pairs.add(key)
        edge_ids.append(item.dependency_id)

    if len(edge_ids) != len(set(edge_ids)):
        raise P0SemanticRequestContractError(
            "semantic edge identifiers must be unique"
        )
    if set(edge_ids) & node_ids:
        raise P0SemanticRequestContractError(
            "semantic node and edge identifiers must be disjoint"
        )

    for entity_id in request.output_entity_ids:
        _require_id("output_entity_id", entity_id)
        if entity_id not in entity_ids:
            raise P0SemanticRequestContractError(
                "output entity is unknown"
            )
    if len(request.output_entity_ids) != len(
        set(request.output_entity_ids)
    ):
        raise P0SemanticRequestContractError(
            "output entity ids must be unique"
        )

    _validate_dependency_dag(
        operation_ids,
        request.dependencies,
    )


def _validate_dependency_dag(
    operation_ids: set[str],
    dependencies: tuple[SemanticDependencyV1, ...],
) -> None:
    outgoing = {node: set() for node in operation_ids}
    indegree = {node: 0 for node in operation_ids}
    for item in dependencies:
        before = item.predecessor_operation_id
        after = item.successor_operation_id
        if after not in outgoing[before]:
            outgoing[before].add(after)
            indegree[after] += 1

    ready = sorted(
        node for node, degree in indegree.items() if degree == 0
    )
    visited = 0
    while ready:
        node = ready.pop(0)
        visited += 1
        for target in sorted(outgoing[node]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort()

    if visited != len(operation_ids):
        raise P0SemanticRequestContractError(
            "semantic dependency graph must be acyclic"
        )
