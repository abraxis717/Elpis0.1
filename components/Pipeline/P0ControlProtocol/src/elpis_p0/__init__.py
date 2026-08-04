"""Elpis P0 structural and TRM control protocol."""

from .contracts import (
    BasisToken,
    DecoderControlPlan,
    P0Result,
    RequestContext,
    StructuralProjection,
    TRMRefinementProposal,
    ValidatorEvidence,
    P0RefinementInputV1,
    P0RefinementError,
    build_refinement_input,
)
from .factory import (
    build_default_controller,
)
from .controller import (
    P0Controller,
)

# P0.2 expansion protocol exports
from .expansion_contracts import (
    ExpansionProposalEvidence,
    ExpansionAdmissionRecord,
    ChildSeedRecord,
    FoldRecord,
    NormalizedAuthorityEvent,
    P02Result,
)
from .expansion import (
    admit_expansion,
    make_semantic_space_digest,
    compute_ranking,
    validate_expansion_cells,
)
from .seeds import (
    create_child_seed_record,
    derive_child_seed,
    fold_child_result,
    apply_fold,
)
from .authority_bridge import L0ExpansionAuthorityBridge
from .p02_runner import DeterministicProposalTRM, run_p02_expansion

# G2.0 refinement exports
from .refinement_scope import (
    RefinementScopeDecisionV1,
    RefinementScopeProvider,
    RefinementScopeError,
)
from .refinement_scope_builder import (
    build_refinement_input_from_scope,
)
from .refinement_proposer import (
    RefinementProposerPort,
    DeterministicShadowRefinementProposer,
)
from .refinement_validation import (
    RefinementValidationRecordV1,
    build_validation_record,
    validate_refinement_proposal,
)
from .refinement_receipt import (
    RefinementInvocationReceiptV1,
    build_receipt,
)
from .refinement_result import (
    RefinementControllerResultV1,
)

# G3.0 initial-void scope provider exports
from .initial_void_scope_provider import (
    INITIAL_VOID_SCOPE_POLICY_ID,
    INITIAL_VOID_SCOPE_POLICY_VERSION,
    derive_initial_void_mask81,
    InitialVoidScopeProvider,
    ScopeDerivationRecordV1,
)
from .scoped_refinement_result import (
    ScopedRefinementControllerResultV1,
)


__all__ = [
    # P0.1 exports
    "BasisToken",
    "DecoderControlPlan",
    "P0Result",
    "RequestContext",
    "StructuralProjection",
    "TRMRefinementProposal",
    "ValidatorEvidence",
    "build_default_controller",
    "P0Controller",
    # P0.2 exports
    "ExpansionProposalEvidence",
    "ExpansionAdmissionRecord",
    "ChildSeedRecord",
    "FoldRecord",
    "NormalizedAuthorityEvent",
    "P02Result",
    "admit_expansion",
    "make_semantic_space_digest",
    "compute_ranking",
    "validate_expansion_cells",
    "create_child_seed_record",
    "derive_child_seed",
    "fold_child_result",
    "apply_fold",
    "L0ExpansionAuthorityBridge",
    "DeterministicProposalTRM",
    "run_p02_expansion",
    # P0 refinement envelope (G1.1)
    "P0RefinementInputV1",
    "P0RefinementError",
    "build_refinement_input",
    # G2.0 refinement integration
    "RefinementScopeDecisionV1",
    "RefinementScopeProvider",
    "RefinementScopeError",
    "build_refinement_input_from_scope",
    "RefinementProposerPort",
    "DeterministicShadowRefinementProposer",
    "RefinementValidationRecordV1",
    "build_validation_record",
    "validate_refinement_proposal",
    "RefinementInvocationReceiptV1",
    "build_receipt",
    "RefinementControllerResultV1",
    # G3.0 initial-void scope provider
    "INITIAL_VOID_SCOPE_POLICY_ID",
    "INITIAL_VOID_SCOPE_POLICY_VERSION",
    "derive_initial_void_mask81",
    "InitialVoidScopeProvider",
    "ScopeDerivationRecordV1",
    "ScopedRefinementControllerResultV1",
]


__version__ = "0.1.0"
