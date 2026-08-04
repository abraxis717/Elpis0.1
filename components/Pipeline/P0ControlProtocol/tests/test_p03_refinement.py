"""G1.0 Phase G9 — P0 refinement envelope and conversion tests.

Tests cover:
- P0RefinementInputV1 envelope validation
- build_refinement_input conversion from StructuralProjection
"""
from __future__ import annotations

import pytest

from elpis_p0.contracts import (
    P0RefinementInputV1,
    P0RefinementError,
    StructuralProjection,
    build_refinement_input,
)
from elpis_fractal_spine.structural_refinement import (
    StructuralRefinementInputV1,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_GRID = tuple((i % 10) for i in range(81))  # 81 cells, values 0..9
VALID_MASK_ALL_ONES = tuple(1 for _ in range(81))
VALID_MASK_ALL_ZEROS = tuple(0 for _ in range(81))
VALID_SNAPSHOT = "a" * 64

PROJECTION = StructuralProjection(
    grid81=VALID_GRID,
    semantic_rows=("row0", "row1", "row2", "row3", "row4", "row5", "row6", "row7", "row8"),
    features=(("feat", 1.0),),
    digest="proj_digest_v1",
)


# ---------------------------------------------------------------------------
# P0RefinementInputV1 — valid cases
# ---------------------------------------------------------------------------

class TestP0RefinementEnvelope:
    def _make_structural(self, grid=None, mask=None):
        return StructuralRefinementInputV1(
            grid81=grid or VALID_GRID,
            writable_mask81=mask or VALID_MASK_ALL_ONES,
        )

    def test_valid_envelope_accepted(self):
        si = self._make_structural()
        env = P0RefinementInputV1(
            request_id="test-001",
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
            structural_input=si,
        )
        assert env.schema_version == "p0.refinement.input.v1"
        assert env.request_id == "test-001"
        assert env.logical_tick == 0
        assert len(env.envelope_digest) == 64

    def test_same_content_produces_identical_envelope_digest(self):
        si = self._make_structural()
        env_a = P0RefinementInputV1(
            request_id="test-001",
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
            structural_input=si,
        )
        env_b = P0RefinementInputV1(
            request_id="test-001",
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
            structural_input=si,
        )
        assert env_a.envelope_digest == env_b.envelope_digest

    def test_request_id_changes_digest(self):
        si = self._make_structural()
        env_a = P0RefinementInputV1(
            request_id="test-001",
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
            structural_input=si,
        )
        env_b = P0RefinementInputV1(
            request_id="test-002",
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
            structural_input=si,
        )
        assert env_a.envelope_digest != env_b.envelope_digest

    def test_logical_tick_changes_digest(self):
        si = self._make_structural()
        env_a = P0RefinementInputV1(
            request_id="test-001",
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
            structural_input=si,
        )
        env_b = P0RefinementInputV1(
            request_id="test-001",
            logical_tick=1,
            snapshot_digest=VALID_SNAPSHOT,
            structural_input=si,
        )
        assert env_a.envelope_digest != env_b.envelope_digest

    def test_snapshot_digest_changes_digest(self):
        si = self._make_structural()
        env_a = P0RefinementInputV1(
            request_id="test-001",
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
            structural_input=si,
        )
        env_b = P0RefinementInputV1(
            request_id="test-001",
            logical_tick=0,
            snapshot_digest="b" * 64,
            structural_input=si,
        )
        assert env_a.envelope_digest != env_b.envelope_digest

    def test_structural_input_changes_digest(self):
        si_a = self._make_structural(mask=tuple(1 for _ in range(81)))
        si_b = self._make_structural(mask=tuple(0 for _ in range(81)))
        env_a = P0RefinementInputV1(
            request_id="test-001",
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
            structural_input=si_a,
        )
        env_b = P0RefinementInputV1(
            request_id="test-001",
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
            structural_input=si_b,
        )
        assert env_a.envelope_digest != env_b.envelope_digest


# ---------------------------------------------------------------------------
# P0RefinementInputV1 — rejection cases
# ---------------------------------------------------------------------------

class TestP0RefinementRejection:
    def test_negative_logical_tick_rejected(self):
        si = StructuralRefinementInputV1(
            grid81=VALID_GRID,
            writable_mask81=VALID_MASK_ALL_ONES,
        )
        with pytest.raises(P0RefinementError, match="non-negative"):
            P0RefinementInputV1(
                request_id="test-001",
                logical_tick=-1,
                snapshot_digest=VALID_SNAPSHOT,
                structural_input=si,
            )

    def test_invalid_snapshot_digest_rejected(self):
        si = StructuralRefinementInputV1(
            grid81=VALID_GRID,
            writable_mask81=VALID_MASK_ALL_ONES,
        )
        with pytest.raises(P0RefinementError, match="64 hex"):
            P0RefinementInputV1(
                request_id="test-001",
                logical_tick=0,
                snapshot_digest="short",
                structural_input=si,
            )

    def test_non_hex_snapshot_digest_rejected(self):
        si = StructuralRefinementInputV1(
            grid81=VALID_GRID,
            writable_mask81=VALID_MASK_ALL_ONES,
        )
        with pytest.raises(P0RefinementError, match="non-hex"):
            P0RefinementInputV1(
                request_id="test-001",
                logical_tick=0,
                snapshot_digest="x" * 64,
                structural_input=si,
            )

    def test_empty_request_id_rejected(self):
        si = StructuralRefinementInputV1(
            grid81=VALID_GRID,
            writable_mask81=VALID_MASK_ALL_ONES,
        )
        with pytest.raises(P0RefinementError, match="request_id"):
            P0RefinementInputV1(
                request_id="",
                logical_tick=0,
                snapshot_digest=VALID_SNAPSHOT,
                structural_input=si,
            )

    def test_none_structural_input_rejected(self):
        with pytest.raises(P0RefinementError, match="structural_input"):
            P0RefinementInputV1(
                request_id="test-001",
                logical_tick=0,
                snapshot_digest=VALID_SNAPSHOT,
                structural_input=None,  # type: ignore
            )


# ---------------------------------------------------------------------------
# Conversion: build_refinement_input
# ---------------------------------------------------------------------------

class TestBuildRefinementInput:
    def test_conversion_requires_explicit_writable_mask81(self):
        result = build_refinement_input(
            projection=PROJECTION,
            writable_mask81=VALID_MASK_ALL_ONES,
            request_id="conv-001",
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        assert isinstance(result, P0RefinementInputV1)
        assert result.structural_input.writable_mask81 == VALID_MASK_ALL_ONES

    def test_conversion_preserves_grid_exactly(self):
        result = build_refinement_input(
            projection=PROJECTION,
            writable_mask81=VALID_MASK_ALL_ONES,
            request_id="conv-001",
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        assert result.structural_input.grid81 == PROJECTION.grid81

    def test_conversion_does_not_read_mask_from_features(self):
        projection_with_mask_in_features = StructuralProjection(
            grid81=VALID_GRID,
            semantic_rows=("r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8"),
            features=(("writable_mask", 0.0),),
            digest="proj_with_mask_in_features",
        )
        result = build_refinement_input(
            projection=projection_with_mask_in_features,
            writable_mask81=VALID_MASK_ALL_ZEROS,
            request_id="conv-002",
            logical_tick=0,
            snapshot_digest=VALID_SNAPSHOT,
        )
        # The mask should be the one we explicitly passed, not read from features
        assert result.structural_input.writable_mask81 == VALID_MASK_ALL_ZEROS

    def test_existing_projection_remains_valid(self):
        # StructuralProjection itself was not mutated
        assert len(PROJECTION.grid81) == 81
        assert len(PROJECTION.semantic_rows) == 9
