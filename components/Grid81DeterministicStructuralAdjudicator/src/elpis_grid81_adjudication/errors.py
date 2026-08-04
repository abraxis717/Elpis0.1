"""Error classes and failure codes for G5.1B adjudication."""


class AdjudicationError(Exception):
    """Base adjudication error."""
    def __init__(self, message, failure_code=None):
        super().__init__(message)
        self.failure_code = failure_code


# --- Upstream seal failures ---

class UpstreamG50ASealMismatch(AdjudicationError):
    def __init__(self, message="G5.0A manifest digest mismatch"):
        super().__init__(message, "UPSTREAM_G50A_SEAL_DIGEST_MISMATCH")


class UpstreamG50BSealMismatch(AdjudicationError):
    def __init__(self, message="G5.0B manifest digest mismatch"):
        super().__init__(message, "UPSTREAM_G50B_SEAL_DIGEST_MISMATCH")


class UpstreamG51ASealMismatch(AdjudicationError):
    def __init__(self, message="G5.1A manifest digest mismatch"):
        super().__init__(message, "UPSTREAM_G51A_SEAL_DIGEST_MISMATCH")


class CrossSealMismatch(AdjudicationError):
    def __init__(self, message="Cross-seal consumption mismatch"):
        super().__init__(message, "CROSS_SEAL_CONSUMPTION_MISMATCH")


class CanonicalInventoryDigestMismatch(AdjudicationError):
    def __init__(self, message="G5.0B canonical inventory digest mismatch"):
        super().__init__(message, "G50B_CANONICAL_INVENTORY_DIGEST_MISMATCH")


# --- Source join failures ---

class SourceJoinMissingRow(AdjudicationError):
    def __init__(self, message="Source row missing from join"):
        super().__init__(message, "SOURCE_JOIN_MISSING_ROW")


class ProposalSetIncomplete(AdjudicationError):
    def __init__(self, message="Proposal set incomplete"):
        super().__init__(message, "PROPOSAL_SET_INCOMPLETE")


class ProposalSetDuplicate(AdjudicationError):
    def __init__(self, message="Duplicate proposal in envelope"):
        super().__init__(message, "PROPOSAL_SET_DUPLICATE")


class OrderingBindingMismatch(AdjudicationError):
    def __init__(self, message="Ordering digest binding mismatch"):
        super().__init__(message, "ORDERING_BINDING_MISMATCH")


class ConflictSetIncomplete(AdjudicationError):
    def __init__(self, message="Conflict set incomplete"):
        super().__init__(message, "CONFLICT_SET_INCOMPLETE")


# --- Policy failures ---

class ReviewSetNegativeEvidenceViolation(AdjudicationError):
    def __init__(self, message="Negative evidence proposal in review set"):
        super().__init__(message, "REVIEW_SET_NEGATIVE_EVIDENCE_VIOLATION")


class DeterministicPolicyDispositionMismatch(AdjudicationError):
    def __init__(self, message="Disposition does not match deterministic policy"):
        super().__init__(message, "DETERMINISTIC_POLICY_DISPOSITION_MISMATCH")


class QuiescenceImplicitVeto(AdjudicationError):
    def __init__(self, message="Quiescence used as implicit veto"):
        super().__init__(message, "QUIESCENCE_IMPLICIT_VETO")


class RationaleReviewSetViolation(AdjudicationError):
    def __init__(self, message="Rationale diagnostic proposal referred for review"):
        super().__init__(message, "RATIONALE_REVIEW_SET_VIOLATION")


class NegativeEvidenceDispositionMissing(AdjudicationError):
    def __init__(self, message="Negative evidence disposition omitted"):
        super().__init__(message, "NEGATIVE_EVIDENCE_DISPOSITION_MISSING")


class DispositionLedgerDuplicate(AdjudicationError):
    def __init__(self, message="Duplicate disposition in ledger"):
        super().__init__(message, "DISPOSITION_LEDGER_DUPLICATE")


class DispositionLedgerIncomplete(AdjudicationError):
    def __init__(self, message="Disposition ledger incomplete"):
        super().__init__(message, "DISPOSITION_LEDGER_INCOMPLETE")


class ReviewSetDispositionMismatch(AdjudicationError):
    def __init__(self, message="Review set disagrees with dispositions"):
        super().__init__(message, "REVIEW_SET_DISPOSITION_MISMATCH")


class ReviewSetSizeMismatch(AdjudicationError):
    def __init__(self, message="Review set size mismatch"):
        super().__init__(message, "REVIEW_SET_SIZE_MISMATCH")


# --- Adjudication failures ---

class AdjudicationOutcomeMismatch(AdjudicationError):
    def __init__(self, message="Adjudication outcome mismatch"):
        super().__init__(message, "ADJUDICATION_OUTCOME_MISMATCH")


class ContradictionReviewRequestViolation(AdjudicationError):
    def __init__(self, message="Logical contradiction formed review request"):
        super().__init__(message, "CONTRADICTION_REVIEW_REQUEST_VIOLATION")


class InsufficientEvidenceReviewRequestViolation(AdjudicationError):
    def __init__(self, message="Insufficient evidence formed review request"):
        super().__init__(message, "INSUFFICIENT_EVIDENCE_REVIEW_REQUEST_VIOLATION")


class AbstentionStateMissing(AdjudicationError):
    def __init__(self, message="Abstention record omitted"):
        super().__init__(message, "ABSTENTION_STATE_MISSING")


class AbstentionKindMismatch(AdjudicationError):
    def __init__(self, message="Abstention kind mismatch"):
        super().__init__(message, "ABSTENTION_KIND_MISMATCH")


class RequestStateMismatch(AdjudicationError):
    def __init__(self, message="Request state mismatch"):
        super().__init__(message, "REQUEST_STATE_MISMATCH")


class RequestReferredSetMismatch(AdjudicationError):
    def __init__(self, message="Referred proposal omitted from request"):
        super().__init__(message, "REQUEST_REFERRED_SET_MISMATCH")


# --- Boundary failures ---

class CapabilityTokenForbidden(AdjudicationError):
    def __init__(self, message="Capability token found in request"):
        super().__init__(message, "CAPABILITY_TOKEN_FORBIDDEN")


class ActivationAuthorityViolation(AdjudicationError):
    def __init__(self, message="Activation/authority field present"):
        super().__init__(message, "ACTIVATION_AUTHORITY_VIOLATION")


# --- Identity failures ---

class ProvenanceContaminatedIdentity(AdjudicationError):
    def __init__(self, message="Provenance data in semantic digest"):
        super().__init__(message, "PROVENANCE_CONTAMINATED_ADJUDICATION_IDENTITY")


class PresentationOrderContaminatedIdentity(AdjudicationError):
    def __init__(self, message="Presentation order affects semantic digest"):
        super().__init__(message, "PRESENTATION_ORDER_CONTAMINATED_IDENTITY")


class DeterminismMismatch(AdjudicationError):
    def __init__(self, message="Determinism check failed across seeds"):
        super().__init__(message, "DETERMINISM_MISMATCH")


class SummaryEvidenceContradiction(AdjudicationError):
    def __init__(self, message="Summary contradicts raw evidence"):
        super().__init__(message, "SUMMARY_EVIDENCE_CONTRADICTION")
