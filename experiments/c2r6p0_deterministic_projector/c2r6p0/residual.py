"""Residual derivation (R16), masks (R14), fingerprint (R17), skeleton (R19).

The residual and declared feature vectors are computed by the authoritative
C2R7-C machinery only — this module adds no second residual calculator:

  * residual(grid, invariants)          -> unsatisfied invariant ids
  * encode_constraint_state(...)        -> (declared529, active529)

The active residual vector is the authoritative encoding of exactly the
unsatisfied invariant set; declared features are the authoritative encoding
of the full declared invariant set. Width 529 and the vocabulary identity
come from structural_trm_features (VOCABULARY_DIGEST checked at ruleset
load).

Masks: frozen_mask and writable_mask are complementary over the 81 cells.
  frozen   = loci whose token is an explicit semantic fact or a determined
             structural rule fact (terminal RESOLUTION).
  writable = the remaining cells — the refiner's search space.
The terminal control cell is frozen (authority: StructuralSchemaV1.validate
requires writable_mask[80] == 0).

structural_input_fingerprint: SHA-256 over canonical bytes covering exactly
the projected structural state relevant to refinement: grid, masks,
invariants, lane bindings, declared features, active residual, and the
semantically material bindings. No timestamps, fixture labels, debug ids,
paths, or Python reprs.
"""
from __future__ import annotations

from typing import Any

from elpis_p0.structural_residual import (
    GRID_SIZE,
    LaneBindingV1,
    StructuralInvariantV1,
    StructuralSchemaV1,
    build_structural_schema,
    residual as authority_residual,
)
import structural_trm_features as FEATURES

from .contracts import (
    FINGERPRINT_DOMAIN,
    EntityBinding,
    ProjectionError,
    StructuralBindingV1,
    binding_payload,
    canonical_bytes,
    domain_digest,
    sha256_hex,
)
from .rules import Ruleset


def derive_residual_state(
    grid: tuple[int, ...],
    invariants: tuple[StructuralInvariantV1, ...],
    ruleset: Ruleset,
) -> tuple[tuple[str, ...], tuple[int, ...], tuple[int, ...]]:
    """(unsatisfied_ids, declared529, active529) via authority machinery."""
    unsatisfied = authority_residual(grid, tuple(invariants))
    declared, active = FEATURES.encode_constraint_state(
        tuple(invariants), unsatisfied
    )
    if len(declared) != ruleset.feature_width:
        raise ProjectionError(  # type: ignore[call-arg]
            code="ERR.RESIDUAL_WIDTH",
            rule="R16.FEATURE_DERIVATION",
            detail={"width": len(declared),
                    "expected": ruleset.feature_width},
        )
    if FEATURES.VOCABULARY_DIGEST != ruleset.vocabulary_digest:
        raise ProjectionError(  # type: ignore[call-arg]
            code="ERR.VOCABULARY",
            rule="R16.FEATURE_DERIVATION",
            detail={"live": FEATURES.VOCABULARY_DIGEST,
                    "pinned": ruleset.vocabulary_digest},
        )
    return unsatisfied, tuple(declared), tuple(active)


def build_masks(
    frozen_cells: set[int],
    ruleset: Ruleset,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """R14: frozen and writable masks; disjoint and covering."""
    if any(c < 0 or c >= GRID_SIZE for c in frozen_cells):
        raise ValueError(f"frozen cell outside grid: {sorted(frozen_cells)}")
    frozen = tuple(1 if i in frozen_cells else 0 for i in range(GRID_SIZE))
    writable = tuple(1 - f for f in frozen)
    # invariants: disjoint + cover
    if any(frozen[i] and writable[i] for i in range(GRID_SIZE)):
        raise AssertionError("frozen/writable masks not disjoint")
    if any(not frozen[i] and not writable[i] for i in range(GRID_SIZE)):
        raise AssertionError("frozen/writable masks do not cover grid")
    if writable[80] != 0:
        raise AssertionError("terminal control cell must be frozen")
    return frozen, writable


def build_fingerprint(
    grid: tuple[int, ...],
    frozen_mask: tuple[int, ...],
    writable_mask: tuple[int, ...],
    invariants: tuple[StructuralInvariantV1, ...],
    lane_bindings: tuple[LaneBindingV1, ...],
    declared_features: tuple[int, ...],
    active_residual: tuple[int, ...],
    bindings: StructuralBindingV1,
) -> str:
    """R17: canonical SHA-256 structural input fingerprint."""
    payload = {
        "schema": "c2r6p0.structural-input-fingerprint.v1",
        "grid81": list(grid),
        "frozen_mask": list(frozen_mask),
        "writable_mask": list(writable_mask),
        "invariants": [
            {
                "invariant_id": i.invariant_id,
                "kind": i.kind,
                "lanes": list(i.lanes),
            }
            for i in sorted(invariants, key=lambda i: i.invariant_id)
        ],
        "lane_bindings": [
            {
                "lane": b.lane,
                "semantic_id": b.semantic_id,
                "role": b.role,
                "operational_token": b.operational_token,
            }
            for b in sorted(lane_bindings, key=lambda b: b.lane)
        ],
        "declared_features": list(declared_features),
        "active_residual": list(active_residual),
        "semantic_bindings": binding_payload(bindings),
    }
    return domain_digest(FINGERPRINT_DOMAIN, payload)


# ---------------------------------------------------------------------------
# R19 — reverse structural skeleton extraction (non-generative diagnostic)
# ---------------------------------------------------------------------------


def extract_semantic_skeleton(
    bindings: StructuralBindingV1,
    invariants: tuple[StructuralInvariantV1, ...],
) -> dict[str, Any]:
    """Recover exactly the explicit semantic facts preserved by projection.

    Non-generative: nothing here is inferred; every field is copied from the
    binding sidecar or a declared invariant. The canonical form of the
    skeleton is the round-trip identity used by the tests.
    """
    ops: dict[str, dict[str, Any]] = {}
    for b in bindings.op_bindings:
        ops[b.semantic_id] = {
            "operation_id": b.semantic_id,
            "operator": b.operator,
            "input_entity_ids": list(b.input_entity_ids),
            "output_entity_ids": list(b.output_entity_ids),
        }
    entities: dict[str, dict[str, Any]] = {}
    for b in bindings.entity_bindings:
        entities[b.semantic_id] = {
            "entity_id": b.semantic_id,
            "kind": b.semantic_kind,
            "identity": b.identity,
            "data_type": b.data_type,
        }
    dependencies: dict[str, dict[str, Any]] = {}
    constraints: dict[str, dict[str, Any]] = {}
    relations: dict[str, dict[str, Any]] = {}
    quantities: dict[str, dict[str, Any]] = {}
    for b in bindings.edge_bindings:
        kind = b.semantic_kind
        if kind == "dependency":
            p = b.payload
            dependencies[b.semantic_id] = {
                "dependency_id": b.semantic_id,
                "predecessor_operation_id": p["predecessor"],
                "successor_operation_id": p["successor"],
                "kind": p["kind"],
            }
        elif kind == "constraint":
            p = b.payload
            constraints[b.semantic_id] = {
                "constraint_id": b.semantic_id,
                "predicate": p["predicate"],
                "subject_id": p["subject"],
                "object_id": p.get("object", ""),
                "negated": p["negated"],
                "hard": p["hard"],
            }
        elif kind == "relation":
            p = b.payload
            if b.structural_kind == "route":
                relations[b.semantic_id] = {
                    "relation_id": b.semantic_id,
                    "source_id": p["source"],
                    "predicate": "route",
                    "target_id": p["target"],
                    "negated": False,
                }
            elif b.structural_kind == "state_feeds":
                relations[b.semantic_id] = {
                    "relation_id": b.semantic_id,
                    "source_id": p["source"],
                    "predicate": "state_feeds",
                    "target_id": p["target"],
                    "negated": False,
                }
            elif b.structural_kind == "interface":
                relations[b.semantic_id] = {
                    "relation_id": b.semantic_id,
                    "source_id": p["interface_entity"],
                    "predicate": "interface",
                    "target_id": p["bound_op"],
                    "negated": False,
                }
            elif b.structural_kind == "mutates":
                relations[b.semantic_id] = {
                    "relation_id": b.semantic_id,
                    "source_id": p["mutator"],
                    "predicate": "mutates",
                    "target_id": p["entity"],
                    "negated": False,
                }
            else:  # preserved:*
                relations[b.semantic_id] = {
                    "relation_id": b.semantic_id,
                    "source_id": p["source"],
                    "predicate": p["predicate"],
                    "target_id": p["target"],
                    "negated": p["negated"],
                }
        elif kind == "quantity":
            p = b.payload
            quantities[b.semantic_id] = {
                "quantity_id": b.semantic_id,
                "subject_id": p["subject"],
                "predicate": p["predicate"],
                "comparator": p["comparator"],
                "value": p["value"],
                "unit": p["unit"],
            }
    return {
        "schema": "c2r6p0.semantic-skeleton.v1",
        "entities": [entities[k] for k in sorted(entities)],
        "operations": [ops[k] for k in sorted(ops)],
        "constraints": [constraints[k] for k in sorted(constraints)],
        "relations": [relations[k] for k in sorted(relations)],
        "dependencies": [dependencies[k] for k in sorted(dependencies)],
        "quantities": [quantities[k] for k in sorted(quantities)],
        "output_entity_ids": sorted(bindings.output_entity_ids),
    }


def canonical_skeleton_of_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """The same canonical skeleton directly from the canonical payload.

    Used by the round-trip test: for the supported subset,
    skeleton(payload) == skeleton(project(payload)).
    """
    return {
        "schema": "c2r6p0.semantic-skeleton.v1",
        "entities": sorted(
            (
                {
                    "entity_id": e["entity_id"],
                    "kind": e["kind"],
                    "identity": e["identity"],
                    "data_type": e.get("data_type", ""),
                }
                for e in payload["entities"]
            ),
            key=lambda e: e["entity_id"],
        ),
        "operations": sorted(
            (
                {
                    "operation_id": o["operation_id"],
                    "operator": o["operator"],
                    "input_entity_ids": list(o["input_entity_ids"]),
                    "output_entity_ids": list(o["output_entity_ids"]),
                }
                for o in payload["operations"]
            ),
            key=lambda o: o["operation_id"],
        ),
        "constraints": sorted(
            (
                {
                    "constraint_id": c["constraint_id"],
                    "predicate": c["predicate"],
                    "subject_id": c["subject_id"],
                    "object_id": c.get("object_id", ""),
                    "negated": c["negated"],
                    "hard": c["hard"],
                }
                for c in payload["constraints"]
            ),
            key=lambda c: c["constraint_id"],
        ),
        "relations": sorted(
            (
                {
                    "relation_id": r["relation_id"],
                    "source_id": r["source_id"],
                    "predicate": r["predicate"],
                    "target_id": r["target_id"],
                    "negated": r["negated"],
                }
                for r in payload["relations"]
            ),
            key=lambda r: r["relation_id"],
        ),
        "dependencies": sorted(
            (
                {
                    "dependency_id": d["dependency_id"],
                    "predecessor_operation_id": (
                        d["predecessor_operation_id"]
                    ),
                    "successor_operation_id": (
                        d["successor_operation_id"]
                    ),
                    "kind": d["kind"],
                }
                for d in payload["dependencies"]
            ),
            key=lambda d: d["dependency_id"],
        ),
        "quantities": sorted(
            (
                {
                    "quantity_id": q["quantity_id"],
                    "subject_id": q["subject_id"],
                    "predicate": q["predicate"],
                    "comparator": q["comparator"],
                    "value": q["value"],
                    "unit": q.get("unit", ""),
                }
                for q in payload["quantities"]
            ),
            key=lambda q: q["quantity_id"],
        ),
        "output_entity_ids": sorted(payload["output_entity_ids"]),
    }
