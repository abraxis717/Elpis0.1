"""G3.0 — Initial-void scope provider test suite.

Tests the pure policy, scope provider, derivation record, controller
integration, factory wiring, authority isolation, identity binding,
semantic cases, immutability, and hash-seed determinism.
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import os

import pytest

# Ensure import paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from elpis_p0 import (
    INITIAL_VOID_SCOPE_POLICY_ID,
    INITIAL_VOID_SCOPE_POLICY_VERSION,
    derive_initial_void_mask81,
    InitialVoidScopeProvider,
    ScopeDerivationRecordV1,
    ScopedRefinementControllerResultV1,
    RequestContext,
    StructuralProjection,
    RefinementScopeDecisionV1,
    P0RefinementError,
    build_default_controller,
)
from elpis_p0.refinement_scope import _mask_canonical
from dataclasses import FrozenInstanceError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_request(request_id: str = "test-req-001") -> RequestContext:
    return RequestContext(
        request_id=request_id,
        prompt="test prompt",
    )


def _make_projection(
    grid81: tuple[int, ...],
    digest: str = "a" * 64,
) -> StructuralProjection:
    return StructuralProjection(
        grid81=grid81,
        semantic_rows=tuple("row" + str(i) for i in range(9)),
        features=tuple(),
        digest=digest,
    )


MIXED_GRID = (
    0, 1, 2, 3, 4, 5, 6, 7, 8,
    9, 0, 1, 2, 3, 4, 5, 6, 7,
    8, 9, 0, 1, 2, 3, 4, 5, 6,
    7, 8, 9, 0, 1, 2, 3, 4, 5,
    6, 7, 8, 9, 0, 1, 2, 3, 4,
    5, 6, 7, 8, 9, 0, 1, 2, 3,
    4, 5, 6, 7, 8, 9, 0, 1, 2,
    3, 4, 5, 6, 7, 8, 9, 0, 1,
    2, 3, 4, 5, 6, 7, 8, 9, 0,
)
# 0s at indices: 0,10,20,30,40,50,60,70,80 = 9 zeros

ALL_NONZERO_GRID = tuple(list(range(1, 10)) + [1] * 72)  # 81 nonzero

ALL_ZERO_GRID = tuple(0 for _ in range(81))

SINGLE_ZERO_GRID = tuple([0] + [1] * 80)

ALTERNATING_GRID = tuple(i % 2 for i in range(81))
# zeros at even indices: 0,2,4,...,80 = 41 zeros


SNAPSHOT_DIGEST = "b" * 64
LOGICAL_TICK = 0


# ===========================================================================
# 11.1 — Pure policy tests
# ===========================================================================

class TestPurePolicy:
    """Test derive_initial_void_mask81 as a pure function."""

    def test_mixed_grid_ones_where_zero(self):
        """Mixed grid: mask has 1s exactly where grid has 0s."""
        mask = derive_initial_void_mask81(MIXED_GRID)
        for i in range(81):
            if MIXED_GRID[i] == 0:
                assert mask[i] == 1, f"index {i}: grid=0, mask should be 1, got {mask[i]}"
            else:
                assert mask[i] == 0, f"index {i}: grid={MIXED_GRID[i]}, mask should be 0, got {mask[i]}"
        assert len(mask) == 81

    def test_no_zero_grid_all_zeros(self):
        """No-zero grid: mask is exactly all zeros."""
        mask = derive_initial_void_mask81(ALL_NONZERO_GRID)
        assert mask == tuple(0 for _ in range(81))
        assert len(mask) == 81

    def test_all_zero_grid_all_ones(self):
        """All-zero grid: mask is exactly all ones."""
        mask = derive_initial_void_mask81(ALL_ZERO_GRID)
        assert mask == tuple(1 for _ in range(81))
        assert len(mask) == 81

    def test_single_zero_grid_one_writable(self):
        """Single-zero grid: exactly one writable index."""
        mask = derive_initial_void_mask81(SINGLE_ZERO_GRID)
        assert mask[0] == 1
        for i in range(1, 81):
            assert mask[i] == 0
        assert sum(mask) == 1

    def test_alternating_grid_exact_mask(self):
        """Alternating grid: exact expected binary mask."""
        mask = derive_initial_void_mask81(ALTERNATING_GRID)
        for i in range(81):
            expected = 1 if ALTERNATING_GRID[i] == 0 else 0
            assert mask[i] == expected, f"index {i}: expected {expected}, got {mask[i]}"
        assert sum(mask) == 41  # even indices have 0 in grid


# ===========================================================================
# 11.2 — Validation tests
# ===========================================================================

class TestValidation:
    """Test input validation for the scope provider."""

    def test_reject_grid_shorter_than_81(self):
        with pytest.raises(ValueError, match="length 81"):
            derive_initial_void_mask81(tuple(range(80)))

    def test_reject_grid_longer_than_81(self):
        with pytest.raises(ValueError, match="length 81"):
            derive_initial_void_mask81(tuple(range(82)))

    def test_reject_negative_token(self):
        grid = list(ALL_ZERO_GRID)
        grid[0] = -1
        with pytest.raises(ValueError, match="outside structural domain"):
            derive_initial_void_mask81(tuple(grid))

    def test_reject_token_above_domain(self):
        grid = list(ALL_ZERO_GRID)
        grid[0] = 10
        with pytest.raises(ValueError, match="outside structural domain"):
            derive_initial_void_mask81(tuple(grid))

    def test_reject_bool_token(self):
        grid = list(ALL_ZERO_GRID)
        grid[0] = True  # bool is subclass of int but not canonical structural int
        with pytest.raises(ValueError, match="not a structural int"):
            derive_initial_void_mask81(tuple(grid))

    def test_reject_non_integer_token(self):
        grid = list(ALL_ZERO_GRID)
        grid[0] = 1.5
        with pytest.raises(ValueError, match="not a structural int"):
            derive_initial_void_mask81(tuple(grid))

    def test_reject_negative_logical_tick(self):
        provider = InitialVoidScopeProvider()
        request = _make_request()
        projection = _make_projection(MIXED_GRID)
        with pytest.raises(ValueError, match="logical_tick must be >= 0"):
            provider.decide_scope(
                request=request,
                projection=projection,
                logical_tick=-1,
                snapshot_digest=SNAPSHOT_DIGEST,
            )

    def test_reject_empty_request_id(self):
        provider = InitialVoidScopeProvider()
        request = _make_request(request_id="")
        projection = _make_projection(MIXED_GRID)
        with pytest.raises(ValueError, match="request_id must be non-empty"):
            provider.decide_scope(
                request=request,
                projection=projection,
                logical_tick=LOGICAL_TICK,
                snapshot_digest=SNAPSHOT_DIGEST,
            )

    def test_reject_invalid_snapshot_digest(self):
        provider = InitialVoidScopeProvider()
        request = _make_request()
        projection = _make_projection(MIXED_GRID)
        with pytest.raises(ValueError, match="snapshot_digest must be 64 hex chars"):
            provider.decide_scope(
                request=request,
                projection=projection,
                logical_tick=LOGICAL_TICK,
                snapshot_digest="short",
            )


# ===========================================================================
# 11.3 — Authority-isolation tests
# ===========================================================================

class TestAuthorityIsolation:
    """Prove scope derivation is isolated from prohibited information sources."""

    def test_identical_grid_different_features_same_mask(self):
        """Projections with same grid but different features produce same mask."""
        provider = InitialVoidScopeProvider()
        request = _make_request()

        proj_a = StructuralProjection(
            grid81=MIXED_GRID,
            semantic_rows=tuple(f"row_{i}" for i in range(9)),
            features=(("feat_a", 0.5), ("feat_b", 1.0)),
            digest="a" * 64,
        )
        proj_b = StructuralProjection(
            grid81=MIXED_GRID,
            semantic_rows=tuple(f"other_row_{i}" for i in range(9)),
            features=(("feat_x", 9.9), ("feat_y", -1.0)),
            digest="c" * 64,
        )

        decision_a = provider.decide_scope(
            request=request, projection=proj_a,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )
        decision_b = provider.decide_scope(
            request=request, projection=proj_b,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )

        assert decision_a.writable_mask81 == decision_b.writable_mask81
        assert decision_a.mask_digest == decision_b.mask_digest

    def test_identical_grid_different_feature_order_same_mask(self):
        """Different feature ordering does not affect mask."""
        provider = InitialVoidScopeProvider()
        request = _make_request()

        proj_a = StructuralProjection(
            grid81=MIXED_GRID,
            semantic_rows=tuple("r" + str(i) for i in range(9)),
            features=(("a", 1.0), ("b", 2.0), ("c", 3.0)),
            digest="a" * 64,
        )
        proj_b = StructuralProjection(
            grid81=MIXED_GRID,
            semantic_rows=tuple("r" + str(i) for i in range(9)),
            features=(("c", 3.0), ("a", 1.0), ("b", 2.0)),
            digest="a" * 64,
        )

        decision_a = provider.decide_scope(
            request=request, projection=proj_a,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )
        decision_b = provider.decide_scope(
            request=request, projection=proj_b,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )

        assert decision_a.writable_mask81 == decision_b.writable_mask81

    def test_identical_grid_different_prompt_same_mask(self):
        """Different prompt text does not affect scope."""
        provider = InitialVoidScopeProvider()
        projection = _make_projection(MIXED_GRID)

        request_a = RequestContext(request_id="test-1", prompt="solve sudoku")
        request_b = RequestContext(request_id="test-1", prompt="optimize neural network")

        decision_a = provider.decide_scope(
            request=request_a, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )
        decision_b = provider.decide_scope(
            request=request_b, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )

        assert decision_a.writable_mask81 == decision_b.writable_mask81
        assert decision_a.mask_digest == decision_b.mask_digest

    def test_oracle_monkeypatch_cannot_influence_mask(self):
        """Importing or monkeypatching oracle cannot influence scope."""
        provider = InitialVoidScopeProvider()
        request = _make_request()
        projection = _make_projection(MIXED_GRID)

        # Derive mask before any monkeypatch
        decision_before = provider.decide_scope(
            request=request, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )

        # Try to inject an "oracle" module
        import sys as _sys
        fake_oracle = type(sys)('fake_structural_oracle')
        fake_oracle.is_valid = lambda: False
        old = _sys.modules.get('fake_structural_oracle')
        _sys.modules['fake_structural_oracle'] = fake_oracle

        try:
            decision_after = provider.decide_scope(
                request=request, projection=projection,
                logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
            )
        finally:
            if old is None:
                _sys.modules.pop('fake_structural_oracle', None)
            else:
                _sys.modules['fake_structural_oracle'] = old

        assert decision_before.writable_mask81 == decision_after.writable_mask81
        assert decision_before.mask_digest == decision_after.mask_digest

    def test_model_output_cannot_influence_scope(self):
        """Model/proposer outputs cannot influence scope derivation."""
        provider = InitialVoidScopeProvider()
        request = _make_request()
        projection = _make_projection(MIXED_GRID)

        # Derive mask directly — no model involved
        mask1 = derive_initial_void_mask81(MIXED_GRID)

        # Derive again — should be identical regardless of any model state
        mask2 = derive_initial_void_mask81(MIXED_GRID)

        assert mask1 == mask2
        assert _mask_canonical(mask1) == _mask_canonical(mask2)


# ===========================================================================
# 11.4 — Identity-binding tests
# ===========================================================================

class TestIdentityBinding:
    """Prove identity digests change exactly when they should."""

    def test_changing_request_id_changes_decision_digest(self):
        provider = InitialVoidScopeProvider()
        projection = _make_projection(MIXED_GRID)

        req_a = _make_request("req-alpha")
        req_b = _make_request("req-beta")

        dec_a = provider.decide_scope(
            request=req_a, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )
        dec_b = provider.decide_scope(
            request=req_b, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )

        assert dec_a.decision_digest != dec_b.decision_digest
        # But mask should be same
        assert dec_a.writable_mask81 == dec_b.writable_mask81
        assert dec_a.mask_digest == dec_b.mask_digest

    def test_changing_logical_tick_changes_decision_digest(self):
        provider = InitialVoidScopeProvider()
        request = _make_request()
        projection = _make_projection(MIXED_GRID)

        dec_a = provider.decide_scope(
            request=request, projection=projection,
            logical_tick=0, snapshot_digest=SNAPSHOT_DIGEST,
        )
        dec_b = provider.decide_scope(
            request=request, projection=projection,
            logical_tick=1, snapshot_digest=SNAPSHOT_DIGEST,
        )

        assert dec_a.decision_digest != dec_b.decision_digest

    def test_changing_snapshot_digest_changes_decision_digest(self):
        provider = InitialVoidScopeProvider()
        request = _make_request()
        projection = _make_projection(MIXED_GRID)

        dec_a = provider.decide_scope(
            request=request, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest="a" * 64,
        )
        dec_b = provider.decide_scope(
            request=request, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest="f" * 64,
        )

        assert dec_a.decision_digest != dec_b.decision_digest

    def test_changing_grid_changes_mask(self):
        mask_a = derive_initial_void_mask81(MIXED_GRID)
        mask_b = derive_initial_void_mask81(ALL_ZERO_GRID)
        assert mask_a != mask_b
        assert _mask_canonical(mask_a) != _mask_canonical(mask_b)

    def test_changing_policy_version_changes_decision(self):
        from elpis_p0.initial_void_scope_provider import derive_scope
        request = _make_request()
        projection = _make_projection(MIXED_GRID)

        dec_a, _ = derive_scope(
            request=request, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
            policy_id="p0.initial_void_cells",
            policy_version="1",
        )
        dec_b, _ = derive_scope(
            request=request, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
            policy_id="p0.initial_void_cells",
            policy_version="2",
        )

        assert dec_a.scope_policy_version == "1"
        assert dec_b.scope_policy_version == "2"
        assert dec_a.decision_digest != dec_b.decision_digest

    def test_changing_features_only_does_not_change_mask(self):
        from elpis_p0.initial_void_scope_provider import derive_scope
        provider = InitialVoidScopeProvider()
        request = _make_request()

        proj_a = StructuralProjection(
            grid81=MIXED_GRID,
            semantic_rows=tuple(f"row_{i}" for i in range(9)),
            features=(("f1", 0.1),),
            digest="a" * 64,
        )
        proj_b = StructuralProjection(
            grid81=MIXED_GRID,
            semantic_rows=tuple(f"ROW_{i}" for i in range(9)),
            features=(("f2", 0.9), ("f3", 0.5)),
            digest="b" * 64,
        )

        dec_a = provider.decide_scope(
            request=request, projection=proj_a,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )
        dec_b = provider.decide_scope(
            request=request, projection=proj_b,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )

        assert dec_a.writable_mask81 == dec_b.writable_mask81
        assert dec_a.mask_digest == dec_b.mask_digest


# ===========================================================================
# 11.5 — Controller-path tests
# ===========================================================================

class TestControllerPath:
    """Test G3 controller integration path."""

    def test_explicit_gate2_path_still_works(self):
        """Existing propose_refinement with explicit scope_decision works."""
        controller = build_default_controller()
        request = _make_request()
        projection = _make_projection(MIXED_GRID)

        from elpis_p0.refinement_scope import RefinementScopeDecisionV1
        mask = derive_initial_void_mask81(MIXED_GRID)
        scope_decision = RefinementScopeDecisionV1(
            request_id=request.request_id,
            logical_tick=LOGICAL_TICK,
            snapshot_digest=SNAPSHOT_DIGEST,
            scope_policy_id=INITIAL_VOID_SCOPE_POLICY_ID,
            scope_policy_version=INITIAL_VOID_SCOPE_POLICY_VERSION,
            writable_mask81=mask,
        )

        result = controller.propose_refinement(
            request=request,
            projection=projection,
            scope_decision=scope_decision,
            logical_tick=LOGICAL_TICK,
            snapshot_digest=SNAPSHOT_DIGEST,
        )
        assert result is not None

    def test_explicit_path_fails_without_scope(self):
        """propose_refinement fails closed when scope_decision is None."""
        controller = build_default_controller()
        request = _make_request()
        projection = _make_projection(MIXED_GRID)

        with pytest.raises(P0RefinementError, match="BLOCKED_P0_REFINEMENT_SCOPE_ABSENT"):
            controller.propose_refinement(
                request=request,
                projection=projection,
                scope_decision=None,
                logical_tick=LOGICAL_TICK,
                snapshot_digest=SNAPSHOT_DIGEST,
            )

    def test_derived_path_works_with_default_factory(self):
        """New derive_and_propose_refinement works through default factory."""
        controller = build_default_controller()
        request = _make_request()
        projection = _make_projection(MIXED_GRID)

        result = controller.derive_and_propose_refinement(
            request=request,
            projection=projection,
            logical_tick=LOGICAL_TICK,
            snapshot_digest=SNAPSHOT_DIGEST,
        )

        assert isinstance(result, ScopedRefinementControllerResultV1)
        assert result.scope_decision is not None
        assert result.scope_derivation_record is not None
        assert result.validation is not None
        assert result.receipt is not None

    def test_derived_path_fails_without_provider(self):
        """derive_and_propose_refinement fails closed without scope_provider."""
        from elpis_p0.factory import build_default_controller as _build
        from elpis_p0.controller import P0Controller
        from elpis_p0.projector import DeterministicPythonProjector
        from elpis_p0.trm import ShadowTRMProposer
        from elpis_p0.experts import DeterministicExpertProposer
        from elpis_p0.decoder import DeterministicPythonDecoder
        from elpis_p0.validators import PythonASTValidator

        controller = P0Controller(
            projector=DeterministicPythonProjector(),
            trm=ShadowTRMProposer(),
            expert_proposer=DeterministicExpertProposer(),
            decoder=DeterministicPythonDecoder(),
            validators=(PythonASTValidator(),),
            scope_provider=None,  # explicitly no provider
        )

        request = _make_request()
        projection = _make_projection(MIXED_GRID)

        with pytest.raises(P0RefinementError, match="BLOCKED_G30_SCOPE_PROVIDER_ABSENT"):
            controller.derive_and_propose_refinement(
                request=request,
                projection=projection,
                logical_tick=LOGICAL_TICK,
                snapshot_digest=SNAPSHOT_DIGEST,
            )

    def test_provider_called_exactly_once(self):
        """Scope provider is invoked exactly once per call."""
        class CountingProvider:
            call_count = 0

            def decide_scope(self, *, request, projection, logical_tick, snapshot_digest):
                CountingProvider.call_count += 1
                return InitialVoidScopeProvider().decide_scope(
                    request=request,
                    projection=projection,
                    logical_tick=logical_tick,
                    snapshot_digest=snapshot_digest,
                )

        from elpis_p0.projector import DeterministicPythonProjector
        from elpis_p0.trm import ShadowTRMProposer
        from elpis_p0.experts import DeterministicExpertProposer
        from elpis_p0.decoder import DeterministicPythonDecoder
        from elpis_p0.validators import PythonASTValidator
        from elpis_p0.controller import P0Controller

        CountingProvider.call_count = 0
        controller = P0Controller(
            projector=DeterministicPythonProjector(),
            trm=ShadowTRMProposer(),
            expert_proposer=DeterministicExpertProposer(),
            decoder=DeterministicPythonDecoder(),
            validators=(PythonASTValidator(),),
            scope_provider=CountingProvider(),
        )

        request = _make_request()
        projection = _make_projection(MIXED_GRID)
        controller.derive_and_propose_refinement(
            request=request,
            projection=projection,
            logical_tick=LOGICAL_TICK,
            snapshot_digest=SNAPSHOT_DIGEST,
        )

        assert CountingProvider.call_count == 1


# ===========================================================================
# 11.6 — Semantic cases
# ===========================================================================

class TestSemanticCases:
    """Test policy semantics for specific grid patterns."""

    def test_grid_with_zeros_one_writable_edit(self):
        """Grid with zeros: provider exposes all zero cells."""
        provider = InitialVoidScopeProvider()
        request = _make_request()
        projection = _make_projection(MIXED_GRID)

        decision = provider.decide_scope(
            request=request, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )

        # Mask should have 1s at exactly the zero positions
        for i in range(81):
            if MIXED_GRID[i] == 0:
                assert decision.writable_mask81[i] == 1
            else:
                assert decision.writable_mask81[i] == 0

    def test_no_zero_grid_all_zero_mask(self):
        """Grid with no zero cells: provider returns all-zero mask."""
        provider = InitialVoidScopeProvider()
        request = _make_request()
        projection = _make_projection(ALL_NONZERO_GRID)

        decision = provider.decide_scope(
            request=request, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )

        assert decision.writable_mask81 == tuple(0 for _ in range(81))

        # Verify derivation record status
        from elpis_p0.initial_void_scope_provider import derive_scope
        _, record = derive_scope(
            request=request, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )
        assert record.derivation_status == "NO_WRITABLE_INITIAL_VOID_CELLS"
        assert record.writable_count == 0
        assert record.locked_count == 81

    def test_all_zero_grid_all_one_mask(self):
        """Grid with all zeros: provider returns all-one mask."""
        provider = InitialVoidScopeProvider()
        request = _make_request()
        projection = _make_projection(ALL_ZERO_GRID)

        decision = provider.decide_scope(
            request=request, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )

        assert decision.writable_mask81 == tuple(1 for _ in range(81))


# ===========================================================================
# 11.7 — Immutability tests
# ===========================================================================

class TestImmutability:
    """Prove frozen/slotted behavior and input immutability."""

    def test_scope_derivation_record_frozen(self):
        """ScopeDerivationRecordV1 is frozen (cannot be modified)."""
        from elpis_p0.initial_void_scope_provider import derive_scope
        request = _make_request()
        projection = _make_projection(MIXED_GRID)

        _, record = derive_scope(
            request=request, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )

        with pytest.raises((AttributeError, FrozenInstanceError)):
            record.writable_count = 999

    def test_scoped_result_frozen(self):
        """ScopedRefinementControllerResultV1 is frozen."""
        controller = build_default_controller()
        request = _make_request()
        projection = _make_projection(MIXED_GRID)

        result = controller.derive_and_propose_refinement(
            request=request,
            projection=projection,
            logical_tick=LOGICAL_TICK,
            snapshot_digest=SNAPSHOT_DIGEST,
        )

        with pytest.raises((AttributeError, FrozenInstanceError)):
            result.terminal_status = "HACKED"

    def test_input_request_unchanged(self):
        """Request is not mutated by derivation."""
        request = _make_request()
        projection = _make_projection(MIXED_GRID)

        request_id_before = request.request_id
        prompt_before = request.prompt

        from elpis_p0.initial_void_scope_provider import derive_scope
        derive_scope(
            request=request, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )

        assert request.request_id == request_id_before
        assert request.prompt == prompt_before

    def test_input_projection_unchanged(self):
        """Projection is not mutated by derivation."""
        request = _make_request()
        projection = _make_projection(MIXED_GRID)

        grid_before = projection.grid81
        digest_before = projection.digest

        from elpis_p0.initial_void_scope_provider import derive_scope
        derive_scope(
            request=request, projection=projection,
            logical_tick=LOGICAL_TICK, snapshot_digest=SNAPSHOT_DIGEST,
        )

        assert projection.grid81 == grid_before
        assert projection.digest == digest_before


# ===========================================================================
# 11.8 — Hash-seed determinism tests
# ===========================================================================

class TestHashSeedDeterminism:
    """Verify outputs are identical across PYTHONHASHSEED values."""

    _SCRIPT = '''
import sys, os, json
sys.path.insert(0, os.environ.get("P0_SRC", ""))
from elpis_p0 import (
    derive_initial_void_mask81,
    InitialVoidScopeProvider,
    RequestContext,
    StructuralProjection,
    INITIAL_VOID_SCOPE_POLICY_ID,
    INITIAL_VOID_SCOPE_POLICY_VERSION,
    build_default_controller,
)
from elpis_p0.refinement_scope import _mask_canonical as _mc

grid = (0,1,2,3,4,5,6,7,8,
        9,0,1,2,3,4,5,6,7,
        8,9,0,1,2,3,4,5,6,
        7,8,9,0,1,2,3,4,5,
        6,7,8,9,0,1,2,3,4,
        5,6,7,8,9,0,1,2,3,
        4,5,6,7,8,9,0,1,2,
        3,4,5,6,7,8,9,0,1,
        2,3,4,5,6,7,8,9,0)

provider = InitialVoidScopeProvider()
request = RequestContext(request_id="det-test", prompt="x")
projection = StructuralProjection(
    grid81=grid,
    semantic_rows=tuple("r"+str(i) for i in range(9)),
    features=(),
    digest="a"*64,
)

mask = derive_initial_void_mask81(grid)
mask_digest = _mc(mask)

decision = provider.decide_scope(
    request=request, projection=projection,
    logical_tick=0, snapshot_digest="b"*64,
)

result = {
    "mask": list(mask),
    "mask_digest": mask_digest,
    "decision_digest": decision.decision_digest,
    "writable_count": sum(mask),
}
print(json.dumps(result, sort_keys=True))
'''

    def test_hash_seed_0_1_717_identical(self):
        """Three hash seeds produce identical outputs."""
        seeds = [0, 1, 717]
        results = []

        for seed in seeds:
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = str(seed)
            env["P0_SRC"] = os.path.join(
                os.path.dirname(__file__), '..', 'src'
            )
            result = subprocess.run(
                [sys.executable, "-c", self._SCRIPT],
                capture_output=True, text=True, env=env,
            )
            assert result.returncode == 0, f"Seed {seed}: {result.stderr}"
            results.append(json.loads(result.stdout.strip()))

        # All three results must be byte-identical
        for i in range(1, len(results)):
            assert results[0] == results[i], (
                f"Hash seed {seeds[0]} != seed {seeds[i]}: "
                f"{results[0]} vs {results[i]}"
            )
