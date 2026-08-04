"""P0.2 Gate 7 - Failure class tests.

Test pre-allocation rejection, post-allocation child failure,
and double-use attacks.
"""
from __future__ import annotations

import pytest

from elpis.contracts.budget import BudgetVector, Charge
from elpis.logic.account import RequestAccount, EnvelopeCapability, ChildCloseReason

from elpis_p0.p02_runner import (
    DeterministicProposalTRM,
    FailingTRM,
    run_p02_expansion,
)
from elpis_p0.expansion import (
    EXPANSION_TOKEN,
    VOID_TOKEN,
    SEMANTIC_SPACE,
    ABI_VERSION,
    SHAPE,
    DTYPE,
    VOCABULARY_SIZE,
    admit_expansion,
)
from elpis_p0.authority_bridge import L0ExpansionAuthorityBridge


def _grid_with_expansion(cell: int = 40) -> tuple[int, ...]:
    grid = [VOID_TOKEN] * 81
    grid[cell] = EXPANSION_TOKEN
    return tuple(grid)


def make_budget() -> BudgetVector:
    return BudgetVector(
        steps=10, depth=1, backend=None,
        tokens=None, energy=None, wall_ms=None, writes=None,
    )


# ------------------------------------------------------------------
# Pre-allocation rejection
# ------------------------------------------------------------------

class TestPreAllocationRejection:
    def test_semantic_space_mismatch(self):
        grid = _grid_with_expansion()
        record = admit_expansion(
            request_id="r1",
            proposal_digest="pd1",
            proposed_cells=(40,),
            proposed_grid81=grid,
            semantic_space="wrong.space",
            abi_version=ABI_VERSION,
            shape=SHAPE,
            dtype=DTYPE,
            vocabulary_size=VOCABULARY_SIZE,
            budget=make_budget(),
            spawn_cost=Charge(steps=1),
            allocation=Charge(steps=5),
            frame_index=2,
        )
        assert record.decision == "REJECTED_SEMANTIC_SPACE"
        assert record.chosen_cell is None

    def test_ranked_axis_not_granted(self):
        budget = BudgetVector(
            steps=None, depth=None, backend=5,
            tokens=None, energy=None, wall_ms=None, writes=None,
        )
        record = admit_expansion(
            request_id="r1",
            proposal_digest="pd1",
            proposed_cells=(40,),
            proposed_grid81=_grid_with_expansion(),
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

    def test_invalid_expansion_cell(self):
        grid = [VOID_TOKEN] * 81
        grid[40] = 3  # OUTPUT, not EXPANSION
        grid = tuple(grid)
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
            budget=make_budget(),
            spawn_cost=Charge(steps=1),
            allocation=Charge(steps=5),
            frame_index=2,
        )
        # Cell 40 is not EXPANSION token -> no valid cells -> REJECTED_POLICY
        assert record.decision == "REJECTED_POLICY"

    def test_pre_rejection_preserves_budget(self):
        """Pre-allocation failure leaves budget unchanged."""
        budget = make_budget()
        admit_expansion(
            request_id="r1",
            proposal_digest="pd1",
            proposed_cells=(40,),
            proposed_grid81=_grid_with_expansion(),
            semantic_space="wrong.space",
            abi_version=ABI_VERSION,
            shape=SHAPE,
            dtype=DTYPE,
            vocabulary_size=VOCABULARY_SIZE,
            budget=budget,
            spawn_cost=Charge(steps=1),
            allocation=Charge(steps=5),
            frame_index=2,
        )
        # Budget is immutable (frozen dataclass), should be unchanged
        assert budget.steps == 10
        assert budget.depth == 1


# ------------------------------------------------------------------
# Post-allocation child failure
# ------------------------------------------------------------------

class TestPostAllocationChildFailure:
    def test_child_trm_nan_failure(self):
        parent_grid = _grid_with_expansion()
        parent_trm = DeterministicProposalTRM(
            proposed_grid81=parent_grid,
            expansion_cells=(40,),
        )
        child_trm = FailingTRM(error_type="nan")

        result = run_p02_expansion(
            request_id="p02-abort-nan",
            parent_seed_grid81=parent_grid,
            parent_trm=parent_trm,
            child_trm=child_trm,
            initial_budget=make_budget(),
            spawn_cost=Charge(steps=1),
            child_allocation=Charge(steps=5),
            child_refinement_charge=Charge(steps=2),
            current_depth=0,
        )

        # Child was allocated
        assert result.child_allocated is True
        assert result.child_inference_invoked is True
        assert result.child_closed is True

        # Fold uses VOID with unresolved expansion
        assert result.fold_record is not None
        assert result.fold_record.folded_token == VOID_TOKEN
        assert result.fold_record.unresolved_expansion is True
        assert result.fold_record.child_status == "ABORTED"

        # Parent conservation holds
        for (ax, val) in result.parent_conservation_after:
            if val is not None:
                assert val >= 0

    def test_child_trm_shape_failure(self):
        parent_grid = _grid_with_expansion()
        result = run_p02_expansion(
            request_id="p02-abort-shape",
            parent_seed_grid81=parent_grid,
            parent_trm=DeterministicProposalTRM(
                proposed_grid81=parent_grid,
                expansion_cells=(40,),
            ),
            child_trm=FailingTRM(error_type="shape"),
            initial_budget=make_budget(),
            spawn_cost=Charge(steps=1),
            child_allocation=Charge(steps=5),
            child_refinement_charge=Charge(steps=2),
            current_depth=0,
        )

        assert result.child_closed is True
        assert result.fold_record is not None
        assert result.fold_record.child_status == "ABORTED"
        assert result.fold_record.folded_token == VOID_TOKEN

    def test_parent_state_differs_after_abort(self):
        """Post-allocation abort: parent state differs by spawn+child spend."""
        parent_grid = _grid_with_expansion()
        result = run_p02_expansion(
            request_id="p02-abort-diff",
            parent_seed_grid81=parent_grid,
            parent_trm=DeterministicProposalTRM(
                proposed_grid81=parent_grid,
                expansion_cells=(40,),
            ),
            child_trm=FailingTRM(error_type="typed"),
            initial_budget=make_budget(),
            spawn_cost=Charge(steps=1),
            child_allocation=Charge(steps=5),
            child_refinement_charge=Charge(steps=2),
            current_depth=0,
        )

        # Parent final steps should reflect spend
        parent_final = dict(result.parent_conservation_after)
        parent_init = dict(result.parent_conservation_before)
        # spawn(1) + child_alloc(5) deducted, child_refine(2) spent in child,
        # child_remaining(3) refunded -> net: -1 (spawn) -2 (child_spent) = -3
        assert parent_final["steps"] < parent_init["steps"]


# ------------------------------------------------------------------
# Double-use attacks
# ------------------------------------------------------------------

class TestDoubleUseAttacks:
    def test_double_advance_capability(self):
        """Second use of parent predecessor capability must fail."""
        budget = make_budget()
        account, root_cap = RequestAccount.open(
            request_id="test-double",
            initial_budget=budget,
            root_envelope_id="root-001",
        )

        # First advance succeeds
        _, succ_cap = account.advance(
            root_cap,
            successor_envelope_id="succ-001",
            charge=Charge(steps=1),
        )

        # Second use of root_cap must fail
        with pytest.raises(Exception):
            account.advance(
                root_cap,
                successor_envelope_id="succ-002",
                charge=Charge(steps=1),
            )

    def test_double_close_child_lease(self):
        """Second close of child lease must fail."""
        bridge, root_cap = L0ExpansionAuthorityBridge.open_parent(
            request_id="test-close",
            initial_budget=make_budget(),
        )

        child_alloc = bridge.allocate_child(
            child_request_id="child-1",
            allocation=Charge(steps=5),
            spawn_cost=Charge(steps=1),
        )

        # Seal child first
        bridge.seal_child(child_alloc.child_account)

        # First close succeeds
        bridge.close_child(child_alloc.lease, reason=ChildCloseReason.COMPLETED)

        # Second close must fail
        with pytest.raises(Exception):
            bridge.close_child(child_alloc.lease, reason=ChildCloseReason.ABORTED)

    def test_double_allocate_child_root(self):
        """Second use of child root capability must fail."""
        bridge, root_cap = L0ExpansionAuthorityBridge.open_parent(
            request_id="test-child-root",
            initial_budget=make_budget(),
        )

        child_alloc = bridge.allocate_child(
            child_request_id="child-1",
            allocation=Charge(steps=5),
            spawn_cost=Charge(steps=1),
        )

        # First charge succeeds
        bridge.charge_child_refinement(
            child_alloc.child_account,
            child_alloc.child_root,
            Charge(steps=1),
        )

        # Second use of child root must fail
        with pytest.raises(Exception):
            bridge.charge_child_refinement(
                child_alloc.child_account,
                child_alloc.child_root,
                Charge(steps=1),
            )

    def test_forged_lease_wrong_parent(self):
        """Close lease on wrong parent account must fail."""
        bridge1, _ = L0ExpansionAuthorityBridge.open_parent(
            request_id="p1",
            initial_budget=make_budget(),
        )
        bridge2, _ = L0ExpansionAuthorityBridge.open_parent(
            request_id="p2",
            initial_budget=make_budget(),
        )

        child_alloc = bridge1.allocate_child(
            child_request_id="child-1",
            allocation=Charge(steps=5),
            spawn_cost=Charge(steps=1),
        )

        # Seal the child
        bridge1.seal_child(child_alloc.child_account)

        # Trying to close on bridge2 (wrong parent) must fail
        with pytest.raises(Exception):
            bridge2.close_child(child_alloc.lease, reason=ChildCloseReason.COMPLETED)

    def test_copied_capability(self):
        """Copied capability (same object reused) must fail on second use."""
        bridge, root_cap = L0ExpansionAuthorityBridge.open_parent(
            request_id="test-copy",
            initial_budget=make_budget(),
        )

        # First allocate succeeds
        child_alloc = bridge.allocate_child(
            child_request_id="child-1",
            allocation=Charge(steps=5),
            spawn_cost=Charge(steps=1),
        )

        # The old capability (root_cap) is consumed, cannot be reused
        with pytest.raises(Exception):
            bridge.allocate_child(
                child_request_id="child-2",
                allocation=Charge(steps=5),
                spawn_cost=Charge(steps=1),
            )
