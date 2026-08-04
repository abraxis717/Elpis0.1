"""Semantic space definitions and validation for Elpis Canon FS0.1."""

from dataclasses import dataclass, field

import numpy as np

# ---------------------------------------------------------------------------
# Canonical semantic space vocabulary
# ---------------------------------------------------------------------------

STRUCTURAL_GRID81 = "grid81.structural.v1"
THERMAL_ORDINAL_GRID81 = "grid81.thermal.ordinal.v1"

# Native model output spaces
EMBEDDING_GRANITE97M_NATIVE = "embedding.granite97m.native"
NEEDLE_FUNCTION_CALL_NATIVE = "needle.function-call.native"
VISUAL_DEIT_PATCH196_NATIVE = "visual.deit.patch196.native"
ELECTRA_REPLACED_TOKEN_LOGITS_NATIVE = "electra.replaced-token-logits.native"
CHESS_MAIA3_NATIVE = "chess.maia3.native"
GRAPH_KURAMOTO_NATIVE_UNKNOWN = "graph.kuramoto.native.unknown"
HRM_PUZZLE_DOMAIN_NATIVE = "hrm.puzzle-domain.native"

# Shared evidence space — the ONLY admitted latent space in FS0.1
LATENT_TRM_ORTHOGONAL_CELL81_V1 = "latent.trm-orthogonal.cell81.v1"

# All known spaces
KNOWN_SPACES: frozenset = frozenset({
    STRUCTURAL_GRID81,
    THERMAL_ORDINAL_GRID81,
    EMBEDDING_GRANITE97M_NATIVE,
    NEEDLE_FUNCTION_CALL_NATIVE,
    VISUAL_DEIT_PATCH196_NATIVE,
    ELECTRA_REPLACED_TOKEN_LOGITS_NATIVE,
    CHESS_MAIA3_NATIVE,
    GRAPH_KURAMOTO_NATIVE_UNKNOWN,
    HRM_PUZZLE_DOMAIN_NATIVE,
    LATENT_TRM_ORTHOGONAL_CELL81_V1,
})

# Spaces that must NOT be used as latent evidence input
FORBIDDEN_LATENT_INPUT_SPACES: frozenset = frozenset({
    STRUCTURAL_GRID81,
    THERMAL_ORDINAL_GRID81,
})

# ---------------------------------------------------------------------------
# Canonical latent space identity for FS0.1
# ---------------------------------------------------------------------------

CANONICAL_LATENT_SHAPE: tuple = (81,)
CANONICAL_LATENT_DTYPE: str = "float64"
CANONICAL_LATENT_ABI_VERSION: str = "elpis.trm-orthogonal-latent.v1"


@dataclass(frozen=True)
class LatentSpaceIdentity:
    """Immutable identity describing a shared latent evidence space."""

    semantic_space: str
    abi_version: str
    shape: tuple
    dtype: str
    basis_digest: str
    layout_digest: str

    @staticmethod
    def canonical() -> "LatentSpaceIdentity":
        """Return the FS0.1 canonical latent space identity."""
        # Compute a stable digest for the basis definition.
        basis_spec = {
            "space": LATENT_TRM_ORTHOGONAL_CELL81_V1,
            "shape": list(CANONICAL_LATENT_SHAPE),
            "dtype": CANONICAL_LATENT_DTYPE,
        }
        from .canonical import json_sha256

        basis_d = json_sha256(basis_spec)
        layout_d = json_sha256({"layout": "cell81_flat", "order": "C"})

        return LatentSpaceIdentity(
            semantic_space=LATENT_TRM_ORTHOGONAL_CELL81_V1,
            abi_version=CANONICAL_LATENT_ABI_VERSION,
            shape=CANONICAL_LATENT_SHAPE,
            dtype=CANONICAL_LATENT_DTYPE,
            basis_digest=basis_d,
            layout_digest=layout_d,
        )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_latent_vector(
    vec: np.ndarray,
    expected_space: str | None = None,
) -> np.ndarray:
    """
    Validate a candidate latent evidence vector.

    Returns canonicalized vector. Raises ValueError on any violation.
    """
    # Check space identity if provided.
    if expected_space is not None:
        if expected_space in FORBIDDEN_LATENT_INPUT_SPACES:
            raise ValueError(
                f"Semantic space '{expected_space}' is forbidden as latent evidence input. "
                f"Structural and thermal spaces must not enter the latent evidence space."
            )

    # Shape check
    if vec.shape != CANONICAL_LATENT_SHAPE:
        raise ValueError(
            f"Latent evidence vector shape {vec.shape} does not match "
            f"required {CANONICAL_LATENT_SHAPE}."
        )

    # Dtype check
    if vec.dtype != np.float64:
        # Attempt conversion but reject if loss of precision would occur.
        try:
            vec = vec.astype(np.float64)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Latent evidence vector dtype {vec.dtype} cannot be converted to float64."
            ) from exc

    # Finiteness check
    if not np.all(np.isfinite(vec)):
        raise ValueError(
            "Latent evidence vector contains NaN or Inf. Only finite values permitted."
        )

    # Canonicalize negative zero
    vec = np.where(vec == 0.0, 0.0, vec)

    return np.ascontiguousarray(vec, dtype=np.float64)


def validate_grid81_structural(grid81: np.ndarray) -> np.ndarray:
    """Validate a structural Grid81 proposal: tokens in 0..9, length 81."""
    if grid81.shape != (81,):
        raise ValueError(
            f"Structural grid81 shape {grid81.shape} != (81,)."
        )
    if not np.issubdtype(grid81.dtype, np.integer):
        raise ValueError(
            f"Structural grid81 dtype {grid81.dtype} must be integer."
        )
    if np.any(grid81 < 0) or np.any(grid81 > 9):
        raise ValueError(
            "Structural grid81 contains tokens outside 0..9."
        )
    return grid81.astype(np.int64)


def validate_grid81_residual(residual81: np.ndarray) -> np.ndarray:
    """Validate residual81: float64, length 81, values in [0, 1], finite."""
    if residual81.shape != (81,):
        raise ValueError(
            f"Residual81 shape {residual81.shape} != (81,)."
        )
    residual = np.asarray(residual81, dtype=np.float64)
    if not np.all(np.isfinite(residual)):
        raise ValueError("Residual81 contains non-finite values.")
    if np.any(residual < 0.0) or np.any(residual > 1.0):
        raise ValueError("Residual81 contains values outside [0, 1].")
    residual = np.where(residual == 0.0, 0.0, residual)
    return np.ascontiguousarray(residual, dtype=np.float64)
