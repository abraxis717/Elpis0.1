"""Deterministic mutation harness (mission 28).

Each mutant is a single, semantically-meaningful edit to a disposable
copy of the c2r6p0 package (never the worktree source). The mutant is
KILLED if the fast core test suite fails against it; SURVIVED if it
passes. Syntax-breaking mutants are rejected by the patch-application
precondition (old text must occur exactly once) and are not counted.

The report is written to the persistent evidence directory
(MUTATION_REPORT.json).

Target: >= 20 substantive mutants, every one killed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# The mutation copy must keep the repo-relative layout because
# c2r6p0/_bootstrap.py derives the pinned authority paths from the
# package location. We therefore copy the whole (12MB) worktree per
# mutant.
WORKTREE = Path(__file__).resolve().parents[3]
EXP_DIR = WORKTREE / "experiments" / "c2r6p0_deterministic_projector"
EVIDENCE_DIR = Path(
    "/mnt/primesauce/Elpis0.1/work/C2R6P0_DETERMINISTIC_PROJECTOR_R0"
)

# Fast core suite (the heavy fuzz/hashseed modules are excluded to keep
# per-mutant cost ~1s).
CORE_MODULES = (
    "tests/test_contract.py",
    "tests/test_canonicalization.py",
    "tests/test_graph.py",
    "tests/test_allocator.py",
    "tests/test_roles.py",
    "tests/test_routes.py",
    "tests/test_memory.py",
    "tests/test_constraints.py",
    "tests/test_interfaces.py",
    "tests/test_masks.py",
    "tests/test_residual.py",
    "tests/test_trace.py",
    "tests/test_roundtrip.py",
    "tests/test_metamorphic.py",
    "tests/test_capacity.py",
)


@dataclass(frozen=True)
class Mutant:
    name: str
    file: str            # relative to c2r6p0 package
    old: str
    new: str
    intent: str


C = "c2r6p0/"  # path prefix (relative to experiment dir)

MUTANTS: list[Mutant] = [
    Mutant(
        "M01_canonical_output_sort_dropped",
        f"{C}canonicalize.py",
        '    content["output_entity_ids"] = sorted(payload["output_entity_ids"])\n',
        "    # M01: output sort removed (declaration order leaks into digest)\n",
        "canonical content must sort declared outputs (mission 8)",
    ),
    Mutant(
        "M02_canonical_output_sort_reversed",
        f"{C}canonicalize.py",
        '    content["output_entity_ids"] = sorted(payload["output_entity_ids"])\n',
        '    content["output_entity_ids"] = list(reversed(payload["output_entity_ids"]))\n',
        "canonical output sort direction (mission 8)",
    ),
    Mutant(
        "M03_dependency_direction_flipped",
        f"{C}canonicalize.py",
        """        edges.append(
            (dep["predecessor_operation_id"],
             dep["successor_operation_id"], 1)
        )""",
        """        edges.append(
            (dep["successor_operation_id"],
             dep["predecessor_operation_id"], 1)
        )""",
        "dependency direction must not be flipped in the schedule DAG",
    ),
    Mutant(
        "M04_route_gap_weakened",
        f"{C}canonicalize.py",
        '            edges.append((rel["source_id"], rel["target_id"], 2))\n        elif rel["predicate"] == STATE_FEEDS_PREDICATE:\n            edges.append((rel["source_id"], rel["target_id"], 2))',
        '            edges.append((rel["source_id"], rel["target_id"], 1))\n        elif rel["predicate"] == STATE_FEEDS_PREDICATE:\n            edges.append((rel["source_id"], rel["target_id"], 2))',
        "route schedule gap must stay 2 (CROSS_LANE_ROUTE needs an "
        "intermediate rank)",
    ),
    Mutant(
        "M05_route_endpoint_lane_swapped",
        f"{C}allocator.py",
        """        c = _place_in_interval(
            placement, lane_of[dst], r_src, r_dst, f"route:{rel['relation_id']}"
        )""",
        """        c = _place_in_interval(
            placement, lane_of[src], r_src, r_dst, f"route:{rel['relation_id']}"
        )""",
        "route locus must sit in the CONSUMER lane between the ranks",
    ),
    Mutant(
        "M06_memory_lane_swapped",
        f"{C}allocator.py",
        """        c = _place_in_interval(
            placement, lane_of[src], r_src, r_dst,
            f"memory:{rel['relation_id']}",
        )""",
        """        c = _place_in_interval(
            placement, lane_of[dst], r_src, r_dst,
            f"memory:{rel['relation_id']}",
        )""",
        "memory span must sit in the PRODUCER lane (MEMORY_SPAN)",
    ),
    Mutant(
        "M07_constraint_placed_before_owner",
        f"{C}allocator.py",
        """            c = _place_tail(placement, lane, r_op + 1,
                            f"constraint:{con['constraint_id']}")""",
        """            c = _place_in_interval(
                placement, lane, r_op - 1, r_op,
                f"constraint:{con['constraint_id']}")""",
        "constraints compile to CONSTRAINT_AFTER the owner (R11)",
    ),
    Mutant(
        "M08_interface_placed_before_bound_op",
        f"{C}allocator.py",
        """        c = _place_tail(placement, lane, r_op + 1,
                        f"interface:{rel['relation_id']}")""",
        """        c = _place_in_interval(
            placement, lane, r_op - 1, r_op,
            f"interface:{rel['relation_id']}")""",
        "interface loci sit after the bound op (R12 INTERFACE_TERMINAL)",
    ),
    Mutant(
        "M09_role_single_op_transform_to_input",
        f"{C}allocator.py",
        """        if has_in and not has_out:
            return INPUT
        if has_out and not has_in:
            return OUTPUT
        return TRANSFORM""",
        """        if has_in and not has_out:
            return INPUT
        if has_out and not has_in:
            return OUTPUT
        return INPUT""",
        "single op with in+out is TRANSFORM (R8.ROLE_TOKEN)",
    ),
    Mutant(
        "M10_terminal_cell_shifted",
        f"{C}allocator.py",
        "    placement.grid[TERMINAL_CELL] = RESOLUTION\n",
        "    placement.grid[TERMINAL_CELL - 1] = RESOLUTION\n",
        "terminal RESOLUTION locus is cell 80 (R13)",
    ),
    Mutant(
        "M11_lane_capacity_boundary_off_by_one",
        f"{C}allocator.py",
        "    if n_ops > MAX_SEMANTIC_LANES:\n",
        "    if n_ops >= MAX_SEMANTIC_LANES:\n",
        "exactly-fitting graphs must still project (R15)",
    ),
    Mutant(
        "M12_rank_capacity_check_removed",
        f"{C}allocator.py",
        "    max_dist = max(analysis.dist.values())\n    if max_dist >= RANKS:\n",
        "    max_dist = max(analysis.dist.values())\n    if False:\n",
        "rank overflow must decompose (R15.CAPACITY_RANKS)",
    ),
    Mutant(
        "M13_rank_overflow_check_flipped",
        f"{C}allocator.py",
        "    if max_dist >= RANKS:\n",
        "    if max_dist < RANKS:\n",
        "rank overflow must decompose (R15.CAPACITY_RANKS); a flipped "
        "check decomposes fitting graphs",
    ),
    Mutant(
        "M14_frozen_writable_overlap",
        f"{C}residual.py",
        '    writable = tuple(1 - f for f in frozen)\n',
        "    writable = tuple(f for f in frozen)\n",
        "frozen and writable must be disjoint and covering (R14)",
    ),
    Mutant(
        "M15_residual_declared_active_swapped",
        f"{C}projector.py",
        "    residual_ids, declared, active = derive_residual_state(\n",
        "    residual_ids, active, declared = derive_residual_state(\n",
        "declared/active 529 vectors must keep their meaning (R16)",
    ),
    Mutant(
        "M16_residual_derivation_skipped",
        f"{C}projector.py",
        "    residual_ids, declared, active = derive_residual_state(\n",
        "    residual_ids, declared, active = ((), (0,) * 529, (0,) * 529)\n    _unused_residual_ids, _unused_declared, _unused_active = derive_residual_state(\n",
        "the authoritative residual must be the one carried (R16)",
    ),
    Mutant(
        "M17_fingerprint_grid_dropped",
        f"{C}residual.py",
        '        "grid81": list(grid),\n',
        "        # M17: grid dropped from fingerprint payload\n",
        "fingerprint must cover the Grid81 state (R17 coverage)",
    ),
    Mutant(
        "M18_skeleton_dependencies_dropped",
        f"{C}residual.py",
        '        "dependencies": [dependencies[k] for k in sorted(dependencies)],\n',
        '        "dependencies": [],\n',
        "skeleton must recover every explicit dependency (mission 22)",
    ),
    Mutant(
        "M19_route_trace_rule_identity_wrong",
        f"{C}allocator.py",
        """        _act(
            placement,
            "ROUTE_INSERTED",
            R.R_ROUTE_PLACE,""",
        """        _act(
            placement,
            "ROUTE_INSERTED",
            R.R_MEMORY_PLACE,""",
        "route events must cite R9.ROUTE_PLACEMENT, not R10 (trace rule "
        "identity, mission 7)",
    ),
    Mutant(
        "M20_cycle_check_removed",
        f"{C}canonicalize.py",
        "        _check_contradictions,\n        _check_schedule_acyclic,\n    ):\n",
        "        _check_contradictions,\n    ):\n",
        "illegal cycles must be rejected deterministically (R5)",
    ),
    Mutant(
        "M21_duplicate_identity_check_relaxed",
        f"{C}canonicalize.py",
        "            if ident in by_id and by_id[ident] != item:\n",
        "            if False and by_id[ident] != item:\n",
        "duplicate incompatible identities must be rejected (R3)",
    ),
    Mutant(
        "M22_dangling_output_check_removed",
        f"{C}canonicalize.py",
        """    for out in payload["output_entity_ids"]:
        if out not in producers:""",
        """    for out in payload["output_entity_ids"]:
        if False and out not in producers:""",
        "declared outputs must have a producer (missing binding)",
    ),
    Mutant(
        "M23_ambiguous_interface_check_removed",
        f"{C}canonicalize.py",
        "    for src, tgts in sorted(interface_sources.items()):\n        if len(tgts) > 1:\n",
        "    for src, tgts in sorted(interface_sources.items()):\n        if False:\n",
        "interface bound to two ops is ambiguous (R4)",
    ),
    Mutant(
        "M24_arity_gt_lt_swapped",
        f"{C}canonicalize.py",
        '    if comparator == "gt":\n        return actual > value\n',
        '    if comparator == "gt":\n        return actual < value\n',
        "arity comparator semantics (R4.ARITY_VIOLATION)",
    ),
    Mutant(
        "M25_op_binding_identity_rewritten",
        f"{C}projector.py",
        """        op_bindings=tuple(sorted(
            placement.op_bindings, key=lambda b: b.semantic_id)),""",
        """        op_bindings=tuple(sorted(
            (b._replace(semantic_id="op_*") for b in placement.op_bindings),
            key=lambda b: b.semantic_id)),""",
        "op binding must keep the semantic operation identity (mission 12)",
    ),
    Mutant(
        "M26_input_digest_constant",
        f"{C}canonicalize.py",
        """    digest = domain_digest(
        "elpis.c2r6p0.semantic-input-canonical.v1", content
    )""",
        """    digest = domain_digest(
        "elpis.c2r6p0.semantic-input-canonical.v1", {}
    )""",
        "semantic input digest must bind the graph content (mission 21)",
    ),
]


def _apply_mutant(copy_dir: Path, m: Mutant) -> None:
    path = copy_dir / m.file
    s = path.read_text()
    assert s.count(m.old) == 1, (
        f"mutant {m.name}: expected exactly 1 occurrence, got "
        f"{s.count(m.old)}"
    )
    path.write_text(s.replace(m.old, m.new))


def _run_core_suite(copy_dir: Path) -> tuple[bool, str]:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    env["CUDA_VISIBLE_DEVICES"] = ""
    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest", *CORE_MODULES,
            "-q", "-p", "no:cacheprovider", "--tb=no", "-x",
        ],
        cwd=str(copy_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    tail = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, tail


def run_all() -> dict:
    rows = []
    baseline_ok, baseline_tail = _run_core_suite(EXP_DIR)
    if not baseline_ok:
        raise AssertionError(
            "baseline core suite must pass before mutation testing:\n"
            + baseline_tail[-2000:]
        )
    for m in MUTANTS:
        with tempfile.TemporaryDirectory(prefix="c2r6p0_mut_") as td:
            copy_root = Path(td) / "repo"
            shutil.copytree(
                WORKTREE, copy_root,
                ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", ".git", ".hermes"
                ),
            )
            copy_exp = copy_root / "experiments" / "c2r6p0_deterministic_projector"
            _apply_mutant(copy_exp, m)
            ok, tail = _run_core_suite(copy_exp)
            lines = [l for l in tail.splitlines() if l.strip()]
            rows.append({
                "mutant": m.name,
                "file": m.file,
                "intent": m.intent,
                "killed": (not ok),
                "failure_tail": lines[-2] if (lines and not ok) else "",
            })
            print(f"{m.name}: {'KILLED' if not ok else 'SURVIVED'}")
    killed = [r for r in rows if r["killed"]]
    survived = [r for r in rows if not r["killed"]]
    report = {
        "schema": "elpis.c2r6p0.mutation_report.v1",
        "core_suite": list(CORE_MODULES),
        "baseline_core_suite_pass": True,
        "mutants_total": len(rows),
        "mutants_killed": len(killed),
        "mutants_survived": len(survived),
        "all_killed": not survived,
        "target_min_killed": 20,
        "target_met": len(killed) >= 20 and not survived,
        "rows": rows,
        "note": "each mutant applied to a disposable copy; killed = fast "
               "core suite fails against the mutant",
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "MUTATION_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return report


if __name__ == "__main__":
    rep = run_all()
    print(f"total={rep['mutants_total']} killed={rep['mutants_killed']} "
          f"survived={rep['mutants_survived']} all_killed={rep['all_killed']}")
