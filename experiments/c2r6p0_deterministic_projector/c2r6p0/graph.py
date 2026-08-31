"""Explicit dependency/schedule graph analysis.

Builds the schedule DAG (precedes dependencies + route/state_feeds value-flow
relations, each with a minimum rank gap) and computes deterministic
topological order, components, roots, sinks, and the longest chain.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import rules as R
from .canonicalize import _schedule_dag_edges, _reject
from .contracts import ErrorCode, ProjectionError, ProjectionStatus
from .taxonomy import ROUTE_PREDICATE, STATE_FEEDS_PREDICATE


@dataclass(frozen=True)
class ScheduleEdge:
    src: str
    dst: str
    gap: int  # minimum rank separation: rank(dst) >= rank(src) + gap
    origin: str  # "precedes:<dep_id>" | "route:<rel_id>" | "state_feeds:<rel_id>"


@dataclass(frozen=True)
class GraphAnalysis:
    op_ids: tuple[str, ...]
    edges: tuple[ScheduleEdge, ...]
    topo_order: tuple[str, ...]      # deterministic (Kahn, lexicographic ties)
    dist: dict[str, int]              # longest-path distance (rank offset)
    longest_chain: int                 # max dist + 1 (node count)
    components: tuple[tuple[str, ...], ...]
    multiple_components: bool
    roots: tuple[str, ...]             # in-degree zero in schedule DAG
    sinks: tuple[str, ...]
    multi_root_note: bool               # informational (mission 9)
    multi_sink_note: bool


def analyze(payload: dict, ) -> tuple[GraphAnalysis | None, ProjectionError | None]:
    """Analyze the schedule graph. Deterministic; no arbitrary tie-breaks."""
    op_ids = tuple(sorted(o["operation_id"] for o in payload["operations"]))
    if not op_ids:
        return None, _reject(
            ProjectionStatus.INVALID_SEMANTIC_IR,
            ErrorCode.INVALID_SEMANTIC_IR,
            R.R_DAG_TOPO,
            {"reason": "no_operations"},
        )

    # dedupe edges (same pair may be declared via multiple relations; the
    # strongest gap wins — still a deterministic, explicit fact)
    best: dict[tuple[str, str], tuple[int, str]] = {}
    for s, d, gap in _schedule_dag_edges(payload):
        cur = best.get((s, d))
        if cur is None or gap > cur[0]:
            best[(s, d)] = (gap, "edge")

    # annotate origins for the trace
    origins: dict[tuple[str, str], list[str]] = {}
    for dep in payload["dependencies"]:
        origins.setdefault(
            (dep["predecessor_operation_id"],
             dep["successor_operation_id"]), []
        ).append(f"precedes:{dep['dependency_id']}")
    for rel in payload["relations"]:
        if rel["predicate"] == ROUTE_PREDICATE:
            origins.setdefault(
                (rel["source_id"], rel["target_id"]), []
            ).append(f"route:{rel['relation_id']}")
        elif rel["predicate"] == STATE_FEEDS_PREDICATE:
            origins.setdefault(
                (rel["source_id"], rel["target_id"]), []
            ).append(f"state_feeds:{rel['relation_id']}")

    edges = tuple(
        ScheduleEdge(
            src=s, dst=d, gap=gap,
            origin=";".join(sorted(origins.get((s, d), []))),
        )
        for (s, d), (gap, _) in sorted(best.items())
    )

    # Kahn with lexicographic ready-set: deterministic topo order.
    indeg = {op: 0 for op in op_ids}
    out: dict[str, list[str]] = {op: [] for op in op_ids}
    for e in edges:
        out[e.src].append(e.dst)
        indeg[e.dst] += 1
    ready = sorted(op for op in op_ids if indeg[op] == 0)
    topo: list[str] = []
    indeg_work = dict(indeg)
    while ready:
        node = ready.pop(0)
        topo.append(node)
        for t in out[node]:
            indeg_work[t] -= 1
            if indeg_work[t] == 0:
                ready.append(t)
        ready.sort()
    if len(topo) != len(op_ids):
        # unreachable here (canonicalize rejects cycles first) but fail closed
        cyclic = sorted(op for op in op_ids if indeg_work[op] > 0)
        return None, _reject(
            ProjectionStatus.STRUCTURAL_CONTRADICTION,
            ErrorCode.CONTRADICTION,
            R.R_CYCLE_REJECT,
            {"operations": cyclic, "reason": "schedule_dag_cycle"},
            ",".join(cyclic),
        )

    # longest-path distances (rank offsets)
    dist: dict[str, int] = {op: 0 for op in op_ids}
    for node in topo:
        for e in edges:
            if e.src == node:
                cand = dist[node] + e.gap
                if cand > dist[e.dst]:
                    dist[e.dst] = cand
    longest_chain = 1 + max(dist.values())

    # connected components (undirected reachability over schedule edges)
    adj: dict[str, set[str]] = {op: set() for op in op_ids}
    for e in edges:
        adj[e.src].add(e.dst)
        adj[e.dst].add(e.src)
    seen: set[str] = set()
    components_list: list[tuple[str, ...]] = []
    for op in op_ids:
        if op in seen:
            continue
        stack = [op]
        comp: list[str] = []
        seen.add(op)
        while stack:
            n = stack.pop()
            comp.append(n)
            for t in sorted(adj[n]):
                if t not in seen:
                    seen.add(t)
                    stack.append(t)
        components_list.append(tuple(sorted(comp)))
    components = tuple(sorted(components_list))

    indeg_final = {op: 0 for op in op_ids}
    outdeg = {op: 0 for op in op_ids}
    for e in edges:
        indeg_final[e.dst] += 1
        outdeg[e.src] += 1
    roots = tuple(sorted(op for op in op_ids if indeg_final[op] == 0))
    sinks = tuple(sorted(op for op in op_ids if outdeg[op] == 0))

    return GraphAnalysis(
        op_ids=op_ids,
        edges=edges,
        topo_order=tuple(topo),
        dist=dist,
        longest_chain=longest_chain,
        components=components,
        multiple_components=len(components) > 1,
        roots=roots,
        sinks=sinks,
        multi_root_note=len(roots) > 1,
        multi_sink_note=len(sinks) > 1,
    ), None
