"""Experimental C2R7-C structural TRM dataset generator.

Teacher inputs:
    current Grid81
    writable mask
    declared structural invariants

The discarded fixture schedule, semantic identifiers, and any final target
grid are not in scope for the teacher.

Only cost-decreasing teacher transitions are emitted as training examples.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import runpy
import sys
import time
import types

from structural_trm_features import (
    FEATURE_WIDTH,
    VOCABULARY_DIGEST,
    encode_constraint_state,
)


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE = HERE / "source"
PROBE = SOURCE / "redteam_c2r7c_residual_probe.py"
EXP_P0 = SOURCE / "elpis_p0"
CANON_P0 = REPO / "components/Pipeline/P0ControlProtocol/src/elpis_p0"
FRACTAL_SRC = REPO / "components/TRMFractalSpine/src"


def _load_probe_namespace() -> dict:
    """Load the frozen Claude probe without executing its main()."""
    if str(FRACTAL_SRC) not in sys.path:
        sys.path.insert(0, str(FRACTAL_SRC))

    pkg = types.ModuleType("elpis_p0")
    pkg.__package__ = "elpis_p0"
    pkg.__path__ = [str(EXP_P0), str(CANON_P0)]
    sys.modules["elpis_p0"] = pkg

    return runpy.run_path(
        str(PROBE),
        run_name="c2r7c_trm_dataset_probe_source",
    )


def teacher_search_trajectory(
    grid,
    mask,
    invariants,
    rng,
    budget,
    *,
    legal_moves,
    apply_move,
    cost_fn,
    restarts=8,
    plateau=25,
):
    """Residual-descent teacher with recorded improving transitions.

    This is the probe's search algorithm with one instrumentation addition:
    whenever a strictly lower-cost move is accepted, (before, after) is
    recorded.

    There is no schema, semantic sidecar, hidden schedule, or final grid in
    this function's inputs.
    """
    best = grid
    best_cost = cost_fn(grid, invariants)
    iterations = 0
    transitions = []

    for _ in range(restarts):
        current = grid
        cost = cost_fn(current, invariants)
        stuck = 0

        while iterations < budget:
            if cost == 0:
                return current, iterations, tuple(transitions)

            iterations += 1
            moves = legal_moves(current, mask)
            if not moves:
                break

            rng.shuffle(moves)
            best_move = None
            best_move_cost = cost

            for move in moves:
                candidate_cost = cost_fn(
                    apply_move(current, move),
                    invariants,
                )
                if candidate_cost < best_move_cost:
                    best_move = move
                    best_move_cost = candidate_cost

            if best_move is not None:
                before = current
                before_cost = cost

                current = apply_move(current, best_move)
                cost = best_move_cost
                stuck = 0

                transitions.append(
                    (
                        iterations,
                        before,
                        current,
                        before_cost,
                        cost,
                    )
                )
            else:
                stuck += 1
                if stuck > plateau:
                    break

                for _ in range(rng.randint(1, 3)):
                    moves = legal_moves(current, mask)
                    if moves:
                        current = apply_move(
                            current,
                            rng.choice(moves),
                        )
                cost = cost_fn(current, invariants)

            if cost < best_cost:
                best = current
                best_cost = cost

        if best_cost == 0:
            break

    return best, iterations, tuple(transitions)


def _sparse(bits):
    return [
        i
        for i, value in enumerate(bits)
        if value
    ]


def _row_digest(row):
    raw = json.dumps(
        row,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--budget", type=int, default=250)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    ns = _load_probe_namespace()

    make_fixture = ns["make_fixture"]
    residual = ns["residual"]
    is_resolved = ns["is_resolved"]
    legal_moves = ns["_legal_moves"]
    apply_move = ns["_apply"]
    cost_fn = ns["_cost"]

    forbidden = {
        "schedule",
        "hidden_schedule",
        "target_grid",
        "expected_grid",
        "solution_grid",
        "final_grid",
        "answer_grid",
        "gold_grid",
        "ground_truth",
        "hidden_answer",
    }

    teacher_names = set(
        teacher_search_trajectory.__code__.co_names
    )
    contaminated = sorted(teacher_names & forbidden)
    if contaminated:
        raise RuntimeError(
            f"teacher contains forbidden capability names: {contaminated}"
        )

    rng = random.Random(args.seed)
    rows = []
    case_reports = []

    for index in range(args.cases):
        started = time.monotonic()

        lane_count = rng.randint(3, 6)
        schema = make_fixture(rng, lane_count)

        initial_residual = residual(
            schema.initial_grid,
            schema.invariants,
        )

        print(
            f"TRM0_DATA case={index + 1}/{args.cases} "
            f"phase=begin lanes={lane_count} "
            f"initial_residual={len(initial_residual)}",
            flush=True,
        )

        final, iterations, transitions = teacher_search_trajectory(
            schema.initial_grid,
            schema.writable_mask,
            schema.invariants,
            random.Random(args.seed + index),
            args.budget,
            legal_moves=legal_moves,
            apply_move=apply_move,
            cost_fn=cost_fn,
        )

        emitted = 0

        for (
            teacher_iteration,
            before,
            after,
            cost_before,
            cost_after,
        ) in transitions:
            if cost_after >= cost_before:
                raise RuntimeError(
                    "non-decreasing teacher transition was emitted"
                )

            residual_before = residual(
                before,
                schema.invariants,
            )
            residual_after = residual(
                after,
                schema.invariants,
            )

            declared, active = encode_constraint_state(
                schema.invariants,
                residual_before,
            )

            row = {
                "schema": "elpis.c2r7c.trm0.training-transition.v1",
                "case": index,
                "teacher_iteration": teacher_iteration,
                "grid81": list(before),
                "writable_mask81": list(schema.writable_mask),
                "declared_indices529": _sparse(declared),
                "residual_indices529": _sparse(active),
                "next_grid81": list(after),
                "cost_before": cost_before,
                "cost_after": cost_after,
                "residual_before": len(residual_before),
                "residual_after": len(residual_after),
            }
            row["digest"] = _row_digest(row)
            rows.append(row)
            emitted += 1

        final_residual = residual(
            final,
            schema.invariants,
        )
        resolved = bool(is_resolved(final, schema))
        elapsed = time.monotonic() - started

        case_reports.append({
            "case": index,
            "lanes": lane_count,
            "iterations": iterations,
            "examples": emitted,
            "initial_residual": len(initial_residual),
            "final_residual": len(final_residual),
            "resolved": resolved,
            "elapsed_s": round(elapsed, 3),
        })

        print(
            f"TRM0_DATA case={index + 1}/{args.cases} "
            f"phase=end iterations={iterations} "
            f"examples={emitted} "
            f"final_residual={len(final_residual)} "
            f"resolved={str(resolved).lower()} "
            f"elapsed_s={elapsed:.3f}",
            flush=True,
        )

    dataset_payload = "\n".join(
        json.dumps(
            row,
            sort_keys=True,
            separators=(",", ":"),
        )
        for row in rows
    )
    if dataset_payload:
        dataset_payload += "\n"

    dataset_sha = hashlib.sha256(
        dataset_payload.encode("utf-8")
    ).hexdigest()

    if args.out:
        args.out.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.out.write_text(
            dataset_payload,
            encoding="utf-8",
        )

    resolved_cases = sum(
        int(report["resolved"])
        for report in case_reports
    )

    print(
        "TRM0_DATA_FINAL "
        f"cases={args.cases} "
        f"resolved={resolved_cases}/{args.cases} "
        f"examples={len(rows)} "
        f"feature_width={FEATURE_WIDTH} "
        f"feature_vocab_sha256={VOCABULARY_DIGEST} "
        f"dataset_sha256={dataset_sha} "
        f"teacher_forbidden_names={contaminated}",
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
