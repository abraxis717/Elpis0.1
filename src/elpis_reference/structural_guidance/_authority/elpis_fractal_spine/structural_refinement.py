"""Canonical structural refinement input contract.

This module defines the lower-level causal input contract used by both
training pipelines and P0 runtime integration.  It is the semantic
authority for structural refinement inputs within elpis_fractal_spine.

The contract is intentionally narrow: it binds a structural grid, an
explicit writable mask, and cryptographic digests that prevent silent
scope inflation.  No field is inferred from absent input.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "structural.refinement.input.v1"
SEMANTIC_SPACE = "grid81.structural.v1"
MASK_SEMANTICS = "writable_mask81.v1"

GRID_SIZE = 81

# Structural opcode domain: cells hold values 0..9
STRUCTURAL_OPCODE_DOMAIN = frozenset(range(10))

# Binary mask domain
MASK_DOMAIN = frozenset((0, 1))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canonical_bytes(obj: Any) -> bytes:
    """Minimal canonical JSON bytes: sorted keys, compact separators."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    """Lowercase SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class StructuralRefinementError(ValueError):
    """Raised when StructuralRefinementInputV1 validation fails."""

    pass


def _validate_grid(grid81: tuple[int, ...]) -> None:
    if len(grid81) != GRID_SIZE:
        raise StructuralRefinementError(
            f"grid81 must have length {GRID_SIZE}, got {len(grid81)}"
        )
    for i, v in enumerate(grid81):
        if v not in STRUCTURAL_OPCODE_DOMAIN:
            raise StructuralRefinementError(
                f"grid81[{i}] = {v} not in structural opcode domain 0..9"
            )


def _validate_mask(writable_mask81: tuple[int, ...]) -> None:
    if len(writable_mask81) != GRID_SIZE:
        raise StructuralRefinementError(
            f"writable_mask81 must have length {GRID_SIZE}, got {len(writable_mask81)}"
        )
    for i, v in enumerate(writable_mask81):
        if v not in MASK_DOMAIN:
            raise StructuralRefinementError(
                f"writable_mask81[{i}] = {v} not in binary domain {{0, 1}}"
            )


def _compute_grid_digest(grid81: tuple[int, ...]) -> str:
    payload = {"grid81": list(grid81)}
    return _sha256_hex(_canonical_bytes(payload))


def _compute_mask_digest(writable_mask81: tuple[int, ...]) -> str:
    payload = {"writable_mask81": list(writable_mask81)}
    return _sha256_hex(_canonical_bytes(payload))


def _compute_combined_digest(
    schema_version: str,
    semantic_space: str,
    mask_semantics: str,
    grid_digest: str,
    mask_digest: str,
) -> str:
    payload = {
        "schema_version": schema_version,
        "semantic_space": semantic_space,
        "mask_semantics": mask_semantics,
        "grid_digest": grid_digest,
        "mask_digest": mask_digest,
    }
    return _sha256_hex(_canonical_bytes(payload))


# ---------------------------------------------------------------------------
# Canonical contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class StructuralRefinementInputV1:
    """Canonical structural refinement input.

    Lower-level causal input contract owned by elpis_fractal_spine.
    Imported by elpis_p0 for P0 runtime envelope binding.

    All fields must be explicitly supplied. No inference from absent
    input is performed.  An explicitly supplied all-ones mask is valid;
    an absent or implicit mask is invalid.
    """

    schema_version: str = SCHEMA_VERSION
    semantic_space: str = SEMANTIC_SPACE
    mask_semantics: str = MASK_SEMANTICS
    grid81: tuple[int, ...] = ()
    writable_mask81: tuple[int, ...] = ()
    grid_digest: str = ""
    mask_digest: str = ""
    combined_digest: str = ""

    def __post_init__(self) -> None:
        # Validate grid
        _validate_grid(self.grid81)

        # Validate mask — all-zero is valid, all-one is valid
        _validate_mask(self.writable_mask81)

        # Compute digests
        grid_digest = _compute_grid_digest(self.grid81)
        mask_digest = _compute_mask_digest(self.writable_mask81)
        combined = _compute_combined_digest(
            self.schema_version,
            self.semantic_space,
            self.mask_semantics,
            grid_digest,
            mask_digest,
        )

        # Freeze computed values
        if self.grid_digest and self.grid_digest != grid_digest:
            raise StructuralRefinementError(
                f"grid_digest mismatch: supplied {self.grid_digest!r} != computed {grid_digest!r}"
            )
        if self.mask_digest and self.mask_digest != mask_digest:
            raise StructuralRefinementError(
                f"mask_digest mismatch: supplied {self.mask_digest!r} != computed {mask_digest!r}"
            )
        if self.combined_digest and self.combined_digest != combined:
            raise StructuralRefinementError(
                f"combined_digest mismatch: supplied {self.combined_digest!r} != computed {combined!r}"
            )

        # Use object.__setattr__ to set computed digests on frozen instance
        object.__setattr__(self, "grid_digest", grid_digest)
        object.__setattr__(self, "mask_digest", mask_digest)
        object.__setattr__(self, "combined_digest", combined)

    def to_dict(self) -> dict[str, Any]:
        """Canonical dictionary representation."""
        return {
            "schema_version": self.schema_version,
            "semantic_space": self.semantic_space,
            "mask_semantics": self.mask_semantics,
            "grid81": list(self.grid81),
            "writable_mask81": list(self.writable_mask81),
            "grid_digest": self.grid_digest,
            "mask_digest": self.mask_digest,
            "combined_digest": self.combined_digest,
        }
