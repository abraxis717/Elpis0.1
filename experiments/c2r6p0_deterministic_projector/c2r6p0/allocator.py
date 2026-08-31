"""Deterministic Grid81 lane/rank allocation and structural compilation.

This is the heart of the projector. Given a canonical semantic graph and
its schedule analysis it compiles, with explicit named rules:

  * one lane per operation (R6), assigned by a total order on
    (longest-path distance, topological index, operation id);
  * one frozen operational locus per operation at rank = longest-path
    distance (R7), with a role token (R8): INPUT for sources, OUTPUT for
    sinks, TRANSFORM otherwise (TRANSFORM is structural; the executable
    meaning stays in the sidecar);
  * ROUTE loci for explicit cross-lane route relations (R9) satisfying
    CROSS_LANE_ROUTE;
  * MEMORY loci for state_feeds relations (R10) satisfying MEMORY_SPAN;
  * CONSTRAINT loci for hard semantic constraints (R11) satisfying
    CONSTRAINT_AFTER;
  * INTERFACE loci for explicit interfaces (R12) satisfying
    INTERFACE_TERMINAL;
  * the frozen terminal RESOLUTION locus (R13) discharging
    TERMINAL_RESOLUTION;
  * frozen = known semantic facts, writable = the refiner's search space
    (R14); frozen and writable are disjoint and cover the grid;
  * capacity checks (R15) returning DECOMPOSITION_REQUIRED rather than
    squeezing.

Unresolved required topology (e.g. a MUTATION_HAZARD that the frozen
schedule cannot discharge) is marked with an EXPANSION locus at a
deterministic cell (R14.UNRESOLVED_LOCUS_DECLARED) — never a guessed
final token.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from elpis_p0.contracts import BasisToken
from elpis_p0.structural_residual import (
    CONTROL_LANE,
    GRID_SIZE,
    MAX_SEMANTIC_LANES,
    RANKS,
    TERMINAL_CELL,
    LaneBindingV1,
    StructuralInvariantV1,
    capacity_requirements,
    decomposition_measure,
)

from . import rules as R
from .contracts import (
    EntityBinding,
    EdgeBinding,
    ErrorCode,
    OpBinding,
    ProjectionError,
    ProjectionStatus,
    StructuralBindingV1,
)
from .graph import GraphAnalysis
from .rules import Ruleset
from .taxonomy import (
    INTERFACE_PREDICATE,
    MUTATES_PREDICATE,
    ROUTE_PREDICATE,
    STATE_FEEDS_PREDICATE,
)

VOID = int(BasisToken.VOID)
INPUT = int(BasisToken.INPUT)
TRANSFORM = int(BasisToken.TRANSFORM)
OUTPUT = int(BasisToken.OUTPUT)
MEMORY = int(BasisToken.MEMORY)
CONSTRAINT = int(BasisToken.CONSTRAINT)
ROUTE = int(BasisToken.ROUTE)
INTERFACE = int(BasisToken.INTERFACE)
RESOLUTION = int(BasisToken.RESOLUTION)
EXPANSION = int(BasisToken.EXPANSION)


def cell(rank: int, lane: int) -> int:
    return rank * 9 + lane


def _reject_decomposition(
    rule: str,
    detail: dict[str, Any],
    capacity: dict[str, int],
) -> ProjectionError:
    return ProjectionError(
        status=ProjectionStatus.DECOMPOSITION_REQUIRED.value,
        code=ErrorCode.DECOMPOSITION.value,
        rule=rule,
        detail={**detail, "capacity": capacity},
    )


@dataclass
class Placement:
    """Mutable working state for one projection (never exposed publicly)."""

    grid: list[int]
    frozen: set[int]
    placed: dict[int, str]          # cell -> what was placed (trace)
    lane_of: dict[str, int]          # op_id -> lane
    rank_of: dict[str, int]           # op_id -> rank
    role_of: dict[str, int]            # op_id -> token
    invariants: list[StructuralInvariantV1]
    op_bindings: list[OpBinding]
    entity_bindings: list[EntityBinding]
    edge_bindings: list[EdgeBinding]
    unsatisfied_hazards: list[dict[str, Any]]
    # Ordered placement actions for the proof-carrying trace. Each action is a
    # deterministic (event_type, rule_id, semantic_ids, cell, detail) tuple in
    # the exact order the projector applied it, so the trace can replay the
    # grid from VOID and reproduce every before/after digest.
    actions: list[dict[str, Any]] = field(default_factory=list)


def _act(
    placement: Placement,
    event_type: str,
    rule_id: str,
    semantic_ids: tuple[str, ...],
    cell_index: int,
    detail: dict[str, Any],
) -> None:
    placement.actions.append(
        {
            "event_type": event_type,
            "rule_id": rule_id,
            "semantic_ids": tuple(semantic_ids),
            "cell": cell_index,
            "detail": detail,
        }
    )


def _role_token(
    op_id: str,
    n_ops: int,
    analysis: GraphAnalysis,
    payload: dict[str, Any],
) -> int:
    """R8.ROLE_TOKEN: structural role from explicit graph position."""
    if n_ops == 1:
        op = next(o for o in payload["operations"]
                  if o["operation_id"] == op_id)
        has_in = bool(op["input_entity_ids"])
        has_out = bool(op["output_entity_ids"])
        if has_in and not has_out:
            return INPUT
        if has_out and not has_in:
            return OUTPUT
        return TRANSFORM
    indeg = {op: 0 for op in analysis.op_ids}
    outdeg = {op: 0 for op in analysis.op_ids}
    for e in analysis.edges:
        outdeg[e.src] += 1
        indeg[e.dst] += 1
    if indeg[op_id] == 0:
        return INPUT
    if outdeg[op_id] == 0:
        return OUTPUT
    return TRANSFORM


def indeg_of(op_id: str, analysis: GraphAnalysis) -> int:
    return sum(1 for e in analysis.edges if e.dst == op_id)


def outdeg_of(op_id: str, analysis: GraphAnalysis) -> int:
    return sum(1 for e in analysis.edges if e.src == op_id)


def _producer_consumers(
    payload: dict[str, Any],
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


def _constraint_owner(
    constraint: dict[str, Any],
    payload: dict[str, Any],
    producers: dict[str, list[str]],
    consumers: dict[str, list[str]],
    analysis: GraphAnalysis,
) -> str | None:
    """Deterministic lane owner for a hard constraint.

    subject operation -> that lane. subject entity -> producer lane if
    declared, else the earliest consumer lane (topological). A constraint
    on an unreferenced entity has no structural lane (preserved in the
    sidecar without structural effect).
    """
    subj = constraint["subject_id"]
    op_ids = set(analysis.op_ids)
    if subj in op_ids:
        return subj
    if subj in producers:
        return producers[subj][0]
    if subj in consumers:
        topo_index = {op: i for i, op in enumerate(analysis.topo_order)}
        return sorted(consumers[subj], key=lambda o: (topo_index[o], o))[0]
    return None


def _place_tail(
    placement: Placement,
    lane: int,
    low_rank: int,
    what: str,
) -> int | None:
    """Place at the smallest free rank >= low_rank in `lane` (<= 8)."""
    for rank in range(low_rank, RANKS):
        c = cell(rank, lane)
        if c not in placement.frozen and c not in placement.placed:
            placement.placed[c] = what
            return c
    return None


def _place_in_interval(
    placement: Placement,
    lane: int,
    lo: int,
    hi: int,
    what: str,
) -> int | None:
    """Place at the smallest free rank r with lo < r < hi in `lane`."""
    for rank in range(lo + 1, hi):
        c = cell(rank, lane)
        if c not in placement.frozen and c not in placement.placed:
            placement.placed[c] = what
            return c
    return None


def allocate(
    payload: dict[str, Any],
    analysis: GraphAnalysis,
    ruleset: Ruleset,
) -> tuple[Placement | None, ProjectionError | None, dict[str, int]]:
    """Run deterministic allocation. Returns (placement, error, capacity)."""
    ops = payload["operations"]
    n_ops = len(analysis.op_ids)

    # ---- capacity: lanes (R15.CAPACITY_LANES)
    if n_ops > MAX_SEMANTIC_LANES:
        lanes_req, ranks_req, loci_req = capacity_requirements(
            n_ops, analysis.longest_chain, 0, 0
        )
        cap = {
            "lanes_required": lanes_req,
            "ranks_required": ranks_req,
            "loci_required": loci_req,
            "decomposition_measure": decomposition_measure(
                lanes_req, ranks_req, loci_req
            ),
        }
        err = _reject_decomposition(
            R.R_CAP_LANES,
            {
                "operations": n_ops,
                "max_semantic_lanes": MAX_SEMANTIC_LANES,
                "reason": "more_operations_than_semantic_lanes",
            },
            cap,
        )
        return None, err, cap

    # ---- capacity: ranks (longest chain offset must fit 0..RANKS-1)
    max_dist = max(analysis.dist.values())
    if max_dist >= RANKS:
        lanes_req, ranks_req, loci_req = capacity_requirements(
            n_ops, analysis.longest_chain, 0, 0
        )
        cap = {
            "lanes_required": lanes_req,
            "ranks_required": ranks_req,
            "loci_required": loci_req,
            "decomposition_measure": decomposition_measure(
                lanes_req, ranks_req, loci_req
            ),
        }
        err = _reject_decomposition(
            R.R_CAP_RANKS,
            {
                "max_rank_offset": max_dist,
                "ranks": RANKS,
                "reason": "longest_chain_exceeds_rank_capacity",
            },
            cap,
        )
        return None, err, cap

    # ---- lane assignment (R6.LANE_ALLOCATION)
    # Total order: (longest-path distance, topological index, op id).
    topo_index = {op: i for i, op in enumerate(analysis.topo_order)}
    lane_key = sorted(
        analysis.op_ids,
        key=lambda op: (analysis.dist[op], topo_index[op], op),
    )
    lane_of = {op: i for i, op in enumerate(lane_key)}

    placement = Placement(
        grid=[VOID] * GRID_SIZE,
        frozen=set(),
        placed={},
        lane_of=lane_of,
        rank_of={},
        role_of={},
        invariants=[],
        op_bindings=[],
        entity_bindings=[],
        edge_bindings=[],
        unsatisfied_hazards=[],
    )
    capacity: dict[str, int] = {}

    # Lane assignments are recorded first (R6), in sorted operation order,
    # before any locus is placed.
    for op_id in sorted(lane_of):
        _act(
            placement,
            "LANE_ASSIGNED",
            R.R_LANE_ALLOC,
            (op_id,),
            cell(analysis.dist[op_id], lane_of[op_id]),
            {
                "lane": lane_of[op_id],
                "rank_offset": analysis.dist[op_id],
                "topo_index": topo_index[op_id],
                "order_key": [
                    analysis.dist[op_id], topo_index[op_id], op_id
                ],
            },
        )

    producers, consumers = _producer_consumers(payload)

    # ---- operational loci (R7/R8)
    for op in sorted(ops, key=lambda o: o["operation_id"]):
        op_id = op["operation_id"]
        lane = lane_of[op_id]
        rank = analysis.dist[op_id]
        role = _role_token(op_id, n_ops, analysis, payload)
        c = cell(rank, lane)
        placement.grid[c] = role
        placement.frozen.add(c)
        placement.placed[c] = f"operation:{op_id}"
        placement.rank_of[op_id] = rank
        placement.role_of[op_id] = role
        _act(
            placement,
            "ROLE_PLACED",
            R.R_ROLE_TOKEN,
            (op_id,),
            c,
            {
                "token": role,
                "rank": rank,
                "lane": lane,
                "role_rule": (
                    "single_operation_arity" if n_ops == 1
                    else ("source" if indeg_of(op_id, analysis) == 0
                           else "sink" if outdeg_of(op_id, analysis) == 0
                           else "intermediate")
                ),
            },
        )
        _act(
            placement,
            "FROZEN_LOCUS_DECLARED",
            R.R_FROZEN,
            (op_id,),
            c,
            {"reason": "explicit_semantic_operation_locus"},
        )
        out_types = tuple(
            sorted(
                (e["entity_id"], e.get("data_type", ""))
                for e in payload["entities"]
                if e["entity_id"] in op["output_entity_ids"]
            )
        )
        placement.op_bindings.append(
            OpBinding(
                binding_id=f"op:{op_id}",
                semantic_id=op_id,
                semantic_kind="operation",
                operator=op["operator"],
                input_entity_ids=tuple(op["input_entity_ids"]),
                output_entity_ids=tuple(op["output_entity_ids"]),
                lane=lane,
                rank=rank,
                cell=c,
                token=role,
                frozen=True,
                data_types=out_types,
            )
        )
        # LANE_SINGLE_OCCUPANCY: exactly one operational locus per lane.
        placement.invariants.append(
            StructuralInvariantV1(
                invariant_id=f"occupy.{op_id}",
                kind="LANE_SINGLE_OCCUPANCY",
                lanes=(lane,),
            )
        )

    # ---- PRECEDES invariants for every distinct schedule pair
    for (s, d), _gap in _deduped_pairs(analysis).items():
        placement.invariants.append(
            StructuralInvariantV1(
                invariant_id=f"precedes.{s}.{d}",
                kind="PRECEDES",
                lanes=(lane_of[s], lane_of[d]),
            )
        )

    # ---- route loci (R9): ROUTE in consumer lane strictly between ranks
    route_rels = sorted(
        (r for r in payload["relations"]
         if r["predicate"] == ROUTE_PREDICATE),
        key=lambda r: r["relation_id"],
    )
    for rel in route_rels:
        src, dst = rel["source_id"], rel["target_id"]
        r_src = placement.rank_of[src]
        r_dst = placement.rank_of[dst]
        c = _place_in_interval(
            placement, lane_of[dst], r_src, r_dst, f"route:{rel['relation_id']}"
        )
        if c is None:
            cap = _capacity_record(payload, analysis, lane_of, placement)
            err = _reject_decomposition(
                R.R_ROUTE_RANK,
                {
                    "relation": rel["relation_id"],
                    "consumer_lane": lane_of[dst],
                    "rank_span": [r_src + 1, r_dst - 1],
                    "reason": "no_free_rank_for_route_in_consumer_lane",
                },
                cap,
            )
            return None, err, cap
        placement.frozen.add(c)
        placement.grid[c] = ROUTE
        _act(
            placement,
            "ROUTE_INSERTED",
            R.R_ROUTE_PLACE,
            (rel["relation_id"], src, dst),
            c,
            {
                "token": ROUTE,
                "producer_lane": lane_of[src],
                "consumer_lane": lane_of[dst],
                "rank": c // 9,
                "invariant": f"route.{src}.{dst}",
            },
        )
        placement.invariants.append(
            StructuralInvariantV1(
                invariant_id=f"route.{src}.{dst}",
                kind="CROSS_LANE_ROUTE",
                lanes=(lane_of[src], lane_of[dst]),
            )
        )
        placement.edge_bindings.append(
            EdgeBinding(
                binding_id=f"rel:{rel['relation_id']}",
                semantic_id=rel["relation_id"],
                semantic_kind="relation",
                structural_kind=ROUTE_PREDICATE,
                lanes=(lane_of[src], lane_of[dst]),
                discharged=True,
                payload={
                    "source": src,
                    "target": dst,
                    "route_cell": c,
                    "route_rank": c // 9,
                },
            )
        )

    # ---- memory loci (R10): MEMORY in producer lane between ranks
    state_rels = sorted(
        (r for r in payload["relations"]
         if r["predicate"] == STATE_FEEDS_PREDICATE),
        key=lambda r: r["relation_id"],
    )
    for rel in state_rels:
        src, dst = rel["source_id"], rel["target_id"]
        r_src = placement.rank_of[src]
        r_dst = placement.rank_of[dst]
        c = _place_in_interval(
            placement, lane_of[src], r_src, r_dst,
            f"memory:{rel['relation_id']}",
        )
        if c is None:
            cap = _capacity_record(payload, analysis, lane_of, placement)
            err = _reject_decomposition(
                R.R_MEMORY_RANK,
                {
                    "relation": rel["relation_id"],
                    "producer_lane": lane_of[src],
                    "rank_span": [r_src + 1, r_dst - 1],
                    "reason": "no_free_rank_for_memory_span_in_producer_lane",
                },
                cap,
            )
            return None, err, cap
        placement.frozen.add(c)
        placement.grid[c] = MEMORY
        _act(
            placement,
            "MEMORY_RELATION_ENCODED",
            R.R_MEMORY_PLACE,
            (rel["relation_id"], src, dst),
            c,
            {
                "token": MEMORY,
                "producer_lane": lane_of[src],
                "consumer_lane": lane_of[dst],
                "rank": c // 9,
                "invariant": f"memory.{src}.{dst}",
            },
        )
        placement.invariants.append(
            StructuralInvariantV1(
                invariant_id=f"memory.{src}.{dst}",
                kind="MEMORY_SPAN",
                lanes=(lane_of[src], lane_of[dst]),
            )
        )
        placement.edge_bindings.append(
            EdgeBinding(
                binding_id=f"rel:{rel['relation_id']}",
                semantic_id=rel["relation_id"],
                semantic_kind="relation",
                structural_kind=STATE_FEEDS_PREDICATE,
                lanes=(lane_of[src], lane_of[dst]),
                discharged=True,
                payload={
                    "source": src,
                    "target": dst,
                    "memory_cell": c,
                    "memory_rank": c // 9,
                },
            )
        )

    # ---- constraint loci (R11): CONSTRAINT after the owner op
    constraints_by_op: dict[str, list[dict[str, Any]]] = {}
    for con in sorted(payload["constraints"],
                     key=lambda c: c["constraint_id"]):
        if not con["hard"]:
            # soft constraints are preserved in the sidecar only
            placement.edge_bindings.append(
                EdgeBinding(
                    binding_id=f"con:{con['constraint_id']}",
                    semantic_id=con["constraint_id"],
                    semantic_kind="constraint",
                    structural_kind="preserved",
                    lanes=(),
                    discharged=False,
                    payload={
                        "subject": con["subject_id"],
                        "predicate": con["predicate"],
                        "object": con["object_id"],
                        "negated": con["negated"],
                        "hard": con["hard"],
                    },
                )
            )
            continue
        owner = _constraint_owner(con, payload, producers, consumers,
                                  analysis)
        if owner is None:
            placement.edge_bindings.append(
                EdgeBinding(
                    binding_id=f"con:{con['constraint_id']}",
                    semantic_id=con["constraint_id"],
                    semantic_kind="constraint",
                    structural_kind="preserved",
                    lanes=(),
                    discharged=False,
                    payload={
                        "subject": con["subject_id"],
                        "predicate": con["predicate"],
                        "object": con["object_id"],
                        "negated": con["negated"],
                        "hard": con["hard"],
                        "note": "no_structural_lane",
                    },
                )
            )
            continue
        constraints_by_op.setdefault(owner, []).append(con)

    ops_with_constraints: set[str] = set()
    for owner in sorted(constraints_by_op):
        lane = lane_of[owner]
        r_op = placement.rank_of[owner]
        for con in constraints_by_op[owner]:
            c = _place_tail(placement, lane, r_op + 1,
                            f"constraint:{con['constraint_id']}")
            if c is None:
                cap = _capacity_record(payload, analysis, lane_of, placement)
                err = _reject_decomposition(
                    R.R_CONSTRAINT_RANK,
                    {
                        "constraint": con["constraint_id"],
                        "lane": lane,
                        "reason": "no_free_rank_after_owner_operation",
                    },
                    cap,
                )
                return None, err, cap
            placement.frozen.add(c)
            placement.grid[c] = CONSTRAINT
            ops_with_constraints.add(owner)
            _act(
                placement,
                "CONSTRAINT_ENCODED",
                R.R_CONSTRAINT_PLACE,
                (con["constraint_id"],),
                c,
                {
                    "token": CONSTRAINT,
                    "owner_op": owner,
                    "lane": lane,
                    "rank": c // 9,
                    "subject": con["subject_id"],
                    "predicate": con["predicate"],
                },
            )
            placement.edge_bindings.append(
                EdgeBinding(
                    binding_id=f"con:{con['constraint_id']}",
                    semantic_id=con["constraint_id"],
                    semantic_kind="constraint",
                    structural_kind="CONSTRAINT_AFTER",
                    lanes=(lane,),
                    discharged=True,
                    payload={
                        "subject": con["subject_id"],
                        "predicate": con["predicate"],
                        "object": con["object_id"],
                        "negated": con["negated"],
                        "hard": con["hard"],
                        "owner_op": owner,
                        "constraint_cell": c,
                        "constraint_rank": c // 9,
                    },
                )
            )
    for owner in sorted(ops_with_constraints):
        placement.invariants.append(
            StructuralInvariantV1(
                invariant_id=f"constraint.{owner}",
                kind="CONSTRAINT_AFTER",
                lanes=(lane_of[owner],),
            )
        )

    # ---- interface loci (R12): INTERFACE after the bound op
    interface_rels = sorted(
        (r for r in payload["relations"]
         if r["predicate"] == INTERFACE_PREDICATE),
        key=lambda r: r["relation_id"],
    )
    ops_with_interfaces: set[str] = set()
    for rel in interface_rels:
        src_entity, dst_op = rel["source_id"], rel["target_id"]
        lane = lane_of[dst_op]
        r_op = placement.rank_of[dst_op]
        c = _place_tail(placement, lane, r_op + 1,
                        f"interface:{rel['relation_id']}")
        if c is None:
            cap = _capacity_record(payload, analysis, lane_of, placement)
            err = _reject_decomposition(
                R.R_INTERFACE_RANK,
                {
                    "relation": rel["relation_id"],
                    "lane": lane,
                    "reason": "no_free_rank_after_bound_operation",
                },
                cap,
            )
            return None, err, cap
        placement.frozen.add(c)
        placement.grid[c] = INTERFACE
        ops_with_interfaces.add(dst_op)
        _act(
            placement,
            "INTERFACE_ENCODED",
            R.R_INTERFACE_PLACE,
            (rel["relation_id"], src_entity, dst_op),
            c,
            {
                "token": INTERFACE,
                "interface_entity": src_entity,
                "bound_op": dst_op,
                "lane": lane,
                "rank": c // 9,
            },
        )
        placement.edge_bindings.append(
            EdgeBinding(
                binding_id=f"rel:{rel['relation_id']}",
                semantic_id=rel["relation_id"],
                semantic_kind="relation",
                structural_kind=INTERFACE_PREDICATE,
                lanes=(lane,),
                discharged=True,
                payload={
                    "interface_entity": src_entity,
                    "bound_op": dst_op,
                    "interface_cell": c,
                    "interface_rank": c // 9,
                    "direction": "entity_to_operation",
                },
            )
        )
    for op in sorted(ops_with_interfaces):
        placement.invariants.append(
            StructuralInvariantV1(
                invariant_id=f"interface.{op}",
                kind="INTERFACE_TERMINAL",
                lanes=(lane_of[op],),
            )
        )

    # ---- MUTATION_HAZARD invariants (declared, may remain active)
    mutates_rels = sorted(
        (r for r in payload["relations"]
         if r["predicate"] == MUTATES_PREDICATE),
        key=lambda r: r["relation_id"],
    )
    hazard_declared: set[tuple[str, str, str]] = set()
    for rel in mutates_rels:
        mutator = rel["source_id"]
        entity = rel["target_id"]
        prods = producers.get(entity, [])
        cons = consumers.get(entity, [])
        if not prods:
            # mutates with no declared producer: preserved, no hazard locus
            placement.edge_bindings.append(
                EdgeBinding(
                    binding_id=f"rel:{rel['relation_id']}",
                    semantic_id=rel["relation_id"],
                    semantic_kind="relation",
                    structural_kind=MUTATES_PREDICATE,
                    lanes=(),
                    discharged=False,
                    payload={
                        "mutator": mutator,
                        "entity": entity,
                        "note": "no_declared_producer",
                    },
                )
            )
            continue
        declared_any = False
        for producer in prods:
            for consumer in cons:
                if consumer in (producer, mutator):
                    continue
                key = (producer, consumer, mutator)
                if key in hazard_declared:
                    continue
                hazard_declared.add(key)
                placement.invariants.append(
                    StructuralInvariantV1(
                        invariant_id=(
                            f"hazard.{producer}.{consumer}.{mutator}"
                        ),
                        kind="MUTATION_HAZARD",
                        lanes=(
                            lane_of[producer],
                            lane_of[consumer],
                            lane_of[mutator],
                        ),
                    )
                )
                declared_any = True
        placement.edge_bindings.append(
            EdgeBinding(
                binding_id=f"rel:{rel['relation_id']}",
                semantic_id=rel["relation_id"],
                semantic_kind="relation",
                structural_kind=MUTATES_PREDICATE,
                lanes=(lane_of[mutator],),
                discharged=declared_any,
                payload={
                    "mutator": mutator,
                    "entity": entity,
                    "producers": prods,
                    "consumers": cons,
                },
            )
        )

    # ---- terminal RESOLUTION locus (R13)
    placement.grid[TERMINAL_CELL] = RESOLUTION
    placement.frozen.add(TERMINAL_CELL)
    placement.placed[TERMINAL_CELL] = "terminal.resolution"
    _act(
        placement,
        "FROZEN_LOCUS_DECLARED",
        R.R_TERMINAL_PLACE,
        ("terminal.resolution",),
        TERMINAL_CELL,
        {"reason": "determined_terminal_control_locus",
         "token": RESOLUTION},
    )
    placement.invariants.append(
        StructuralInvariantV1(
            invariant_id="terminal.resolution",
            kind="TERMINAL_RESOLUTION",
            lanes=(),
        )
    )

    # ---- entity bindings (sidecar identity for every explicit entity)
    out_ids = set(payload["output_entity_ids"])
    for ent in sorted(payload["entities"], key=lambda e: e["entity_id"]):
        placement.entity_bindings.append(
            EntityBinding(
                binding_id=f"ent:{ent['entity_id']}",
                semantic_id=ent["entity_id"],
                semantic_kind=ent["kind"],
                identity=ent["identity"],
                data_type=ent.get("data_type", ""),
                producer_ops=tuple(producers.get(ent["entity_id"], ())),
                consumer_ops=tuple(consumers.get(ent["entity_id"], ())),
                declared_output=ent["entity_id"] in out_ids,
            )
        )

    # ---- preserved (non-structural) relations/dependencies/quantities
    structural_rel_ids = {
        r["relation_id"]
        for r in payload["relations"]
        if r["predicate"] in (
            ROUTE_PREDICATE, STATE_FEEDS_PREDICATE, INTERFACE_PREDICATE,
            MUTATES_PREDICATE,
        )
    }
    for dep in sorted(payload["dependencies"],
                     key=lambda d: d["dependency_id"]):
        placement.edge_bindings.append(
            EdgeBinding(
                binding_id=f"dep:{dep['dependency_id']}",
                semantic_id=dep["dependency_id"],
                semantic_kind="dependency",
                structural_kind=dep["kind"],
                lanes=(
                    lane_of[dep["predecessor_operation_id"]],
                    lane_of[dep["successor_operation_id"]],
                ) if dep["kind"] == "precedes" else (),
                discharged=dep["kind"] == "precedes",
                payload={
                    "predecessor": dep["predecessor_operation_id"],
                    "successor": dep["successor_operation_id"],
                    "kind": dep["kind"],
                },
            )
        )
    for rel in sorted(payload["relations"],
                     key=lambda r: r["relation_id"]):
        if rel["relation_id"] in structural_rel_ids:
            continue
        placement.edge_bindings.append(
            EdgeBinding(
                binding_id=f"rel:{rel['relation_id']}",
                semantic_id=rel["relation_id"],
                semantic_kind="relation",
                structural_kind=f"preserved:{rel['predicate']}",
                lanes=(),
                discharged=False,
                payload={
                    "source": rel["source_id"],
                    "predicate": rel["predicate"],
                    "target": rel["target_id"],
                    "negated": rel["negated"],
                },
            )
        )
    for q in sorted(payload["quantities"],
                   key=lambda q: q["quantity_id"]):
        placement.edge_bindings.append(
            EdgeBinding(
                binding_id=f"qty:{q['quantity_id']}",
                semantic_id=q["quantity_id"],
                semantic_kind="quantity",
                structural_kind=(
                    "arity_checked"
                    if q["predicate"] in (
                        "input_arity", "output_arity"
                    )
                    else "preserved"
                ),
                lanes=(),
                discharged=False,
                payload={
                    "subject": q["subject_id"],
                    "predicate": q["predicate"],
                    "comparator": q["comparator"],
                    "value": q["value"],
                    "unit": q.get("unit", ""),
                },
            )
        )

    # ---- final per-lane capacity check (R15.CAPACITY_LOCI)
    cap = _capacity_record(payload, analysis, lane_of, placement)
    per_lane_loci: dict[int, int] = {}
    for c in sorted(placement.frozen | set(placement.placed)):
        per_lane_loci[c % 9] = per_lane_loci.get(c % 9, 0) + 1
    cap["max_loci_per_lane"] = max(per_lane_loci.values(), default=0)
    cap["loci_total"] = len(placement.frozen | set(placement.placed))
    if any(v > RANKS for v in per_lane_loci.values()):
        err = _reject_decomposition(
            R.R_CAP_LOCI,
            {
                "per_lane_loci": {str(k): v for k, v in
                                  sorted(per_lane_loci.items())},
                "reason": "lane_exceeds_rank_capacity",
            },
            cap,
        )
        return None, err, cap

    return placement, None, cap


def _deduped_pairs(analysis: GraphAnalysis):
    pairs: dict[tuple[str, str], int] = {}
    for e in analysis.edges:
        cur = pairs.get((e.src, e.dst))
        if cur is None or e.gap > cur:
            pairs[(e.src, e.dst)] = e.gap
    return pairs


def _capacity_record(
    payload: dict[str, Any],
    analysis: GraphAnalysis,
    lane_of: dict[str, int],
    placement: Placement,
) -> dict[str, int]:
    route_count = sum(
        1 for r in payload["relations"]
        if r["predicate"] == ROUTE_PREDICATE
    )
    memory_count = sum(
        1 for r in payload["relations"]
        if r["predicate"] == STATE_FEEDS_PREDICATE
    )
    lanes_req, ranks_req, loci_req = capacity_requirements(
        len(analysis.op_ids),
        analysis.longest_chain,
        route_count,
        memory_count,
    )
    return {
        "lanes_required": lanes_req,
        "ranks_required": ranks_req,
        "loci_required": loci_req,
        "decomposition_measure": decomposition_measure(
            lanes_req, ranks_req, loci_req
        ),
        "route_count": route_count,
        "memory_span_count": memory_count,
        "longest_chain": analysis.longest_chain,
    }
