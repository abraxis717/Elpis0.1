"""P0.2 Gate 2 - Admission and ranking tests.

Test deterministic cell validation, selection, ranking arithmetic,
and admission rejection paths.
"""
from __future__ import annotations

import pytest

from elpis.contracts.budget import BudgetVector, Charge

from elpis_p0.expansion import (
    EXPANSION_TOKEN,
    VOID_TOKEN,
    SEMANTIC_SPACE,
    ABI_VERSION,
    SHAPE,
    DTYPE,
    VOCABULARY_SIZE,
    admit_expansion,
    validate_expansion_cells,
    compute_ranking,
    compute_spawn_rank_cost,
    has_granted_ranked_axes,
    make_semantic_space_digest,
)


def _grid_with_expansions(cells: tuple[int, ...]) -> tuple[int, ...]:
    """Build a grid81 with EXPANSION tokens at given cell indices."""
    grid = [VOID_TOKEN] * 81
    for c in cells:
        grid[c] = EXPANSION_TOKEN
    return tuple(grid)


class TestCellValidation:
    def test_valid_expansion_cell(self):
        grid = _grid_with_expansions((40, 55))
        valid, rejected = validate_expansion_cells((40, 55), grid)
        assert valid == (40, 55)
        assert rejected == ()

    def test_invalid_index(self):
        grid = _grid_with_expansions((40,))
        valid, rejected = validate_expansion_cells((40, 99), grid)
        assert valid == (40,)
        assert rejected == (99,)

    def test_negative_index(self):
        grid = _grid_with_expansions((40,))
        valid, rejected = validate_expansion_cells((-1, 40), grid)
        assert valid == (40,)
        assert rejected == (-1,)

    def test_cell_not_expansion_token(self):
        grid = _grid_with_expansions((40,))
        grid_list = list(grid)
        grid_list[55] = 0  # VOID, not EXPANSION
        grid = tuple(grid_list)
        valid, rejected = validate_expansion_cells((40, 55), grid)
        assert valid == (40,)
        assert rejected == (55,)

    def test_admitted_child_rejected(self):
        grid = _grid_with_expansions((40, 55))
        valid, rejected = validate_expansion_cells(
            (40, 55), grid, admitted_children={40}
        )
        assert valid == (55,)
        assert rejected == (40,)

    def test_empty_proposal(self):
        grid = _grid_with_expansions((40,))
        valid, rejected = validate_expansion_cells((), grid)
        assert valid == ()
        assert rejected == ()


class TestRanking:
    def test_ranking_computation(self):
        budget = BudgetVector(
            steps=10, depth=2, backend=None,
            tokens=None, energy=None, wall_ms=None, writes=None,
        )
        assert compute_ranking(budget) == 12  # 1*10 + 1*2

    def test_ranking_not_granted(self):
        budget = BudgetVector(
            steps=10, depth=None, backend=None,
            tokens=None, energy=None, wall_ms=None, writes=None,
        )
        assert compute_ranking(budget) == 10  # only steps granted

    def test_ranking_both_not_granted(self):
        budget = BudgetVector(
            steps=None, depth=None, backend=5,
            tokens=None, energy=None, wall_ms=None, writes=None,
        )
        assert compute_ranking(budget) == 0

    def test_spawn_rank_cost(self):
        spawn = Charge(steps=1, depth=0)
        assert compute_spawn_rank_cost(spawn) == 1

    def test_spawn_rank_cost_zero(self):
        spawn = Charge(steps=0, depth=0)
        assert compute_spawn_rank_cost(spawn) == 0

    def test_spawn_rank_cost_depth(self):
        spawn = Charge(steps=0, depth=1)
        assert compute_spawn_rank_cost(spawn) == 1

    def test_has_granted_ranked_axes(self):
        b1 = BudgetVector(steps=5, depth=None, backend=None,
                          tokens=None, energy=None, wall_ms=None, writes=None)
        assert has_granted_ranked_axes(b1) is True

        b2 = BudgetVector(steps=None, depth=None, backend=5,
                          tokens=None, energy=None, wall_ms=None, writes=None)
        assert has_granted_ranked_axes(b2) is False


class TestAdmissionSuccess:
    def test_admit_one_cell(self):
        grid = _grid_with_expansions((40,))
        budget = BudgetVector(
            steps=10, depth=1, backend=None,
            tokens=None, energy=None, wall_ms=None, writes=None,
        )
        spawn = Charge(steps=1, depth=0)
        alloc = Charge(steps=5, depth=0)

        record = admit_expansion(
            request_id="r1",
            proposal_digest="pd1",
            proposed_cells=(40,),
            proposed_grid81=grid,
            semantic_space=SEMANTIC_SPACE,
            abi_version=ABI_VERSION,
            shape=SHAPE,
            dtype=DTYPE,
            vocabulary_size=VOCABULARY_SIZE,
            budget=budget,
            spawn_cost=spawn,
            allocation=alloc,
            frame_index=2,
        )
        assert record.decision == "ADMITTED"
        assert record.chosen_cell == 40
        assert record.ranking_before == 11
        assert record.spawn_rank_cost == 1
        assert record.ranking_after == 10

    def test_min_cell_selected(self):
        grid = _grid_with_expansions((10, 40, 70))
        budget = BudgetVector(
            steps=10, depth=1, backend=None,
            tokens=None, energy=None, wall_ms=None, writes=None,
        )
        record = admit_expansion(
            request_id="r1",
            proposal_digest="pd1",
            proposed_cells=(70, 10, 40),
            proposed_grid81=grid,
            semantic_space=SEMANTIC_SPACE,
            abi_version=ABI_VERSION,
            shape=SHAPE,
            dtype=DTYPE,
            vocabulary_size=VOCABULARY_SIZE,
            budget=budget,
            spawn_cost=Charge(steps=1),
            allocation=Charge(steps=5),
            frame_index=2,
        )
        assert record.decision == "ADMITTED"
        assert record.chosen_cell == 10


class TestAdmissionRejection:
    def test_rejected_semantic_space(self):
        record = admit_expansion(
            request_id="r1",
            proposal_digest="pd1",
            proposed_cells=(40,),
            proposed_grid81=_grid_with_expansions((40,)),
            semantic_space="wrong.space",
            abi_version=ABI_VERSION,
            shape=SHAPE,
            dtype=DTYPE,
            vocabulary_size=VOCABULARY_SIZE,
            budget=BudgetVector(steps=10, depth=1, backend=None,
                                tokens=None, energy=None, wall_ms=None, writes=None),
            spawn_cost=Charge(steps=1),
            allocation=Charge(steps=5),
            frame_index=2,
        )
        assert record.decision == "REJECTED_SEMANTIC_SPACE"
        assert record.chosen_cell is None

    def test_rejected_no_proposal(self):
        record = admit_expansion(
            request_id="r1",
            proposal_digest="pd1",
            proposed_cells=(),
            proposed_grid81=_grid_with_expansions((40,)),
            semantic_space=SEMANTIC_SPACE,
            abi_version=ABI_VERSION,
            shape=SHAPE,
            dtype=DTYPE,
            vocabulary_size=VOCABULARY_SIZE,
            budget=BudgetVector(steps=10, depth=1, backend=None,
                                tokens=None, energy=None, wall_ms=None, writes=None),
            spawn_cost=Charge(steps=1),
            allocation=Charge(steps=5),
            frame_index=2,
        )
        assert record.decision == "NONE_PROPOSED"

    def test_rejected_ranking_no_granted_axes(self):
        budget = BudgetVector(
            steps=None, depth=None, backend=5,
            tokens=None, energy=None, wall_ms=None, writes=None,
        )
        record = admit_expansion(
            request_id="r1",
            proposal_digest="pd1",
            proposed_cells=(40,),
            proposed_grid81=_grid_with_expansions((40,)),
            semantic_space=SEMANTIC_SPACE,
            abi_version=ABI_VERSION,
            shape=SHAPE,
            dtype=DTYPE,
            vocabulary_size=VOCABULARY_SIZE,
            budget=budget,
            spawn_cost=Charge(steps=1),
            allocation=Charge(steps=5),
            frame_index=2,
        )
        assert record.decision == "REJECTED_RANKING"

    def test_rejected_zero_spawn_charge(self):
        budget = BudgetVector(
            steps=10, depth=1, backend=None,
            tokens=None, energy=None, wall_ms=None, writes=None,
        )
        record = admit_expansion(
            request_id="r1",
            proposal_digest="pd1",
            proposed_cells=(40,),
            proposed_grid81=_grid_with_expansions((40,)),
            semantic_space=SEMANTIC_SPACE,
            abi_version=ABI_VERSION,
            shape=SHAPE,
            dtype=DTYPE,
            vocabulary_size=VOCABULARY_SIZE,
            budget=budget,
            spawn_cost=Charge(steps=0, depth=0),
            allocation=Charge(steps=5),
            frame_index=2,
        )
        assert record.decision == "REJECTED_RANKING"

    def test_rejected_depth_exceeded(self):
        budget = BudgetVector(
            steps=10, depth=1, backend=None,
            tokens=None, energy=None, wall_ms=None, writes=None,
        )
        record = admit_expansion(
            request_id="r1",
            proposal_digest="pd1",
            proposed_cells=(40,),
            proposed_grid81=_grid_with_expansions((40,)),
            semantic_space=SEMANTIC_SPACE,
            abi_version=ABI_VERSION,
            shape=SHAPE,
            dtype=DTYPE,
            vocabulary_size=VOCABULARY_SIZE,
            budget=budget,
            spawn_cost=Charge(steps=1),
            allocation=Charge(steps=5),
            current_depth=1,
            frame_index=2,
        )
        assert record.decision == "REJECTED_POLICY"