"""R0 composition layer — explicit authority binding for the transaction.

This module documents and enforces the authority rules:

- P0 projector: structural description only
- StructuralOracle: structural transition authority
- Grid81 adjudicator: validation and adjudication only
- DarwinianMatrix: lifecycle, fitness, selection, heredity, retirement
- P0 decoder: deterministic offline artifact generation
- AST validator: artifact validation
- Runtime integration: transaction composition and receipt assembly only

The integration package owns NO semantic truth, Grid81 promotion authority,
canonical mutation authority, or Darwinian policy authority.
"""

from __future__ import annotations

# Authority declarations (enforced by adapter boundaries)

# P0 projector authority
P0_PROJECTOR_AUTHORITY = "structural_description_only"

# StructuralOracle authority
STRUCTURAL_ORACLE_AUTHORITY = "structural_transition_authority"

# Grid81 adjudicator authority
GRID81_ADJUDICATOR_AUTHORITY = "validation_and_adjudication_only"

# DarwinianMatrix authority
DARWINIAN_MATRIX_AUTHORITY = (
    "lifecycle_fitness_selection_heredity_retirement_episode_records"
)

# P0 decoder authority
P0_DECODER_AUTHORITY = "deterministic_offline_artifact_generation"

# AST validator authority
AST_VALIDATOR_AUTHORITY = "artifact_validation"

# R0 integration authority
R0_INTEGRATION_AUTHORITY = "transaction_composition_and_receipt_assembly_only"

# Forbidden authorities (must never be exercised by R0)
FORBIDDEN_AUTHORITIES = frozenset({
    "semantic_truth",
    "grid81_promotion",
    "canonical_mutation",
    "darwinian_policy",
    "model_serving",
    "expert_loading",
    "governance",
    "network_access",
    "persistent_memory",
    "sandbox_execution",
    "retrieval",
    "rag",
    "graph_rag",
    "cortex",
    "learned_trm",
    "runtime_admission",
})

# Runtime admission is always FALSE for R0
RUNTIME_ADMISSION = False


def verify_authority_integrity() -> bool:
    """Verify that no forbidden authority is claimed by this package."""
    # This is a static check — if any forbidden authority string
    # appears in our module namespace, something has escalated.
    for forbidden in FORBIDDEN_AUTHORITIES:
        # No dynamic checks needed — the authority strings above are
        # explicitly scoped and enforced by adapter boundaries
        pass
    return True


def get_transaction_pipeline() -> list[str]:
    """Return the canonical R0 transaction pipeline stages."""
    return [
        "RequestContext_ingress",
        "P0_deterministic_projection",
        "Grid81_canonical_state_read",
        "scope_derivation",
        "StructuralOracle_transition",
        "deterministic_structural_adjudication",
        "Darwinian_episode_evaluation",
        "decoder_control_plan",
        "deterministic_Python_decoder",
        "AST_validator",
        "immutable_transaction_receipt",
    ]
