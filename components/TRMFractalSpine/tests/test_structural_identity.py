"""Tests for elpis_fractal_spine.structural_identity (Patch 0).

CPU only. No GPU inspection, no torch, no network, no model loading.

Real Canon objects are used throughout: StructuralOracle.evaluate() produces
every OracleTransition and OracleNextState under test. Synthetic construction
is used only for mutation targets that the oracle does not currently emit
(fold_expectations, child_specifications, provenance-bearing states), where the
public frozen constructors are the only way to reach the field.
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from elpis_fractal_spine.structural_identity import (
    DOMAIN_ORACLE_NEXT_STATE,
    DOMAIN_ORACLE_TRANSITION,
    DOMAIN_STRUCTURAL_STATE,
    StructuralIdentityError,
    encode_oracle_next_state,
    encode_structural_state,
    oracle_next_state_identity,
    oracle_transition_identity,
    structural_state_identity,
)
from elpis_fractal_spine.structural_oracle import (
    ChildSpecification,
    ExpansionTarget,
    FoldExpectation,
    OracleNextState,
    OracleTransition,
    StructuralOracle,
)
from elpis_fractal_spine.structural_semantics import (
    GRID_SIZE,
    ParentProvenance,
    StructuralGrid,
    StructuralState,
)

HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")


# ---------------------------------------------------------------------------
# Real Canon fixtures
# ---------------------------------------------------------------------------


def _grid(**overrides: int) -> StructuralGrid:
    tokens = [0] * GRID_SIZE
    for index, value in overrides.items():
        tokens[int(index.lstrip("c"))] = value
    return StructuralGrid(tokens=tuple(tokens))


@pytest.fixture(scope="module")
def oracle() -> StructuralOracle:
    return StructuralOracle()


@pytest.fixture(scope="module")
def void_state() -> StructuralState:
    return StructuralState.root(grid=_grid())


@pytest.fixture(scope="module")
def expansion_state() -> StructuralState:
    return StructuralState.root(grid=_grid(c0=6, c40=6))


@pytest.fixture(scope="module")
def terminal_state() -> StructuralState:
    return StructuralState.root(grid=StructuralGrid(tokens=(1,) * GRID_SIZE))


@pytest.fixture(scope="module")
def void_transition(oracle, void_state) -> OracleTransition:
    return oracle.evaluate(void_state)


@pytest.fixture(scope="module")
def expansion_transition(oracle, expansion_state) -> OracleTransition:
    return oracle.evaluate(expansion_state)


@pytest.fixture(scope="module")
def terminal_transition(oracle, terminal_state) -> OracleTransition:
    return oracle.evaluate(terminal_state)


@pytest.fixture(scope="module")
def next_state(void_transition) -> OracleNextState:
    return void_transition.canonical_next_state


# ---------------------------------------------------------------------------
# StructuralState identity
# ---------------------------------------------------------------------------


def test_structural_state_identity_replay(void_state):
    first = structural_state_identity(void_state)
    second = structural_state_identity(
        StructuralState(
            grid=StructuralGrid(tokens=void_state.grid.tokens),
            mask=void_state.mask,
            depth=void_state.depth,
            provenance=void_state.provenance,
        )
    )
    assert first == second
    assert HEX64.match(first)


def test_structural_state_grid_mutation_changes_identity(void_state):
    mutated = replace(void_state, grid=_grid(c17=4))
    assert structural_state_identity(mutated) != structural_state_identity(void_state)


def test_structural_state_mask_mutation_changes_identity(void_state):
    mask = list(void_state.mask)
    mask[5] = 0
    mutated = replace(void_state, mask=tuple(mask))
    assert mutated.grid.digest() == void_state.grid.digest()  # grid digest blind
    assert structural_state_identity(mutated) != structural_state_identity(void_state)


def test_structural_state_depth_mutation_changes_identity(void_state):
    mutated = replace(void_state, depth=3)
    assert mutated.grid.digest() == void_state.grid.digest()
    assert structural_state_identity(mutated) != structural_state_identity(void_state)


def test_structural_state_provenance_presence_changes_identity(void_state):
    provenance = ParentProvenance(
        parent_grid_digest="a" * 64,
        parent_expansion_cell=7,
        fold_rule_id="fold.replace_cell.v1",
        depth=1,
    )
    with_provenance = replace(void_state, provenance=provenance)
    assert void_state.provenance is None
    assert structural_state_identity(with_provenance) != structural_state_identity(
        void_state
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("parent_grid_digest", "b" * 64),
        ("parent_expansion_cell", 8),
        ("fold_rule_id", "fold.other.v1"),
        ("depth", 2),
    ],
)
def test_structural_state_each_provenance_field_changes_identity(
    void_state, field, value
):
    base = ParentProvenance(
        parent_grid_digest="a" * 64,
        parent_expansion_cell=7,
        fold_rule_id="fold.replace_cell.v1",
        depth=1,
    )
    mutated = replace(base, **{field: value})
    left = structural_state_identity(replace(void_state, provenance=base))
    right = structural_state_identity(replace(void_state, provenance=mutated))
    assert left != right


def test_structural_state_optional_cell_absent_differs_from_present(void_state):
    present = ParentProvenance("a" * 64, 0, "fold.replace_cell.v1", 1)
    absent = ParentProvenance("a" * 64, None, "fold.replace_cell.v1", 1)
    assert structural_state_identity(
        replace(void_state, provenance=present)
    ) != structural_state_identity(replace(void_state, provenance=absent))


# ---------------------------------------------------------------------------
# OracleNextState identity
# ---------------------------------------------------------------------------


def test_oracle_next_state_identity_replay(next_state):
    identity = oracle_next_state_identity(next_state)
    assert identity == oracle_next_state_identity(next_state)
    assert HEX64.match(identity)


def test_oracle_next_state_grid_mutation_changes_identity(next_state):
    mutated = replace(next_state, grid=_grid(c3=9))
    assert oracle_next_state_identity(mutated) != oracle_next_state_identity(next_state)


@pytest.mark.parametrize(
    "targets",
    [
        (ExpansionTarget(cell=1, rationale_code="R1"),),
        (ExpansionTarget(cell=2, rationale_code="R1"),),
        (ExpansionTarget(cell=1, rationale_code="R2"),),
        (
            ExpansionTarget(cell=1, rationale_code="R1"),
            ExpansionTarget(cell=2, rationale_code="R1"),
        ),
    ],
)
def test_oracle_next_state_expansion_target_mutation_changes_identity(
    next_state, targets
):
    base = replace(next_state, expansion_targets=())
    mutated = replace(next_state, expansion_targets=targets)
    assert oracle_next_state_identity(mutated) != oracle_next_state_identity(base)


@pytest.mark.parametrize(
    "field,value",
    [
        ("parent_cell", 4),
        ("seed_grid_digest", "d" * 64),
        ("seed_rule_id", "child_seed.other.v1"),
    ],
)
def test_oracle_next_state_child_specification_mutation_changes_identity(
    next_state, field, value
):
    base = ChildSpecification(parent_cell=3, seed_grid_digest="c" * 64)
    mutated = replace(base, **{field: value})
    left = oracle_next_state_identity(replace(next_state, child_specifications=(base,)))
    right = oracle_next_state_identity(
        replace(next_state, child_specifications=(mutated,))
    )
    assert left != right


@pytest.mark.parametrize(
    "field,value",
    [
        ("parent_cell", 6),
        ("expected_token", 5),
        ("unresolved_expansion", True),
        ("fold_rule_id", "fold.other.v1"),
    ],
)
def test_oracle_next_state_fold_expectation_mutation_changes_identity(
    next_state, field, value
):
    base = FoldExpectation(
        parent_cell=5, expected_token=1, unresolved_expansion=False
    )
    mutated = replace(base, **{field: value})
    left = oracle_next_state_identity(replace(next_state, fold_expectations=(base,)))
    right = oracle_next_state_identity(replace(next_state, fold_expectations=(mutated,)))
    assert left != right
    # the legacy digest is blind to fold_expectations entirely
    assert (
        replace(next_state, fold_expectations=(base,)).digest()
        == replace(next_state, fold_expectations=(mutated,)).digest()
    )


def test_oracle_next_state_quiescence_changes_identity(next_state):
    left = oracle_next_state_identity(replace(next_state, quiescence=False))
    right = oracle_next_state_identity(replace(next_state, quiescence=True))
    assert left != right


def test_oracle_next_state_violation_codes_change_identity(next_state):
    left = oracle_next_state_identity(replace(next_state, violation_codes=()))
    right = oracle_next_state_identity(replace(next_state, violation_codes=("V1",)))
    assert left != right


def test_oracle_next_state_rationale_codes_change_identity(next_state):
    left = oracle_next_state_identity(replace(next_state, rationale_codes=()))
    right = oracle_next_state_identity(replace(next_state, rationale_codes=("A1",)))
    assert left != right
    # the legacy digest is blind to rationale_codes entirely
    assert (
        replace(next_state, rationale_codes=()).digest()
        == replace(next_state, rationale_codes=("A1",)).digest()
    )


def test_oracle_next_state_set_like_fields_are_order_invariant(next_state):
    a = ExpansionTarget(cell=1, rationale_code="R1")
    b = ExpansionTarget(cell=2, rationale_code="R2")
    assert oracle_next_state_identity(
        replace(next_state, expansion_targets=(a, b))
    ) == oracle_next_state_identity(replace(next_state, expansion_targets=(b, a)))


# ---------------------------------------------------------------------------
# OracleTransition identity
# ---------------------------------------------------------------------------


def test_oracle_transition_identity_replay(oracle, void_state, void_transition):
    recomputed = oracle.evaluate(void_state)
    assert oracle_transition_identity(recomputed) == oracle_transition_identity(
        void_transition
    )
    assert HEX64.match(oracle_transition_identity(void_transition))


def test_oracle_transition_candidate_order_invariant(void_transition):
    candidates = list(void_transition.valid_next_states)
    assert len(candidates) > 2, "fixture must exercise real multi-candidate output"
    shuffled = tuple(reversed(candidates))
    rotated = tuple(candidates[7:] + candidates[:7])
    base = oracle_transition_identity(void_transition)
    assert oracle_transition_identity(replace(void_transition, valid_next_states=shuffled)) == base
    assert oracle_transition_identity(replace(void_transition, valid_next_states=rotated)) == base


def test_oracle_transition_candidate_membership_changes_identity(void_transition):
    trimmed = void_transition.valid_next_states[:-1]
    assert oracle_transition_identity(
        replace(void_transition, valid_next_states=trimmed)
    ) != oracle_transition_identity(void_transition)


def test_oracle_transition_canonical_candidate_changes_identity(void_transition):
    alternative = void_transition.valid_next_states[1]
    assert alternative != void_transition.canonical_next_state
    assert oracle_transition_identity(
        replace(void_transition, canonical_next_state=alternative)
    ) != oracle_transition_identity(void_transition)


def test_oracle_transition_nested_next_state_field_changes_identity(void_transition):
    candidates = list(void_transition.valid_next_states)
    candidates[0] = replace(candidates[0], rationale_codes=("DEEP_CHANGE",))
    assert oracle_transition_identity(
        replace(void_transition, valid_next_states=tuple(candidates))
    ) != oracle_transition_identity(void_transition)


@pytest.mark.parametrize(
    "field,value",
    [
        ("quiescence", True),
        ("violation_codes", ("V_NEW",)),
        ("rationale_codes", ("R_NEW",)),
        ("expansion_targets", (ExpansionTarget(cell=9, rationale_code="E"),)),
        (
            "child_specifications",
            (ChildSpecification(parent_cell=9, seed_grid_digest="e" * 64),),
        ),
        (
            "fold_expectations",
            (
                FoldExpectation(
                    parent_cell=9, expected_token=2, unresolved_expansion=True
                ),
            ),
        ),
    ],
)
def test_oracle_transition_each_metadata_field_changes_identity(
    void_transition, field, value
):
    base = replace(
        void_transition,
        quiescence=False,
        violation_codes=(),
        rationale_codes=(),
        expansion_targets=(),
        child_specifications=(),
        fold_expectations=(),
    )
    mutated = replace(base, **{field: value})
    assert oracle_transition_identity(mutated) != oracle_transition_identity(base)


def test_real_transitions_have_distinct_identities(
    void_transition, expansion_transition, terminal_transition
):
    identities = {
        oracle_transition_identity(void_transition),
        oracle_transition_identity(expansion_transition),
        oracle_transition_identity(terminal_transition),
    }
    assert len(identities) == 3


def test_quiescent_transition_binds(terminal_transition):
    assert terminal_transition.quiescence is True
    assert HEX64.match(oracle_transition_identity(terminal_transition))


# ---------------------------------------------------------------------------
# Encoding law
# ---------------------------------------------------------------------------


def test_domain_separation(void_state, next_state, void_transition):
    assert encode_structural_state(void_state).startswith(
        len(DOMAIN_STRUCTURAL_STATE).to_bytes(8, "big") + DOMAIN_STRUCTURAL_STATE
    )
    assert encode_oracle_next_state(next_state).startswith(
        len(DOMAIN_ORACLE_NEXT_STATE).to_bytes(8, "big") + DOMAIN_ORACLE_NEXT_STATE
    )
    assert len({
        DOMAIN_STRUCTURAL_STATE,
        DOMAIN_ORACLE_NEXT_STATE,
        DOMAIN_ORACLE_TRANSITION,
    }) == 3
    # identical payloads under different domains must not collide
    assert structural_state_identity(void_state) != oracle_next_state_identity(
        next_state
    )


def test_nested_boundary_ambiguity_is_impossible(void_state):
    """Field-boundary shifts cannot produce equal preimages.

    Two provenances that differ only in where a boundary falls between adjacent
    string fields must encode differently, because every element is length
    prefixed.
    """
    left = ParentProvenance("ab", 0, "cd", 1)
    right = ParentProvenance("a", 0, "bcd", 1)
    assert structural_state_identity(
        replace(void_state, provenance=left)
    ) != structural_state_identity(replace(void_state, provenance=right))

    a = ExpansionTarget(cell=1, rationale_code="XY")
    b = ExpansionTarget(cell=1, rationale_code="X")
    c = ExpansionTarget(cell=1, rationale_code="Y")
    base = OracleNextState(grid=_grid())
    assert oracle_next_state_identity(
        replace(base, expansion_targets=(a,))
    ) != oracle_next_state_identity(replace(base, expansion_targets=(b, c)))


def test_digest_is_lowercase_sha256(void_state, next_state, void_transition):
    for identity in (
        structural_state_identity(void_state),
        oracle_next_state_identity(next_state),
        oracle_transition_identity(void_transition),
    ):
        assert HEX64.match(identity), identity
        assert identity == identity.lower()
        assert len(identity) == 64


def test_encoding_rejects_non_canon_types():
    with pytest.raises(StructuralIdentityError):
        structural_state_identity(object())
    with pytest.raises(StructuralIdentityError):
        oracle_next_state_identity(object())
    with pytest.raises(StructuralIdentityError):
        oracle_transition_identity(object())


def test_no_forbidden_constructs_in_module_source():
    """AST-level check: comments and docstrings cannot mask a violation."""
    import ast

    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "elpis_fractal_spine"
        / "structural_identity.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not (imported & {"pickle", "json", "marshal", "shelve"}), imported

    called_names = set()
    called_attrs = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            called_names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            called_attrs.add(node.func.attr)

    assert "repr" not in called_names
    assert "hash" not in called_names
    assert "eval" not in called_names
    # the legacy partial digests must not be reused as identities
    assert "digest" not in called_attrs, called_attrs


# ---------------------------------------------------------------------------
# Fresh-process replay
# ---------------------------------------------------------------------------

_REPLAY = """
import sys
sys.path.insert(0, {src!r})
from elpis_fractal_spine.structural_identity import (
    structural_state_identity, oracle_next_state_identity, oracle_transition_identity)
from elpis_fractal_spine.structural_oracle import StructuralOracle
from elpis_fractal_spine.structural_semantics import (
    GRID_SIZE, ParentProvenance, StructuralGrid, StructuralState)

tokens = [0] * GRID_SIZE
tokens[0] = 6
tokens[40] = 6
state = StructuralState(
    grid=StructuralGrid(tokens=tuple(tokens)),
    mask=(1,) * GRID_SIZE,
    depth=2,
    provenance=ParentProvenance("a" * 64, 7, "fold.replace_cell.v1", 1),
)
transition = StructuralOracle().evaluate(state)
print(structural_state_identity(state))
print(oracle_next_state_identity(transition.canonical_next_state))
print(oracle_transition_identity(transition))
"""


def test_fresh_process_replay():
    src = str(Path(__file__).resolve().parents[1] / "src")
    script = _REPLAY.format(src=src)
    outputs = []
    for index in range(3):
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": str(index * 977), "PATH": "/usr/bin:/bin"},
        )
        outputs.append(proc.stdout)
    assert len(outputs) == 3
    assert outputs[0] == outputs[1] == outputs[2]
    lines = outputs[0].strip().splitlines()
    assert len(lines) == 3
    for line in lines:
        assert HEX64.match(line), line
    assert len(set(lines)) == 3
