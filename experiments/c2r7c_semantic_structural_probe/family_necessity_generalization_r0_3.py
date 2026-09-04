from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import family_necessity_r0_3 as r03
import guided_search_r0_2 as r02
import structural_trm_generalization as r01


EXPECTED_PREREG_SHA256 = (
    "678437194065a1cd030d912657f65c63f4431783cded0396e4e304fa2695aed3"
)
EXPECTED_CHECKPOINT_SHA256 = (
    "e58e44c9227d68971d0ab5f5e4f0eaf2e05d4faa97ec8232108aa73898273129"
)
EXPECTED_CORPUS_SHA256 = (
    "952d3bff676fd4c74f0bb1684ec23e70f261025d8ffb9adca59cf3a7850f1230"
)

PLAIN = "plain_search"
MATCHED = "matched"

FAMILIES = r03.ACTIVE_FAMILIES

ARMS = (
    PLAIN,
    MATCHED,
    *tuple(f"ablate_{family}" for family in FAMILIES),
    *tuple(f"count_control_{family}" for family in FAMILIES),
)


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
        "budget": int(prereg["search_contract"]["budget"]),
    }


def final_open_allowed(population: str, open_final: bool) -> bool:
    return population != "final" or bool(open_final)


def parse_guided_arm(arm: str):
    if arm == MATCHED:
        return "matched", None

    if arm.startswith("ablate_"):
        family = arm[len("ablate_"):]
        if family not in FAMILIES:
            raise ValueError(arm)
        return "family", family

    if arm.startswith("count_control_"):
        family = arm[len("count_control_"):]
        if family not in FAMILIES:
            raise ValueError(arm)
        return "count_control", family

    raise ValueError(arm)


def empty_totals():
    return {
        arm: {
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
        for arm in ARMS
    }


def run_r03_arm(
    *,
    arm_name,
    model,
    schema,
    rng,
    budget,
    residual_fn,
    is_resolved_fn,
    validate_transition_fn,
    materialisable_fn,
    quiescent_fn,
):
    mode, family = parse_guided_arm(arm_name)

    proposal_fn = r03.build_proposal_fn(
        model=model,
        schema=schema,
        residual_fn=residual_fn,
        mode=mode,
        family=family,
    )

    initial = schema.initial_grid
    initial_residual = residual_fn(
        initial,
        schema.invariants,
    )

    final, steps, stats = r03.refine_r03_search(
        initial,
        schema.writable_mask,
        schema.invariants,
        rng,
        budget,
        proposal_fn=proposal_fn,
    )

    result = {
        "arm": arm_name,
        "initial_residual": len(initial_residual),
        "final_residual": len(initial_residual),
        "residual_reduction": 0,
        "steps": int(steps),
        "resolved": False,
        "materialisable": False,
        "quiescent": False,
        "frozen_cell_violations": 0,
        "authority_granted": 0,
        "valid_transitions": 0,
        "invalid_transitions": 0,
        "proposed_edits": 0,
        "accepted_edits": 0,
        "error": "",
    }

    try:
        validate_transition_fn(
            initial,
            final,
            schema,
        )
        result["valid_transitions"] = 1
    except Exception as exc:
        result["invalid_transitions"] = 1
        result["error"] = (
            f"{type(exc).__name__}: {exc}"
        )
        final = initial
        result["steps"] = 0

    if result["valid_transitions"]:
        changed = [
            i
            for i in range(len(initial))
            if final[i] != initial[i]
        ]

        result["frozen_cell_violations"] = sum(
            int(not schema.writable_mask[i])
            for i in changed
        )

        result["proposed_edits"] = len(changed)
        result["accepted_edits"] = len(changed)

    final_residual = residual_fn(
        final,
        schema.invariants,
    )

    result["final_residual"] = len(final_residual)
    result["residual_reduction"] = (
        len(initial_residual) - len(final_residual)
    )
    result["resolved"] = bool(
        is_resolved_fn(final, schema)
    )
    result["materialisable"] = bool(
        materialisable_fn(final, schema)
    )
    result["quiescent"] = bool(
        quiescent_fn(final)
    )

    result.update(stats)
    return result


def mechanism_summary(rows):
    keys = (
        "guidance_queries",
        "ordered_iterations",
        "order_changed_iterations",
        "equal_best_ties",
        "guidance_tiebreak_changed_choice",
        "r03_queries",
        "r03_target_removed_sum",
        "r03_actual_removed_sum",
        "r03_control_overlap_sum",
        "r03_control_distinct_steps",
        "r03_control_alternative_steps",
        "r03_nonzero_dose_queries",
        "r03_dose_mismatch_steps",
    )

    return {
        key: sum(int(row.get(key, 0)) for row in rows)
        for key in keys
    }


def mean(values):
    return sum(values) / len(values) if values else None


def run(args) -> int:
    prereg = args.prereg.resolve()
    checkpoint = args.checkpoint.resolve()
    corpus = args.train_corpus.resolve()

    if not prereg.is_file():
        print("R0_3_BLOCKED prereg_missing", flush=True)
        return 3

    prereg_sha = sha256_file(prereg)

    if prereg_sha != EXPECTED_PREREG_SHA256:
        print(
            "R0_3_BLOCKED prereg_sha_mismatch "
            f"actual={prereg_sha}",
            flush=True,
        )
        return 3

    prereg_obj = json.loads(prereg.read_text())

    if not final_open_allowed(
        args.population,
        args.open_final,
    ):
        print(
            "R0_3_BLOCKED final_population_requires_--open-final",
            flush=True,
        )
        return 3

    spec = population_spec(
        prereg_obj,
        args.population,
    )

    if not checkpoint.is_file() or not corpus.is_file():
        print(
            "R0_3_BLOCKED authority_file_missing",
            flush=True,
        )
        return 3

    checkpoint_sha = sha256_file(checkpoint)
    corpus_sha = sha256_file(corpus)

    if checkpoint_sha != EXPECTED_CHECKPOINT_SHA256:
        print(
            "R0_3_BLOCKED checkpoint_sha_mismatch",
            flush=True,
        )
        return 3

    if corpus_sha != EXPECTED_CORPUS_SHA256:
        print(
            "R0_3_BLOCKED corpus_sha_mismatch",
            flush=True,
        )
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

    selected = sum(
        int(row["disjoint"])
        for row in manifest
    )

    if selected != spec["cases"]:
        print(
            "R0_3_BLOCKED heldout_disjointness",
            flush=True,
        )
        return 4

    model, checkpoint_obj = r01.load_model(
        checkpoint
    )

    results = {
        arm: []
        for arm in ARMS
    }

    per_fixture = []

    print(
        "R0_3_BEGIN "
        f"population={args.population} "
        f"cases={spec['cases']} "
        f"seed={spec['base_seed']} "
        f"seed_count={spec['seed_count']} "
        f"budget={spec['budget']} "
        f"arms={len(ARMS)} "
        f"checkpoint_epoch={int(checkpoint_obj.get('epoch', -1))}",
        flush=True,
    )

    started_all = time.monotonic()

    for index, schema in enumerate(fixtures):
        paired_seed = (
            spec["base_seed"] + index
        )

        initial_residual = residual_fn(
            schema.initial_grid,
            schema.invariants,
        )

        case_row = {
            "fixture": index,
            "initial_residual": len(initial_residual),
            "arms": {},
        }

        plain = r02.run_guided_search_arm(
            arm_name=r02.ARM_PLAIN,
            guidance_mode=None,
            model=model,
            schema=schema,
            rng=random.Random(paired_seed),
            budget=spec["budget"],
            residual_fn=residual_fn,
            is_resolved_fn=is_resolved_fn,
            validate_transition_fn=validate_transition_fn,
            materialisable_fn=materialisable_fn,
            quiescent_fn=quiescent_fn,
        )

        results[PLAIN].append(plain)
        case_row["arms"][PLAIN] = plain

        for arm in ARMS:
            if arm == PLAIN:
                continue

            outcome = run_r03_arm(
                arm_name=arm,
                model=model,
                schema=schema,
                rng=random.Random(paired_seed),
                budget=spec["budget"],
                residual_fn=residual_fn,
                is_resolved_fn=is_resolved_fn,
                validate_transition_fn=validate_transition_fn,
                materialisable_fn=materialisable_fn,
                quiescent_fn=quiescent_fn,
            )

            results[arm].append(outcome)
            case_row["arms"][arm] = outcome

        per_fixture.append(case_row)

        if (
            (index + 1) % 4 == 0
            or index + 1 == spec["cases"]
        ):
            plain_n = sum(
                int(r["resolved"])
                for r in results[PLAIN]
            )
            matched_n = sum(
                int(r["resolved"])
                for r in results[MATCHED]
            )

            family_text = " ".join(
                (
                    f"{family}="
                    f"{sum(int(r['resolved']) for r in results[f'ablate_{family}'])}/"
                    f"{sum(int(r['resolved']) for r in results[f'count_control_{family}'])}"
                )
                for family in FAMILIES
            )

            print(
                "R0_3_PROGRESS "
                f"case={index + 1}/{spec['cases']} "
                f"plain={plain_n} "
                f"matched={matched_n} "
                f"{family_text}",
                flush=True,
            )

    wall = time.monotonic() - started_all

    totals = empty_totals()
    r01._aggregate(
        totals,
        results,
    )

    mechanisms = {
        arm: mechanism_summary(rows)
        for arm, rows in results.items()
        if arm != PLAIN
    }

    family_effects = {}

    for family in FAMILIES:
        ablate_arm = f"ablate_{family}"
        control_arm = f"count_control_{family}"

        m = totals[MATCHED]["resolved"]
        a = totals[ablate_arm]["resolved"]
        c = totals[control_arm]["resolved"]

        jointly_matched_ablate = [
            i
            for i, row in enumerate(per_fixture)
            if row["arms"][MATCHED]["resolved"]
            and row["arms"][ablate_arm]["resolved"]
        ]

        jointly_control_ablate = [
            i
            for i, row in enumerate(per_fixture)
            if row["arms"][control_arm]["resolved"]
            and row["arms"][ablate_arm]["resolved"]
        ]

        family_effects[family] = {
            "matched_resolved": m,
            "ablated_resolved": a,
            "count_control_resolved": c,
            "matched_minus_ablated": m - a,
            "control_minus_ablated": c - a,
            "primary_direction": m > a,
            "specificity_direction": c > a,
            "development_localization_direction":
                (m > a and c > a),
            "joint_matched_ablated": {
                "fixtures": len(jointly_matched_ablate),
                "matched_mean_steps": mean([
                    per_fixture[i]["arms"][MATCHED]["steps"]
                    for i in jointly_matched_ablate
                ]),
                "ablated_mean_steps": mean([
                    per_fixture[i]["arms"][ablate_arm]["steps"]
                    for i in jointly_matched_ablate
                ]),
            },
            "joint_control_ablated": {
                "fixtures": len(jointly_control_ablate),
                "control_mean_steps": mean([
                    per_fixture[i]["arms"][control_arm]["steps"]
                    for i in jointly_control_ablate
                ]),
                "ablated_mean_steps": mean([
                    per_fixture[i]["arms"][ablate_arm]["steps"]
                    for i in jointly_control_ablate
                ]),
            },
        }

    all_rows = [
        row
        for rows in results.values()
        for row in rows
    ]

    dose_mismatch_steps = sum(
        int(row.get(
            "r03_dose_mismatch_steps",
            0,
        ))
        for row in all_rows
    )

    control_distinct_violations = 0

    for family in FAMILIES:
        s = mechanisms[
            f"count_control_{family}"
        ]

        control_distinct_violations += (
            int(s["r03_control_alternative_steps"])
            - int(s["r03_control_distinct_steps"])
        )

    integrity = {
        "heldout_disjoint": True,
        "checkpoint_sha_match": (
            checkpoint_sha
            == EXPECTED_CHECKPOINT_SHA256
        ),
        "corpus_sha_match": (
            corpus_sha
            == EXPECTED_CORPUS_SHA256
        ),
        "frozen_cell_violations_zero": (
            sum(
                totals[arm]["frozen_cell_violations"]
                for arm in ARMS
            )
            == 0
        ),
        "authority_granted_zero": (
            sum(
                totals[arm]["authority_granted"]
                for arm in ARMS
            )
            == 0
        ),
        "invalid_transitions_zero": (
            sum(
                totals[arm]["invalid_transitions"]
                for arm in ARMS
            )
            == 0
        ),
        "dose_mismatch_steps_zero": (
            dose_mismatch_steps == 0
        ),
        "count_control_distinct_contract": (
            control_distinct_violations == 0
        ),
    }

    report = {
        "schema": (
            "elpis.c2r7c.trm0-family-necessity."
            "r0-3-report.v1"
        ),
        "role": (
            "DEVELOPMENT"
            if args.population == "dev"
            else "FINAL_HELDOUT"
        ),
        "population": args.population,
        "population_spec": spec,
        "preregistration_path": str(prereg),
        "preregistration_sha256": prereg_sha,
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha,
        "checkpoint_epoch": int(
            checkpoint_obj.get("epoch", -1)
        ),
        "train_corpus_path": str(corpus),
        "train_corpus_sha256": corpus_sha,
        "manifest": manifest,
        "arm_totals": totals,
        "family_effects": family_effects,
        "mechanism_activity": mechanisms,
        "integrity": integrity,
        "wall_seconds": wall,
        "per_fixture": per_fixture,
    }

    args.out.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.out.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print(
        "===== R0.3 DEVELOPMENT SUMMARY ====="
        if args.population == "dev"
        else "===== R0.3 FINAL SUMMARY =====",
        flush=True,
    )

    print(
        f"plain={totals[PLAIN]['resolved']}/{spec['cases']} "
        f"matched={totals[MATCHED]['resolved']}/{spec['cases']}",
        flush=True,
    )

    for family in FAMILIES:
        effect = family_effects[family]
        a = mechanisms[f"ablate_{family}"]
        c = mechanisms[f"count_control_{family}"]

        print(
            f"family={family} "
            f"ablated={effect['ablated_resolved']}/{spec['cases']} "
            f"control={effect['count_control_resolved']}/{spec['cases']} "
            f"matched_minus_ablated="
            f"{effect['matched_minus_ablated']} "
            f"control_minus_ablated="
            f"{effect['control_minus_ablated']} "
            f"ablation_nonzero_dose_queries="
            f"{a['r03_nonzero_dose_queries']} "
            f"control_nonzero_dose_queries="
            f"{c['r03_nonzero_dose_queries']} "
            f"dose_mismatch="
            f"{a['r03_dose_mismatch_steps'] + c['r03_dose_mismatch_steps']} "
            f"control_alt="
            f"{c['r03_control_alternative_steps']} "
            f"control_distinct="
            f"{c['r03_control_distinct_steps']}",
            flush=True,
        )

    print(
        "R0_3_INTEGRITY "
        + " ".join(
            f"{k}={str(v).lower()}"
            for k, v in integrity.items()
        ),
        flush=True,
    )

    print(
        f"R0_3_EVIDENCE out={args.out}",
        flush=True,
    )

    return (
        0
        if all(integrity.values())
        else 5
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="family-necessity-generalization-r0-3"
    )

    parser.add_argument(
        "--population",
        choices=("dev", "final"),
        required=True,
    )
    parser.add_argument(
        "--open-final",
        action="store_true",
    )
    parser.add_argument(
        "--prereg",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--train-corpus",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
    )

    return run(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
