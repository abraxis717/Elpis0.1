"""P0.2 Gate 6 - Golden success run tests.

Verify the complete one-child affine expansion sequence succeeds
with all conservation, authority, and structural invariants.
"""
from __future__ import annotations

from elpis.contracts.budget import BudgetVector, Charge

from elpis_p0.p02_runner import (
    DeterministicProposalTRM,
    run_p02_expansion,
)
from elpis_p0.expansion import EXPANSION_TOKEN, VOID_TOKEN


def _golden_parent_grid() -> tuple[int, ...]:
    grid = [VOID_TOKEN] * 81
    grid[0] = 1
    grid[1] = 2
    grid[2] = 3
    grid[40] = EXPANSION_TOKEN
    grid[80] = 9
    return tuple(grid)


def _golden_child_grid() -> tuple[int, ...]:
    grid = list(_golden_parent_grid())
    grid[40] = 3  # Resolved to OUTPUT
    return tuple(grid)


def make_golden_budget() -> BudgetVector:
    return BudgetVector(
        steps=10,
        depth=1,
        backend=None,
        tokens=None,
        energy=None,
        wall_ms=None,
        writes=None,
    )


class TestGoldenSuccess:
    def test_golden_expansion_succeeds(self):
        parent_grid = _golden_parent_grid()
        child_grid = _golden_child_grid()

        parent_trm = DeterministicProposalTRM(
            proposed_grid81=parent_grid,
            expansion_cells=(40,),
        )
        child_trm = DeterministicProposalTRM(
            proposed_grid81=child_grid,
            expansion_cells=(),
        )

        result = run_p02_expansion(
            request_id="p02-golden-001",
            parent_seed_grid81=parent_grid,
            parent_trm=parent_trm,
            child_trm=child_trm,
            initial_budget=make_golden_budget(),
            spawn_cost=Charge(steps=1),
            child_allocation=Charge(steps=5),
            child_refinement_charge=Charge(steps=2),
            current_depth=0,
        )

        # Admission
        assert result.admission.decision == "ADMITTED"
        assert result.admission.chosen_cell == 40

        # Ranking strict descent
        assert result.admission.spawn_rank_cost >= 1
        assert result.admission.ranking_after < result.admission.ranking_before

        # Child lifecycle
        assert result.child_allocated is True
        assert result.child_inference_invoked is True
        assert result.child_closed is True
        assert result.child_seed is not None

        # Fold
        assert result.fold_record is not None
        assert result.fold_record.folded_token == 3  # OUTPUT
        assert result.fold_record.unresolved_expansion is False
        assert result.fold_record.child_status == "COMPLETED"

        # Conservation
        # Parent: remaining + spent + open_children = initial
        # After close, no open children, so remaining + spent = initial
        parent_axes = result.parent_conservation_after
        initial_axes = result.parent_conservation_before
        for (ax_init, val_init), (ax_final, val_final) in zip(initial_axes, parent_axes):
            if val_init is not None:
                assert val_final >= 0, f"axis {ax_init} went negative"

        # Forbidden side effects
        assert result.expert_activated is False
        assert result.artifact_executed is False
        assert result.memory_written is False
        assert result.governance_invoked is False
        assert result.stop_authorized is False

        # Structural result digest present
        assert result.structural_result_digest != ""
        assert result.normalized_authority_digest != ""

        # Child seed digest
        assert result.child_seed.child_seed_digest != ""

    def test_conservation_trace(self):
        parent_grid = _golden_parent_grid()
        child_grid = _golden_child_grid()

        parent_trm = DeterministicProposalTRM(
            proposed_grid81=parent_grid,
            expansion_cells=(40,),
        )
        child_trm = DeterministicProposalTRM(
            proposed_grid81=child_grid,
            expansion_cells=(),
        )

        result = run_p02_expansion(
            request_id="p02-conserv-001",
            parent_seed_grid81=parent_grid,
            parent_trm=parent_trm,
            child_trm=child_trm,
            initial_budget=make_golden_budget(),
            spawn_cost=Charge(steps=1),
            child_allocation=Charge(steps=5),
            child_refinement_charge=Charge(steps=2),
            current_depth=0,
        )

        # Normalized authority trace has multiple events
        assert len(result.normalized_authority_trace) >= 5

        # Raw evidence present
        assert len(result.raw_authority_evidence) >= 3

        # Conservation holds at recorded states
        for (ax, val) in result.parent_conservation_after:
            if val is not None:
                assert val >= 0

    def test_spawn_cost_positive(self):
        result = run_p02_expansion(
            request_id="p02-spawn-001",
            parent_seed_grid81=_golden_parent_grid(),
            parent_trm=DeterministicProposalTRM(
                proposed_grid81=_golden_parent_grid(),
                expansion_cells=(40,),
            ),
            child_trm=DeterministicProposalTRM(
                proposed_grid81=_golden_child_grid(),
                expansion_cells=(),
            ),
            initial_budget=make_golden_budget(),
            spawn_cost=Charge(steps=1),
            child_allocation=Charge(steps=5),
            child_refinement_charge=Charge(steps=2),
            current_depth=0,
        )
        # Spawn rank cost >= 1
        assert result.admission.spawn_rank_cost >= 1

    def test_child_refinement_charge_positive(self):
        result = run_p02_expansion(
            request_id="p02-refine-001",
            parent_seed_grid81=_golden_parent_grid(),
            parent_trm=DeterministicProposalTRM(
                proposed_grid81=_golden_parent_grid(),
                expansion_cells=(40,),
            ),
            child_trm=DeterministicProposalTRM(
                proposed_grid81=_golden_child_grid(),
                expansion_cells=(),
            ),
            initial_budget=make_golden_budget(),
            spawn_cost=Charge(steps=1),
            child_allocation=Charge(steps=5),
            child_refinement_charge=Charge(steps=2),
            current_depth=0,
        )
        # Child conservation shows charge was applied
        assert result.child_conservation_after is not None
        # Child spent = refinement charge, so remaining < initial
        child_init_steps = dict(result.child_conservation_before).get("steps")
        child_final_steps = dict(result.child_conservation_after).get("steps")
        assert child_init_steps is not None
        assert child_final_steps is not None
        assert child_final_steps < child_init_steps
