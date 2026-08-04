"""G5.3B Deterministic Capability Consumption Compiler.

Implements capability consumption and inert structural-influence artifact
compilation. No activation, no application, no model selection.
"""
from .canonical import canonical_json, canonical_digest
from .errors import ConsumptionError, ValidationFailed, SchemaMismatch, ForbiddenFieldError
from .policy import create_consumption_policy, create_compiler_contract
from .input import create_transaction_input
from .validation import validate_transaction, validate_artifact_invariants, validate_receipt, FORBIDDEN_FIELDS
from .transaction import consume_capability, ConsumptionTransactionResult
from .artifact import create_structural_influence_artifact
from .receipt import create_consumption_receipt, create_rejection_record
from .lifecycle import create_lifecycle_transition
from .replay import replay_transaction
from .boundary import verify_authority_boundary

__all__ = [
    "canonical_json", "canonical_digest",
    "ConsumptionError", "ValidationFailed", "SchemaMismatch", "ForbiddenFieldError",
    "create_consumption_policy", "create_compiler_contract",
    "create_transaction_input",
    "validate_transaction", "validate_artifact_invariants", "validate_receipt", "FORBIDDEN_FIELDS",
    "consume_capability", "ConsumptionTransactionResult",
    "create_structural_influence_artifact",
    "create_consumption_receipt", "create_rejection_record",
    "create_lifecycle_transition",
    "replay_transaction",
    "verify_authority_boundary",
]
