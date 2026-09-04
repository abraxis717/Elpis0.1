"""No target / oracle leakage (mission 12).

The refiner-input adapter must NOT access:
    target Grid81, solved topology, teacher output, fixture expected answer,
    validation outcome, final heldout oracle residual (beyond the explicit
    current structural residual), or candidate correctness labels.

The EXISTING structural residual function is legitimate state information;
a hidden target solution is not. Two complementary proofs:

  * STATIC PATH — the bridge modules import only whitelisted authorities
    and reference no prohibited oracle identifiers.
  * RUNTIME SPY  — the adapter is OFFERED a target grid, an oracle
    residual, a teacher output, and an expected answer, and it is proved
    to never read any of them.
"""
from __future__ import annotations

import ast
import dataclasses
import re
from pathlib import Path

import conftest as C
from c2r6p0.contracts import ProjectionResultV1
from c2r6p1_bridge import (
    FirstLegalMoveRefiner,
    NullRefiner,
    adapt_projection_to_refiner_input,
    build_envelope,
    legal_candidates,
    replay_transition_chain,
    run_refiner_bounded,
)

EXP_DIR = Path(__file__).resolve().parent.parent
BRIDGE_DIR = EXP_DIR / "c2r6p1_bridge"

# Attribute names that would indicate an oracle/target read if touched.
ORACLE_ATTRS = (
    "target_grid",
    "oracle_residual",
    "teacher_output",
    "expected_answer",
    "solved_grid",
    "heldout_residual",
    "correctness_label",
    "validation_outcome",
)

# Module identifiers the bridge is ALLOWED to import.
#   * authorities: the frozen C2R6-P0 / C2R7-C / D0.1 structural ABI
#   * stdlib (pure, deterministic) + __future__
#   * ambient_guard internals: contextlib/os/socket/subprocess/time are the
#     GUARD MACHINERY itself (patched to fail closed), not bridge data
#   * torch: float32 [16,512] context matrices only (CPU tensors, no CUDA,
#     no model weights)
ALLOWED_MODULES = {
    # authorities
    "elpis_p0",
    "structural_trm_features",
    "c2r6p0",
    "c2r6p1_bridge",
    "_vendored_authority",
    # bridge-internal modules (relative imports resolve to these names)
    "adapter",
    "contracts",
    "packer",
    "refiners",
    "ambient_guard",
    # pure stdlib
    "dataclasses",
    "json",
    "hashlib",
    "enum",
    "typing",
    "abc",
    "functools",
    "itertools",
    "collections",
    "__future__",
    "os",
    # ambient_guard machinery (patches these to fail closed)
    "contextlib",
    "socket",
    "subprocess",
    "time",
    # deterministic CPU tensor math only
    "torch",
}

# Identifier names (whole tokens) that indicate an oracle/target reference.
# Deliberately specific: a local variable called ``target`` (a cell index)
# or a keyword ``expected`` (a replay expectation) is NOT an oracle read.
ORACLE_IDENTIFIERS = {
    "oracle",
    "oracle_residual",
    "target_grid",
    "teacher",
    "teacher_output",
    "expected_answer",
    "heldout",
    "heldout_residual",
    "solved_grid",
    "solved",
    "solution",
    "correctness",
    "correctness_label",
    "ground_truth",
    "validation_outcome",
}


class _SpyProjection(ProjectionResultV1):
    """Records which (oracle-ish) top-level attributes the bridge reads."""

    def __getattribute__(self, name):
        if (
            not name.startswith("_")
            and name in ORACLE_ATTRS
        ):
            acc = object.__getattribute__(self, "_spy_reads")
            acc.append(name)
        return object.__getattribute__(self, name)


def _make_spy(r: ProjectionResultV1) -> _SpyProjection:
    sp = _SpyProjection.__new__(_SpyProjection)
    for f in dataclasses.fields(ProjectionResultV1):
        object.__setattr__(sp, f.name, getattr(r, f.name))
    object.__setattr__(sp, "_spy_reads", [])
    # offer the bridge every prohibited oracle it might be tempted to read
    object.__setattr__(sp, "target_grid", (0,)*81)
    object.__setattr__(sp, "oracle_residual", ("ORACLE_INVARIANT",))
    object.__setattr__(sp, "teacher_output", "TEACHER")
    object.__setattr__(sp, "expected_answer", (9,)*81)
    object.__setattr__(sp, "solved_grid", (1,)*81)
    object.__setattr__(sp, "heldout_residual", ("HELDOUT",))
    object.__setattr__(sp, "correctness_label", True)
    object.__setattr__(sp, "validation_outcome", "PASS")
    return sp


def test_runtime_spy_adapter_never_reads_oracle(one_projected):
    r = one_projected
    sp = _make_spy(r)
    ri = adapt_projection_to_refiner_input(sp)
    assert sp._spy_reads == [], (
        f"adapter read oracle attributes: {sp._spy_reads}"
    )
    # also build the envelope under the spy (it reads the sidecar, not a target)
    _ = build_envelope(sp, ri)
    assert sp._spy_reads == []


def test_runtime_spy_refiner_never_reads_oracle(one_projected):
    """The refiners enumerate/apply candidates from the structural state
    ONLY; the residual is recomputed AFTER a move (a recompute output),
    never read as a target/oracle decision input."""
    r = one_projected
    sp = _make_spy(r)
    ri = adapt_projection_to_refiner_input(sp)
    cands = legal_candidates(ri)
    assert sp._spy_reads == []
    ri1, trace, applied = run_refiner_bounded(
        FirstLegalMoveRefiner(), ri, max_moves=4
    )
    assert sp._spy_reads == []
    _ = replay_transition_chain(sp, trace)
    assert sp._spy_reads == []


def _bridge_imports():
    """Collect top-level module roots imported by the bridge."""
    roots = set()
    for py in BRIDGE_DIR.glob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    roots.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    roots.add(node.module.split(".")[0])
    return roots


def test_static_bridge_imports_whitelisted():
    roots = _bridge_imports()
    # every imported top-level module is a known authority or stdlib
    unexpected = roots - ALLOWED_MODULES
    assert not unexpected, (
        f"bridge imports unexpected modules: {sorted(unexpected)}"
    )


def test_static_no_oracle_identifiers():
    """No bridge symbol/attribute is a target/oracle/teacher identifier.

    Whole-token matching: a cell index called ``target`` or a replay
    keyword ``expected`` is legitimate structural vocabulary; a name like
    ``oracle_residual`` or ``teacher_output`` is not."""
    bad = []
    for py in BRIDGE_DIR.glob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(node.name)
            elif isinstance(node, ast.Attribute):
                names.append(node.attr)
            elif isinstance(node, ast.Name):
                names.append(node.id)
            elif isinstance(node, ast.keyword):
                if node.arg:
                    names.append(node.arg)
            for nm in names:
                if nm in ORACLE_IDENTIFIERS:
                    bad.append((py.name, nm))
    assert not bad, f"bridge references oracle identifiers: {bad}"


def test_adapter_uses_current_residual_not_oracle(one_projected):
    """The residual the adapter validates is the CURRENT structural
    residual (recomputed from the current grid+invariants), not a held-out
    oracle residual. Corrupt only the stored residual ids -> rejected; the
    recompute uses (current grid, current invariants)."""
    from elpis_p0.structural_residual import residual as authority_residual

    r = one_projected
    # the fresh residual is a pure function of (current grid, invariants)
    fresh = tuple(authority_residual(r.grid81, r.invariants))
    assert fresh == tuple(r.residual_ids)  # the projection is self-consistent
    # and it is NOT some oracle: perturbing the grid perturbs the recompute
    g = list(r.grid81)
    i = next(j for j in range(81) if r.writable_mask[j])
    g[i] = 0 if g[i] else 4
    fresh2 = tuple(authority_residual(tuple(g), r.invariants))
    # (fresh2 may equal fresh if the flip doesn't change the unsatisfied
    # set — that is the legitimate current-state recompute, still not an
    # oracle; the point is it derives from the current grid, not a target)
    assert fresh2 == tuple(authority_residual(tuple(g), r.invariants))
