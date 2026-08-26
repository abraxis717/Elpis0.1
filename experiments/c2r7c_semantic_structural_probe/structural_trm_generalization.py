"""Held-out C2R7-C structural TRM generalization probe.

This probe never receives a hidden/final Grid81.

Each held-out fixture is generated from a seed disjoint from the training
smoke seed. The neural candidate receives only:

    current Grid81
    writable mask
    declared structural constraint signatures
    residual-support signatures according to the selected ablation

The deterministic structural evaluator independently decides whether the
result is coherent/resolved.

Arms:
    null
    random
    search
    trm_matched
    trm_zero_residual
    trm_mismatched_residual

TRM outer structural steps reset latent carry deliberately: TRM-0 training
examples are independent one-step transitions. Persistent carry is a later
experiment and must not be smuggled into this gate.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import random
import sys
import time

import torch

from structural_trm_dataset import _load_probe_namespace
from structural_trm_features import (
    FEATURE_WIDTH,
    encode_constraint_state,
)
from structural_trm_model import StructuralTRM64


DEFAULT_CHECKPOINT = Path(
    "/Users/abraxis/Elpis/Elpis_Qualification/work/"
    "C2R7C_TRM0_LONG/best.pt"
)

HELDOUT_DEFAULT_SEED = 20260926


def bits_tensor(bits):
    return torch.tensor(
        [bits],
        dtype=torch.float32,
    )


def grid_tensor(grid):
    return torch.tensor(
        [grid],
        dtype=torch.long,
    )


def load_model(checkpoint_path: Path):
    checkpoint = torch.load(
        checkpoint_path,
        map_location="cpu",
    )

    config = checkpoint.get(
        "config",
        {},
    )

    hidden = int(
        config.get("hidden", 64)
    )
    h_cycles = int(
        config.get("h_cycles", 3)
    )
    l_cycles = int(
        config.get("l_cycles", 6)
    )

    model = StructuralTRM64(
        hidden=hidden,
        h_cycles=h_cycles,
        l_cycles=l_cycles,
    )

    model.load_state_dict(
        checkpoint["model_state"]
    )

    model.eval()

    return model, checkpoint


@torch.no_grad()
def run_trm(
    *,
    model,
    schema,
    residual_fn,
    is_resolved_fn,
    validate_transition_fn,
    mode,
    mismatched_active,
    max_steps,
):
    current = schema.initial_grid
    initial_residual = residual_fn(
        current,
        schema.invariants,
    )

    declared, _ = encode_constraint_state(
        schema.invariants,
        initial_residual,
    )

    steps = 0
    authority_violations = 0
    stalled = False
    error = ""

    for step in range(max_steps):
        current_residual = residual_fn(
            current,
            schema.invariants,
        )

        if not current_residual:
            break

        if mode == "matched":
            _, active = encode_constraint_state(
                schema.invariants,
                current_residual,
            )

        elif mode == "zero":
            active = (0,) * FEATURE_WIDTH

        elif mode == "mismatched":
            active = mismatched_active

        else:
            raise ValueError(
                f"unknown TRM mode {mode!r}"
            )

        grid = grid_tensor(current)
        mask = grid_tensor(
            schema.writable_mask
        )

        _, proposed_tensor, _ = model.propose(
            grid,
            mask,
            bits_tensor(declared),
            bits_tensor(active),
            carry=None,
        )

        proposed = tuple(
            int(v)
            for v in proposed_tensor[
                0
            ].tolist()
        )

        try:
            validate_transition_fn(
                current,
                proposed,
                schema,
            )
        except Exception as exc:
            authority_violations += 1
            error = (
                f"{type(exc).__name__}: "
                f"{exc}"
            )
            break

        steps = step + 1

        if proposed == current:
            stalled = True
            break

        current = proposed

    final_residual = residual_fn(
        current,
        schema.invariants,
    )

    return {
        "resolved": bool(
            is_resolved_fn(
                current,
                schema,
            )
        ),
        "initial_residual": len(
            initial_residual
        ),
        "final_residual": len(
            final_residual
        ),
        "steps": steps,
        "authority_violations": (
            authority_violations
        ),
        "stalled": stalled,
        "error": error,
    }


def concise_control(outcome):
    return {
        "resolved": bool(
            outcome.get(
                "resolved",
                False,
            )
        ),
        "final_residual": int(
            outcome.get(
                "residual_remaining",
                -1,
            )
        ),
        "steps": int(
            outcome.get(
                "steps",
                0,
            )
        ),
        "authority_violations": int(
            outcome.get(
                "authority_violation",
                False,
            )
        ),
        "error": str(
            outcome.get(
                "error",
                "",
            )
        ),
    }


def print_arm(
    case_number,
    name,
    outcome,
    elapsed,
):
    print(
        f"TRM_GEN case={case_number} "
        f"arm={name} "
        f"resolved={str(outcome['resolved']).lower()} "
        f"residual={outcome['final_residual']} "
        f"steps={outcome['steps']} "
        f"authority={outcome['authority_violations']} "
        f"elapsed_s={elapsed:.3f}"
        + (
            f" error={outcome['error']}"
            if outcome.get("error")
            else ""
        ),
        flush=True,
    )


def build_heldout_fixtures(
    *,
    make_fixture,
    cases,
    seed,
):
    rng = random.Random(seed)

    fixtures = []

    for _ in range(cases):
        lane_count = rng.randint(
            3,
            6,
        )

        fixtures.append(
            make_fixture(
                rng,
                lane_count,
            )
        )

    return fixtures


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="trm-generalization"
    )

    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=DEFAULT_CHECKPOINT,
    )
    parser.add_argument(
        "--cases",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=HELDOUT_DEFAULT_SEED,
    )
    parser.add_argument(
        "--trm-steps",
        type=int,
        default=32,
    )
    parser.add_argument(
        "--control-budget",
        type=int,
        default=3000,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    args = parser.parse_args()

    ns = _load_probe_namespace()

    make_fixture = ns[
        "make_fixture"
    ]
    residual_fn = ns[
        "residual"
    ]
    is_resolved_fn = ns[
        "is_resolved"
    ]
    validate_transition_fn = ns[
        "validate_transition"
    ]
    run_case_fn = ns[
        "run_case"
    ]

    fixtures = build_heldout_fixtures(
        make_fixture=make_fixture,
        cases=args.cases,
        seed=args.seed,
    )

    print(
        "TRM_GEN_BEGIN "
        f"cases={args.cases} "
        f"heldout_seed={args.seed} "
        f"trm_steps={args.trm_steps} "
        f"control_budget={args.control_budget}",
        flush=True,
    )

    initial_active = []

    for schema in fixtures:
        ids = residual_fn(
            schema.initial_grid,
            schema.invariants,
        )

        _, active = encode_constraint_state(
            schema.invariants,
            ids,
        )

        initial_active.append(
            active
        )

    if args.dry_run:
        for index, schema in enumerate(
            fixtures
        ):
            ids = residual_fn(
                schema.initial_grid,
                schema.invariants,
            )

            declared, active = (
                encode_constraint_state(
                    schema.invariants,
                    ids,
                )
            )

            print(
                f"TRM_GEN_DRY case={index + 1}/{args.cases} "
                f"invariants={sum(declared)} "
                f"initial_residual={len(ids)} "
                f"active_features={sum(active)} "
                f"writable={sum(schema.writable_mask)}",
                flush=True,
            )

        print(
            "TRM_GEN_DRY_FINAL "
            "verdict=PASS "
            f"cases={args.cases}",
            flush=True,
        )

        return 0

    if not args.checkpoint.is_file():
        print(
            "TRM_GEN_BLOCKED "
            f"checkpoint_missing={args.checkpoint}",
            flush=True,
        )
        return 3

    model, checkpoint = load_model(
        args.checkpoint
    )

    checkpoint_epoch = int(
        checkpoint.get(
            "epoch",
            -1,
        )
    )

    print(
        "TRM_GEN_MODEL "
        f"checkpoint={args.checkpoint} "
        f"epoch={checkpoint_epoch}",
        flush=True,
    )

    totals = defaultdict(
        lambda: {
            "resolved": 0,
            "cases": 0,
            "authority": 0,
            "residual_sum": 0,
        }
    )

    arms = (
        "null",
        "random",
        "search",
        "trm_matched",
        "trm_zero_residual",
        "trm_mismatched_residual",
    )

    for index, schema in enumerate(
        fixtures
    ):
        case_number = (
            f"{index + 1}/{args.cases}"
        )

        initial_residual = residual_fn(
            schema.initial_grid,
            schema.invariants,
        )

        print(
            f"TRM_GEN case={case_number} "
            f"phase=begin "
            f"initial_residual={len(initial_residual)}",
            flush=True,
        )

        for control_name in (
            "null",
            "random",
            "search",
        ):
            started = time.monotonic()

            outcome = concise_control(
                run_case_fn(
                    schema,
                    control_name,
                    random.Random(
                        args.seed
                        + index
                    ),
                    args.control_budget,
                )
            )

            elapsed = (
                time.monotonic()
                - started
            )

            print_arm(
                case_number,
                control_name,
                outcome,
                elapsed,
            )

            stats = totals[
                control_name
            ]

            stats["cases"] += 1
            stats["resolved"] += int(
                outcome["resolved"]
            )
            stats["authority"] += int(
                outcome[
                    "authority_violations"
                ]
            )
            stats["residual_sum"] += int(
                outcome[
                    "final_residual"
                ]
            )

        donor_index = (
            index + 1
        ) % len(fixtures)

        mismatched = initial_active[
            donor_index
        ]

        for arm_name, mode in (
            (
                "trm_matched",
                "matched",
            ),
            (
                "trm_zero_residual",
                "zero",
            ),
            (
                "trm_mismatched_residual",
                "mismatched",
            ),
        ):
            started = time.monotonic()

            outcome = run_trm(
                model=model,
                schema=schema,
                residual_fn=residual_fn,
                is_resolved_fn=is_resolved_fn,
                validate_transition_fn=(
                    validate_transition_fn
                ),
                mode=mode,
                mismatched_active=(
                    mismatched
                ),
                max_steps=args.trm_steps,
            )

            elapsed = (
                time.monotonic()
                - started
            )

            print_arm(
                case_number,
                arm_name,
                outcome,
                elapsed,
            )

            stats = totals[
                arm_name
            ]

            stats["cases"] += 1
            stats["resolved"] += int(
                outcome["resolved"]
            )
            stats["authority"] += int(
                outcome[
                    "authority_violations"
                ]
            )
            stats["residual_sum"] += int(
                outcome[
                    "final_residual"
                ]
            )

        print(
            f"TRM_GEN case={case_number} "
            "phase=end",
            flush=True,
        )

    print(
        "===== TRM GENERALIZATION SUMMARY =====",
        flush=True,
    )

    for name in arms:
        stats = totals[name]

        mean_residual = (
            stats["residual_sum"]
            / max(
                1,
                stats["cases"],
            )
        )

        print(
            f"TRM_GEN_SUMMARY "
            f"arm={name} "
            f"resolved={stats['resolved']}/{stats['cases']} "
            f"mean_final_residual={mean_residual:.3f} "
            f"authority={stats['authority']}",
            flush=True,
        )

    matched = totals[
        "trm_matched"
    ]
    zero = totals[
        "trm_zero_residual"
    ]
    mismatch = totals[
        "trm_mismatched_residual"
    ]
    null = totals[
        "null"
    ]

    mechanism_signal = (
        matched["resolved"]
        > null["resolved"]
        and (
            matched["resolved"]
            > zero["resolved"]
            or matched["residual_sum"]
            < zero["residual_sum"]
        )
        and (
            matched["resolved"]
            > mismatch["resolved"]
            or matched["residual_sum"]
            < mismatch["residual_sum"]
        )
        and matched["authority"] == 0
    )

    print(
        "TRM_GEN_FINAL "
        f"mechanism_signal="
        f"{'PASS' if mechanism_signal else 'FAIL'} "
        f"matched={matched['resolved']}/{matched['cases']} "
        f"zero={zero['resolved']}/{zero['cases']} "
        f"mismatched={mismatch['resolved']}/{mismatch['cases']} "
        f"null={null['resolved']}/{null['cases']} "
        f"matched_authority={matched['authority']}",
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
