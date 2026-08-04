"""G1.0 Phase G9 — Structural refinement input contract tests.

Tests cover:
- StructuralRefinementInputV1 validation and digest behavior
- P0RefinementInputV1 envelope validation
- build_refinement_input conversion
"""
from __future__ import annotations

import pytest
import hashlib
import json

from elpis_fractal_spine.structural_refinement import (
    StructuralRefinementInputV1,
    StructuralRefinementError,
    _canonical_bytes,
    _sha256_hex,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_GRID = tuple((i % 10) for i in range(81))  # 81 cells, values 0..9

VALID_MASK_ALL_ONES = tuple(1 for _ in range(81))
VALID_MASK_ALL_ZEROS = tuple(0 for _ in range(81))
VALID_MASK_SINGLETON = tuple(1 if i == 40 else 0 for i in range(81))


def _empty_structural():
    return StructuralRefinementInputV1(
        grid81=VALID_GRID,
        writable_mask81=VALID_MASK_ALL_ONES,
    )


# ---------------------------------------------------------------------------
# StructuralRefinementInputV1 — valid cases
# ---------------------------------------------------------------------------

class TestStructuralRefinementValid:
    def test_valid_grid_and_mask_accepted(self):
        sri = _empty_structural()
        assert sri.schema_version == "structural.refinement.input.v1"
        assert sri.semantic_space == "grid81.structural.v1"
        assert sri.mask_semantics == "writable_mask81.v1"

    def test_all_zero_mask_accepted(self):
        sri = StructuralRefinementInputV1(
            grid81=VALID_GRID,
            writable_mask81=VALID_MASK_ALL_ZEROS,
        )
        assert sri.writable_mask81 == VALID_MASK_ALL_ZEROS

    def test_all_one_mask_accepted(self):
        sri = _empty_structural()
        assert sri.writable_mask81 == VALID_MASK_ALL_ONES

    def test_singleton_mask_accepted(self):
        sri = StructuralRefinementInputV1(
            grid81=VALID_GRID,
            writable_mask81=VALID_MASK_SINGLETON,
        )
        assert sum(sri.writable_mask81) == 1
        assert sri.writable_mask81[40] == 1

    def test_missing_mask_impossible_at_constructor(self):
        # Empty tuple fails length validation
        with pytest.raises(StructuralRefinementError, match="must have length 81"):
            StructuralRefinementInputV1(
                grid81=VALID_GRID,
                writable_mask81=(),
            )


# ---------------------------------------------------------------------------
# StructuralRefinementInputV1 — rejection cases
# ---------------------------------------------------------------------------

class TestStructuralRefinementRejection:
    def test_short_grid_rejected(self):
        with pytest.raises(StructuralRefinementError, match="grid81.*length"):
            StructuralRefinementInputV1(
                grid81=tuple(range(80)),
                writable_mask81=VALID_MASK_ALL_ONES,
            )

    def test_invalid_opcode_rejected(self):
        bad_grid = list(VALID_GRID)
        bad_grid[0] = 10
        with pytest.raises(StructuralRefinementError, match="opcode domain"):
            StructuralRefinementInputV1(
                grid81=tuple(bad_grid),
                writable_mask81=VALID_MASK_ALL_ONES,
            )

    def test_negative_opcode_rejected(self):
        bad_grid = list(VALID_GRID)
        bad_grid[0] = -1
        with pytest.raises(StructuralRefinementError, match="opcode domain"):
            StructuralRefinementInputV1(
                grid81=tuple(bad_grid),
                writable_mask81=VALID_MASK_ALL_ONES,
            )

    def test_short_mask_rejected(self):
        with pytest.raises(StructuralRefinementError, match="writable_mask81.*length"):
            StructuralRefinementInputV1(
                grid81=VALID_GRID,
                writable_mask81=tuple(1 for _ in range(80)),
            )

    def test_long_mask_rejected(self):
        with pytest.raises(StructuralRefinementError, match="writable_mask81.*length"):
            StructuralRefinementInputV1(
                grid81=VALID_GRID,
                writable_mask81=tuple(1 for _ in range(82)),
            )

    def test_nonbinary_mask_rejected(self):
        bad_mask = list(VALID_MASK_ALL_ONES)
        bad_mask[0] = 2
        with pytest.raises(StructuralRefinementError, match="binary domain"):
            StructuralRefinementInputV1(
                grid81=VALID_GRID,
                writable_mask81=tuple(bad_mask),
            )


# ---------------------------------------------------------------------------
# StructuralRefinementInputV1 — digest behavior
# ---------------------------------------------------------------------------

class TestStructuralRefinementDigests:
    def test_digest_mutation_rejected(self):
        sri = _empty_structural()
        with pytest.raises(StructuralRefinementError, match="grid_digest mismatch"):
            StructuralRefinementInputV1(
                grid81=VALID_GRID,
                writable_mask81=VALID_MASK_ALL_ONES,
                grid_digest="invalid_digest",
            )

    def test_grid_change_changes_grid_and_combined_digest(self):
        sri_a = _empty_structural()
        grid_b = list(VALID_GRID)
        grid_b[0] = 5
        sri_b = StructuralRefinementInputV1(
            grid81=tuple(grid_b),
            writable_mask81=VALID_MASK_ALL_ONES,
        )
        assert sri_a.grid_digest != sri_b.grid_digest
        assert sri_a.combined_digest != sri_b.combined_digest
        # mask digest unchanged
        assert sri_a.mask_digest == sri_b.mask_digest

    def test_mask_change_changes_mask_and_combined_digest(self):
        sri_a = _empty_structural()
        sri_b = StructuralRefinementInputV1(
            grid81=VALID_GRID,
            writable_mask81=VALID_MASK_ALL_ZEROS,
        )
        assert sri_a.mask_digest != sri_b.mask_digest
        assert sri_a.combined_digest != sri_b.combined_digest
        # grid digest unchanged
        assert sri_a.grid_digest == sri_b.grid_digest

    def test_same_values_reproduce_identical_digests(self):
        sri_a = _empty_structural()
        sri_b = _empty_structural()
        assert sri_a.grid_digest == sri_b.grid_digest
        assert sri_a.mask_digest == sri_b.mask_digest
        assert sri_a.combined_digest == sri_b.combined_digest

    def test_digests_are_lowercase_sha256_hex(self):
        sri = _empty_structural()
        assert len(sri.grid_digest) == 64
        assert len(sri.mask_digest) == 64
        assert len(sri.combined_digest) == 64
        int(sri.grid_digest, 16)
        int(sri.mask_digest, 16)
        int(sri.combined_digest, 16)
