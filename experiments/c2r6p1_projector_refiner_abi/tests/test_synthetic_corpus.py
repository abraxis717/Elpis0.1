"""Synthetic corpus (mission 18) + performance characterization (25).

Reuses the frozen C2R6-P0 fixture generator (``gen_valid``) via the
authority import — no duplicated fixture semantics — and drives at least
5,000 PROJECTED synthetic inputs through the full bridge:

  * adapter succeeds
  * packer round-trip exact (declared + active planes)
  * candidate enumeration respects masks
  * NullRefiner byte-continuity (every case)

and, for cases with legal candidates (bounded sample):
  * FirstLegalMoveRefiner transition validates (fresh residual)

No training. Bounded CPU. Writes SYNTHETIC_CORPUS_REPORT.json and
PERFORMANCE_REPORT.json to the persistent work dir.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import conftest as C
from c2r6p0 import fixtures as F
from c2r6p0 import projector as PROJ
from c2r6p0.rules import load_ruleset
from c2r6p1_bridge import (
    FirstLegalMoveRefiner,
    NullRefiner,
    adapt_projection_to_refiner_input,
    legal_candidates,
    replay_transition_chain,
    roundtrip_529,
    run_refiner_bounded,
)
import structural_trm_features as FEATURES
from elpis_p0.structural_residual import residual as authority_residual

RS = load_ruleset()

EXP_DIR = Path(__file__).resolve().parent.parent
WORK_DIR = Path("/mnt/primesauce/Elpis0.1/work/C2R6P1_PROJECTOR_REFINER_ABI_R0")

TARGET = int(os.environ.get("C2R6P1_CORPUS_N", "5000"))
# bounded sample for the heavier transition/replay path
TRANSITION_SAMPLE = 200


def _projected(seed: int):
    req = F.gen_valid(seed)
    pin = C.wrap(req, request_id=req.request_id, debug_tag=f"seed{seed}")
    r = PROJ.project(pin, RS)
    return r if r.status == "PROJECTED" else None


def _shape(r) -> str:
    """Deterministic structural shape label for coverage accounting."""
    n_ops = len(r.bindings.op_bindings)
    lanes = {b.lane for b in r.lane_bindings}
    if n_ops <= 1:
        base = "linear"
    elif n_ops >= 4:
        base = "near-capacity"
    else:
        base = "branched"
    if lanes and max(lanes) >= 3:
        base += "_wide"
    return base


def _run_corpus(n_target: int, max_seeds: int,
                write: bool = True):
    n = 0
    seed = 0
    shapes: dict[str, int] = {}
    legal_cases = 0
    null_ok = 0
    packer_ok = 0
    # timings (ns accumulated)
    t_adapt = 0.0
    t_enum = 0.0
    t_packer = 0.0
    t_null = 0.0
    t_trans = 0.0
    t_residual = 0.0
    t_replay = 0.0
    n_trans = 0
    n_replay = 0
    errors = []

    while n < n_target and seed < max_seeds:
        r = _projected(seed)
        seed += 1
        if r is None:
            continue
        n += 1
        shapes[_shape(r)] = shapes.get(_shape(r), 0) + 1

        # 1. adapter
        t0 = time.perf_counter_ns()
        try:
            ri = adapt_projection_to_refiner_input(r)
        except Exception as exc:  # noqa: BLE001
            errors.append((seed, "adapter", repr(exc)))
            continue
        t_adapt += time.perf_counter_ns() - t0

        # 2. packer round-trip exact (both planes)
        t0 = time.perf_counter_ns()
        try:
            decl_rt = roundtrip_529(ri.declared_features, ri.active_residual)
            ok = (
                decl_rt[0] == ri.declared_features
                and decl_rt[1] == ri.active_residual
            )
        except Exception as exc:  # noqa: BLE001
            ok = False
            errors.append((seed, "packer", repr(exc)))
        t_packer += time.perf_counter_ns() - t0
        if ok:
            packer_ok += 1
        else:
            errors.append((seed, "packer-mismatch", ""))

        # 3. candidate enumeration respects masks
        t0 = time.perf_counter_ns()
        cands = legal_candidates(ri)
        t_enum += time.perf_counter_ns() - t0
        for cm in cands:
            op, a, b = cm.move
            # op-aware target cell (matches D0.1 apply_move / bridge
            # apply_candidate): set writes cell a; move writes
            # cell(rank=b, lane=a) and clears the lane's operational cell.
            tgt = a if op == "set" else b * 9 + a
            if not (0 <= tgt < 81):
                errors.append((seed, "enum-out-of-range", str(cm.move)))
                break
            if ri.frozen_mask[tgt]:
                errors.append((seed, "enum-frozen", str(cm.move)))
                break

        # 4. NullRefiner byte-continuity (every case)
        t0 = time.perf_counter_ns()
        try:
            ri_n, tr_n, ap_n = run_refiner_bounded(
                NullRefiner(), ri, max_moves=1
            )
            cont = (
                ri_n.grid81 == ri.grid81
                and ri_n.frozen_mask == ri.frozen_mask
                and ri_n.writable_mask == ri.writable_mask
                and ri_n.invariants == ri.invariants
                and ri_n.lane_bindings == ri.lane_bindings
                and ri_n.declared_features == ri.declared_features
                and ri_n.active_residual == ri.active_residual
                and ri_n.refinement_state_fingerprint
                == ri.refinement_state_fingerprint
            )
        except Exception as exc:  # noqa: BLE001
            cont = False
            errors.append((seed, "null", repr(exc)))
        t_null += time.perf_counter_ns() - t0
        if cont:
            null_ok += 1
        else:
            errors.append((seed, "null-mismatch", ""))

        # 5. bounded transition sample: FirstLegalMoveRefiner + replay
        if cands:
            legal_cases += 1
            if n_trans < TRANSITION_SAMPLE:
                t0 = time.perf_counter_ns()
                try:
                    ri1, tr1, applied1 = run_refiner_bounded(
                        FirstLegalMoveRefiner(), ri, max_moves=4
                    )
                    valid = applied1 >= 0
                except Exception as exc:  # noqa: BLE001
                    valid = False
                    errors.append((seed, "transition", repr(exc)))
                t_trans += time.perf_counter_ns() - t0
                if valid:
                    n_trans += 1
                # fresh residual check + replay on the produced trace
                if valid and n_replay < TRANSITION_SAMPLE:
                    t0 = time.perf_counter_ns()
                    try:
                        final = replay_transition_chain(r, tr1)
                        # fresh-residual boundary (mission 11): the residual
                        # is recomputed from the MUTATED grid via the
                        # authoritative structural machinery, and the
                        # 529-bit active vector is its encoding.
                        fresh_ids = tuple(
                            authority_residual(final.grid81, final.invariants)
                        )
                        fresh_decl, fresh_act = FEATURES.encode_constraint_state(
                            final.invariants, fresh_ids
                        )
                        res_ok = (
                            fresh_ids == tuple(final.residual_ids)
                            and tuple(fresh_act) == tuple(final.active_residual)
                            and tuple(fresh_decl) == tuple(final.declared_features)
                        )
                        # replay byte-identity (deterministic re-derivation)
                        replayed = replay_transition_chain(r, tr1)
                        replay_ok = (
                            replayed.grid81 == final.grid81
                            and replayed.residual_ids == final.residual_ids
                            and replayed.refinement_state_fingerprint
                            == final.refinement_state_fingerprint
                        )
                    except Exception as exc:  # noqa: BLE001
                        res_ok = False
                        replay_ok = False
                        errors.append((seed, "replay", repr(exc)))
                    t_replay += time.perf_counter_ns() - t0
                    n_replay += 1
                    if not (res_ok and replay_ok):
                        errors.append(
                            (seed, "residual-or-replay", f"{res_ok}/{replay_ok}")
                        )

    return {
        "n_projected": n,
        "seeds_scanned": seed,
        "shapes": shapes,
        "legal_cases": legal_cases,
        "null_ok": null_ok,
        "packer_ok": packer_ok,
        "transitions": n_trans,
        "replays": n_replay,
        "errors": errors,
        "timings_ns": {
            "adapter": t_adapt,
            "enumeration": t_enum,
            "packer_roundtrip": t_packer,
            "null_refiner": t_null,
            "transition": t_trans,
            "replay": t_replay,
        },
    }


def test_synthetic_corpus_gate():
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    res = _run_corpus(TARGET, max_seeds=TARGET * 4 + 200, write=True)

    assert res["n_projected"] >= TARGET, (
        f"only {res['n_projected']} projected cases (target {TARGET})"
    )
    assert res["packer_ok"] == res["n_projected"], (
        f"packer roundtrip mismatch: {res['packer_ok']}/{res['n_projected']}"
    )
    assert res["null_ok"] == res["n_projected"], (
        f"NullRefiner continuity mismatch: {res['null_ok']}/{res['n_projected']}"
    )
    assert not res["errors"], (
        f"{len(res['errors'])} corpus errors; first: {res['errors'][:5]}"
    )

    report = {
        "mission": "C2R6P1 synthetic corpus (18) + performance (25)",
        "target_cases": TARGET,
        "n_projected": res["n_projected"],
        "seeds_scanned": res["seeds_scanned"],
        "coverage_shapes": res["shapes"],
        "packer_roundtrip_exact": res["packer_ok"],
        "null_refiner_continuity": res["null_ok"],
        "transitions_validated": res["transitions"],
        "replays_validated": res["replays"],
        "errors": res["errors"],
        "per_case_latency_ns": {
            k: (v / res["n_projected"] if res["n_projected"] else 0)
            for k, v in res["timings_ns"].items()
        },
        "total_latency_ns": res["timings_ns"],
    }
    out = WORK_DIR / "SYNTHETIC_CORPUS_REPORT.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(f"corpus: {res['n_projected']} projected; shapes={res['shapes']}")


def test_performance_report():
    """Bounded CPU overhead characterization (mission 25).

    Characterizes only — no threshold beyond detecting pathological
    behavior (a per-case adapter > 5 ms or packer roundtrip > 5 ms would
    indicate pathology for 529-bit vectors)."""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    res = _run_corpus(300, max_seeds=1200, write=False)
    n = max(1, res["n_projected"])
    per = {k: v / n for k, v in res["timings_ns"].items()}
    report = {
        "mission": "C2R6P1 performance (25)",
        "cases": res["n_projected"],
        "per_case_ns": per,
        "per_case_ms": {k: v / 1e6 for k, v in per.items()},
        "total_ns": res["timings_ns"],
        "note": (
            "characterization only; no threshold beyond pathology "
            "detection (per-case adapter/packer < 5 ms)"
        ),
    }
    out = WORK_DIR / "PERFORMANCE_REPORT.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True))
    # pathology guard
    assert per["adapter"] < 5e6, f"adapter pathological: {per['adapter']} ns"
    assert per["packer_roundtrip"] < 5e6, (
        f"packer pathological: {per['packer_roundtrip']} ns"
    )
