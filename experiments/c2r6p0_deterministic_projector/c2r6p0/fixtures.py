"""Deterministic synthetic Semantic IR fixture generator.

Not D1 fixtures: every fixture is generated here from an explicit seed and
has a deterministic canonical identity. Two families:

  * POSITIVE_FIXTURES — hand-shaped named cases covering the mission's
    required shapes (mission 23);
  * gen_valid / gen_malformed — seeded random generators for the fuzz
    campaign (mission 26): 10,000 valid + >= 2,000 malformed graphs.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from elpis_p0 import semantic_ir as IR
from elpis_p0.semantic_ir import (
    P0SemanticRequestV1,
    SemanticConstraintV1,
    SemanticDependencyV1,
    SemanticEntityV1,
    SemanticOperationV1,
    SemanticQuantityV1,
    SemanticRelationV1,
    build_semantic_request_v1,
)


@dataclass(frozen=True)
class Fixture:
    name: str
    graph: P0SemanticRequestV1
    expect: str  # "PROJECTED" | "DECOMPOSITION_REQUIRED" | other status
    note: str = ""


# ---------------------------------------------------------------------------
# Named positive / negative fixtures (mission 23)
# ---------------------------------------------------------------------------


def _named() -> list[Fixture]:
    out: list[Fixture] = []

    def add(name, graph, expect, note=""):
        out.append(Fixture(name, graph, expect, note))

    # 1) single input -> transform -> output
    g = build_semantic_request_v1(
        request_id="fx_single",
        entities=(
            SemanticEntityV1("in0", "input", "src", "str"),
            SemanticEntityV1("out0", "output", "dst", "str"),
        ),
        operations=(
            SemanticOperationV1(
                "t0", "transform",
                input_entity_ids=("in0",), output_entity_ids=("out0",),
            ),
        ),
        output_entity_ids=("out0",),
    )
    add("single_transform_output", g, "PROJECTED")

    # 2) multiple inputs -> transform -> output
    g = build_semantic_request_v1(
        request_id="fx_multi_in",
        entities=(
            SemanticEntityV1("in0", "input", "a", "str"),
            SemanticEntityV1("in1", "input", "b", "int"),
            SemanticEntityV1("in2", "input", "c", "dict"),
            SemanticEntityV1("out0", "output", "dst", "str"),
        ),
        operations=(
            SemanticOperationV1(
                "t0", "combine",
                input_entity_ids=("in0", "in1", "in2"),
                output_entity_ids=("out0",),
            ),
        ),
        output_entity_ids=("out0",),
    )
    add("multi_input_single_output", g, "PROJECTED")

    # 3) branch fan-out: one op feeding two downstream ops
    g = build_semantic_request_v1(
        request_id="fx_fanout",
        entities=(
            SemanticEntityV1("in0", "input", "a", "str"),
            SemanticEntityV1("mid", "state", "m", "dict"),
            SemanticEntityV1("o1", "output", "r1", "str"),
            SemanticEntityV1("o2", "output", "r2", "str"),
        ),
        operations=(
            SemanticOperationV1(
                "base", "read", input_entity_ids=("in0",),
                output_entity_ids=("mid",),
            ),
            SemanticOperationV1(
                "left", "derive1", input_entity_ids=("mid",),
                output_entity_ids=("o1",),
            ),
            SemanticOperationV1(
                "right", "derive2", input_entity_ids=("mid",),
                output_entity_ids=("o2",),
            ),
        ),
        dependencies=(
            SemanticDependencyV1("d1", "base", "left"),
            SemanticDependencyV1("d2", "base", "right"),
        ),
        output_entity_ids=("o1", "o2"),
    )
    add("fan_out_multiple_outputs", g, "PROJECTED")

    # 4) fan-in: two branches converging on one op
    g = build_semantic_request_v1(
        request_id="fx_fanin",
        entities=(
            SemanticEntityV1("in0", "input", "a", "str"),
            SemanticEntityV1("in1", "input", "b", "str"),
            SemanticEntityV1("s1", "state", "s1", "dict"),
            SemanticEntityV1("s2", "state", "s2", "dict"),
            SemanticEntityV1("o0", "output", "r", "str"),
        ),
        operations=(
            SemanticOperationV1("a", "prep", input_entity_ids=("in0",),
                                output_entity_ids=("s1",)),
            SemanticOperationV1("b", "prep", input_entity_ids=("in1",),
                                output_entity_ids=("s2",)),
            SemanticOperationV1(
                "join", "combine",
                input_entity_ids=("s1", "s2"),
                output_entity_ids=("o0",),
            ),
        ),
        dependencies=(
            SemanticDependencyV1("d1", "a", "join"),
            SemanticDependencyV1("d2", "b", "join"),
        ),
        output_entity_ids=("o0",),
    )
    add("fan_in_converge", g, "PROJECTED")

    # 5) multi-stage DAG, independent branches converging later
    g = build_semantic_request_v1(
        request_id="fx_dag",
        entities=(
            SemanticEntityV1("in0", "input", "a", "str"),
            SemanticEntityV1("in1", "input", "b", "str"),
            SemanticEntityV1("s1", "state", "s1", "dict"),
            SemanticEntityV1("s2", "state", "s2", "dict"),
            SemanticEntityV1("s3", "state", "s3", "dict"),
            SemanticEntityV1("o0", "output", "r", "str"),
        ),
        operations=(
            SemanticOperationV1("p1", "step", input_entity_ids=("in0",),
                                output_entity_ids=("s1",)),
            SemanticOperationV1("p2", "step", input_entity_ids=("in1",),
                                output_entity_ids=("s2",)),
            SemanticOperationV1("m1", "step", input_entity_ids=("s1",),
                                output_entity_ids=("s3",)),
            SemanticOperationV1("m2", "step", input_entity_ids=("s2",),
                                output_entity_ids=("s3",)),
            SemanticOperationV1("fin", "step", input_entity_ids=("s3",),
                                output_entity_ids=("o0",)),
        ),
        dependencies=(
            SemanticDependencyV1("d1", "p1", "m1"),
            SemanticDependencyV1("d2", "p2", "m2"),
            SemanticDependencyV1("d3", "m1", "fin"),
            SemanticDependencyV1("d4", "m2", "fin"),
        ),
        output_entity_ids=("o0",),
    )
    add("multi_stage_dag_converging", g, "PROJECTED")

    # 6) explicit route requirement
    g = build_semantic_request_v1(
        request_id="fx_route",
        entities=(
            SemanticEntityV1("in0", "input", "a", "str"),
            SemanticEntityV1("s1", "state", "s1", "dict"),
            SemanticEntityV1("o0", "output", "r", "str"),
        ),
        operations=(
            SemanticOperationV1("src", "emit", input_entity_ids=("in0",),
                                output_entity_ids=("s1",)),
            SemanticOperationV1("mid", "step", input_entity_ids=("s1",),
                                output_entity_ids=("s1",)),
            SemanticOperationV1("dst", "consume", input_entity_ids=("s1",),
                                output_entity_ids=("o0",)),
        ),
        dependencies=(
            SemanticDependencyV1("d1", "src", "mid"),
            SemanticDependencyV1("d2", "mid", "dst"),
        ),
        relations=(
            SemanticRelationV1("rt", "src", "route", "dst"),
        ),
        output_entity_ids=("o0",),
    )
    add("explicit_route", g, "PROJECTED",
        "CROSS_LANE_ROUTE discharged by a placed ROUTE locus")

    # 7) explicit memory/state relationship
    g = build_semantic_request_v1(
        request_id="fx_memory",
        entities=(
            SemanticEntityV1("in0", "input", "a", "str"),
            SemanticEntityV1("st", "state", "st", "dict"),
            SemanticEntityV1("o0", "output", "r", "str"),
        ),
        operations=(
            SemanticOperationV1("prod", "emit", input_entity_ids=("in0",),
                                output_entity_ids=("st",)),
            SemanticOperationV1("gap", "step", input_entity_ids=(),
                                output_entity_ids=()),
            SemanticOperationV1("cons", "use", input_entity_ids=("st",),
                                output_entity_ids=("o0",)),
        ),
        dependencies=(
            SemanticDependencyV1("d1", "prod", "gap"),
            SemanticDependencyV1("d2", "gap", "cons"),
        ),
        relations=(
            SemanticRelationV1("sf", "prod", "state_feeds", "cons"),
        ),
        output_entity_ids=("o0",),
    )
    add("explicit_memory_state", g, "PROJECTED",
        "MEMORY_SPAN discharged by a placed MEMORY locus")

    # 8) explicit constraint
    g = build_semantic_request_v1(
        request_id="fx_constraint",
        entities=(
            SemanticEntityV1("in0", "input", "a", "str"),
            SemanticEntityV1("o0", "output", "r", "str"),
        ),
        operations=(
            SemanticOperationV1(
                "t0", "transform",
                input_entity_ids=("in0",), output_entity_ids=("o0",),
            ),
        ),
        constraints=(
            SemanticConstraintV1("c0", "bounded_depth", "t0"),
        ),
        output_entity_ids=("o0",),
    )
    add("explicit_constraint", g, "PROJECTED")

    # 9) explicit interface
    g = build_semantic_request_v1(
        request_id="fx_interface",
        entities=(
            SemanticEntityV1("in0", "input", "a", "str"),
            SemanticEntityV1("api", "interface", "http", ""),
            SemanticEntityV1("o0", "output", "r", "str"),
        ),
        operations=(
            SemanticOperationV1(
                "t0", "transform",
                input_entity_ids=("in0",), output_entity_ids=("o0",),
            ),
        ),
        relations=(
            SemanticRelationV1("if0", "api", "interface", "t0"),
        ),
        output_entity_ids=("o0",),
    )
    add("explicit_interface", g, "PROJECTED")

    # 10) multiple outputs (declared)
    g = build_semantic_request_v1(
        request_id="fx_multi_out",
        entities=(
            SemanticEntityV1("in0", "input", "a", "str"),
            SemanticEntityV1("o1", "output", "r1", "str"),
            SemanticEntityV1("o2", "output", "r2", "str"),
        ),
        operations=(
            SemanticOperationV1(
                "t0", "split",
                input_entity_ids=("in0",),
                output_entity_ids=("o1", "o2"),
            ),
        ),
        output_entity_ids=("o1", "o2"),
    )
    add("multiple_declared_outputs", g, "PROJECTED")

    # 11) near-capacity graph: 8 lanes (max semantic lanes)
    g = build_semantic_request_v1(
        request_id="fx_near_capacity",
        entities=tuple(
            SemanticEntityV1(f"n{i}", "input", f"n{i}", "str")
            for i in range(8)
        ),
        operations=tuple(
            SemanticOperationV1(f"opn{i}", "step", input_entity_ids=(f"n{i}",))
            for i in range(8)
        ),
    )
    add("near_capacity_eight_lanes", g, "PROJECTED")

    # 12) decomposition-required: 9 lanes
    g = build_semantic_request_v1(
        request_id="fx_lane_overflow",
        entities=tuple(
            SemanticEntityV1(f"m{i}", "input", f"m{i}", "str")
            for i in range(9)
        ),
        operations=tuple(
            SemanticOperationV1(f"opm{i}", "step", input_entity_ids=(f"m{i}",))
            for i in range(9)
        ),
    )
    add("lane_overflow_nine", g, "DECOMPOSITION_REQUIRED")

    # 13) decomposition-required: rank overflow. Rank capacity is reached
    #     through gap-2 route edges (a pure chain trips the LANE check
    #     first: 9 ops > 8 lanes). A 6-op route chain c0..c5 schedules
    #     dist(c5) = 10 >= RANKS -> R15.CAPACITY_RANKS. A 5-op route chain
    #     (max dist 8) still fits — the boundary case.
    def _route_chain(n: int):
        return build_semantic_request_v1(
            request_id=f"fx_rank_overflow_{n}",
            entities=tuple(
                SemanticEntityV1(f"ri{i}", "input", f"ri{i}", "str")
                for i in range(n)
            ),
            operations=tuple(
                SemanticOperationV1(
                    f"rc{i}", "step", input_entity_ids=(f"ri{i}",)
                )
                for i in range(n)
            ),
            relations=tuple(
                SemanticRelationV1(f"rr{i}", f"rc{i}", "route", f"rc{i+1}")
                for i in range(n - 1)
            ),
        )
    add(
        "rank_overflow_route6",
        _route_chain(6),
        "DECOMPOSITION_REQUIRED",
        "route-chain schedule distance >= RANKS",
    )
    add("rank_boundary_route5", _route_chain(5), "PROJECTED")

    # 14) route-induced overflow: two independent producers at the same
    #     rank, one consumer, TWO explicit routes. Both routes must place
    #     a ROUTE locus strictly between producer rank (0) and consumer
    #     rank (2) in the consumer lane: only rank 1 exists. The first
    #     route takes it; the second has no legal locus ->
    #     DECOMPOSITION_REQUIRED (no silent overwrite).
    g = build_semantic_request_v1(
        request_id="fx_route_tight",
        entities=(
            SemanticEntityV1("e1", "input", "a", "str"),
            SemanticEntityV1("e2", "input", "b", "str"),
        ),
        operations=(
            SemanticOperationV1("x1", "emit", input_entity_ids=("e1",)),
            SemanticOperationV1("x2", "emit", input_entity_ids=("e2",)),
            SemanticOperationV1("d", "consume"),
        ),
        relations=(
            SemanticRelationV1("rt1", "x1", "route", "d"),
            SemanticRelationV1("rt2", "x2", "route", "d"),
        ),
        output_entity_ids=(),
    )
    add("route_induced_overflow", g, "DECOMPOSITION_REQUIRED",
        "two CROSS_LANE_ROUTE loci compete for one rank in the consumer lane")

    # 14b) interface-induced overflow: a 4-route chain a->b->c->d->e puts
    #      e at rank 8 (gap 2 per route edge); an INTERFACE locus must sit
    #      strictly after the bound op in its lane: no rank >= 9 exists
    #      -> DECOMPOSITION_REQUIRED.
    g = build_semantic_request_v1(
        request_id="fx_iface_tight",
        entities=(
            SemanticEntityV1("ie1", "input", "a", "str"),
            SemanticEntityV1("api", "interface", "http", ""),
        ),
        operations=(
            SemanticOperationV1("a", "emit", input_entity_ids=("ie1",)),
            SemanticOperationV1("b", "step"),
            SemanticOperationV1("c", "step"),
            SemanticOperationV1("d", "step"),
            SemanticOperationV1("e", "step"),
        ),
        relations=(
            SemanticRelationV1("ra", "a", "route", "b"),
            SemanticRelationV1("rb", "b", "route", "c"),
            SemanticRelationV1("rc", "c", "route", "d"),
            SemanticRelationV1("rd", "d", "route", "e"),
            SemanticRelationV1("if0", "api", "interface", "e"),
        ),
        output_entity_ids=(),
    )
    add("interface_induced_overflow", g, "DECOMPOSITION_REQUIRED",
        "bound op at rank 8 leaves no rank for the INTERFACE locus")

    # 14c) constraint-induced overflow: one op at rank 0 with nine hard
    #      constraints. CONSTRAINT_AFTER loci take ranks 1..8; the ninth
    #      has no rank -> DECOMPOSITION_REQUIRED.
    g = build_semantic_request_v1(
        request_id="fx_con_tight",
        entities=(
            SemanticEntityV1("ce1", "input", "a", "str"),
        ),
        operations=(
            SemanticOperationV1("a", "step", input_entity_ids=("ce1",)),
        ),
        constraints=tuple(
            SemanticConstraintV1(f"hc{i}", "bounded", "a", hard=True)
            for i in range(9)
        ),
        output_entity_ids=(),
    )
    add("constraint_induced_overflow", g, "DECOMPOSITION_REQUIRED",
        "nine CONSTRAINT_AFTER loci exceed the eight free ranks")

    # ---- negative cases ------------------------------------------------
    # 15) dangling dependency (directly constructed; authority rejects)
    g = P0SemanticRequestV1(
        request_id="fx_dangling",
        entities=(SemanticEntityV1("e1", "input", "e", "str"),),
        operations=(
            SemanticOperationV1("a", "step"),
            SemanticOperationV1("b", "step"),
        ),
        dependencies=(
            SemanticDependencyV1("db", "a", "b"),
            SemanticDependencyV1("dc", "b", "ghost"),
        ),
        digest="",
    )
    add("dangling_dependency", g, "INVALID_SEMANTIC_IR")

    # 16) duplicate conflicting identity (same op id, different operator)
    g = P0SemanticRequestV1(
        request_id="fx_dupconflict",
        entities=(SemanticEntityV1("e1", "input", "e", "str"),),
        operations=(
            SemanticOperationV1("a", "step1"),
            SemanticOperationV1("a", "step2"),
        ),
        digest="",
    )
    add("duplicate_conflicting_identity", g, "INVALID_SEMANTIC_IR")

    # 17) duplicate identical identity (same op id, identical content)
    g = P0SemanticRequestV1(
        request_id="fx_dupident",
        entities=(SemanticEntityV1("e1", "input", "e", "str"),),
        operations=(
            SemanticOperationV1("a", "step"),
            SemanticOperationV1("a", "step"),
        ),
        digest="",
    )
    add("duplicate_identity", g, "INVALID_SEMANTIC_IR")

    # 18) contradictory constraints (opposing hard predicates)
    g = build_semantic_request_v1(
        request_id="fx_contra",
        entities=(
            SemanticEntityV1("in0", "input", "a", "str"),
            SemanticEntityV1("o0", "output", "r", "str"),
        ),
        operations=(
            SemanticOperationV1(
                "t0", "transform",
                input_entity_ids=("in0",), output_entity_ids=("o0",),
            ),
        ),
        constraints=(
            SemanticConstraintV1("c0", "bounded", "t0", negated=False),
            SemanticConstraintV1("c1", "bounded", "t0", negated=True),
        ),
        output_entity_ids=("o0",),
    )
    add("contradictory_constraint", g, "STRUCTURAL_CONTRADICTION")

    # 19) illegal cycle (dependency cycle — not a state recurrence)
    g = P0SemanticRequestV1(
        request_id="fx_cycle",
        entities=(SemanticEntityV1("e1", "input", "e", "str"),),
        operations=(
            SemanticOperationV1("a", "step"),
            SemanticOperationV1("b", "step"),
        ),
        dependencies=(
            SemanticDependencyV1("ab", "a", "b"),
            SemanticDependencyV1("ba", "b", "a"),
        ),
        digest="",
    )
    add("illegal_cycle", g, "INVALID_SEMANTIC_IR",
        "dependency cycle is not legitimate state recurrence")

    # 20) missing binding: declared output with no producer
    g = P0SemanticRequestV1(
        request_id="fx_nobinding",
        entities=(
            SemanticEntityV1("in0", "input", "a", "str"),
            SemanticEntityV1("o0", "output", "r", "str"),
        ),
        operations=(
            SemanticOperationV1(
                "t0", "transform", input_entity_ids=("in0",),
                output_entity_ids=(),
            ),
        ),
        output_entity_ids=("o0",),
        digest="",
    )
    add("missing_binding_declared_output", g, "INVALID_SEMANTIC_IR")

    # 21) malformed type: non-string entity id field
    g = P0SemanticRequestV1(
        request_id="fx_badtype",
        entities=(
            SemanticEntityV1(123, "input", "e", "str"),  # type: ignore[arg-type]
        ),
        operations=(
            SemanticOperationV1("a", "step"),
        ),
        digest="",
    )
    add("malformed_type", g, "INVALID_SEMANTIC_IR")

    # 22) impossible interface relation: interface entity bound to two ops
    g = build_semantic_request_v1(
        request_id="fx_ambig_iface",
        entities=(
            SemanticEntityV1("api", "interface", "http", ""),
            SemanticEntityV1("in0", "input", "a", "str"),
            SemanticEntityV1("o0", "output", "r", "str"),
        ),
        operations=(
            SemanticOperationV1(
                "t0", "a", input_entity_ids=("in0",),
                output_entity_ids=("o0",),
            ),
            SemanticOperationV1("t1", "b"),
        ),
        relations=(
            SemanticRelationV1("if0", "api", "interface", "t0"),
            SemanticRelationV1("if1", "api", "interface", "t1"),
        ),
        output_entity_ids=("o0",),
    )
    add("ambiguous_interface_binding", g, "AMBIGUOUS_BINDING")

    # 23) capacity overflow (same as 12, distinct name for the negative set)
    add("capacity_overflow", g_lane_overflow := build_semantic_request_v1(
        request_id="fx_cap_overflow",
        entities=tuple(
            SemanticEntityV1(f"k{i}", "input", f"k{i}", "str")
            for i in range(12)
        ),
        operations=tuple(
            SemanticOperationV1(f"opk{i}", "step", input_entity_ids=(f"k{i}",))
            for i in range(12)
        ),
    ), "DECOMPOSITION_REQUIRED")

    # 24) unsupported entity kind
    g = build_semantic_request_v1(
        request_id="fx_unk",
        entities=(SemanticEntityV1("w", "widget", "w", "str"),),
        operations=(SemanticOperationV1("a", "step",
                                       input_entity_ids=("w",)),),
    )
    add("unsupported_entity_kind", g, "UNSUPPORTED_SEMANTIC_SHAPE")

    # 25) arity contradiction (explicit quantity vs declared arity)
    g = build_semantic_request_v1(
        request_id="fx_arity",
        entities=(
            SemanticEntityV1("e1", "input", "a", "str"),
            SemanticEntityV1("e2", "input", "b", "str"),
        ),
        operations=(SemanticOperationV1(
            "a", "step", input_entity_ids=("e1",),
        ),),
        quantities=(
            SemanticQuantityV1("q", "a", "input_arity", "eq", 2),
        ),
    )
    add("arity_contradiction", g, "STRUCTURAL_CONTRADICTION")

    # 26) route to nonexistent node
    g = P0SemanticRequestV1(
        request_id="fx_route_ghost",
        entities=(SemanticEntityV1("e1", "input", "e", "str"),),
        operations=(
            SemanticOperationV1("a", "step"),
        ),
        relations=(
            SemanticRelationV1("rt", "a", "route", "ghost"),
        ),
        digest="",
    )
    add("route_to_nonexistent_node", g, "INVALID_SEMANTIC_IR")

    # 27) state_feeds self-recurrence (unexpressible in 529 vocabulary)
    g = build_semantic_request_v1(
        request_id="fx_selffeed",
        entities=(
            SemanticEntityV1("e1", "state", "e", "dict"),
        ),
        operations=(
            SemanticOperationV1(
                "a", "step", input_entity_ids=("e1",),
                output_entity_ids=("e1",),
            ),
        ),
        relations=(
            SemanticRelationV1("sf", "a", "state_feeds", "a"),
        ),
    )
    add("state_feeds_self_recurrence", g, "UNSUPPORTED_SEMANTIC_SHAPE")

    # 28) schedule cycle: precedes + state_feeds in opposite directions
    g = build_semantic_request_v1(
        request_id="fx_sched_cycle",
        entities=(
            SemanticEntityV1("e1", "state", "e", "dict"),
        ),
        operations=(
            SemanticOperationV1(
                "a", "step", input_entity_ids=("e1",),
                output_entity_ids=("e1",),
            ),
            SemanticOperationV1("b", "step"),
        ),
        dependencies=(
            SemanticDependencyV1("ab", "a", "b"),
        ),
        relations=(
            SemanticRelationV1("sf", "b", "state_feeds", "a"),
        ),
    )
    add("schedule_cycle", g, "STRUCTURAL_CONTRADICTION")

    return out


POSITIVE_FIXTURES: list[Fixture] = _named()


# ---------------------------------------------------------------------------
# Seeded random generators (mission 26)
# ---------------------------------------------------------------------------

_KINDS = ("input", "state", "interface", "output")
_PREDICATES = ("bounded", "monotone", "finite", "unique", "ordered")


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def gen_valid(seed: int) -> P0SemanticRequestV1:
    """Deterministic random VALID supported-subset graph.

    Shape: a layered DAG. Every layer i+1 operation depends (if any) on
    at least one operation of layer i, so the graph is always acyclic;
    relations are only between existing operations and respect
    direction (routes/state_feeds go from earlier to later rank;
    interfaces bind a distinct interface entity to exactly one op).
    """
    rng = _rng(seed * 2654435761 % (2**31))
    n_layers = rng.randint(1, 4)
    ops: list[SemanticOperationV1] = []
    deps: list[SemanticDependencyV1] = []
    ents: list[SemanticEntityV1] = []
    rels: list[SemanticRelationV1] = []
    cons: list[SemanticConstraintV1] = []
    outs: list[str] = []

    layer_ranges: list[tuple[int, int]] = []
    total_ops = 0
    for L in range(n_layers):
        count = rng.randint(1, 3)
        start = total_ops
        for j in range(count):
            idx = start + j
            nm = f"op{idx}"
            if L == 0:
                # layer 0: reads an input entity
                in_ent = f"in{idx}"
                ents.append(SemanticEntityV1(in_ent, "input",
                                              f"val.{in_ent}", "str"))
                inp = (in_ent,)
            else:
                # depends on 1-2 ops of the previous layer
                lo, hi = layer_ranges[L - 1]
                prev = list(range(lo, hi))
                k = rng.randint(1, min(2, len(prev)))
                for s in rng.sample(prev, k):
                    deps.append(SemanticDependencyV1(
                        f"d{idx}_{s}", f"op{s}", nm,
                    ))
                inp = ()
            if L == n_layers - 1 and rng.random() < 0.7:
                out_ent = f"out{idx}"
                ents.append(SemanticEntityV1(out_ent, "output",
                                              f"val.{out_ent}", "str"))
                outs.append(out_ent)
                outp = (out_ent,)
            else:
                outp = ()
            if rng.random() < 0.25:
                st = f"st{idx}"
                ents.append(SemanticEntityV1(st, "state", f"val.{st}",
                                              "dict"))
                outp = outp + (st,)
            ops.append(SemanticOperationV1(nm, f"kind{idx % 5}",
                                           input_entity_ids=inp,
                                           output_entity_ids=outp))
            if rng.random() < 0.15:
                ents.append(SemanticEntityV1(f"api{idx}", "interface",
                                              f"api.{idx}", ""))
                rels.append(SemanticRelationV1(
                    f"if{idx}", f"api{idx}", "interface", nm,
                ))
            if rng.random() < 0.2:
                cons.append(SemanticConstraintV1(
                    f"c{idx}", rng.choice(_PREDICATES), nm,
                    negated=rng.random() < 0.2,
                ))
        layer_ranges.append((start, total_ops + count))
        total_ops += count

    # cross relations between distinct ops, always across a layer gap
    # of >= 2 so a route/state_feeds locus always has a legal rank
    if n_layers >= 3 and rng.random() < 0.5:
        la = rng.randint(0, n_layers - 3)
        a = rng.randrange(*layer_ranges[la])
        b = rng.randrange(*layer_ranges[n_layers - 1])
        kind = rng.choice(("route", "state_feeds"))
        rels.append(SemanticRelationV1(
            f"x{seed}", f"op{a}", kind, f"op{b}",
        ))

    return build_semantic_request_v1(
        request_id=f"fuzz_{seed:07d}",
        entities=tuple(ents),
        operations=tuple(ops),
        dependencies=tuple(deps),
        relations=tuple(rels),
        constraints=tuple(cons),
        output_entity_ids=tuple(outs),
    )


_MALFORM_KINDS = (
    "dangling_dependency",
    "dangling_relation",
    "dangling_constraint",
    "dangling_output",
    "cycle",
    "duplicate_conflict",
    "duplicate_entity",
    "contradictory_constraint",
    "ambig_interface",
    "bad_type",
    "arity_conflict",
    "unsupported_kind",
    "self_state_feeds",
    "self_route",
    "route_to_ghost",
)


def _signed(
    unsigned: P0SemanticRequestV1,
) -> P0SemanticRequestV1:
    """Attach the authority digest to a raw (possibly malformed) request.

    The malformed generators build raw requests so the projector's own
    canonicalizer is what must reject them; but the authority digest must
    still be valid so that the DIGEST check does not shadow the SEMANTIC
    check under test. The digest is computed over the payload as the
    authority defines it, without re-validating structure.
    """
    return P0SemanticRequestV1(
        request_id=unsigned.request_id,
        entities=unsigned.entities,
        operations=unsigned.operations,
        constraints=unsigned.constraints,
        relations=unsigned.relations,
        dependencies=unsigned.dependencies,
        quantities=unsigned.quantities,
        output_entity_ids=unsigned.output_entity_ids,
        schema=unsigned.schema,
        digest=IR._digest(IR.semantic_request_payload(unsigned)),
    )


def gen_malformed(seed: int) -> P0SemanticRequestV1:
    """Deterministic random MALFORMED / adversarial graph.

    Each kind is built directly (bypassing build_semantic_request_v1
    where the authority would reject first) so the projector's own
    canonicalizer is what must reject it deterministically. The authority
    digest is attached so the digest check does not shadow the semantic
    check under test.
    """
    rng = _rng(seed * 40503 + 7)
    kind = _MALFORM_KINDS[seed % len(_MALFORM_KINDS)]
    rid = f"mf_{seed:07d}"
    base_ent = (SemanticEntityV1("e0", "input", "v", "str"),)

    if kind == "dangling_dependency":
        return _signed(P0SemanticRequestV1(
            request_id=rid,
            entities=base_ent,
            operations=(
                SemanticOperationV1("a", "s"),
                SemanticOperationV1("b", "s"),
            ),
            dependencies=(
                SemanticDependencyV1("d1", "a", "b"),
                SemanticDependencyV1("d2", "b", "ghost"),
            ),
            digest="",
        ))
    if kind == "dangling_relation":
        return _signed(P0SemanticRequestV1(
            request_id=rid,
            entities=base_ent,
            operations=(SemanticOperationV1("a", "s"),),
            relations=(SemanticRelationV1("r1", "a", "route", "ghost"),),
            digest="",
        ))
    if kind == "dangling_constraint":
        return _signed(P0SemanticRequestV1(
            request_id=rid,
            entities=base_ent,
            operations=(SemanticOperationV1("a", "s"),),
            constraints=(SemanticConstraintV1("c1", "bounded", "ghost"),),
            digest="",
        ))
    if kind == "dangling_output":
        return _signed(P0SemanticRequestV1(
            request_id=rid,
            entities=base_ent + (
                SemanticEntityV1("o0", "output", "v", "str"),
            ),
            operations=(SemanticOperationV1(
                "a", "s", input_entity_ids=("e0",),
            ),),
            output_entity_ids=("o0",),
            digest="",
        ))
    if kind == "cycle":
        return _signed(P0SemanticRequestV1(
            request_id=rid,
            entities=base_ent,
            operations=(
                SemanticOperationV1("a", "s"),
                SemanticOperationV1("b", "s"),
                SemanticOperationV1("c", "s"),
            ),
            dependencies=(
                SemanticDependencyV1("d1", "a", "b"),
                SemanticDependencyV1("d2", "b", "c"),
                SemanticDependencyV1("d3", "c", "a"),
            ),
            digest="",
        ))
    if kind == "duplicate_conflict":
        return _signed(P0SemanticRequestV1(
            request_id=rid,
            entities=base_ent,
            operations=(
                SemanticOperationV1("a", "s1"),
                SemanticOperationV1("a", "s2"),
            ),
            digest="",
        ))
    if kind == "duplicate_entity":
        return _signed(P0SemanticRequestV1(
            request_id=rid,
            entities=base_ent
            + (SemanticEntityV1("e0", "input", "x", "i"),),
            operations=(SemanticOperationV1("a", "s"),),
            digest="",
        ))
    if kind == "contradictory_constraint":
        return _signed(P0SemanticRequestV1(
            request_id=rid,
            entities=base_ent,
            operations=(SemanticOperationV1("a", "s"),),
            constraints=(
                SemanticConstraintV1("c1", "bounded", "a", negated=False),
                SemanticConstraintV1("c2", "bounded", "a", negated=True),
            ),
            digest="",
        ))
    if kind == "ambig_interface":
        return _signed(P0SemanticRequestV1(
            request_id=rid,
            entities=base_ent + (
                SemanticEntityV1("api", "interface", "i", ""),
            ),
            operations=(
                SemanticOperationV1("a", "s"),
                SemanticOperationV1("b", "s"),
            ),
            relations=(
                SemanticRelationV1("r1", "api", "interface", "a"),
                SemanticRelationV1("r2", "api", "interface", "b"),
            ),
            digest="",
        ))
    if kind == "bad_type":
        return _signed(P0SemanticRequestV1(
            request_id=rid,
            entities=(SemanticEntityV1(7, "input", "v", "str"),),  # type: ignore[arg-type]
            operations=(SemanticOperationV1("a", "s"),),
            digest="",
        ))
    if kind == "arity_conflict":
        return _signed(P0SemanticRequestV1(
            request_id=rid,
            entities=base_ent,
            operations=(SemanticOperationV1("a", "s"),),
            quantities=(
                SemanticQuantityV1("q", "a", "input_arity", "eq", 3),
            ),
            digest="",
        ))
    if kind == "unsupported_kind":
        return _signed(P0SemanticRequestV1(
            request_id=rid,
            entities=(SemanticEntityV1("w", "widget", "v", "str"),),
            operations=(SemanticOperationV1("a", "s"),),
            digest="",
        ))
    if kind == "self_state_feeds":
        return _signed(P0SemanticRequestV1(
            request_id=rid,
            entities=(SemanticEntityV1("s0", "state", "v", "dict"),),
            operations=(SemanticOperationV1("a", "s"),),
            relations=(SemanticRelationV1("r1", "a", "state_feeds", "a"),),
            digest="",
        ))
    if kind == "self_route":
        return _signed(P0SemanticRequestV1(
            request_id=rid,
            entities=base_ent,
            operations=(SemanticOperationV1("a", "s"),),
            relations=(SemanticRelationV1("r1", "a", "route", "a"),),
            digest="",
        ))
    # route_to_ghost
    return _signed(P0SemanticRequestV1(
        request_id=rid,
        entities=base_ent,
        operations=(SemanticOperationV1("a", "s"),),
        relations=(SemanticRelationV1("r1", "a", "route", "missing"),),
        digest="",
    ))
