"""ProjectionTraceV1 construction: proof-carrying derivation record.

The trace is a deterministic, machine-readable replay of how the seed was
derived:

  * every placement action is recorded in application order;
  * before/after digests are recomputed by replaying the actions from a
    VOID grid — so the trace independently proves the final grid;
  * sequence numbers, rule identifiers, and semantic identities are
    explicit; no timestamps, object ids, or UUIDs;
  * the trace digest binds every event.
"""
from __future__ import annotations

from elpis_p0.structural_residual import GRID_SIZE

from .contracts import (
    EV_DECLARED_FEATURE_DERIVED,
    EV_ACTIVE_RESIDUAL_DERIVED,
    EV_SEMANTIC_NODE_ACCEPTED,
    EV_DEPENDENCY_ACCEPTED,
    EV_TYPE_RELATION_ACCEPTED,
    EV_REJECTION,
    PROJECTION_DOMAIN,
    ProjectionTraceEvent,
    ProjectionTraceV1,
    canonical_bytes,
    grid_digest,
    sha256_hex,
)
from . import rules as R

_VOID = 0


def _replay(
    actions: list[dict],
) -> tuple[list[int], list[str]]:
    """Replay placement actions from VOID; return (final_grid, digests)."""
    grid = [_VOID] * GRID_SIZE
    digests: list[str] = [grid_digest(tuple(grid))]
    for action in actions:
        c = action["cell"]
        token = action["detail"].get("token")
        if token is not None and c is not None:
            grid[c] = int(token)
        digests.append(grid_digest(tuple(grid)))
    return grid, digests


def build_trace(
    content_digest: str,
    payload: dict,
    actions: list[dict],
    invariants,
    declared_features: tuple[int, ...],
    active_residual: tuple[int, ...],
    residual_ids: tuple[str, ...],
    ruleset_digest: str,
) -> ProjectionTraceV1:
    """Assemble the trace from semantic acceptance + placement actions."""
    events: list[ProjectionTraceEvent] = []
    seq = 0
    grid, digests = _replay(actions)

    # 1) semantic node acceptance (explicit facts entering projection)
    for e in sorted(payload["entities"], key=lambda x: x["entity_id"]):
        events.append(
            ProjectionTraceEvent(
                seq=seq,
                event_type=EV_SEMANTIC_NODE_ACCEPTED,
                rule_id=R.R_ENTITY_ACCEPT,
                semantic_ids=(e["entity_id"],),
                loci=(),
                before_digest=digests[0],
                after_digest=digests[0],
                detail={
                    "kind": e["kind"],
                    "identity": e["identity"],
                    "data_type": e.get("data_type", ""),
                },
            )
        )
        seq += 1
    for o in sorted(payload["operations"],
                   key=lambda x: x["operation_id"]):
        events.append(
            ProjectionTraceEvent(
                seq=seq,
                event_type=EV_SEMANTIC_NODE_ACCEPTED,
                rule_id=R.R_INPUT_ACCEPT,
                semantic_ids=(o["operation_id"],),
                loci=(),
                before_digest=digests[0],
                after_digest=digests[0],
                detail={
                    "operator": o["operator"],
                    "input_entity_ids": list(o["input_entity_ids"]),
                    "output_entity_ids": list(o["output_entity_ids"]),
                },
            )
        )
        seq += 1
    for d in sorted(payload["dependencies"],
                   key=lambda x: x["dependency_id"]):
        events.append(
            ProjectionTraceEvent(
                seq=seq,
                event_type=EV_DEPENDENCY_ACCEPTED,
                rule_id=R.R_DAG_TOPO,
                semantic_ids=(
                    d["dependency_id"],
                    d["predecessor_operation_id"],
                    d["successor_operation_id"],
                ),
                loci=(),
                before_digest=digests[0],
                after_digest=digests[0],
                detail={"kind": d["kind"]},
            )
        )
        seq += 1
    for r in sorted(payload["relations"],
                   key=lambda x: x["relation_id"]):
        events.append(
            ProjectionTraceEvent(
                seq=seq,
                event_type=EV_TYPE_RELATION_ACCEPTED,
                rule_id=R.R_CONTRACT_ACCEPT,
                semantic_ids=(
                    r["relation_id"],
                    r["source_id"],
                    r["target_id"],
                ),
                loci=(),
                before_digest=digests[0],
                after_digest=digests[0],
                detail={
                    "predicate": r["predicate"],
                    "negated": r["negated"],
                },
            )
        )
        seq += 1

    # 2) placement actions (lane assignment, role, route, memory,
    #    constraint, interface, terminal) with replayed digests
    for i, action in enumerate(actions):
        c = action["cell"]
        events.append(
            ProjectionTraceEvent(
                seq=seq,
                event_type=action["event_type"],
                rule_id=action["rule_id"],
                semantic_ids=tuple(action["semantic_ids"]),
                loci=(c,) if c is not None else (),
                before_digest=digests[i],
                after_digest=digests[i + 1],
                detail=dict(action["detail"]),
            )
        )
        seq += 1

    # 3) mask + residual derivation events
    events.append(
        ProjectionTraceEvent(
            seq=seq,
            event_type="FROZEN_LOCUS_DECLARED",
            rule_id=R.R_MASK_DISJOINT,
            semantic_ids=(),
            loci=(),
            before_digest=digests[-1],
            after_digest=digests[-1],
            detail={
                "invariant": "frozen_mask XOR writable_mask == full grid",
                "rule": "R14.MASK_DISJOINT",
            },
        )
    )
    seq += 1
    events.append(
        ProjectionTraceEvent(
            seq=seq,
            event_type=EV_DECLARED_FEATURE_DERIVED,
            rule_id=R.R_FEATURE_DERIVE,
            semantic_ids=tuple(sorted(
                i.invariant_id for i in invariants
            )),
            loci=(),
            before_digest=digests[-1],
            after_digest=digests[-1],
            detail={
                "declared_count": sum(declared_features),
                "width": len(declared_features),
                "authority": "structural_trm_features.encode_constraint_state",
            },
        )
    )
    seq += 1
    events.append(
        ProjectionTraceEvent(
            seq=seq,
            event_type=EV_ACTIVE_RESIDUAL_DERIVED,
            rule_id=R.R_RESIDUAL_DERIVE,
            semantic_ids=tuple(sorted(residual_ids)),
            loci=(),
            before_digest=digests[-1],
            after_digest=digests[-1],
            detail={
                "active_count": sum(active_residual),
                "unsatisfied": list(residual_ids),
                "authority": "elpis_p0.structural_residual.residual",
            },
        )
    )
    seq += 1

    payload_dict = {
        "schema": "c2r6p0.projection-trace.v1",
        "semantic_input_digest": content_digest,
        "rule_set_digest": ruleset_digest,
        "events": [e.to_dict() for e in events],
    }
    digest = sha256_hex(canonical_bytes(payload_dict))
    return ProjectionTraceV1(
        schema="c2r6p0.projection-trace.v1",
        events=tuple(events),
        trace_digest=digest,
    )


def build_rejection_trace(
    content_digest: str,
    ruleset_digest: str,
    status: str,
    error,
    rule: str = R.R_CONTRACT_ACCEPT,
    detail: dict | None = None,
) -> ProjectionTraceV1:
    """Trace for a typed rejection (still canonical, still hashable)."""
    ev = ProjectionTraceEvent(
        seq=0,
        event_type=EV_REJECTION,
        rule_id=rule,
        semantic_ids=(error.semantic_identity,) if error.semantic_identity else (),
        loci=(),
        before_digest="",
        after_digest="",
        detail={
            "status": status,
            "code": error.code,
            "error_detail": error.detail,
            **({} if detail is None else detail),
        },
    )
    events = (ev,)
    payload_dict = {
        "schema": "c2r6p0.projection-trace.v1",
        "semantic_input_digest": content_digest,
        "rule_set_digest": ruleset_digest,
        "events": [e.to_dict() for e in events],
    }
    digest = sha256_hex(canonical_bytes(payload_dict))
    return ProjectionTraceV1(
        schema="c2r6p0.projection-trace.v1",
        events=events,
        trace_digest=digest,
    )
