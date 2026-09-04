from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import torch

import guided_search_r0_2 as r02
import signed_composition_r0_4 as r04
import structural_trm_generalization as r01
import structural_trm_features as features


EXPECTED_PREREG_SHA256 = (
    "cc03fdcd66c4f69b065ba38b04a3f88a5f239dbfd8d7f84d2ccd6f7a1376e84e"
)
EXPECTED_CHECKPOINT_SHA256 = (
    "e58e44c9227d68971d0ab5f5e4f0eaf2e05d4faa97ec8232108aa73898273129"
)
EXPECTED_CORPUS_SHA256 = (
    "952d3bff676fd4c74f0bb1684ec23e70f261025d8ffb9adca59cf3a7850f1230"
)

PLAIN = "plain_search"

ARMS = (
    "plain_search",
    "matched_full",
    "positive_core",
    "positive_core_count_control",
    "positive_plus_PRECEDES",
    "positive_plus_INTERFACE_TERMINAL",
    "negative_pair_only",
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


def validate_active_family_support(matched_active):
    active_kinds = {
        str(features.SIGNATURES[i][0])
        for i, bit in enumerate(matched_active)
        if int(bit)
    }

    vocabulary_kinds = {
        str(kind)
        for kind, lanes in features.SIGNATURES
    }

    unknown = sorted(
        active_kinds - vocabulary_kinds
    )

    if unknown:
        raise r04.R04ContractError(
            "active residual escaped frozen vocabulary: "
            + ",".join(unknown)
        )

    return tuple(sorted(active_kinds))


def manipulate_active(
    arm: str,
    matched_active,
    current,
):
    validate_active_family_support(matched_active)

    if arm == "matched_full":
        matched = tuple(int(v) for v in matched_active)
        return matched, r04.CompositionMetadata(
            mode="matched_full",
            target_removed=(),
            actual_removed=(),
            removed_count=0,
            control_overlap_count=0,
            control_distinct=False,
            control_alternative_exists=False,
        )

    if arm == "positive_core":
        return r04.apply_positive_core(
            matched_active
        )

    if arm == "positive_core_count_control":
        return r04.apply_positive_core_count_control(
            matched_active,
            current,
        )

    if arm == "positive_plus_PRECEDES":
        return r04.apply_positive_plus_precedes(
            matched_active
        )

    if arm == "positive_plus_INTERFACE_TERMINAL":
        return r04.apply_positive_plus_interface_terminal(
            matched_active
        )

    if arm == "negative_pair_only":
        return r04.apply_negative_pair_only(
            matched_active
        )

    raise ValueError(arm)


def build_proposal_fn(
    *,
    arm,
    model,
    schema,
    residual_fn,
):
    initial_residual = residual_fn(
        schema.initial_grid,
        schema.invariants,
    )

    declared, _ = r01.encode_constraint_state(
        schema.invariants,
        initial_residual,
    )

    mask_t = r01.grid_tensor(
        schema.writable_mask
    )

    def proposal_fn(current):
        current_residual = residual_fn(
            current,
            schema.invariants,
        )

        _, matched_active = r01.encode_constraint_state(
            schema.invariants,
            current_residual,
        )

        active, meta = manipulate_active(
            arm,
            matched_active,
            current,
        )

        r04.validate_subset(
            declared,
            matched_active,
            active,
        )

        grid_t = r01.grid_tensor(current)

        with torch.inference_mode():
            _, proposed_tensor, _ = model.propose(
                grid_t,
                mask_t,
                r01.bits_tensor(declared),
                r01.bits_tensor(active),
                carry=None,
            )

        proposal = tuple(
            int(v)
            for v in proposed_tensor[0].tolist()
        )

        metadata = {
            "r04_mode": meta.mode,
            "r04_target_removed": len(
                meta.target_removed
            ),
            "r04_actual_removed": len(
                meta.actual_removed
            ),
            "r04_control_overlap":
                meta.control_overlap_count,
            "r04_control_distinct":
                meta.control_distinct,
            "r04_control_alternative_exists":
                meta.control_alternative_exists,
        }

        return proposal, metadata

    return proposal_fn


def refine_r04_search(
    grid,
    mask,
    invariants,
    rng,
    budget,
    *,
    proposal_fn,
):
    accum = {
        "r04_queries": 0,
        "r04_target_removed_sum": 0,
        "r04_actual_removed_sum": 0,
        "r04_control_overlap_sum": 0,
        "r04_control_distinct_steps": 0,
        "r04_control_alternative_steps": 0,
        "r04_nonzero_dose_queries": 0,
        "r04_dose_mismatch_steps": 0,
    }

    def wrapped(current):
        proposal, metadata = proposal_fn(
            current
        )

        accum["r04_queries"] += 1
        accum["r04_target_removed_sum"] += int(
            metadata["r04_target_removed"]
        )
        accum["r04_actual_removed_sum"] += int(
            metadata["r04_actual_removed"]
        )
        accum["r04_control_overlap_sum"] += int(
            metadata["r04_control_overlap"]
        )
        accum["r04_control_distinct_steps"] += int(
            metadata["r04_control_distinct"]
        )
        accum["r04_control_alternative_steps"] += int(
            metadata[
                "r04_control_alternative_exists"
            ]
        )
        accum["r04_nonzero_dose_queries"] += int(
            metadata["r04_target_removed"] > 0
        )
        accum["r04_dose_mismatch_steps"] += int(
            metadata["r04_target_removed"]
            != metadata["r04_actual_removed"]
        )

        return proposal, metadata

    final, steps, search_stats = (
        r02.refine_guided_search(
            grid,
            mask,
            invariants,
            rng,
            budget,
            proposal_fn=wrapped,
        )
    )

    search_stats.update(accum)

    return final, steps, search_stats


def run_guided_arm(
    *,
    arm,
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
    proposal_fn = build_proposal_fn(
        arm=arm,
        model=model,
        schema=schema,
        residual_fn=residual_fn,
    )

    initial = schema.initial_grid

    initial_residual = residual_fn(
        initial,
        schema.invariants,
    )

    final, steps, stats = refine_r04_search(
        initial,
        schema.writable_mask,
        schema.invariants,
        rng,
        budget,
        proposal_fn=proposal_fn,
    )

    result = {
        "arm": arm,
        "initial_residual": len(
            initial_residual
        ),
        "final_residual": len(
            initial_residual
        ),
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

        result[
            "frozen_cell_violations"
        ] = sum(
            int(
                not schema.writable_mask[i]
            )
            for i in changed
        )

        result["proposed_edits"] = len(
            changed
        )
        result["accepted_edits"] = len(
            changed
        )

    final_residual = residual_fn(
        final,
        schema.invariants,
    )

    result["final_residual"] = len(
        final_residual
    )
    result["residual_reduction"] = (
        len(initial_residual)
        - len(final_residual)
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


def mechanism_summary(rows):
    keys = (
        "guidance_queries",
        "ordered_iterations",
        "order_changed_iterations",
        "equal_best_ties",
        "guidance_tiebreak_changed_choice",
        "r04_queries",
        "r04_target_removed_sum",
        "r04_actual_removed_sum",
        "r04_control_overlap_sum",
        "r04_control_distinct_steps",
        "r04_control_alternative_steps",
        "r04_nonzero_dose_queries",
        "r04_dose_mismatch_steps",
    )

    return {
        key: sum(
            int(row.get(key, 0))
            for row in rows
        )
        for key in keys
    }


def mean(values):
    if not values:
        return None
    return sum(values) / len(values)


def paired_steps(per_fixture, a, b):
    indices = [
        i
        for i, row in enumerate(
            per_fixture
        )
        if row["arms"][a]["resolved"]
        and row["arms"][b]["resolved"]
    ]

    return {
        "fixtures": len(indices),
        f"{a}_mean_steps": mean([
            per_fixture[i]["arms"][a][
                "steps"
            ]
            for i in indices
        ]),
        f"{b}_mean_steps": mean([
            per_fixture[i]["arms"][b][
                "steps"
            ]
            for i in indices
        ]),
    }


def run(args) -> int:
    prereg = args.prereg.resolve()
    checkpoint = args.checkpoint.resolve()
    corpus = args.train_corpus.resolve()

    if not prereg.is_file():
        print(
            "R0_4_BLOCKED prereg_missing",
            flush=True,
        )
        return 3

    prereg_sha = sha256_file(prereg)

    if prereg_sha != EXPECTED_PREREG_SHA256:
        print(
            "R0_4_BLOCKED prereg_sha_mismatch "
            f"actual={prereg_sha}",
            flush=True,
        )
        return 3

    prereg_obj = json.loads(
        prereg.read_text()
    )

    if not final_open_allowed(
        args.population,
        args.open_final,
    ):
        print(
            "R0_4_BLOCKED "
            "final_population_requires_--open-final",
            flush=True,
        )
        return 3

    spec = population_spec(
        prereg_obj,
        args.population,
    )

    if (
        not checkpoint.is_file()
        or not corpus.is_file()
    ):
        print(
            "R0_4_BLOCKED authority_file_missing",
            flush=True,
        )
        return 3

    checkpoint_sha = sha256_file(
        checkpoint
    )
    corpus_sha = sha256_file(corpus)

    if (
        checkpoint_sha
        != EXPECTED_CHECKPOINT_SHA256
    ):
        print(
            "R0_4_BLOCKED checkpoint_sha_mismatch",
            flush=True,
        )
        return 3

    if corpus_sha != EXPECTED_CORPUS_SHA256:
        print(
            "R0_4_BLOCKED corpus_sha_mismatch",
            flush=True,
        )
        return 3

    r04.validate_vocabulary()

    ns = r01._load_probe_namespace()

    make_fixture = ns["make_fixture"]
    residual_fn = ns["residual"]
    is_resolved_fn = ns["is_resolved"]
    validate_transition_fn = ns[
        "validate_transition"
    ]
    materialisable_fn = ns[
        "materialisable"
    ]
    quiescent_fn = ns["quiescent"]

    fixtures, manifest = (
        r01.build_heldout_manifest(
            make_fixture=make_fixture,
            residual_fn=residual_fn,
            train_jsonl=corpus,
            cases=spec["cases"],
            base_seed=spec["base_seed"],
            seed_count=spec[
                "seed_count"
            ],
        )
    )

    selected = sum(
        int(row["disjoint"])
        for row in manifest
    )

    if selected != spec["cases"]:
        print(
            "R0_4_BLOCKED heldout_disjointness",
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
        "R0_4_BEGIN "
        f"population={args.population} "
        f"cases={spec['cases']} "
        f"seed={spec['base_seed']} "
        f"seed_count={spec['seed_count']} "
        f"budget={spec['budget']} "
        f"arms={len(ARMS)} "
        f"checkpoint_epoch="
        f"{int(checkpoint_obj.get('epoch', -1))}",
        flush=True,
    )

    started_all = time.monotonic()

    for index, schema in enumerate(
        fixtures
    ):
        paired_seed = (
            spec["base_seed"] + index
        )

        initial_residual = residual_fn(
            schema.initial_grid,
            schema.invariants,
        )

        declared, active = (
            r01.encode_constraint_state(
                schema.invariants,
                initial_residual,
            )
        )

        validate_active_family_support(
            active
        )

        case_row = {
            "fixture": index,
            "initial_residual": len(
                initial_residual
            ),
            "initial_active_families":
                validate_active_family_support(
                    active
                ),
            "arms": {},
        }

        plain = r02.run_guided_search_arm(
            arm_name=r02.ARM_PLAIN,
            guidance_mode=None,
            model=model,
            schema=schema,
            rng=random.Random(
                paired_seed
            ),
            budget=spec["budget"],
            residual_fn=residual_fn,
            is_resolved_fn=is_resolved_fn,
            validate_transition_fn=
                validate_transition_fn,
            materialisable_fn=
                materialisable_fn,
            quiescent_fn=quiescent_fn,
        )

        results[PLAIN].append(plain)
        case_row["arms"][PLAIN] = plain

        for arm in ARMS:
            if arm == PLAIN:
                continue

            outcome = run_guided_arm(
                arm=arm,
                model=model,
                schema=schema,
                rng=random.Random(
                    paired_seed
                ),
                budget=spec["budget"],
                residual_fn=residual_fn,
                is_resolved_fn=
                    is_resolved_fn,
                validate_transition_fn=
                    validate_transition_fn,
                materialisable_fn=
                    materialisable_fn,
                quiescent_fn=
                    quiescent_fn,
            )

            results[arm].append(
                outcome
            )
            case_row["arms"][arm] = (
                outcome
            )

        per_fixture.append(case_row)

        if (
            (index + 1) % 4 == 0
            or index + 1 == spec["cases"]
        ):
            counts = {
                arm: sum(
                    int(r["resolved"])
                    for r in results[arm]
                )
                for arm in ARMS
            }

            print(
                "R0_4_PROGRESS "
                f"case={index + 1}/{spec['cases']} "
                f"plain={counts['plain_search']} "
                f"full={counts['matched_full']} "
                f"core={counts['positive_core']} "
                f"control="
                f"{counts['positive_core_count_control']} "
                f"+P="
                f"{counts['positive_plus_PRECEDES']} "
                f"+I="
                f"{counts['positive_plus_INTERFACE_TERMINAL']} "
                f"neg="
                f"{counts['negative_pair_only']}",
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

    comparisons = {
        "core_vs_plain": paired_steps(
            per_fixture,
            "positive_core",
            "plain_search",
        ),
        "core_vs_full": paired_steps(
            per_fixture,
            "positive_core",
            "matched_full",
        ),
        "core_vs_control": paired_steps(
            per_fixture,
            "positive_core",
            "positive_core_count_control",
        ),
        "core_vs_plus_precedes":
            paired_steps(
                per_fixture,
                "positive_core",
                "positive_plus_PRECEDES",
            ),
        "core_vs_plus_interface":
            paired_steps(
                per_fixture,
                "positive_core",
                "positive_plus_INTERFACE_TERMINAL",
            ),
    }

    dose_mismatch_steps = sum(
        int(
            row.get(
                "r04_dose_mismatch_steps",
                0,
            )
        )
        for rows in results.values()
        for row in rows
    )

    control = mechanisms[
        "positive_core_count_control"
    ]

    control_distinct_ok = (
        int(
            control[
                "r04_control_alternative_steps"
            ]
        )
        ==
        int(
            control[
                "r04_control_distinct_steps"
            ]
        )
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
        "feature_vocabulary_match": (
            features.VOCABULARY_DIGEST
            == r04.EXPECTED_VOCABULARY_DIGEST
        ),
        "frozen_cell_violations_zero": (
            sum(
                totals[arm][
                    "frozen_cell_violations"
                ]
                for arm in ARMS
            )
            == 0
        ),
        "authority_granted_zero": (
            sum(
                totals[arm][
                    "authority_granted"
                ]
                for arm in ARMS
            )
            == 0
        ),
        "invalid_transitions_zero": (
            sum(
                totals[arm][
                    "invalid_transitions"
                ]
                for arm in ARMS
            )
            == 0
        ),
        "dose_mismatch_steps_zero": (
            dose_mismatch_steps == 0
        ),
        "count_control_distinct_contract":
            control_distinct_ok,
    }

    resolved = {
        arm: int(
            totals[arm]["resolved"]
        )
        for arm in ARMS
    }

    directional = {
        "core_minus_plain": (
            resolved["positive_core"]
            - resolved["plain_search"]
        ),
        "core_minus_full": (
            resolved["positive_core"]
            - resolved["matched_full"]
        ),
        "core_minus_control": (
            resolved["positive_core"]
            - resolved[
                "positive_core_count_control"
            ]
        ),
        "core_minus_plus_precedes": (
            resolved["positive_core"]
            - resolved[
                "positive_plus_PRECEDES"
            ]
        ),
        "core_minus_plus_interface": (
            resolved["positive_core"]
            - resolved[
                "positive_plus_INTERFACE_TERMINAL"
            ]
        ),
    }

    report = {
        "schema": (
            "elpis.c2r7c.trm0-signed-composition."
            "r0-4-report.v1"
        ),
        "role": (
            "DEVELOPMENT"
            if args.population == "dev"
            else "FINAL_HELDOUT"
        ),
        "population": args.population,
        "population_spec": spec,
        "preregistration_path": str(
            prereg
        ),
        "preregistration_sha256":
            prereg_sha,
        "checkpoint_path": str(
            checkpoint
        ),
        "checkpoint_sha256":
            checkpoint_sha,
        "checkpoint_epoch": int(
            checkpoint_obj.get(
                "epoch",
                -1,
            )
        ),
        "train_corpus_path": str(
            corpus
        ),
        "train_corpus_sha256":
            corpus_sha,
        "manifest": manifest,
        "arm_totals": totals,
        "resolved": resolved,
        "directional_effects":
            directional,
        "paired_steps": comparisons,
        "mechanism_activity":
            mechanisms,
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

    title = (
        "DEVELOPMENT"
        if args.population == "dev"
        else "FINAL"
    )

    print(
        f"===== R0.4 {title} SUMMARY =====",
        flush=True,
    )

    for arm in ARMS:
        s = totals[arm]
        print(
            f"{arm}: "
            f"resolved={s['resolved']}/{s['cases']} "
            f"steps_sum={s['steps_sum']} "
            f"mean_final_residual="
            f"{s['mean_final_residual']:.6f}",
            flush=True,
        )

    print(
        "R0_4_DIRECTIONAL "
        + " ".join(
            f"{k}={v}"
            for k, v in directional.items()
        ),
        flush=True,
    )

    for arm, s in mechanisms.items():
        print(
            f"{arm}: "
            f"queries={s['r04_queries']} "
            f"nonzero_dose="
            f"{s['r04_nonzero_dose_queries']} "
            f"removed="
            f"{s['r04_actual_removed_sum']} "
            f"dose_mismatch="
            f"{s['r04_dose_mismatch_steps']} "
            f"changed_choice="
            f"{s['guidance_tiebreak_changed_choice']} "
            f"control_alt="
            f"{s['r04_control_alternative_steps']} "
            f"control_distinct="
            f"{s['r04_control_distinct_steps']}",
            flush=True,
        )

    print(
        "R0_4_INTEGRITY "
        + " ".join(
            f"{k}={str(v).lower()}"
            for k, v in integrity.items()
        ),
        flush=True,
    )

    print(
        f"R0_4_EVIDENCE out={args.out}",
        flush=True,
    )

    return (
        0
        if all(integrity.values())
        else 5
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="signed-composition-generalization-r0-4"
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

    return run(
        parser.parse_args()
    )


if __name__ == "__main__":
    sys.exit(main())
