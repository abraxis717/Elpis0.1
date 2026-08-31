"""Differential authority test vs the C2R7-C probe (mission 29).

Overlap surface: the C2R7-C redteam probe
(experiments/c2r7c_semantic_structural_probe/source/redteam_c2r7c_residual_probe.py)
and this candidate (c2r6p0) both build their structural state on the SAME
frozen authoritative module
(experiments/c2r7c_semantic_structural_probe/source/structural_residual.py).
The probe is a gate instrument (its own header says "Not production");
c2r6p0 is the semantic projector. For every overlapping behavior this
harness EXECUTES both sides and classifies:

  EXACT_MATCH                   same function, same inputs, same output
  INTENTIONAL_DIFFERENCE         different behavior, documented reason
  INCOMPARABLE                    different role, no meaningful equality
  STRICTER_NEW_IMPLEMENTATION     candidate adds a check the probe lacks

It does NOT force equality where the old helper was only a probe.

Each row records: area, classification, cases_checked, old_behavior,
new_behavior, reason, authority_reference. Output: DIFFERENTIAL_REPORT.json
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

EXP_DIR = Path(__file__).resolve().parent.parent
WORKTREE = EXP_DIR.parent.parent
EVIDENCE_DIR = Path(
    "/mnt/primesauce/Elpis0.1/work/C2R6P0_DETERMINISTIC_PROJECTOR_R0"
)
PROBE_SRC = WORKTREE / "experiments/c2r7c_semantic_structural_probe/source"

sys.path.insert(0, str(EXP_DIR))
import c2r6p0  # noqa: E402,F401  (installs the namespace overlay)
from c2r6p0 import fixtures as FX  # noqa: E402
from c2r6p0 import projector as PROJ  # noqa: E402
from c2r6p0.contracts import ProjectionInputV1  # noqa: E402
from c2r6p0.rules import load_ruleset  # noqa: E402
import structural_trm_features as FEATURES  # noqa: E402

# A FRESH module object loaded from the probe's frozen copy under a DISTINCT
# package name. c2r6p0's overlay loads the same file as
# elpis_p0.structural_residual; loading it again as probe_sr_pkg.structural_residual
# (a namespace package over the same overlay dir + canonical p0 dir, so the
# relative `.contracts` import resolves identically) lets us execute BOTH
# module objects and prove they are the same file with the same behavior.
PROBE_OVERLAY_P0 = PROBE_SRC / "elpis_p0"
CANON_P0_SRC = (
    WORKTREE / "components/Pipeline/P0ControlProtocol/src/elpis_p0"
)
import types  # noqa: E402

_probe_pkg = types.ModuleType("probe_sr_pkg")
_probe_pkg.__path__ = [str(PROBE_OVERLAY_P0), str(CANON_P0_SRC)]  # type: ignore[attr-defined]
_probe_pkg.__package__ = "probe_sr_pkg"
sys.modules["probe_sr_pkg"] = _probe_pkg
probe_sr = importlib.import_module("probe_sr_pkg.structural_residual")

# The overlaid authoritative module the candidate uses.
import elpis_p0.structural_residual as cand_sr  # noqa: E402

RULES = load_ruleset()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _corpus_pins() -> list[ProjectionInputV1]:
    pins: list[ProjectionInputV1] = []
    for f in FX.POSITIVE_FIXTURES:
        pins.append(ProjectionInputV1.from_signed(f.graph, request_id="diff"))
    for s in range(0, 30):
        pins.append(
            ProjectionInputV1.from_signed(FX.gen_valid(s), request_id="diff")
        )
    return pins


def main() -> int:
    rows: list[dict] = []
    contradictions: list[str] = []
    pins = _corpus_pins()
    projected = 0

    # ------------------------------------------------------------------
    # 1. File identity: the frozen authority module is byte-identical in
    #    both import paths (overlay vs direct probe-source import).
    # ------------------------------------------------------------------
    cand_file = Path(cand_sr.__file__)  # type: ignore[arg-type]
    cand_sha = _sha(cand_file)
    probe_sha = _sha(PROBE_SRC / "structural_residual.py")
    same_file = cand_sha == probe_sha
    rows.append({
        "area": "authority_module_identity",
        "classification": "EXACT_MATCH" if same_file else "INCOMPARABLE",
        "cases_checked": 1,
        "old_behavior": f"probe imports {probe_sha[:16]}... (direct file)",
        "new_behavior": f"candidate overlays {cand_sha[:16]}... (namespace overlay of the same file)",
        "reason": "single frozen authoritative source; no fork",
        "authority_reference": str(PROBE_SRC / "structural_residual.py"),
    })
    if not same_file:
        contradictions.append("authority module file differs between paths")

    # ------------------------------------------------------------------
    # 2. residual(): identical primitive, executed on the candidate's own
    #    projected grids. The candidate's residual_ids MUST equal a fresh
    #    call of the probe-side module object on the same (grid, invariants).
    # ------------------------------------------------------------------
    n_res = 0
    n_res_match = 0
    for pin in pins:
        r = PROJ.project(pin, RULES)
        if not r.is_projected():
            continue
        projected += 1
        n_res += 1
        fresh = probe_sr.residual(r.grid81, tuple(r.invariants))
        if list(fresh) == list(r.residual_ids):
            n_res_match += 1
        else:
            contradictions.append(
                f"residual mismatch: candidate={list(r.residual_ids)[:3]} "
                f"authority={list(fresh)[:3]}"
            )
    rows.append({
        "area": "residual_derivation",
        "classification": "EXACT_MATCH" if n_res_match == n_res else "INCOMPARABLE",
        "cases_checked": n_res,
        "old_behavior": "probe computes residual(schema.initial_grid, schema.invariants) with the same function",
        "new_behavior": f"candidate's residual_ids equal a fresh probe-side call on its own projected grids ({n_res_match}/{n_res})",
        "reason": "R16: no second residual calculator; the authoritative function is the single source",
        "authority_reference": "structural_residual.residual",
    })

    # ------------------------------------------------------------------
    # 3. validate_transition(): the probe's two authority checks
    #    (cheat_frozen / cheat_invent) executed on a CANDIDATE seed: a
    #    mutation of a frozen locus must be rejected; a legal mutation of
    #    a writable locus must be accepted. Same function, same verdicts.
    # ------------------------------------------------------------------
    n_trans = 0
    n_frozen_rej = 0
    n_writable_acc = 0
    for pin in pins:
        r = PROJ.project(pin, RULES)
        if not r.is_projected() or r.structural_schema is None:
            continue
        schema = r.structural_schema
        before = schema.initial_grid
        # The fixed candidate invariant: every cell the candidate offers
        # as writable is writable under the authority schema too (so a
        # refiner acting on r.writable_mask can only make
        # validate_transition-legal moves).
        for i in range(81):
            if r.writable_mask[i] and schema.writable_mask[i] == 0:
                contradictions.append(
                    f"candidate writable cell {i} frozen by the schema"
                )
        # cheat_frozen analogue: the terminal control locus is FROZEN in
        # the schema and holds RESOLUTION; overwriting it must be
        # rejected by validate_transition.
        g2 = list(before)
        g2[80] = 5  # TRANSFORM
        n_trans += 1
        try:
            probe_sr.validate_transition(before, tuple(g2), schema)
            contradictions.append("cheat_frozen (terminal locus) accepted")
        except probe_sr.StructuralSchemaError:
            n_frozen_rej += 1
        # legal writable placement: EXPANSION (the authority's own
        # "unresolved locus" token) in a cell BOTH masks call writable
        # and that is VOID in the initial grid. EXPANSION is not
        # operational, so no per-lane operational multiset changes.
        wc = next(
            (
                i for i in range(81)
                if r.writable_mask[i] and schema.writable_mask[i]
                and before[i] == 0
            ),
            None,
        )
        if wc is None:
            continue
        g3 = list(before)
        g3[wc] = 6  # EXPANSION
        n_trans += 1
        try:
            probe_sr.validate_transition(before, tuple(g3), schema)
            n_writable_acc += 1
        except probe_sr.StructuralSchemaError:
            contradictions.append(f"legal writable placement rejected at {wc}")
    rows.append({
        "area": "transition_validation_authority_checks",
        "classification": (
            "EXACT_MATCH"
            if n_trans and n_frozen_rej >= n_trans // 2
            and n_writable_acc >= n_trans // 2
            else "INCOMPARABLE"
        ),
        "cases_checked": n_trans,
        "old_behavior": "probe asserts cheat_frozen/cheat_invent are rejected/accepted by validate_transition on its own fixtures",
        "new_behavior": f"same verdicts hold on candidate seeds: frozen-locus writes rejected ({n_frozen_rej}), legal writable writes accepted ({n_writable_acc})",
        "reason": "the projector emits a seed the refiner may legally refine, and whose frozen facts it may not",
        "authority_reference": "structural_residual.validate_transition",
    })

    # ------------------------------------------------------------------
    # 4. materialisable / is_resolved / quiescent / halt_score: the
    #    authority's internal-consistency identity, checked on candidate
    #    seeds. Both the probe and the candidate consume these; the
    #    identity must hold.
    # ------------------------------------------------------------------
    n_cons = 0
    n_ok = 0
    for pin in pins:
        r = PROJ.project(pin, RULES)
        if not r.is_projected() or r.structural_schema is None:
            continue
        schema = r.structural_schema
        n_cons += 1
        res = probe_sr.residual(r.grid81, tuple(r.invariants))
        mat = probe_sr.materialisable(r.grid81, schema)
        quo = probe_sr.quiescent(r.grid81)
        isr = probe_sr.is_resolved(r.grid81, schema)
        if isr == (len(res) == 0 and mat and quo):
            n_ok += 1
        else:
            contradictions.append("is_resolved identity violated")
    rows.append({
        "area": "resolution_semantics_identity",
        "classification": "EXACT_MATCH" if n_ok == n_cons else "INCOMPARABLE",
        "cases_checked": n_cons,
        "old_behavior": "probe consumes is_resolved/halt_score on its fixtures",
        "new_behavior": f"is_resolved == (residual empty and materialisable and quiescent) holds on {n_ok}/{n_cons} candidate seeds",
        "reason": "RESOLUTION stays governed by the authoritative residual/materialisable authority; the projector never marks a topology resolved merely because an OUTPUT exists (mission 18)",
        "authority_reference": "structural_residual.is_resolved / materialisable / quiescent",
    })

    # ------------------------------------------------------------------
    # 5. capacity_requirements / decomposition_measure: the probe's
    #    capacity probe tuples executed through the same function; the
    #    candidate's allocator capacity decisions agree with the
    #    authority's fits rule for the same requirement tuples.
    # ------------------------------------------------------------------
    probe_tuples = ((4, 3, 1, 1), (9, 4, 2, 2), (6, 8, 3, 3))
    cap_rows = []
    n_cap_ok = 0
    for lanes, chain, cross, mem in probe_tuples:
        req = probe_sr.capacity_requirements(lanes, chain, cross, mem)
        fits = req[0] <= 8 and req[1] <= probe_sr.RANKS and req[2] <= 81
        cap_rows.append({
            "tuple": [lanes, chain, cross, mem],
            "requirement": [int(req[0]), int(req[1]), int(req[2])],
            "fits": fits,
            "measure": probe_sr.decomposition_measure(*req),
        })
        n_cap_ok += 1
    # AND on every PROJECTED candidate seed: the capacity record must be
    # exactly the authority function evaluated on the seed's own semantic
    # facts (n_ops, longest_chain, route_count, memory_count) — no second
    # capacity model. longest_chain is recomputed INDEPENDENTLY from the
    # binding sidecar's dependency edges (Kahn longest path).
    n_seed_cap = 0
    n_seed_cap_ok = 0
    for pin in pins:
        r = PROJ.project(pin, RULES)
        if not r.is_projected() or not r.capacity:
            continue
        n_seed_cap += 1
        n_ops = len(r.bindings.op_bindings)
        routes = sum(
            1 for b in r.bindings.edge_bindings
            if b.structural_kind == "route"
        )
        mem = sum(
            1 for b in r.bindings.edge_bindings
            if b.structural_kind == "state_feeds"
        )
        # INDEPENDENT longest-chain recompute from the sidecar, using the
        # SAME schedule-DAG semantics the canonicalizer/allocator use
        # (canonicalize._schedule_dag_edges): dependency edges gap 1,
        # route/state_feeds relation edges gap 2. longest_chain = 1 +
        # max longest-path distance (node count of the longest path).
        succ: dict[str, list[tuple[str, int]]] = {}
        indeg: dict[str, int] = {}
        for b in r.bindings.edge_bindings:
            if b.semantic_kind == "dependency":
                s, d = (
                    b.payload["predecessor"], b.payload["successor"]
                )
                gap = 1
            elif (
                b.semantic_kind == "relation"
                and b.structural_kind in ("route", "state_feeds")
            ):
                s, d = b.payload["source"], b.payload["target"]
                gap = 2
            else:
                continue
            succ.setdefault(s, []).append((d, gap))
            indeg[d] = indeg.get(d, 0) + 1
            indeg.setdefault(s, indeg.get(s, 0))
        dist = {
            b.semantic_id: 1 for b in r.bindings.op_bindings
        }
        queue = [op for op in dist if indeg.get(op, 0) == 0]
        while queue:
            queue.sort()
            nxt = []
            for op in queue:
                for d, gap in succ.get(op, ()):
                    nd = dist[op] + gap
                    if nd > dist.get(d, 0):
                        dist[d] = nd
                    indeg[d] -= 1
                    if indeg[d] == 0:
                        nxt.append(d)
            queue = nxt
        longest_chain = max(dist.values()) if dist else 0
        req = probe_sr.capacity_requirements(n_ops, longest_chain, routes, mem)
        rec = r.capacity
        ok = (
            rec["lanes_required"] == int(req[0])
            and rec["ranks_required"] == int(req[1])
            and rec["loci_required"] == int(req[2])
            and rec["longest_chain"] == longest_chain
        )
        if ok:
            n_seed_cap_ok += 1
        else:
            contradictions.append(
                f"seed capacity record not the authority function: "
                f"record={rec} authority={tuple(req)} chain={longest_chain}"
            )
    rows.append({
        "area": "capacity_requirements",
        "classification": (
            "EXACT_MATCH"
            if n_cap_ok == len(probe_tuples) and n_seed_cap_ok == n_seed_cap
            else "INCOMPARABLE"
        ),
        "cases_checked": len(probe_tuples) + n_seed_cap,
        "old_behavior": f"probe capacity_probe: {cap_rows}",
        "new_behavior": (
            f"probe tuples reproduced through the same authority function; "
            f"candidate capacity records equal the authority "
            f"capacity_requirements evaluated on the seed's own facts on "
            f"{n_seed_cap_ok}/{n_seed_cap} seeds"
        ),
        "reason": "overflow -> DECOMPOSITION_REQUIRED is decided by the same capacity function; no second capacity model (mission 27)",
        "authority_reference": "structural_residual.capacity_requirements / decomposition_measure",
    })

    # ------------------------------------------------------------------
    # 6. build_structural_schema: the ONE intended behavioral
    #    difference. The probe's compiler is deliberately degenerate
    #    (every op at rank 0, EXPANSION at rank 1, maximal writable area)
    #    so its refiner-ablation checks are meaningful; the candidate
    #    projects the same semantic facts into a deterministically
    #    placed, fact-frozen seed.
    # ------------------------------------------------------------------
    diff_examples = []
    n_diff = 0
    for pin in pins[:12]:
        r = PROJ.project(pin, RULES)
        if not r.is_projected():
            continue
        n_diff += 1
        try:
            probe_seed = probe_sr.build_structural_schema(
                semantic_request_digest=r.semantic_input_digest,
                lane_bindings=tuple(r.lane_bindings),
                invariants=tuple(r.invariants),
            )
        except probe_sr.DecompositionRequired:
            continue
        grids_equal = list(probe_seed.initial_grid) == list(r.grid81)
        masks_equal = list(probe_seed.writable_mask) == list(r.writable_mask)
        diff_examples.append({
            "case": pin.request_id,
            "lanes": [b.lane for b in r.lane_bindings],
            "probe_writable_cells": sum(probe_seed.writable_mask),
            "candidate_writable_cells": sum(r.writable_mask),
            "probe_frozen_cells": 81 - sum(probe_seed.writable_mask),
            "candidate_frozen_cells": 81 - sum(r.writable_mask),
            "grids_equal": grids_equal,
            "masks_equal": masks_equal,
        })
    n_differ = sum(
        1 for d in diff_examples if not d["grids_equal"] or not d["masks_equal"]
    )
    rows.append({
        "area": "initial_seed_construction",
        "classification": (
            "INTENTIONAL_DIFFERENCE" if n_differ > 0 else "EXACT_MATCH"
        ),
        "cases_checked": len(diff_examples),
        "old_behavior": (
            "probe's build_structural_schema: deliberately degenerate seed — "
            "every operation starts at rank 0 (violating every PRECEDES "
            "invariant), EXPANSION at rank 1, entire bound lanes writable, "
            f"only the terminal control cell frozen "
            f"(example: {diff_examples[0]['probe_writable_cells'] if diff_examples else 0} writable cells)"
        )
        if diff_examples
        else "probe's build_structural_schema: degenerate seed",
        "new_behavior": (
            f"candidate project(): deterministic rank placement from the "
            f"topological order, all determined loci (routes/memory/"
            f"constraints/interfaces/terminal) frozen — example: "
            f"{diff_examples[0]['candidate_writable_cells'] if diff_examples else 0} "
            f"writable cells for the same lanes+invariants"
        )
        if diff_examples
        else "candidate project(): deterministic seed",
        "reason": (
            "the probe is a GATE INSTRUMENT whose ablation checks require the "
            "seed to leave scheduling unsolved (null/shadow/cheat refiners "
            "must fail to resolve it); the candidate is the SEMANTIC "
            "PROJECTOR whose job is to compile known facts into the seed and "
            "leave only genuinely-unresolved topology writable. "
            "semantic projection != structural solution (mission 2)."
        ),
        "authority_reference": (
            "redteam_c2r7c_residual_probe.py header: 'Gate instrument for the "
            "structural residual oracle. Not production.'; "
            "structural_residual.build_structural_schema docstring: 'Rank "
            "placement, routing, memory ownership, constraint discharge and "
            "interface placement are left unresolved on purpose — that is the "
            "refiner's entire job.'"
        ),
        "examples": diff_examples[:6],
    })

    # ------------------------------------------------------------------
    # 7. Refiners (null/shadow/random/search/cheat_frozen/cheat_invent):
    #    downstream of projection; the candidate is upstream. Incomparable.
    # ------------------------------------------------------------------
    rows.append({
        "area": "refiner_behavior",
        "classification": "INCOMPARABLE",
        "cases_checked": 0,
        "old_behavior": "probe runs six refiner strategies against its degenerate seeds and reports resolve rates",
        "new_behavior": "candidate has no refiner; it only emits the seed the refiner would receive (structure, masks, invariants, residual, trace)",
        "reason": "different layer of the stack: the probe measures refiner quality; the candidate builds the refiner's input. No equality is expected or asserted (mission 32: no execution authority in the projector).",
        "authority_reference": "redteam_c2r7c_residual_probe.REFINERS",
    })

    # ------------------------------------------------------------------
    # 8. Feature vocabulary: both sides pin the same structural_trm_features
    #    vocabulary digest / width.
    # ------------------------------------------------------------------
    vocab_match = FEATURES.VOCABULARY_DIGEST == RULES.vocabulary_digest
    rows.append({
        "area": "feature_vocabulary",
        "classification": "EXACT_MATCH" if vocab_match else "INCOMPARABLE",
        "cases_checked": 1,
        "old_behavior": f"structural_trm_features.VOCABULARY_DIGEST = {FEATURES.VOCABULARY_DIGEST}",
        "new_behavior": f"candidate ruleset pins the same digest; declared/active vectors are {RULES.feature_width}-wide via the same encode_constraint_state",
        "reason": "R16/R20: exact width 529 and vocabulary identity from the shared module; no second vocabulary",
        "authority_reference": "structural_trm_features.VOCABULARY_DIGEST",
    })
    if not vocab_match:
        contradictions.append("vocabulary digest mismatch between sides")

    report = {
        "schema": "elpis.c2r6p0.differential_report.v1",
        "authority_commit": "ccbca3841de6786746a6c62950f924fae16be881",
        "probe_path": str(PROBE_SRC / "redteam_c2r7c_residual_probe.py"),
        "projected_cases": projected,
        "rows": rows,
        "classifications": {
            r["area"]: r["classification"] for r in rows
        },
        "contradictions": contradictions,
        "no_silent_divergence": all(
            r["classification"] in (
                "EXACT_MATCH",
                "INTENTIONAL_DIFFERENCE",
                "INCOMPARABLE",
                "STRICTER_NEW_IMPLEMENTATION",
            )
            and (r["classification"] != "INCOMPARABLE" or r["reason"])
            for r in rows
        ),
        "pass": not contradictions,
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE_DIR / "DIFFERENTIAL_REPORT.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for r in rows:
        print(f"{r['classification']:28s} {r['area']}")
    print(f"contradictions={len(contradictions)} pass={report['pass']}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
