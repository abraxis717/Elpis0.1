#!/usr/bin/env python3
"""Offline adversarial diagnostic for the Grid81 semantic compiler.

Read-only. No network, no model download, no torch requirement, no mutation of
production state. Imports the real P0 projector/contracts and the real semantic
refinement/trace contracts, exercises them over an embedded metamorphic prompt
suite, and emits one deterministic JSON report on stdout.

Exit code is 0 unless a HARD CONTRACT CONTRADICTION is found. Poor quality
metrics (low contrast sensitivity, high collision rate, high irrelevant-text
sensitivity) are reported as numbers and never converted into invented
pass/fail thresholds.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import math
import sys
import types
from collections import Counter
from pathlib import Path

HARNESS = "elpis.redteam-grid81-semantic-compiler.v1"
REPO = Path(__file__).resolve().parent.parent

P0_SRC = REPO / "components" / "Pipeline" / "P0ControlProtocol" / "src"
SPINE_SRC = REPO / "components" / "TRMFractalSpine" / "src"
SEMANTICS_SRC = REPO / "components" / "Grid81StructuralSemantics" / "src"
REFERENCE_SRC = REPO / "src"

CONTRADICTIONS: list[str] = []


def contradiction(message: str) -> None:
    CONTRADICTIONS.append(message)


# --------------------------------------------------------------- import shims


def _load_p0():
    """Import elpis_p0 submodules without executing the package __init__.

    The real elpis_p0/__init__.py imports elpis.contracts.budget, which imports
    torch. This diagnostic must run with neither. Registering a namespace stub
    lets the genuine projector/contracts modules load unmodified.
    """
    for path in (SPINE_SRC, SEMANTICS_SRC, REFERENCE_SRC):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    stub = types.ModuleType("elpis_p0")
    stub.__path__ = [str(P0_SRC / "elpis_p0")]
    sys.modules.setdefault("elpis_p0", stub)

    contracts = importlib.import_module("elpis_p0.contracts")
    projector = importlib.import_module("elpis_p0.projector")
    expansion_src = (P0_SRC / "elpis_p0" / "expansion.py").read_text(encoding="utf-8")
    return contracts, projector, expansion_src


def _module_constant(path: Path, name: str):
    """Read a module-level literal constant without importing the module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    return None


# -------------------------------------------------------------- prompt suite

# (case_id, family, prompt, parameters)
CASES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    # -- paraphrase: same intent, different surface form -------------------
    ("para_read_a", "paraphrase", "write a function that reads a file and returns its contents", ("path",)),
    ("para_read_b", "paraphrase", "implement a routine which opens a file and gives back what is inside", ("path",)),
    ("para_read_c", "paraphrase", "produce code loading a file from disk and yielding its body", ("path",)),
    ("para_sum_a", "paraphrase", "write a function that adds two numbers together", ("a", "b")),
    ("para_sum_b", "paraphrase", "implement addition of a pair of numeric values", ("a", "b")),
    ("para_sum_c", "paraphrase", "give me code that computes the total of two numeric arguments", ("a", "b")),
    ("para_srv_a", "paraphrase", "build an async handler that answers requests over the network", ("request",)),
    ("para_srv_b", "paraphrase", "create an async responder serving replies across the network", ("request",)),
    # -- minimal semantic contrasts ---------------------------------------
    ("cont_sync", "contrast", "write a function that fetches a record", ("key",)),
    ("cont_async", "contrast", "write an async function that fetches a record", ("key",)),
    ("cont_plainclass", "contrast", "write a function that stores a value", ("value",)),
    ("cont_class", "contrast", "write a class that stores a value", ("value",)),
    # -- negation ----------------------------------------------------------
    ("neg_use_rec", "negation", "write a recursive function that walks a tree", ("node",)),
    ("neg_no_rec", "negation", "write a function that walks a tree, do not make it recursive", ("node",)),
    ("neg_use_async", "negation", "write an async function that polls a queue", ("queue",)),
    ("neg_no_async", "negation", "write a function that polls a queue, it must never be async", ("queue",)),
    ("neg_use_cache", "negation", "write a function that uses a cache to speed up lookups", ("key",)),
    ("neg_no_cache", "negation", "write a function for lookups without any cache", ("key",)),
    # -- arity / type ------------------------------------------------------
    ("arity_1", "arity", "write a function that combines its arguments", ("a",)),
    ("arity_2", "arity", "write a function that combines its arguments", ("a", "b")),
    ("arity_3", "arity", "write a function that combines its arguments", ("a", "b", "c")),
    ("arity_4", "arity", "write a function that combines its arguments", ("a", "b", "c", "d")),
    ("arity_5", "arity", "write a function that combines its arguments", ("a", "b", "c", "d", "e")),
    ("arity_6", "arity", "write a function that combines its arguments", ("a", "b", "c", "d", "e", "f")),
    ("type_int", "arity", "write a function taking two integers", ("a", "b")),
    ("type_str", "arity", "write a function taking two strings", ("a", "b")),
    # -- dependency / ordering --------------------------------------------
    ("order_fd", "ordering", "read from a file and then write to a database", ("path", "dsn")),
    ("order_df", "ordering", "read from a database and then write to a file", ("dsn", "path")),
    ("order_vt", "ordering", "validate the input and then transform it", ("value",)),
    ("order_tv", "ordering", "transform the input and then validate it", ("value",)),
    # -- recursion vs iteration -------------------------------------------
    ("rec_recursive", "recursion", "compute the traversal using recursive descent", ("tree",)),
    ("rec_iterative", "recursion", "compute the traversal using an explicit loop and a stack", ("tree",)),
    # -- serial vs parallel ------------------------------------------------
    ("par_serial", "parallel", "process every item one after another in order", ("items",)),
    ("par_parallel", "parallel", "process every item in parallel across workers", ("items",)),
    # -- stateful vs stateless --------------------------------------------
    ("state_ful", "state", "write a handler that keeps memory of previous calls", ("event",)),
    ("state_less", "state", "write a handler that keeps nothing between calls", ("event",)),
    # -- resource kind -----------------------------------------------------
    ("res_file", "resource", "load the records from a file", ("source",)),
    ("res_network", "resource", "load the records from a network endpoint", ("source",)),
    ("res_database", "resource", "load the records from a database", ("source",)),
    ("res_stream", "resource", "load the records from a stream", ("source",)),
    # -- output format -----------------------------------------------------
    ("out_json", "output", "return the result as json", ("data",)),
    ("out_csv", "output", "return the result as csv", ("data",)),
    ("out_iterator", "output", "return the result as an iterator", ("data",)),
    ("out_bytes", "output", "return the result as raw bytes", ("data",)),
    # -- constraints present vs removed -----------------------------------
    ("constr_with", "constraints", "write a deterministic typed function that must validate its input and never raise", ("value",)),
    ("constr_without", "constraints", "write a function for its input", ("value",)),
    # -- irrelevant text injection ----------------------------------------
    ("inj_base", "injection", "write a function that parses a configuration", ("blob",)),
    (
        "inj_padded",
        "injection",
        "write a function that parses a configuration. By the way the weather here has been "
        "unusually mild and my neighbour has repainted his fence a colour I would not have "
        "chosen. Anyway, as I was saying, that is the whole request.",
        ("blob",),
    ),
    (
        "inj_padded_long",
        "injection",
        "write a function that parses a configuration. Some further unrelated background: the "
        "train timetable changed last spring, the bakery on the corner now opens earlier, and "
        "there is scaffolding on the building opposite which has been there for months without "
        "anyone apparently working on it. None of this bears on the request above at all.",
        ("blob",),
    ),
    # -- identical keyword multiset, different intent ----------------------
    ("kw_a", "keyword_collision", "write a function that reads a file and writes to a database", ("path", "dsn")),
    ("kw_b", "keyword_collision", "write a function that reads a database and writes to a file", ("dsn", "path")),
    ("kw_c", "keyword_collision", "a database writes to a file when a function reads", ("dsn", "path")),
    ("kw_valid_a", "keyword_collision", "validate the output but never validate the input", ("value",)),
    ("kw_valid_b", "keyword_collision", "validate the input but never validate the output", ("value",)),
    # -- interface distinctions -------------------------------------------
    ("iface_cli", "interface", "expose the behaviour through a command line entry point", ("argv",)),
    ("iface_http", "interface", "expose the behaviour through an http endpoint", ("request",)),
    ("iface_lib", "interface", "expose the behaviour as an importable library call", ("value",)),
)

# (kind, a, b, expectation)  expectation in {"same", "differ"}
RELATIONS: tuple[tuple[str, str, str, str], ...] = (
    ("paraphrase", "para_read_a", "para_read_b", "same"),
    ("paraphrase", "para_read_a", "para_read_c", "same"),
    ("paraphrase", "para_sum_a", "para_sum_b", "same"),
    ("paraphrase", "para_sum_a", "para_sum_c", "same"),
    ("paraphrase", "para_srv_a", "para_srv_b", "same"),
    ("contrast", "cont_sync", "cont_async", "differ"),
    ("contrast", "cont_plainclass", "cont_class", "differ"),
    ("negation", "neg_use_rec", "neg_no_rec", "differ"),
    ("negation", "neg_use_async", "neg_no_async", "differ"),
    ("negation", "neg_use_cache", "neg_no_cache", "differ"),
    ("arity", "arity_1", "arity_2", "differ"),
    ("arity", "arity_2", "arity_3", "differ"),
    ("arity", "arity_3", "arity_4", "differ"),
    ("arity", "arity_4", "arity_5", "differ"),
    ("arity", "arity_5", "arity_6", "differ"),
    ("arity", "type_int", "type_str", "differ"),
    ("ordering", "order_fd", "order_df", "differ"),
    ("ordering", "order_vt", "order_tv", "differ"),
    ("recursion", "rec_recursive", "rec_iterative", "differ"),
    ("parallel", "par_serial", "par_parallel", "differ"),
    ("state", "state_ful", "state_less", "differ"),
    ("resource", "res_file", "res_network", "differ"),
    ("resource", "res_file", "res_database", "differ"),
    ("resource", "res_network", "res_database", "differ"),
    ("resource", "res_file", "res_stream", "differ"),
    ("output", "out_json", "out_csv", "differ"),
    ("output", "out_json", "out_iterator", "differ"),
    ("output", "out_csv", "out_bytes", "differ"),
    ("constraints", "constr_with", "constr_without", "differ"),
    ("injection", "inj_base", "inj_padded", "same"),
    ("injection", "inj_base", "inj_padded_long", "same"),
    ("keyword_collision", "kw_a", "kw_b", "differ"),
    ("keyword_collision", "kw_a", "kw_c", "differ"),
    ("keyword_collision", "kw_valid_a", "kw_valid_b", "differ"),
    ("interface", "iface_cli", "iface_http", "differ"),
    ("interface", "iface_http", "iface_lib", "differ"),
)


# ------------------------------------------------------------------ metrics


def hamming(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    return sum(1 for x, y in zip(a, b) if x != y)


def row_hamming(a: tuple[int, ...], b: tuple[int, ...]) -> list[int]:
    return [hamming(a[r * 9:(r + 1) * 9], b[r * 9:(r + 1) * 9]) for r in range(9)]


def entropy(values: list[int]) -> float:
    total = len(values)
    if total == 0:
        return 0.0
    counts = Counter(values)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


# ------------------------------------------------------------------- audits


def audit_token_abi(contracts, expansion_src: str) -> dict[str, object]:
    """Is P0 BasisToken a valid specialization of StructuralOpcode, or aliasing?"""
    basis = contracts.BasisToken
    p0_space = importlib.import_module("elpis_p0.semantic_space")
    try:
        spine = importlib.import_module("elpis_fractal_spine.structural_semantics")
        opcode = spine.StructuralOpcode
        opcode_names = {int(m): m.name for m in opcode}
    except Exception as exc:  # pragma: no cover
        return {"available": False, "error": repr(exc)}

    basis_names = {int(m): m.name for m in basis}
    table = []
    coarse_conflicts = []
    for value in range(10):
        b = basis_names.get(value)
        o = opcode_names.get(value)
        # Coarse class is the only thing the refinement algebra depends on.
        b_class = "void" if value == 0 else ("expansion" if b == "EXPANSION" else "terminal")
        o_class = "void" if value == 0 else ("expansion" if o == "EXPANSION" else "terminal")
        if b_class != o_class:
            coarse_conflicts.append(value)
        table.append({
            "token_id": value,
            "p0_basis_token": b,
            "spine_structural_opcode": o,
            "p0_coarse_class": b_class,
            "spine_coarse_class": o_class,
            "names_agree": b == o,
        })

    if coarse_conflicts:
        contradiction(
            "token ABI: coarse refinement class disagrees between BasisToken and "
            f"StructuralOpcode at token ids {coarse_conflicts}"
        )

    # Does the declared semantic-space identity bind the token->meaning mapping?
    binds = any(
        name in expansion_src.split("def make_semantic_space_digest")[-1].split("def ")[0]
        for name in ("BasisToken", "StructuralOpcode", "token_names", "vocabulary_names")
    )

    return {
        "available": True,
        "semantic_space": _module_constant(P0_SRC / "elpis_p0" / "expansion.py", "SEMANTIC_SPACE"),
        "abi_version": _module_constant(P0_SRC / "elpis_p0" / "expansion.py", "ABI_VERSION"),
        "vocabulary_size": _module_constant(P0_SRC / "elpis_p0" / "expansion.py", "VOCABULARY_SIZE"),
        "p0_semantic_space": p0_space.P0_SEMANTIC_SPACE,
        "p0_semantic_space_digest": p0_space.P0_SEMANTIC_SPACE_DIGEST,
        "p0_allowed_d4_elements": list(p0_space.P0_ALLOWED_D4_ELEMENTS),
        "table": table,
        "coarse_class_conflicts": coarse_conflicts,
        "names_agreeing_ids": [row["token_id"] for row in table if row["names_agree"]],
        "names_diverging_ids": [row["token_id"] for row in table if not row["names_agree"]],
        "space_digest_binds_token_semantics": binds,
        "p0_space_is_distinct": p0_space.P0_SEMANTIC_SPACE != _module_constant(P0_SRC / "elpis_p0" / "expansion.py", "SEMANTIC_SPACE"),
        "interpretation": (
            "Valid specialization of the coarse refinement algebra (VOID=0, EXPANSION=6 "
            "agree) but the space identity digest covers only name/version/shape/dtype/"
            "vocabulary_size, so two producers with incompatible meanings for ids "
            "1-5,7-9 both validate against the same semantic_space digest."
        ),
    }


def audit_d4(projector) -> dict[str, object]:
    """Is D4 a semantic symmetry of P0 grids with fixed row meanings?"""
    try:
        d4mod = importlib.import_module("elpis_grid81_semantics.d4")
    except Exception as exc:
        return {"available": False, "error": repr(exc)}

    rows = list(projector.DeterministicPythonProjector.semantic_rows)
    results = []
    row_preserving = []
    cell_preserving = []
    for element in d4mod.D4_ELEMENTS:
        row_ok = True
        cell_ok = True
        for index in range(81):
            moved = d4mod.transform_index(index, element)
            if moved // 9 != index // 9:
                row_ok = False
            if moved != index:
                cell_ok = False
        results.append({
            "element": element.name,
            "preserves_row_index": row_ok,
            "preserves_cell_index": cell_ok,
        })
        if row_ok:
            row_preserving.append(element.name)
        if cell_ok:
            cell_preserving.append(element.name)

    return {
        "available": True,
        "p0_row_semantics": rows,
        "elements": results,
        "row_semantics_stabilizer": row_preserving,
        "full_p0_semantics_stabilizer": cell_preserving,
        "interpretation": (
            "P0 fixes meaning at both axes: row index names a semantic row and column "
            "index selects a specific feature within that row. Any D4 element that moves "
            "a cell therefore changes what the cell means. The subgroup preserving full "
            "P0 semantics is trivial."
        ),
    }


def audit_projector_contracts(contracts, projector) -> dict[str, object]:
    p = projector.DeterministicPythonProjector()

    # determinism
    ctx = contracts.RequestContext(
        request_id="determinism-probe", domain="python",
        prompt="write a function that validates typed json input", parameters=("blob",),
    )
    first = p.project(ctx)
    second = p.project(ctx)
    if first.grid81 != second.grid81 or first.digest != second.digest:
        contradiction("projector is not deterministic for identical RequestContext")

    # domain gate
    domain_rejected = False
    try:
        p.project(contracts.RequestContext(
            request_id="domain-probe", domain="rust", prompt="x", parameters=(),
        ))
    except ValueError:
        domain_rejected = True
    if not domain_rejected:
        contradiction("projector accepted a non-python domain")

    # shape / vocabulary
    if len(first.grid81) != 81:
        contradiction(f"projection grid81 length is {len(first.grid81)}, not 81")
    out_of_range = sorted({v for v in first.grid81 if v < 0 or v > 9})
    if out_of_range:
        contradiction(f"projection emitted tokens outside 0..9: {out_of_range}")

    # request_id enters the digest but not the grid -> digest identity != grid identity
    other = p.project(contracts.RequestContext(
        request_id="determinism-probe-2", domain="python",
        prompt="write a function that validates typed json input", parameters=("blob",),
    ))
    digest_vs_grid = {
        "same_grid_different_request_id": other.grid81 == first.grid81,
        "same_digest_different_request_id": other.digest == first.digest,
    }

    return {
        "deterministic": True,
        "non_python_domain_rejected": domain_rejected,
        "grid_length": len(first.grid81),
        "digest_identity_vs_grid_identity": digest_vs_grid,
        "note": (
            "projection_digest binds request_id and scalar features (prompt_chars, "
            "word_count) that never reach grid81, so two requests can share a grid while "
            "differing in digest. Components keyed on the digest and components keyed on "
            "the grid do not partition requests the same way."
        ),
    }


LEXICAL_TRIGGERS = (
    "json", "file", "path", "stream", "class", "async", "recursive", "cache",
    "memory", "iterator", "generator", "typed", "type", "typing", "test", "ast",
    "python", "parallel", "must", "never", "without", "validate", "safe",
    "deterministic", "database", "network",
)


def audit_structural_ceiling(contracts, projector) -> dict[str, object]:
    """How many of the 81 cells can vary for ANY input, not just this suite."""
    p = projector.DeterministicPythonProjector()
    base = p.project(contracts.RequestContext(
        request_id="ceiling-base", domain="python", prompt="x", parameters=(),
    )).grid81

    variable: set[int] = set()
    for trigger in LEXICAL_TRIGGERS:
        for count in range(0, 7):
            grid = p.project(contracts.RequestContext(
                request_id="ceiling", domain="python", prompt=trigger,
                parameters=tuple("abcdef"[:count]),
            )).grid81
            variable |= {i for i in range(81) if grid[i] != base[i]}
    for length in (0, 200, 500, 900, 1200, 1500):
        grid = p.project(contracts.RequestContext(
            request_id="ceiling-len", domain="python",
            prompt="word " * (length // 5), parameters=("a", "b", "c"),
        )).grid81
        variable |= {i for i in range(81) if grid[i] != base[i]}

    rows = projector.DeterministicPythonProjector.semantic_rows
    per_row = {
        rows[r]: sorted(i % 9 for i in variable if i // 9 == r) for r in range(9)
    }
    return {
        "lexical_triggers_probed": list(LEXICAL_TRIGGERS),
        "variable_cells": sorted(variable),
        "variable_cell_count": len(variable),
        "structurally_constant_cell_count": 81 - len(variable),
        "variable_columns_per_row": per_row,
        "interpretation": (
            "Cells absent from variable_cells hold the same token for every possible "
            "RequestContext. Each variable cell observed is binary (VOID or one fixed "
            "token), so the projector's information ceiling is at most one bit per "
            "variable cell before accounting for shared lexical triggers."
        ),
    }


def audit_n1b(projector, contracts, projections: dict[str, object]) -> dict[str, object]:
    """Verify post-C2R6B validator failures resolve to one predeclared sub-locus."""
    try:
        ingress = importlib.import_module("elpis_reference.p0_validator_ingress")
        semref = importlib.import_module("elpis_reference.semantic_refinement")
        p0space = importlib.import_module("elpis_p0.semantic_space")
    except Exception as exc:
        return {"available": False, "error": repr(exc)}

    p = projector.DeterministicPythonProjector()
    ctx = contracts.RequestContext(
        request_id="n1b-probe", domain="python",
        prompt="write a typed python function with tests that must validate its input",
        parameters=("value",),
    )
    projection = p.project(ctx)
    trace = ingress.build_p0_projection_trace(
        projection_digest=projection.digest,
        grid81=projection.grid81,
        semantic_rows=projection.semantic_rows,
    )
    try:
        release = importlib.import_module("elpis_reference.projector_release")
        cap = int(release.MAX_RELEASE_CELLS_PER_TRAVERSAL)
    except Exception:
        cap = _module_constant(
            REFERENCE_SRC / "elpis_reference" / "projector_release.py",
            "MAX_RELEASE_CELLS_PER_TRAVERSAL",
        )
    mappings = []
    for (validator_id, code), role in sorted(
        p0space.P0_VALIDATOR_FAILURE_ROLE_BY_KEY.items()
    ):
        locus = trace.semantic_digest_for_role(role)
        residual = semref.TaskResidualV1(
            task_scope_id="n1b-probe",
            frame_index=0,
            subject_digest="0" * 64,
            producer_id=validator_id,
            locus_namespace=semref.SEMANTIC_OBJECT,
            locus_identity=locus,
            diagnostic_digest="1" * 64,
            reason_codes=(code,),
        )
        resolved = trace.reverse_trace_index().resolve(residual)
        expected = p0space.validator_failure_cell_index(validator_id, code)
        mappings.append({
            "validator_id": validator_id,
            "code": code,
            "role": role,
            "expected_cell": expected,
            "resolved_cells": list(resolved.P7_cell_indices),
            "resolution_cardinality": len(resolved.P7_cell_indices),
            "token": projection.grid81[expected],
        })
    valid = all(
        row["resolved_cells"] == [row["expected_cell"]]
        and row["resolution_cardinality"] == 1
        and row["token"] != 0
        for row in mappings
    )
    distinct = len({row["expected_cell"] for row in mappings}) == len(mappings)
    return {
        "available": True,
        "max_release_cells_per_traversal": cap,
        "failure_mappings": mappings,
        "all_failure_loci_single_cell": valid,
        "all_failure_loci_distinct": distinct,
        "resolvable_by_current_policy": bool(valid and distinct and cap == 1),
        "legacy_row_wide_resolution_removed": True,
    }


# --------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(prog="redteam_grid81_semantic_compiler")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    contracts, projector, expansion_src = _load_p0()
    p = projector.DeterministicPythonProjector()

    grids: dict[str, tuple[int, ...]] = {}
    digests: dict[str, str] = {}
    families: dict[str, str] = {}
    for case_id, family, prompt, parameters in CASES:
        projection = p.project(contracts.RequestContext(
            request_id=case_id, domain="python", prompt=prompt, parameters=parameters,
        ))
        grids[case_id] = tuple(projection.grid81)
        digests[case_id] = projection.digest
        families[case_id] = family

    # ---- per-cell occupancy and entropy over the whole suite
    per_cell = []
    constant_cells = []
    for cell in range(81):
        column = [grids[c][cell] for c in grids]
        h = entropy(column)
        occupancy = sum(1 for v in column if v != 0) / len(column)
        per_cell.append({
            "cell": cell,
            "row": cell // 9,
            "row_name": projector.DeterministicPythonProjector.semantic_rows[cell // 9],
            "col": cell % 9,
            "distinct_values": sorted(set(column)),
            "occupancy_non_void": round(occupancy, 6),
            "entropy_bits": round(h, 6),
        })
        if h == 0.0:
            constant_cells.append(cell)

    # ---- exact collision structure over the suite
    by_grid: dict[tuple[int, ...], list[str]] = {}
    for case_id, grid in grids.items():
        by_grid.setdefault(grid, []).append(case_id)
    colliding_groups = [sorted(v) for v in by_grid.values() if len(v) > 1]
    total_pairs = len(grids) * (len(grids) - 1) // 2
    colliding_pairs = sum(len(g) * (len(g) - 1) // 2 for g in colliding_groups)

    # ---- relations
    relation_rows = []
    for kind, a, b, expectation in RELATIONS:
        ga, gb = grids[a], grids[b]
        d = hamming(ga, gb)
        rows = row_hamming(ga, gb)
        satisfied = (d == 0) if expectation == "same" else (d > 0)
        relation_rows.append({
            "kind": kind,
            "a": a,
            "b": b,
            "expectation": expectation,
            "grid_hamming": d,
            "identical_projection": d == 0,
            "row_hamming": rows,
            "complexity_flags_row_hamming": rows[5],
            "expectation_satisfied": satisfied,
        })

    def rate(kind_filter, predicate) -> float | None:
        subset = [r for r in relation_rows if kind_filter(r)]
        if not subset:
            return None
        return round(sum(1 for r in subset if predicate(r)) / len(subset), 6)

    contrast_kinds = {
        "contrast", "negation", "arity", "ordering", "recursion", "parallel",
        "state", "resource", "output", "constraints", "keyword_collision", "interface",
    }

    summary = {
        "suite_size": len(grids),
        "distinct_projections": len(by_grid),
        "exact_collision_groups": colliding_groups,
        "exact_collision_pair_rate": round(colliding_pairs / total_pairs, 6) if total_pairs else 0.0,
        "constant_cells": constant_cells,
        "constant_cell_count": len(constant_cells),
        "variable_cell_count": 81 - len(constant_cells),
        "grid_entropy_bits_upper_bound": round(sum(c["entropy_bits"] for c in per_cell), 6),
        "paraphrase_identical_rate": rate(lambda r: r["kind"] == "paraphrase", lambda r: r["identical_projection"]),
        "paraphrase_mean_hamming": round(
            sum(r["grid_hamming"] for r in relation_rows if r["kind"] == "paraphrase")
            / max(1, sum(1 for r in relation_rows if r["kind"] == "paraphrase")), 6),
        "semantic_contrast_sensitivity": rate(
            lambda r: r["kind"] in contrast_kinds, lambda r: r["grid_hamming"] > 0),
        "semantic_contrast_mean_hamming": round(
            sum(r["grid_hamming"] for r in relation_rows if r["kind"] in contrast_kinds)
            / max(1, sum(1 for r in relation_rows if r["kind"] in contrast_kinds)), 6),
        "complexity_flags_row_sensitivity": rate(
            lambda r: r["kind"] in contrast_kinds, lambda r: r["complexity_flags_row_hamming"] > 0),
        "irrelevant_text_stability": rate(
            lambda r: r["kind"] == "injection", lambda r: r["grid_hamming"] == 0),
        "expectations_satisfied": round(
            sum(1 for r in relation_rows if r["expectation_satisfied"]) / len(relation_rows), 6),
    }

    # ---- validator-row active-cell cardinality across the suite
    validation_index = list(
        projector.DeterministicPythonProjector.semantic_rows
    ).index("validation_repair_loci")
    cardinalities = Counter(
        sum(1 for t in grids[c][validation_index * 9:validation_index * 9 + 9] if t != 0)
        for c in grids
    )

    report = {
        "schema": HARNESS,
        "role": "READ_ONLY_DIAGNOSTIC_NOT_A_GATE",
        "projector_contracts": audit_projector_contracts(contracts, projector),
        "structural_ceiling": audit_structural_ceiling(contracts, projector),
        "token_abi": audit_token_abi(contracts, expansion_src),
        "d4_semantic_compatibility": audit_d4(projector),
        "per_cell": per_cell,
        "relations": relation_rows,
        "summary": summary,
        "validation_row_active_cardinality_histogram": {
            str(k): v for k, v in sorted(cardinalities.items())
        },
        "n1b_reproduction": audit_n1b(projector, contracts, grids),
        "hard_contract_contradictions": CONTRADICTIONS,
        "notes": [
            "Metrics are descriptive. No pass/fail threshold is applied to any quality metric.",
            "Exit code is non-zero only for hard contract contradictions.",
            "No network, no model download, no production state mutation.",
        ],
    }

    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    if not args.quiet:
        print(text)
    return 1 if CONTRADICTIONS else 0


if __name__ == "__main__":
    raise SystemExit(main())
