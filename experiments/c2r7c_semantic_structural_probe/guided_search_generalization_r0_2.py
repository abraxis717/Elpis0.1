"""C2R7C TRM-0 guided bounded-search R0.2.

R0.2 asks whether the already-frozen TRM-0 signal can do causal work when
used only as an equal-cost tie-breaker inside the predecessor legal search.

The TRM:
  * cannot add or remove legal candidates,
  * cannot alter the deterministic residual cost,
  * cannot alter the fixed search budget,
  * cannot directly execute a proposal,
  * cannot touch frozen cells,
  * cannot grant itself authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import guided_search_r0_2 as guided
import structural_trm_generalization as r01


EXPECTED_PREREG_SHA256 = (
    "96d5ac41218be5c469daa70d18779ef390c80a1efff0d6a2ac678e3d06c2b254"
)
EXPECTED_CHECKPOINT_SHA256 = (
    "e58e44c9227d68971d0ab5f5e4f0eaf2e05d4faa97ec8232108aa73898273129"
)
EXPECTED_CORPUS_SHA256 = (
    "952d3bff676fd4c74f0bb1684ec23e70f261025d8ffb9adca59cf3a7850f1230"
)

ARMS = (
    guided.ARM_PLAIN,
    guided.ARM_MATCHED,
    guided.ARM_ZERO,
    guided.ARM_MISMATCH,
)

GUIDANCE_MODE = {
    guided.ARM_PLAIN: None,
    guided.ARM_MATCHED: "matched",
    guided.ARM_ZERO: "zero",
    guided.ARM_MISMATCH: "mismatched",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def population_spec(prereg: dict, population: str) -> dict:
    if population == "dev":
        src = prereg["development_population"]
    elif population == "final":
        src = prereg["final_population"]
    else:
        raise ValueError(population)

    return {
        "base_seed": int(src["base_seed"]),
        "cases": int(src["cases"]),
        "seed_count": int(src["seed_count"]),
        "budget": int(prereg["search_budget"]),
    }


def final_open_allowed(population: str, open_final: bool) -> bool:
    return population != "final" or bool(open_final)


def _arm_totals():
    return {
        name: {
            "resolved": 0,
            "cases": 0,
            "authority": 0,
            "residual_sum": 0,
            "residual_initial_sum": 0,
            "frozen_cell_violations": 0,
            "authority_granted": 0,
            "valid_transitions": 0,
            "invalid_transitions": 0,
            "materialisable": 0,
            "steps_sum": 0,
        }
        for name in ARMS
    }


def _mean(values):
    return sum(values) / len(values) if values else None


def run(args) -> int:
    prereg_path = args.prereg.resolve()

    if not prereg_path.is_file():
        print("R0_2_BLOCKED prereg_missing", flush=True)
        return 3

    prereg_sha = sha256_file(prereg_path)
    if prereg_sha != EXPECTED_PREREG_SHA256:
        print(
            "R0_2_BLOCKED prereg_sha_mismatch "
            f"actual={prereg_sha}",
            flush=True,
        )
        return 3

    prereg = json.loads(prereg_path.read_text())

    if not final_open_allowed(args.population, args.open_final):
        print(
            "R0_2_BLOCKED final_population_requires_--open-final",
            flush=True,
        )
        return 3

    spec = population_spec(prereg, args.population)

    if spec["budget"] != guided.SEARCH_BUDGET:
        print("R0_2_BLOCKED budget_contract_mismatch", flush=True)
        return 3

    checkpoint = args.checkpoint.resolve()
    corpus = args.train_corpus.resolve()

    if not checkpoint.is_file() or not corpus.is_file():
        print("R0_2_BLOCKED authority_file_missing", flush=True)
        return 3

    checkpoint_sha = sha256_file(checkpoint)
    corpus_sha = sha256_file(corpus)

    if checkpoint_sha != EXPECTED_CHECKPOINT_SHA256:
        print("R0_2_BLOCKED checkpoint_sha_mismatch", flush=True)
        return 3

    if corpus_sha != EXPECTED_CORPUS_SHA256:
        print("R0_2_BLOCKED corpus_sha_mismatch", flush=True)
        return 3

    ns = r01._load_probe_namespace()

    make_fixture = ns["make_fixture"]
    residual_fn = ns["residual"]
    is_resolved_fn = ns["is_resolved"]
    validate_transition_fn = ns["validate_transition"]
    materialisable_fn = ns["materialisable"]
    quiescent_fn = ns["quiescent"]

    fixtures, manifest = r01.build_heldout_manifest(
        make_fixture=make_fixture,
        residual_fn=residual_fn,
        train_jsonl=corpus,
        cases=spec["cases"],
        base_seed=spec["base_seed"],
        seed_count=spec["seed_count"],
    )

    selected = sum(int(row["disjoint"]) for row in manifest)
    if selected != spec["cases"]:
        print("R0_2_BLOCKED heldout_disjointness", flush=True)
        return 4

    model, checkpoint_obj = r01.load_model(checkpoint)

    results_by_arm = {name: [] for name in ARMS}
    per_fixture = []

    print(
        "R0_2_BEGIN "
        f"population={args.population} "
        f"cases={spec['cases']} "
        f"seed={spec['base_seed']} "
        f"seed_count={spec['seed_count']} "
        f"budget={spec['budget']} "
        f"checkpoint_epoch={int(checkpoint_obj.get('epoch', -1))}",
        flush=True,
    )

    started_all = time.monotonic()

    for index, schema in enumerate(fixtures):
        initial_residual = residual_fn(
            schema.initial_grid,
            schema.invariants,
        )

        row = {
            "fixture": index,
            "initial_residual": len(initial_residual),
            "arms": {},
        }

        # Critical paired-control rule:
        # every arm starts from the exact same RNG state for this fixture.
        paired_seed = spec["base_seed"] + index

        for arm_name in ARMS:
            rng = random.Random(paired_seed)

            outcome = guided.run_guided_search_arm(
                arm_name=arm_name,
                guidance_mode=GUIDANCE_MODE[arm_name],
                model=model,
                schema=schema,
                rng=rng,
                budget=spec["budget"],
                residual_fn=residual_fn,
                is_resolved_fn=is_resolved_fn,
                validate_transition_fn=validate_transition_fn,
                materialisable_fn=materialisable_fn,
                quiescent_fn=quiescent_fn,
            )

            results_by_arm[arm_name].append(outcome)
            row["arms"][arm_name] = outcome

        per_fixture.append(row)

        if (
            (index + 1) % 16 == 0
            or index + 1 == spec["cases"]
        ):
            counts = {
                arm: sum(
                    int(r["resolved"])
                    for r in results_by_arm[arm]
                )
                for arm in ARMS
            }

            print(
                "R0_2_PROGRESS "
                f"case={index + 1}/{spec['cases']} "
                + " ".join(
                    f"{arm}={counts[arm]}"
                    for arm in ARMS
                ),
                flush=True,
            )

    wall = time.monotonic() - started_all

    totals = _arm_totals()
    r01._aggregate(totals, results_by_arm)

    mismatch_evaluable = [
        i
        for i, row in enumerate(per_fixture)
        if not row["arms"][guided.ARM_MISMATCH][
            "mismatch_unevaluable"
        ]
    ]

    matched_vs_mismatch = {
        "paired_evaluable": len(mismatch_evaluable),
        "matched_resolved": sum(
            int(
                per_fixture[i]["arms"][
                    guided.ARM_MATCHED
                ]["resolved"]
            )
            for i in mismatch_evaluable
        ),
        "mismatched_resolved": sum(
            int(
                per_fixture[i]["arms"][
                    guided.ARM_MISMATCH
                ]["resolved"]
            )
            for i in mismatch_evaluable
        ),
    }

    jointly_resolved = {}
    for other in (
        guided.ARM_PLAIN,
        guided.ARM_ZERO,
        guided.ARM_MISMATCH,
    ):
        indices = [
            i
            for i, row in enumerate(per_fixture)
            if row["arms"][guided.ARM_MATCHED]["resolved"]
            and row["arms"][other]["resolved"]
            and (
                other != guided.ARM_MISMATCH
                or not row["arms"][other]["mismatch_unevaluable"]
            )
        ]

        jointly_resolved[other] = {
            "fixtures": len(indices),
            "matched_mean_steps": _mean([
                per_fixture[i]["arms"][
                    guided.ARM_MATCHED
                ]["steps"]
                for i in indices
            ]),
            "other_mean_steps": _mean([
                per_fixture[i]["arms"][other]["steps"]
                for i in indices
            ]),
        }

    mechanism_activity = {}
    for arm in (
        guided.ARM_MATCHED,
        guided.ARM_ZERO,
        guided.ARM_MISMATCH,
    ):
        rows = results_by_arm[arm]
        mechanism_activity[arm] = {
            "guidance_queries": sum(
                int(r["guidance_queries"]) for r in rows
            ),
            "ordered_iterations": sum(
                int(r["ordered_iterations"]) for r in rows
            ),
            "order_changed_iterations": sum(
                int(r["order_changed_iterations"]) for r in rows
            ),
            "equal_best_ties": sum(
                int(r["equal_best_ties"]) for r in rows
            ),
            "guidance_tiebreak_changed_choice": sum(
                int(r["guidance_tiebreak_changed_choice"])
                for r in rows
            ),
            "mismatch_distinct_steps": sum(
                int(r["mismatch_distinct_steps"])
                for r in rows
            ),
            "mismatch_unevaluable_fixtures": sum(
                int(r["mismatch_unevaluable"])
                for r in rows
            ),
        }

    integrity = {
        "heldout_disjoint": True,
        "checkpoint_sha_match": (
            checkpoint_sha == EXPECTED_CHECKPOINT_SHA256
        ),
        "corpus_sha_match": (
            corpus_sha == EXPECTED_CORPUS_SHA256
        ),
        "frozen_cell_violations_zero": (
            sum(
                totals[a]["frozen_cell_violations"]
                for a in ARMS
            )
            == 0
        ),
        "authority_granted_zero": (
            sum(
                totals[a]["authority_granted"]
                for a in ARMS
            )
            == 0
        ),
        "invalid_transitions_zero": (
            sum(
                totals[a]["invalid_transitions"]
                for a in ARMS
            )
            == 0
        ),
    }

    development_signal = {
        "matched_minus_plain_resolved": (
            totals[guided.ARM_MATCHED]["resolved"]
            - totals[guided.ARM_PLAIN]["resolved"]
        ),
        "matched_minus_zero_resolved": (
            totals[guided.ARM_MATCHED]["resolved"]
            - totals[guided.ARM_ZERO]["resolved"]
        ),
        "matched_minus_mismatch_paired_resolved": (
            matched_vs_mismatch["matched_resolved"]
            - matched_vs_mismatch["mismatched_resolved"]
        ),
    }

    report = {
        "schema": "elpis.c2r7c.trm0-guided-search.r0-2-report.v1",
        "role": (
            "DEVELOPMENT"
            if args.population == "dev"
            else "FINAL_HELDOUT"
        ),
        "population": args.population,
        "population_spec": spec,
        "preregistration_path": str(prereg_path),
        "preregistration_sha256": prereg_sha,
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha,
        "checkpoint_epoch": int(checkpoint_obj.get("epoch", -1)),
        "train_corpus_path": str(corpus),
        "train_corpus_sha256": corpus_sha,
        "manifest": manifest,
        "arm_totals": totals,
        "paired_mismatch": matched_vs_mismatch,
        "jointly_resolved": jointly_resolved,
        "mechanism_activity": mechanism_activity,
        "development_signal": development_signal,
        "integrity": integrity,
        "wall_seconds": wall,
        "per_fixture": per_fixture,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )

    print("===== R0.2 SUMMARY =====", flush=True)
    for arm in ARMS:
        t = totals[arm]
        print(
            f"{arm}: "
            f"resolved={t['resolved']}/{t['cases']} "
            f"steps_sum={t['steps_sum']} "
            f"mean_final_residual={t['mean_final_residual']:.6f}",
            flush=True,
        )

    for arm, activity in mechanism_activity.items():
        print(
            f"{arm}: "
            f"queries={activity['guidance_queries']} "
            f"order_changed={activity['order_changed_iterations']} "
            f"equal_best_ties={activity['equal_best_ties']} "
            f"changed_choice={activity['guidance_tiebreak_changed_choice']} "
            f"mismatch_unevaluable="
            f"{activity['mismatch_unevaluable_fixtures']}",
            flush=True,
        )

    print(
        "R0_2_DEV_SIGNAL "
        + " ".join(
            f"{k}={v}"
            for k, v in development_signal.items()
        ),
        flush=True,
    )

    print(
        "R0_2_INTEGRITY "
        + " ".join(
            f"{k}={str(v).lower()}"
            for k, v in integrity.items()
        ),
        flush=True,
    )

    print(
        f"R0_2_EVIDENCE out={args.out}",
        flush=True,
    )

    return 0 if all(integrity.values()) else 5


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="guided-search-generalization-r0-2"
    )
    parser.add_argument(
        "--population",
        choices=("dev", "final"),
        required=True,
    )
    parser.add_argument(
        "--open-final",
        action="store_true",
        help=(
            "required to execute the preregistered final population; "
            "never needed for development"
        ),
    )
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--train-corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
