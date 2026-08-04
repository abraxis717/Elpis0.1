"""P0.2 Gate 1 - Contract record tests.

Verify all frozen, slotted expansion evidence records behave correctly.
"""
from __future__ import annotations

import pickle

import pytest

from elpis_p0.expansion_contracts import (
    ExpansionProposalEvidence,
    ExpansionAdmissionRecord,
    ChildSeedRecord,
    FoldRecord,
    NormalizedAuthorityEvent,
    P02Result,
)


class TestExpansionProposalEvidence:
    def test_create_valid(self):
        ev = ExpansionProposalEvidence.create(
            request_id="req-1",
            parent_proposal_digest="abcd1234",
            semantic_space_digest="ss0000",
            proposed_cells=(40, 55),
            valid_cells=(40,),
            rejected_cells=(55,),
            frame_index=1,
        )
        assert ev.request_id == "req-1"
        assert ev.proposed_cells == (40, 55)
        assert ev.valid_cells == (40,)
        assert ev.rejected_cells == (55,)
        assert ev.digest != ""
        assert ev.wall_time_ns > 0
        assert ev.monotonic_ns > 0
        assert ev.frame_index == 1

    def test_frozen(self):
        ev = ExpansionProposalEvidence.create(
            request_id="req-1",
            parent_proposal_digest="abcd",
            semantic_space_digest="ss",
            proposed_cells=(),
            valid_cells=(),
            rejected_cells=(),
            frame_index=0,
        )
        with pytest.raises(Exception):
            ev.request_id = "mutated"  # type: ignore

    def test_deterministic_digest(self):
        e1 = ExpansionProposalEvidence.create(
            request_id="r1",
            parent_proposal_digest="p1",
            semantic_space_digest="s1",
            proposed_cells=(10,),
            valid_cells=(10,),
            rejected_cells=(),
            frame_index=1,
        )
        e2 = ExpansionProposalEvidence.create(
            request_id="r1",
            parent_proposal_digest="p1",
            semantic_space_digest="s1",
            proposed_cells=(10,),
            valid_cells=(10,),
            rejected_cells=(),
            frame_index=1,
        )
        # Digest is structural (no clocks), so identical inputs -> identical digest
        assert e1.digest == e2.digest


class TestExpansionAdmissionRecord:
    def test_admitted(self):
        rec = ExpansionAdmissionRecord.create(
            request_id="req-1",
            proposal_digest="pd1",
            chosen_cell=40,
            decision="ADMITTED",
            allocation=(5, 0),
            spawn_cost=(1, 0),
            ranking_before=10,
            spawn_rank_cost=1,
            ranking_after=9,
            reason_codes=(),
            frame_index=2,
        )
        assert rec.decision == "ADMITTED"
        assert rec.chosen_cell == 40
        assert rec.ranking_after == rec.ranking_before - rec.spawn_rank_cost

    def test_rejected(self):
        rec = ExpansionAdmissionRecord.create(
            request_id="req-1",
            proposal_digest="pd1",
            chosen_cell=None,
            decision="REJECTED_SEMANTIC_SPACE",
            allocation=None,
            spawn_cost=(0, 0),
            ranking_before=0,
            spawn_rank_cost=0,
            ranking_after=0,
            reason_codes=("SEMANTIC_SPACE_MISMATCH",),
            frame_index=2,
        )
        assert rec.decision == "REJECTED_SEMANTIC_SPACE"
        assert rec.chosen_cell is None

    def test_frozen(self):
        rec = ExpansionAdmissionRecord.create(
            request_id="r1",
            proposal_digest="p1",
            chosen_cell=0,
            decision="ADMITTED",
            allocation=(1, 0),
            spawn_cost=(1, 0),
            ranking_before=1,
            spawn_rank_cost=1,
            ranking_after=0,
            reason_codes=(),
            frame_index=0,
        )
        with pytest.raises(Exception):
            rec.decision = "MUTATED"  # type: ignore


class TestChildSeedRecord:
    def test_create(self):
        seed_grid = (0,) * 81
        rec = ChildSeedRecord.create(
            request_id="req-1",
            child_request_id="child-1",
            chosen_cell=40,
            seed_rule_id="child_seed.copy_void_cell.v1",
            parent_grid_digest="pg1",
            child_seed_grid81=seed_grid,
            child_seed_digest="sg1",
            frame_index=3,
        )
        assert rec.chosen_cell == 40
        assert rec.seed_rule_id == "child_seed.copy_void_cell.v1"
        assert rec.child_seed_digest == "sg1"

    def test_frozen(self):
        rec = ChildSeedRecord.create(
            request_id="r1",
            child_request_id="c1",
            chosen_cell=0,
            seed_rule_id="rule1",
            parent_grid_digest="p1",
            child_seed_grid81=(0,) * 81,
            child_seed_digest="s1",
            frame_index=0,
        )
        with pytest.raises(Exception):
            rec.chosen_cell = 99  # type: ignore


class TestFoldRecord:
    def test_completed_fold(self):
        rec = FoldRecord.create(
            request_id="req-1",
            child_request_id="child-1",
            chosen_cell=40,
            fold_rule_id="fold.replace_cell.v1",
            child_status="COMPLETED",
            child_token=3,
            folded_token=3,
            unresolved_expansion=False,
            parent_before_digest="pb1",
            parent_after_digest="pa1",
            frame_index=5,
        )
        assert rec.fold_rule_id == "fold.replace_cell.v1"
        assert rec.unresolved_expansion is False

    def test_aborted_fold(self):
        rec = FoldRecord.create(
            request_id="req-1",
            child_request_id="child-1",
            chosen_cell=40,
            fold_rule_id="fold.replace_cell.v1",
            child_status="ABORTED",
            child_token=0,
            folded_token=0,
            unresolved_expansion=True,
            parent_before_digest="pb1",
            parent_after_digest="pa1",
            frame_index=5,
        )
        assert rec.folded_token == 0
        assert rec.unresolved_expansion is True


class TestNormalizedAuthorityEvent:
    def test_create(self):
        evt = NormalizedAuthorityEvent(
            event_kind="ACCOUNT_OPEN",
            account_role="parent",
            capability_role="parent-root-capability",
            lease_role=None,
            charge_axes=tuple(),
            budget_before_axes=None,
            budget_after_axes=(("steps", 10), ("depth", 1)),
            close_reason=None,
            sequence_role="open",
        )
        assert evt.event_kind == "ACCOUNT_OPEN"
        assert evt.account_role == "parent"

    def test_no_clocks(self):
        """NormalizedAuthorityEvent must not carry wall_time or monotonic."""
        evt = NormalizedAuthorityEvent(
            event_kind="X",
            account_role="X",
            capability_role=None,
            lease_role=None,
            charge_axes=(),
            budget_before_axes=None,
            budget_after_axes=None,
            close_reason=None,
            sequence_role="x",
        )
        assert not hasattr(evt, "wall_time_ns")
        assert not hasattr(evt, "monotonic_ns")
