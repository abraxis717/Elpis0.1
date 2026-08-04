"""Grid81 Deterministic Capability Authority Evaluator (G5.2B).

Deterministic authority evaluation governed by the sealed G5.2A
Structural Influence Capability Authority Contract.

Canonical pipeline:
    G5.1B CapabilityReviewRequestV1
      -> CapabilityAuthorityEvaluationInputV1
      -> CapabilityAuthorityDecisionV1
      -> StructuralInfluenceCapabilityV1
      -> GRANTED_UNCONSUMED lifecycle state
"""

__version__ = "0.1.0"
__disposition__ = "G52B_DETERMINISTIC_CAPABILITY_AUTHORITY_EVALUATOR_SEALED"
