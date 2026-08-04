"""Frozen structural-refinement contracts and qualification adapters."""

from .contract import (
    REFINEMENT_ACCEPTED,
    REFINEMENT_REJECTED,
    FrozenStructuralAdapter,
    StructuralAdapterManifest,
    StructuralRefinementRequest,
    StructuralRefinementResult,
    build_refinement_result,
    execute_refinement,
)
from .reference_solver import (
    DeterministicSudokuReferenceAdapter,
)

__all__ = (
    "REFINEMENT_ACCEPTED",
    "REFINEMENT_REJECTED",
    "DeterministicSudokuReferenceAdapter",
    "FrozenStructuralAdapter",
    "StructuralAdapterManifest",
    "StructuralRefinementRequest",
    "StructuralRefinementResult",
    "build_refinement_result",
    "execute_refinement",
)
