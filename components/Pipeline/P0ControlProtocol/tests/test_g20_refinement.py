"""G2.0 — Comprehensive refinement integration tests.

Phase L: Negative tests
Phase M: Static authority tests (subset that can run as pytest)
Phase N: Fresh-process import verification

Tests cover:
- Scope absence and mismatch
- No scope inference
- Proposal binding
- Structural locality
- Tier separation
- Immutability
- Determinism
- Call count
- Existing protocol preservation
"""
from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import ast as py_ast

import pytest

from elpis_p0 import (
    P0Controller,
    P0RefinementInputV1,
    P0RefinementError,
    RequestContext,
    StructuralProjection,
    TRMRefinementProposal,
    build_refinement_input,
    build_default_controller,
    RefinementScopeDecisionV1,
    RefinementScopeProvider,
    RefinementScopeError,
    build_refinement_input_from_scope,
    RefinementProposerPort,
    DeterministicShadowRefinementProposer,
    RefinementValidationRecordV1,
    build_validation_record,
    validate_refinement_proposal,
    RefinementInvocationReceiptV1,
    build_receipt,
    RefinementControllerResultV1,
)
from elpis_fractal_spine.structural_refinement import (
    StructuralRefinementInputV1,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_GRID = tuple((i % 10) for i in range(81))
VALID_MASK_ALL_ONES = tuple(1 for _ in range(81))
VALID_MASK_ALL_ZEROS = tuple(0 for _ in range(81))
VALID_MASK_ONE_WRITABLE = tuple(1 if i == 10 else 0 for i in range(81))
VALID_SNAPSHOT = "a" * 64

PROJECTION = StructuralProjection(
    grid81=VALID_GRID,
    semantic_rows=("r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8"),
    features=(("feat", 1.0),),
    digest="proj_digest_g2",
)

REQUEST = RequestContext(
    request_id="g2-test-001",
    prompt="test prompt",
)


def _make_scope_decision(
    *,
    request_id: str = "g2-test-001",
    logical_tick: int = 0,
    snapshot_digest: str = VALID_SNAPSHOT,
    scope_policy_id: str = "test-policy",
    scope_policy_version: str = "1.0",
    writable_mask81: tuple[int, ...] = VALID_MASK_ALL_ONES,
) -> RefinementScopeDecisionV1:
    return RefinementScopeDecisionV1(
        request_id=request_id,
        logical_tick=logical_tick,
        snapshot_digest=snapshot_digest,
        scope_policy_id=scope_policy_id,
        scope_policy_version=scope_policy_version,
        writable_mask81=writable_mask81,
    )


# ===================================================================
# Phase L — Negative tests
# ===================================================================

class TestScopeAuthorityContract:
    """Test RefinementScopeDecisionV1 validation."""

    def test_valid_scope_decision(self):
        sd = _make_scope_decision()
        assert sd.schema_version == "p0.refinement.scope.v1"
        assert sd.request_id == "g2-test-001"
        assert sd.logical_tick == 0
        assert len(sd.writable_mask81) == 81
        assert len(sd.mask_digest) == 64
        assert len(sd.decision_digest) == 64

    def test_scope_decision_frozen(self):
        sd = _make_scope_decision()
        with pytest.raises(dataclasses.FrozenInstanceError):
            sd.request_id = "other"  # type: ignore

    def test_scope_decision_has_slots(self):
        sd = _make_scope_decision()
        with pytest.raises((AttributeError, TypeError)):
            sd.arbitrary_attr = "nope"  # type: ignore

    def test_empty_request_id_rejected(self):
        with pytest.raises(RefinementScopeError, match="request_id"):
            _make_scope_decision(request_id="")

    def test_negative_tick_rejected(self):
        with pytest.raises(RefinementScopeError, match="logical_tick"):
            _make_scope_decision(logical_tick=-1)

    def test_bad_snapshot_digest_rejected(self):
        with pytest.raises(RefinementScopeError, match="snapshot"):
            _make_scope_decision(snapshot_digest="short")

    def test_non_hex_snapshot_rejected(self):
        with pytest.raises(RefinementScopeError, match="non-hex"):
            _make_scope_decision(snapshot_digest="x" * 64)

    def test_empty_policy_id_rejected(self):
        with pytest.raises(RefinementScopeError, match="scope_policy_id"):
            _make_scope_decision(scope_policy_id="")

    def test_empty_policy_version_rejected(self):
        with pytest.raises(RefinementScopeError, match="scope_policy_version"):
            _make_scope_decision(scope_policy_version="")

    def test_mask_length_mismatch_rejected(self):
        with pytest.raises(RefinementScopeError, match="length 81"):
            _make_scope_decision(writable_mask81=(1, 0))

    def test_non_binary_mask_rejected(self):
        mask = tuple(2 if i == 0 else 0 for i in range(81))
        with pytest.raises(RefinementScopeError, match="not in"):
            _make_scope_decision(writable_mask81=mask)

    def test_mask_digest_auto_computed(self):
        sd = _make_scope_decision(writable_mask81=VALID_MASK_ALL_ONES)
        sd2 = _make_scope_decision(writable_mask81=VALID_MASK_ALL_ONES)
        assert sd.mask_digest == sd2.mask_digest

    def test_decision_digest_different_mask(self):
        sd1 = _make_scope_decision(writable_mask81=VALID_MASK_ALL_ONES)
        sd2 = _make_scope_decision(writable_mask81=VALID_MASK_ALL_ZEROS)
        assert sd1.decision_digest != sd2.decision_digest

    def test_decision_digest_different_request(self):
        sd1 = _make_scope_decision(request_id="a")
        sd2 = _make_scope_decision(request_id="b")
        assert sd1.decision_digest != sd2.decision_digest

    def test_decision_digest_different_tick(self):
        sd1 = _make_scope_decision(logical_tick=0)
        sd2 = _make_scope_decision(logical_tick=1)
        assert sd1.decision_digest != sd2.decision_digest

    def test_decision_digest_different_policy(self):
        sd1 = _make_scope_decision(scope_policy_id="pol1")
        sd2 = _make_scope_decision(scope_policy_id="pol2")
        assert sd1.decision_digest != sd2.decision_digest


class TestScopeAbsenceAndMismatch:
    """Missing scope decision fails closed, no fallback."""

    def test_missing_scope_decision_fails_closed(self):
        controller = build_default_controller()
        with pytest.raises(P0RefinementError, match="BLOCKED_P0_REFINEMENT_SCOPE_ABSENT"):
            controller.propose_refinement(
                request=REQUEST,
                projection=PROJECTION,
                scope_decision=None,  # type: ignore
                logical_tick=0,
                snapshot_digest=VALID_SNAPSHOT,
            )

    def test_scope_request_mismatch_rejected(self):
        sd = _make_scope_decision(request_id="different-request")
        with pytest.raises(P0RefinementError, match="BLOCKED_P0_REFINEMENT_SCOPE_REQUEST_MISMATCH"):
            build_refinement_input_from_scope(
                request=REQUEST,
                projection=PROJECTION,
                scope_decision=sd,
                logical_tick=0,
                snapshot_digest=VALID_SNAPSHOT,
            )

    def test_scope_tick_mismatch_rejected(self):
        sd = _make_scope_decision(logical_tick=99)
        with pytest.raises(P0RefinementError, match="BLOCKED_P0_REFINEMENT_SCOPE_TICK_MISMATCH"):
            build_refinement_input_from_scope(
                request=REQUEST,
                projection=PROJECTION,
                scope_decision=sd,
                logical_tick=0,
                snapshot_digest=VALID_SNAPSHOT,
            )

    def test_scope_snapshot_mismatch_rejected(self):
        sd = _make_scope_decision(snapshot_digest="b" * 64)
        with pytest.raises(P0RefinementError, match="BLOCKED_P0_REFINEMENT_SCOPE_SNAPSHOT_MISMATCH"):
            build_refinement_input_from_scope(
                request=REQUEST,
                projection=PROJECTION,
                scope_decision=sd,
                logical_tick=0,
                snapshot_digest=VALID_SNAPSHOT,
            )


class TestNoScopeInference:
    """Mask is never inferred from any source."""

    def test_mask_not_read_from_projection_features(self):
        projection_with_mask_in_features = StructuralProjection(
            grid81=VALID_GRID,
            semantic_rows=("r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8"),
            features=(("writable_mask", 1.0), ("all_ones", 1.0)),
            digest="proj_with_features_mask",
        )
        sd = _make_scope_decision(writable_mask81=VALID_MASK_ALL_ZEROS)
        env = build_refinement_input_from_scope(
            request=REQUEST,
            projection=projection_with_mask_in_features,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        assert env.structural_input.writable_mask81 == VALID_MASK_ALL_ZEROS

    def test_mask_not_read_from_semantic_rows(self):
        projection = StructuralProjection(
            grid81=VALID_GRID,
            semantic_rows=("mask=1", "mask=1", "mask=1", "mask=1", "mask=1", "mask=1", "mask=1", "mask=1", "mask=1"),
            features=(("feat", 0.0),),
            digest="proj_semantic_rows_mask",
        )
        sd = _make_scope_decision(writable_mask81=VALID_MASK_ALL_ZEROS)
        env = build_refinement_input_from_scope(
            request=REQUEST,
            projection=projection,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        assert env.structural_input.writable_mask81 == VALID_MASK_ALL_ZEROS

    def test_no_all_ones_fallback_exists(self):
        """There is no implicit all-ones mask fallback."""
        # If no scope decision is provided, it must fail — not default to all-ones
        controller = build_default_controller()
        with pytest.raises((P0RefinementError, RefinementScopeError, ValueError)):
            controller.propose_refinement(
                request=REQUEST,
                projection=PROJECTION,
                scope_decision=None,  # type: ignore
                logical_tick=0,
                snapshot_digest=VALID_SNAPSHOT,
            )

    def test_bare_projection_insufficient(self):
        """A StructuralProjection alone is not enough to invoke refinement."""
        # The controller requires an explicit scope decision
        controller = build_default_controller()
        with pytest.raises((P0RefinementError, RefinementScopeError, ValueError)):
            controller.propose_refinement(
                request=REQUEST,
                projection=PROJECTION,
                scope_decision=None,  # type: ignore
                logical_tick=0,
                snapshot_digest=VALID_SNAPSHOT,
            )


class TestProposalBinding:
    """Proposal must bind to envelope digest, not projection/grid digest."""

    def test_proposal_bound_to_envelope_accepted(self):
        sd = _make_scope_decision(writable_mask81=VALID_MASK_ALL_ONES)
        env = build_refinement_input_from_scope(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        proposer = DeterministicShadowRefinementProposer(fixture_mode="NOOP")
        proposal = proposer.propose_refinement(env)
        assert proposal.input_digest == env.envelope_digest

    def test_proposal_bound_to_projection_digest_rejected(self):
        sd = _make_scope_decision(writable_mask81=VALID_MASK_ALL_ONES)
        env = build_refinement_input_from_scope(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        proposal = TRMRefinementProposal(
            input_digest=PROJECTION.digest,  # wrong — projection digest
            proposed_grid81=VALID_GRID,
            residual81=(0.0,) * 81,
            halt_score=0.5,
            expansion_cells=(),
            rationale=(),
            digest="fake_digest",
        )
        result = validate_refinement_proposal(env, proposal)
        assert result.status == "REJECTED_P0_REFINEMENT_INPUT_DIGEST_MISMATCH"

    def test_proposal_bound_to_grid_digest_rejected(self):
        sd = _make_scope_decision(writable_mask81=VALID_MASK_ALL_ONES)
        env = build_refinement_input_from_scope(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        grid_digest = env.structural_input.grid_digest
        proposal = TRMRefinementProposal(
            input_digest=grid_digest,  # wrong — grid-only digest
            proposed_grid81=VALID_GRID,
            residual81=(0.0,) * 81,
            halt_score=0.5,
            expansion_cells=(),
            rationale=(),
            digest="fake_digest",
        )
        result = validate_refinement_proposal(env, proposal)
        assert result.status == "REJECTED_P0_REFINEMENT_INPUT_DIGEST_MISMATCH"

    def test_proposal_from_wrong_request_rejected(self):
        sd = _make_scope_decision(writable_mask81=VALID_MASK_ALL_ONES)
        env = build_refinement_input_from_scope(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        # Simulate proposal from another request (different envelope digest)
        proposal = TRMRefinementProposal(
            input_digest="b" * 64,  # completely different
            proposed_grid81=VALID_GRID,
            residual81=(0.0,) * 81,
            halt_score=0.5,
            expansion_cells=(),
            rationale=(),
            digest="fake_digest",
        )
        result = validate_refinement_proposal(env, proposal)
        assert result.status == "REJECTED_P0_REFINEMENT_INPUT_DIGEST_MISMATCH"


class TestStructuralLocality:
    """NOOP, single-edit, multiple-edits, locked-cell, invalid token."""

    def _make_env(self, mask: tuple[int, ...] = VALID_MASK_ALL_ONES):
        sd = _make_scope_decision(writable_mask81=mask)
        return build_refinement_input_from_scope(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )

    def test_noop_scope_valid(self):
        env = self._make_env()
        proposal = TRMRefinementProposal(
            input_digest=env.envelope_digest,
            proposed_grid81=VALID_GRID,
            residual81=(0.0,) * 81,
            halt_score=0.5,
            expansion_cells=(),
            rationale=(),
            digest="noop_digest",
        )
        result = validate_refinement_proposal(env, proposal)
        assert result.scope_validity == "PASS"
        assert result.transition_kind == "NOOP"

    def test_one_writable_edit_scope_valid(self):
        env = self._make_env()
        grid = list(VALID_GRID)
        grid[10] = (grid[10] + 1) % 10
        proposal = TRMRefinementProposal(
            input_digest=env.envelope_digest,
            proposed_grid81=tuple(grid),
            residual81=(0.0,) * 81,
            halt_score=0.5,
            expansion_cells=(),
            rationale=(),
            digest="edit_digest",
        )
        result = validate_refinement_proposal(env, proposal)
        assert result.scope_validity == "PASS"
        assert result.transition_kind == "SINGLE_EDIT"
        assert result.changed_cells == (10,)

    def test_one_locked_edit_rejected(self):
        mask = tuple(0 if i == 5 else 1 for i in range(81))
        env = self._make_env(mask)
        grid = list(VALID_GRID)
        grid[5] = (grid[5] + 1) % 10  # cell 5 is locked
        proposal = TRMRefinementProposal(
            input_digest=env.envelope_digest,
            proposed_grid81=tuple(grid),
            residual81=(0.0,) * 81,
            halt_score=0.5,
            expansion_cells=(),
            rationale=(),
            digest="locked_digest",
        )
        result = validate_refinement_proposal(env, proposal)
        assert result.scope_validity == "FAIL"
        assert result.status == "REJECTED_P0_REFINEMENT_LOCKED_CELL_WRITE"

    def test_two_edits_rejected(self):
        env = self._make_env()
        grid = list(VALID_GRID)
        grid[10] = (grid[10] + 1) % 10
        grid[20] = (grid[20] + 1) % 10
        proposal = TRMRefinementProposal(
            input_digest=env.envelope_digest,
            proposed_grid81=tuple(grid),
            residual81=(0.0,) * 81,
            halt_score=0.5,
            expansion_cells=(),
            rationale=(),
            digest="multi_digest",
        )
        result = validate_refinement_proposal(env, proposal)
        assert result.scope_validity == "FAIL"
        assert result.status == "REJECTED_P0_REFINEMENT_MULTIPLE_EDITS"

    def test_invalid_token_rejected(self):
        env = self._make_env()
        grid = list(VALID_GRID)
        grid[10] = 99  # outside 0..9
        proposal = TRMRefinementProposal(
            input_digest=env.envelope_digest,
            proposed_grid81=tuple(grid),
            residual81=(0.0,) * 81,
            halt_score=0.5,
            expansion_cells=(),
            rationale=(),
            digest="invalid_token_digest",
        )
        result = validate_refinement_proposal(env, proposal)
        assert result.scope_validity == "FAIL"
        assert result.status == "REJECTED_P0_REFINEMENT_STRUCTURAL_INVALID"

    def test_wrong_grid_length_rejected(self):
        env = self._make_env()
        proposal = TRMRefinementProposal(
            input_digest=env.envelope_digest,
            proposed_grid81=tuple(range(80)),  # 80 cells
            residual81=(0.0,) * 81,
            halt_score=0.5,
            expansion_cells=(),
            rationale=(),
            digest="wrong_length",
        )
        result = validate_refinement_proposal(env, proposal)
        assert result.scope_validity == "FAIL"
        assert result.status == "REJECTED_P0_REFINEMENT_STRUCTURAL_INVALID"


class TestTierSeparation:
    """oracle_legality, policy_admissibility, progress_verdict always NOT_EVALUATED."""

    def _make_env(self):
        sd = _make_scope_decision(writable_mask81=VALID_MASK_ALL_ONES)
        return build_refinement_input_from_scope(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )

    def test_oracle_legality_not_evaluated(self):
        env = self._make_env()
        proposal = TRMRefinementProposal(
            input_digest=env.envelope_digest,
            proposed_grid81=VALID_GRID,
            residual81=(0.0,) * 81,
            halt_score=0.5,
            expansion_cells=(),
            rationale=(),
            digest="tier_digest",
        )
        record = build_validation_record(env, proposal)
        assert record.oracle_legality == "NOT_EVALUATED"

    def test_policy_admissibility_not_evaluated(self):
        env = self._make_env()
        proposal = TRMRefinementProposal(
            input_digest=env.envelope_digest,
            proposed_grid81=VALID_GRID,
            residual81=(0.0,) * 81,
            halt_score=0.5,
            expansion_cells=(),
            rationale=(),
            digest="tier_digest",
        )
        record = build_validation_record(env, proposal)
        assert record.policy_admissibility == "NOT_EVALUATED"

    def test_progress_verdict_not_evaluated(self):
        env = self._make_env()
        proposal = TRMRefinementProposal(
            input_digest=env.envelope_digest,
            proposed_grid81=VALID_GRID,
            residual81=(0.0,) * 81,
            halt_score=0.5,
            expansion_cells=(),
            rationale=(),
            digest="tier_digest",
        )
        record = build_validation_record(env, proposal)
        assert record.progress_verdict == "NOT_EVALUATED"

    def test_cannot_set_oracle_legality_to_pass(self):
        with pytest.raises(ValueError, match="oracle_legality"):
            RefinementValidationRecordV1(
                envelope_digest="a" * 64,
                proposal_digest="b" * 64,
                transition_kind="NOOP",
                scope_validity="PASS",
                oracle_legality="PASS",
                status="ACCEPTED",
            )

    def test_cannot_set_policy_admissibility_to_pass(self):
        with pytest.raises(ValueError, match="policy_admissibility"):
            RefinementValidationRecordV1(
                envelope_digest="a" * 64,
                proposal_digest="b" * 64,
                transition_kind="NOOP",
                scope_validity="PASS",
                policy_admissibility="PASS",
                status="ACCEPTED",
            )

    def test_cannot_set_progress_verdict_to_pass(self):
        with pytest.raises(ValueError, match="progress_verdict"):
            RefinementValidationRecordV1(
                envelope_digest="a" * 64,
                proposal_digest="b" * 64,
                transition_kind="NOOP",
                scope_validity="PASS",
                progress_verdict="PASS",
                status="ACCEPTED",
            )


class TestImmutability:
    """All G2 contracts are frozen dataclasses."""

    def test_scope_decision_frozen(self):
        sd = _make_scope_decision()
        with pytest.raises(dataclasses.FrozenInstanceError):
            sd.request_id = "x"  # type: ignore

    def test_input_envelope_frozen(self):
        sd = _make_scope_decision()
        env = build_refinement_input_from_scope(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            env.request_id = "x"  # type: ignore

    def test_proposal_frozen(self):
        sd = _make_scope_decision()
        env = build_refinement_input_from_scope(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        proposer = DeterministicShadowRefinementProposer(fixture_mode="NOOP")
        proposal = proposer.propose_refinement(env)
        with pytest.raises(dataclasses.FrozenInstanceError):
            proposal.proposed_grid81 = VALID_GRID  # type: ignore

    def test_validation_record_frozen(self):
        sd = _make_scope_decision()
        env = build_refinement_input_from_scope(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        proposer = DeterministicShadowRefinementProposer(fixture_mode="NOOP")
        proposal = proposer.propose_refinement(env)
        record = build_validation_record(env, proposal)
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.scope_validity = "FAIL"  # type: ignore

    def test_receipt_frozen(self):
        sd = _make_scope_decision()
        env = build_refinement_input_from_scope(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        proposer = DeterministicShadowRefinementProposer(fixture_mode="NOOP")
        proposal = proposer.propose_refinement(env)
        record = build_validation_record(env, proposal)
        receipt = build_receipt(
            request_id=REQUEST.request_id,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
            projection_digest=PROJECTION.digest,
            scope_decision=sd,
            input_envelope=env,
            proposer_id=proposer.proposer_id,
            proposer_version=proposer.proposer_version,
            proposal=proposal,
            validation=record,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            receipt.request_id = "x"  # type: ignore

    def test_result_frozen(self):
        controller = build_default_controller()
        sd = _make_scope_decision()
        result = controller.propose_refinement(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.validation = None  # type: ignore


class TestDeterminism:
    """Same input produces same output across all layers."""

    def test_same_input_same_envelope(self):
        sd = _make_scope_decision()
        env_a = build_refinement_input_from_scope(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        env_b = build_refinement_input_from_scope(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        assert env_a.envelope_digest == env_b.envelope_digest

    def test_same_input_same_proposal(self):
        sd = _make_scope_decision()
        env = build_refinement_input_from_scope(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        proposer = DeterministicShadowRefinementProposer(fixture_mode="ONE_WRITABLE_EDIT")
        p1 = proposer.propose_refinement(env)
        p2 = proposer.propose_refinement(env)
        assert p1.digest == p2.digest
        assert p1.proposed_grid81 == p2.proposed_grid81

    def test_same_input_same_validation(self):
        sd = _make_scope_decision()
        env = build_refinement_input_from_scope(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        proposer = DeterministicShadowRefinementProposer(fixture_mode="ONE_WRITABLE_EDIT")
        proposal = proposer.propose_refinement(env)
        v1 = build_validation_record(env, proposal)
        v2 = build_validation_record(env, proposal)
        assert v1.validation_digest == v2.validation_digest

    def test_same_input_same_receipt(self):
        controller = build_default_controller()
        sd = _make_scope_decision()
        r1 = controller.propose_refinement(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        r2 = controller.propose_refinement(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        assert r1.receipt.receipt_digest == r2.receipt.receipt_digest

    def test_same_input_same_complete_result(self):
        controller = build_default_controller()
        sd = _make_scope_decision()
        r1 = controller.propose_refinement(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        r2 = controller.propose_refinement(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        assert r1.input_envelope.envelope_digest == r2.input_envelope.envelope_digest
        assert r1.receipt.receipt_digest == r2.receipt.receipt_digest
        assert r1.proposal.digest == r2.proposal.digest
        assert r1.validation.validation_digest == r2.validation.validation_digest


class TestControllerIntegration:
    """End-to-end controller propose_refinement path."""

    def test_controller_propose_refinement_returns_result(self):
        controller = build_default_controller()
        sd = _make_scope_decision()
        result = controller.propose_refinement(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        assert isinstance(result, RefinementControllerResultV1)
        assert isinstance(result.input_envelope, P0RefinementInputV1)
        assert isinstance(result.scope_decision, RefinementScopeDecisionV1)
        assert isinstance(result.proposal, TRMRefinementProposal)
        assert isinstance(result.validation, RefinementValidationRecordV1)
        assert isinstance(result.receipt, RefinementInvocationReceiptV1)

    def test_controller_result_binds_all_fields(self):
        controller = build_default_controller()
        sd = _make_scope_decision()
        result = controller.propose_refinement(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        assert result.input_envelope.request_id == REQUEST.request_id
        assert result.scope_decision.request_id == REQUEST.request_id
        assert result.receipt.request_id == REQUEST.request_id
        assert result.receipt.logical_tick == 0
        assert result.receipt.snapshot_digest == VALID_SNAPSHOT

    def test_controller_result_has_no_apply_method(self):
        controller = build_default_controller()
        sd = _make_scope_decision()
        result = controller.propose_refinement(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        assert not hasattr(result, "apply")
        assert not hasattr(result, "commit")

    def test_controller_with_custom_proposer(self):
        custom = DeterministicShadowRefinementProposer(fixture_mode="NOOP")
        controller = P0Controller(
            projector=None,  # type: ignore
            trm=None,  # type: ignore
            expert_proposer=None,  # type: ignore
            decoder=None,  # type: ignore
            validators=(None,),  # type: ignore
            refinement_proposer=custom,
        )
        sd = _make_scope_decision()
        result = controller.propose_refinement(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        assert result.receipt.proposer_id == "shadow-refinement.v1"

    def test_existing_run_path_still_works(self):
        """P0.1 run() path is unaffected by G2 integration."""
        controller = build_default_controller()
        ctx = RequestContext(
            request_id="g2-run-test",
            prompt="def foo(): return 42",
        )
        result = controller.run(ctx)
        assert result.request_id == "g2-run-test"
        assert not result.expansion_executed
        assert not result.governance_invoked


class TestFixtureModes:
    """Deterministic shadow proposer fixture modes."""

    def _make_env(self, mask=VALID_MASK_ALL_ONES):
        sd = _make_scope_decision(writable_mask81=mask)
        return build_refinement_input_from_scope(
            request=REQUEST,
            projection=PROJECTION,
            scope_decision=sd,
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )

    def test_noop_mode(self):
        env = self._make_env()
        p = DeterministicShadowRefinementProposer(fixture_mode="NOOP")
        proposal = p.propose_refinement(env)
        assert proposal.proposed_grid81 == VALID_GRID

    def test_one_writable_edit_mode(self):
        env = self._make_env()
        p = DeterministicShadowRefinementProposer(fixture_mode="ONE_WRITABLE_EDIT")
        proposal = p.propose_refinement(env)
        changes = sum(
            1 for a, b in zip(VALID_GRID, proposal.proposed_grid81) if a != b
        )
        assert changes == 1

    def test_one_locked_edit_mode(self):
        mask = tuple(0 if i == 5 else 1 for i in range(81))
        env = self._make_env(mask)
        p = DeterministicShadowRefinementProposer(fixture_mode="ONE_LOCKED_EDIT")
        proposal = p.propose_refinement(env)
        # Should change cell 5 which is locked
        changes = [
            i for i, (a, b) in enumerate(zip(VALID_GRID, proposal.proposed_grid81))
            if a != b
        ]
        assert 5 in changes

    def test_multiple_edits_mode(self):
        env = self._make_env()
        p = DeterministicShadowRefinementProposer(fixture_mode="MULTIPLE_EDITS")
        proposal = p.propose_refinement(env)
        changes = sum(
            1 for a, b in zip(VALID_GRID, proposal.proposed_grid81) if a != b
        )
        assert changes == 2

    def test_wrong_input_digest_mode(self):
        env = self._make_env()
        p = DeterministicShadowRefinementProposer(fixture_mode="WRONG_INPUT_DIGEST")
        proposal = p.propose_refinement(env)
        assert proposal.input_digest != env.envelope_digest

    def test_invalid_token_mode(self):
        env = self._make_env()
        p = DeterministicShadowRefinementProposer(fixture_mode="INVALID_TOKEN")
        proposal = p.propose_refinement(env)
        # Should have a token outside 0..9
        assert any(v > 9 for v in proposal.proposed_grid81)


class TestRefinementScopeProviderPort:
    """The scope provider port exists and is abstract."""

    def test_port_is_protocol(self):
        from typing import Protocol
        assert issubclass(RefinementScopeProvider, Protocol)

    def test_port_has_decide_scope(self):
        assert hasattr(RefinementScopeProvider, "decide_scope")
        sig = inspect.signature(RefinementScopeProvider.decide_scope)
        params = list(sig.parameters.keys())
        assert "request" in params
        assert "projection" in params
        assert "logical_tick" in params
        assert "snapshot_digest" in params
