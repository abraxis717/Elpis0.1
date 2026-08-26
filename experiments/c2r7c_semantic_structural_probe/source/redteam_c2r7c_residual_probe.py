#!/usr/bin/env python3
"""Gate instrument for the structural residual oracle. Not production.

Generates ECS component fixtures, compiles each to a bounded structural
refinement problem, and runs refiners against it:

    null          identity map
    shadow        the shipped ShadowTRMProposer behaviour (cell 80, cell 63)
    random        uniform legal moves
    search        generic residual-descent hill climb with restarts
    cheat_frozen  writes a frozen locus -- must be rejected
    cheat_invent  invents an operational locus -- must be rejected

The search refiner receives exactly ``(grid, writable_mask, invariants)``.
It is structurally incapable of reading a semantic identifier: the sidecar
is never passed to it. Every transition is checked by
``validate_transition``, so a refiner that writes a frozen locus or invents
an operational token fails closed rather than scoring.

Read-only. No network. Deterministic given --seed.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for _p in (
    "components/Pipeline/P0ControlProtocol/src",
    "components/TRMFractalSpine/src",
    "components/Grid81StructuralSemantics/src",
    "components",
    "src",
):
    _s = str(REPO / _p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from elpis_p0.contracts import BasisToken  # noqa: E402
from elpis_p0.structural_residual import (  # noqa: E402
    LANES,
    OPERATIONAL_TOKENS,
    PLACEABLE_TOKENS,
    RANKS,
    DecompositionRequired,
    LaneBindingV1,
    StructuralInvariantV1,
    StructuralSchemaError,
    build_structural_schema,
    capacity_requirements,
    cell,
    decomposition_measure,
    halt_score,
    is_resolved,
    materialisable,
    quiescent,
    residual,
    validate_transition,
)

VOID = int(BasisToken.VOID)


# ------------------------------------------------------------- fixture gen


def make_fixture(rng: random.Random, lane_count: int):
    """Build a satisfiable component fixture.

    A hidden schedule is drawn, invariants consistent with it are emitted, and
    the schedule is then DISCARDED. The oracle checks; it never supplies. The
    refiner is not required to rediscover this particular schedule -- any grid
    with an empty residual is accepted.
    """
    lanes = list(range(lane_count))
    order = lanes[:]
    rng.shuffle(order)
    # distinct ranks, ascending, leaving room for routes/memory/constraints
    ranks = sorted(rng.sample(range(0, RANKS - 2), lane_count))
    schedule = {lane: rank for lane, rank in zip(order, ranks)}

    bindings = []
    for position, lane in enumerate(order):
        if position == 0:
            token = int(BasisToken.INPUT)
        elif position == lane_count - 1:
            token = int(BasisToken.OUTPUT)
        else:
            token = int(BasisToken.TRANSFORM)
        bindings.append(LaneBindingV1(
            lane=lane,
            semantic_id=f"op.{position}.{rng.randrange(1 << 20):05x}",
            role="operation",
            operational_token=token,
        ))

    invariants = [StructuralInvariantV1("terminal", "TERMINAL_RESOLUTION", ())]
    for lane in lanes:
        invariants.append(
            StructuralInvariantV1(f"occupancy.{lane}", "LANE_SINGLE_OCCUPANCY", (lane,))
        )
    for i in range(len(order) - 1):
        a, b = order[i], order[i + 1]
        invariants.append(
            StructuralInvariantV1(f"precedes.{a}.{b}", "PRECEDES", (a, b))
        )

    spans = [
        (a, b) for a in lanes for b in lanes
        if a != b and schedule[b] - schedule[a] >= 2
    ]
    rng.shuffle(spans)
    for a, b in spans[:rng.randint(0, 2)]:
        invariants.append(
            StructuralInvariantV1(f"route.{a}.{b}", "CROSS_LANE_ROUTE", (a, b))
        )
    rng.shuffle(spans)
    for a, b in spans[:rng.randint(0, 2)]:
        invariants.append(
            StructuralInvariantV1(f"memory.{a}.{b}", "MEMORY_SPAN", (a, b))
        )

    if lane_count >= 3 and spans and rng.random() < 0.5:
        a, b = spans[0]
        outside = [
            c for c in lanes
            if c not in (a, b) and not (schedule[a] < schedule[c] < schedule[b])
        ]
        if outside:
            c = rng.choice(outside)
            invariants.append(
                StructuralInvariantV1(f"hazard.{a}.{b}.{c}",
                                      "MUTATION_HAZARD", (a, b, c))
            )

    tail = order[-1]
    invariants.append(
        StructuralInvariantV1(f"constraint.{tail}", "CONSTRAINT_AFTER", (tail,))
    )
    invariants.append(
        StructuralInvariantV1(f"interface.{tail}", "INTERFACE_TERMINAL", (tail,))
    )

    schema = build_structural_schema(
        semantic_request_digest=f"{rng.randrange(1 << 64):064x}",
        lane_bindings=tuple(bindings),
        invariants=tuple(invariants),
    )
    schema.validate()
    del schedule  # the answer does not leave this function
    return schema


# ---------------------------------------------------------------- refiners


def _legal_moves(grid, mask):
    """Neighbourhood over (grid, mask) only. No schema, no sidecar."""
    moves = []
    op_lanes = {}
    for lane in range(LANES):
        for rank in range(RANKS):
            if grid[cell(rank, lane)] in OPERATIONAL_TOKENS:
                op_lanes[lane] = rank
    for index in range(len(grid)):
        if not mask[index]:
            continue
        if grid[index] in OPERATIONAL_TOKENS:
            continue
        for token in PLACEABLE_TOKENS:
            if token != grid[index]:
                moves.append(("set", index, token))
    for lane, current in op_lanes.items():
        for rank in range(RANKS):
            target = cell(rank, lane)
            if rank == current or not mask[target]:
                continue
            if grid[target] in OPERATIONAL_TOKENS:
                continue
            moves.append(("move", lane, rank))
    return moves


def _apply(grid, move):
    out = list(grid)
    if move[0] == "set":
        _, index, token = move
        out[index] = token
    else:
        _, lane, rank = move
        current = next(
            r for r in range(RANKS)
            if grid[cell(r, lane)] in OPERATIONAL_TOKENS
        )
        token = grid[cell(current, lane)]
        out[cell(current, lane)] = VOID
        out[cell(rank, lane)] = token
    return tuple(out)


def refine_null(grid, mask, invariants, rng, budget):
    return grid, 0


def refine_shadow(grid, mask, invariants, rng, budget):
    """The shipped ShadowTRMProposer, reduced to its two writes."""
    out = list(grid)
    if mask[80]:
        out[80] = int(BasisToken.RESOLUTION)
    if int(BasisToken.CONSTRAINT) not in out[63:72] and mask[63]:
        out[63] = int(BasisToken.CONSTRAINT)
    return tuple(out), 1


def refine_random(grid, mask, invariants, rng, budget):
    current = grid
    for step in range(budget):
        moves = _legal_moves(current, mask)
        if not moves:
            break
        current = _apply(current, rng.choice(moves))
        if not residual(current, invariants):
            return current, step + 1
    return current, budget


def _cost(grid, invariants):
    return len(residual(grid, invariants)) + sum(
        1 for v in grid if v == int(BasisToken.EXPANSION)
    )


def refine_search(grid, mask, invariants, rng, budget,
                  restarts=8, plateau=25):
    """Generic residual descent. Inputs: grid, mask, invariants. Nothing else.

    No schema, no lane bindings, no semantic identifiers are in scope.
    """
    best = grid
    best_cost = _cost(grid, invariants)
    iterations = 0

    for _ in range(restarts):
        current = grid
        cost = _cost(current, invariants)
        stuck = 0
        while iterations < budget:
            if cost == 0:
                return current, iterations
            iterations += 1
            moves = _legal_moves(current, mask)
            if not moves:
                break
            rng.shuffle(moves)
            best_move, best_move_cost = None, cost
            for move in moves:
                candidate_cost = _cost(_apply(current, move), invariants)
                if candidate_cost < best_move_cost:
                    best_move, best_move_cost = move, candidate_cost
            if best_move is not None:
                current, cost = _apply(current, best_move), best_move_cost
                stuck = 0
            else:
                stuck += 1
                if stuck > plateau:
                    break
                for _ in range(rng.randint(1, 3)):
                    moves = _legal_moves(current, mask)
                    if moves:
                        current = _apply(current, rng.choice(moves))
                cost = _cost(current, invariants)
            if cost < best_cost:
                best, best_cost = current, cost
        if best_cost == 0:
            break
    return best, iterations


def refine_cheat_frozen(grid, mask, invariants, rng, budget):
    """Writes a frozen locus. Must be caught by validate_transition."""
    out = list(grid)
    frozen = next((i for i in range(len(grid)) if not mask[i]), 0)
    out[frozen] = int(BasisToken.ROUTE)
    return tuple(out), 1


def refine_cheat_invent(grid, mask, invariants, rng, budget):
    """Invents an operational locus. Must be caught by validate_transition."""
    out = list(grid)
    target = next(
        (i for i in range(len(grid)) if mask[i] and grid[i] == VOID), 0
    )
    out[target] = int(BasisToken.TRANSFORM)
    return tuple(out), 1


REFINERS = {
    "null": refine_null,
    "shadow": refine_shadow,
    "random": refine_random,
    "search": refine_search,
    "cheat_frozen": refine_cheat_frozen,
    "cheat_invent": refine_cheat_invent,
}


# ------------------------------------------------------------------ driver


def run_case(schema, name, rng, budget):
    fn = REFINERS[name]
    grid = schema.initial_grid
    try:
        final, steps = fn(grid, schema.writable_mask, schema.invariants, rng, budget)
        validate_transition(grid, final, schema)
        authority_ok = True
        error = ""
    except StructuralSchemaError as exc:
        return {
            "refiner": name, "resolved": False, "authority_violation": True,
            "error": str(exc), "steps": 0,
        }
    return {
        "refiner": name,
        "resolved": bool(is_resolved(final, schema)),
        "residual_remaining": len(residual(final, schema.invariants)),
        "quiescent": quiescent(final),
        "materialisable": materialisable(final, schema),
        "halt_score": round(halt_score(final, schema), 6),
        "void_fraction": round(sum(1 for v in final if v == VOID) / 81.0, 4),
        "steps": steps,
        "authority_violation": not authority_ok,
        "error": error,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="redteam_c2r7c_residual_probe")
    parser.add_argument("--cases", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--budget", type=int, default=3000)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    results = {name: {"resolved": 0, "total": 0, "authority_violations": 0}
               for name in REFINERS}
    per_case = []
    contradictions: list[str] = []

    for index in range(args.cases):
        lane_count = rng.randint(3, 6)
        schema = make_fixture(rng, lane_count)
        initial_residual = residual(schema.initial_grid, schema.invariants)
        if not initial_residual:
            contradictions.append(
                f"case {index}: projector emitted a fully resolved grid; "
                "the fixture requires no refinement"
            )
        case = {
            "case": index,
            "lanes": lane_count,
            "invariants": len(schema.invariants),
            "initial_residual": len(initial_residual),
            "initial_halt_score": round(halt_score(schema.initial_grid, schema), 6),
            "writable_cells": sum(schema.writable_mask),
            "runs": [],
        }
        for name in REFINERS:
            outcome = run_case(schema, name, random.Random(args.seed + index), args.budget)
            case["runs"].append(outcome)
            results[name]["total"] += 1
            results[name]["resolved"] += int(outcome.get("resolved", False))
            results[name]["authority_violations"] += int(
                outcome.get("authority_violation", False)
            )
        per_case.append(case)

    for name in ("cheat_frozen", "cheat_invent"):
        if results[name]["authority_violations"] != results[name]["total"]:
            contradictions.append(
                f"AUTHORITY FAILURE: {name} was not rejected on every case"
            )

    for name in ("null", "shadow", "cheat_frozen", "cheat_invent"):
        if results[name]["resolved"]:
            contradictions.append(
                f"ABLATION FAILURE: {name} refiner resolved "
                f"{results[name]['resolved']} case(s); the projector is solving "
                "the problem it claims to leave open"
            )

    capacity = []
    for lanes, chain, cross, mem in ((4, 3, 1, 1), (9, 4, 2, 2), (6, 8, 3, 3)):
        req = capacity_requirements(lanes, chain, cross, mem)
        fits = req[0] <= 8 and req[1] <= RANKS and req[2] <= 81
        capacity.append({
            "lanes_required": req[0], "ranks_required": req[1],
            "loci_required": req[2], "fits": fits,
            "measure": decomposition_measure(*req),
        })
    try:
        build_structural_schema(
            semantic_request_digest="0" * 64,
            lane_bindings=tuple(
                LaneBindingV1(lane=i, semantic_id=f"x{i}", role="operation",
                              operational_token=int(BasisToken.TRANSFORM))
                for i in range(9)
            ),
            invariants=(),
        )
        contradictions.append("nine semantic lanes accepted; capacity not enforced")
        overflow = "ACCEPTED"
    except DecompositionRequired as exc:
        overflow = f"DECOMPOSITION_REQUIRED: {exc}"

    report = {
        "schema": "elpis.redteam-c2r7c-residual-probe.v1",
        "role": "GATE_INSTRUMENT_NOT_PRODUCTION",
        "seed": args.seed,
        "cases": args.cases,
        "budget": args.budget,
        "summary": {
            name: {
                **stats,
                "resolve_rate": round(stats["resolved"] / max(1, stats["total"]), 6),
            }
            for name, stats in results.items()
        },
        "capacity_probe": capacity,
        "overflow_probe": overflow,
        "contradictions": contradictions,
        "per_case": per_case,
    }
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    if not args.quiet:
        print(text)
    return 1 if contradictions else 0


if __name__ == "__main__":
    raise SystemExit(main())
