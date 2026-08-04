"""G5.3B Validation predicates for capability consumption transactions.

Implements all acceptance/rejection predicates with exact rejection precedence:
1. schema and canonical identity
2. capability identity
3. lifecycle and consumption count
4. revocation
5. logical validity
6. nonce
7. consumer and consumer contract
8. operation
9. scope
10. artifact contract and atomicity
11. acceptance
"""
from .canonical import check_hex64, canonical_digest
from .errors import ValidationFailed, SchemaMismatch, ForbiddenFieldError

FORBIDDEN_FIELDS = frozenset([
    "apply", "applied", "activation", "execute", "dispatch",
    "winner", "selected", "rank", "priority", "score", "weight",
    "confidence", "probability", "model_id", "model_name",
    "model_path", "adapter_id", "adapter_name", "adapter_path",
    "runtime_target", "device", "gpu", "port", "endpoint",
    "command", "process_id", "server", "ecs_entity", "token_commit",
])

VALID_LIFECYCLE_STATES = frozenset([
    "GRANTED_UNCONSUMED", "CONSUMED", "REVOKED", "EXPIRED",
])

ACCEPTED_OUTCOME = "CONSUMPTION_ACCEPTED"
REJECTION_REPLAY = "CONSUMPTION_REJECTED_REPLAY"
REJECTION_REVOKED = "CONSUMPTION_REJECTED_REVOKED"
REJECTION_EXPIRED = "CONSUMPTION_REJECTED_EXPIRED"
REJECTION_CONSUMER_MISMATCH = "CONSUMPTION_REJECTED_CONSUMER_MISMATCH"
REJECTION_SCOPE_MISMATCH = "CONSUMPTION_REJECTED_SCOPE_MISMATCH"
REJECTION_INVALID_CAPABILITY = "CONSUMPTION_REJECTED_INVALID_CAPABILITY"


def validate_schema_and_identity(request: dict) -> tuple[str, list[str]]:
    """Check 1: schema version and canonical identity."""
    reasons = []
    if request.get("schema_version") != "capability-consumption-transaction-input.v1":
        reasons.append("invalid_schema_version")
    # Check all required hex64 digests
    for field in ["capability_digest", "capability_semantic_digest", "nonce_digest",
                   "consumer_contract_digest", "consumption_request_digest",
                   "consumption_policy_digest", "transaction_input_digest"]:
        if not check_hex64(request.get(field, "")):
            reasons.append(f"invalid_digest_{field}")
    if not request.get("requested_proposal_digests") or not isinstance(request.get("requested_proposal_digests"), list):
        reasons.append("missing_proposal_digests")
    else:
        for pd in request["requested_proposal_digests"]:
            if not check_hex64(pd):
                reasons.append("invalid_proposal_digest")
                break
    if not reasons:
        return ACCEPTED_OUTCOME, []
    return REJECTION_INVALID_CAPABILITY, reasons


def validate_capability_identity(capability: dict, request: dict) -> tuple[str, list[str]]:
    """Check 2: capability identity and class."""
    reasons = []
    if capability.get("capability_class") != "STRUCTURAL_INFLUENCE_CAPABILITY_V1":
        reasons.append("unsupported_capability_class")
    if capability.get("schema_version") != "structural-influence-capability.v1":
        reasons.append("invalid_capability_schema")
    if capability.get("capability_digest") != request.get("capability_digest"):
        reasons.append("capability_digest_mismatch")
    if capability.get("capability_semantic_digest") != request.get("capability_semantic_digest"):
        reasons.append("capability_semantic_digest_mismatch")
    if not reasons:
        return ACCEPTED_OUTCOME, []
    return REJECTION_INVALID_CAPABILITY, reasons


def validate_lifecycle(lifecycle: dict) -> tuple[str, list[str]]:
    """Check 3: lifecycle state and consumption count.

    Rejection precedence within lifecycle:
    - Invalid state (data integrity) -> REJECTION_INVALID_CAPABILITY
    - Already consumed (replay) -> REJECTION_REPLAY
    - Nonzero consumption count (replay) -> REJECTION_REPLAY
    """
    current_state = lifecycle.get("current_state", lifecycle.get("initial_lifecycle_state", "GRANTED_UNCONSUMED"))

    # Invalid state is a data integrity failure, not a replay
    if current_state not in VALID_LIFECYCLE_STATES:
        return REJECTION_INVALID_CAPABILITY, ["invalid_lifecycle_state"]

    # Replay conditions only apply to valid states
    if current_state == "CONSUMED":
        return REJECTION_REPLAY, ["already_consumed"]

    consumption_count = lifecycle.get("consumption_count", 0)
    if consumption_count > 0:
        return REJECTION_REPLAY, ["consumption_count_nonzero"]

    return ACCEPTED_OUTCOME, []


def validate_revocation(lifecycle: dict) -> tuple[str, list[str]]:
    """Check 4: revocation state."""
    revocation_state = lifecycle.get("revocation_state", "NOT_REVOKED")
    if revocation_state == "REVOKED":
        return REJECTION_REVOKED, ["capability_revoked"]
    return ACCEPTED_OUTCOME, []


def validate_logical_validity(request: dict) -> tuple[str, list[str]]:
    """Check 5: logical tick within validity."""
    reasons = []
    logical_tick = request.get("logical_tick", -1)
    if logical_tick < 0:
        reasons.append("invalid_logical_tick")
        return REJECTION_EXPIRED, reasons
    return ACCEPTED_OUTCOME, []


def validate_nonce(capability: dict, request: dict) -> tuple[str, list[str]]:
    """Check 6: nonce exact match."""
    if capability.get("nonce_digest") != request.get("nonce_digest"):
        return REJECTION_INVALID_CAPABILITY, ["nonce_mismatch"]
    return ACCEPTED_OUTCOME, []


def validate_consumer(request: dict, policy: dict) -> tuple[str, list[str]]:
    """Check 7: consumer class and consumer contract digest."""
    reasons = []
    consumer_class = request.get("consumer_class", "")
    supported_consumers = policy.get("supported_consumer_classes", [])
    if consumer_class not in supported_consumers:
        reasons.append("unsupported_consumer_class")
    if not check_hex64(request.get("consumer_contract_digest", "")):
        reasons.append("invalid_consumer_contract_digest")
    if reasons:
        return REJECTION_CONSUMER_MISMATCH, reasons
    return ACCEPTED_OUTCOME, []


def validate_operation(request: dict, policy: dict) -> tuple[str, list[str]]:
    """Check 8: operation class."""
    operation = request.get("requested_operation_class", "")
    supported_ops = policy.get("supported_operation_classes", [])
    if operation not in supported_ops:
        return REJECTION_INVALID_CAPABILITY, ["unsupported_operation_class"]
    return ACCEPTED_OUTCOME, []


def validate_scope(capability: dict, request: dict) -> tuple[str, list[str]]:
    """Check 9: requested scope exactly equals capability scope."""
    capability_proposals = sorted(capability.get("authorized_proposal_digests", []))
    requested_proposals = sorted(request.get("requested_proposal_digests", []))
    if capability_proposals != requested_proposals:
        return REJECTION_SCOPE_MISMATCH, ["scope_mismatch"]
    return ACCEPTED_OUTCOME, []


def validate_artifact_invariants(artifact: dict) -> tuple[bool, list[str]]:
    """Validate artifact law: inert, unapplied, no forbidden fields."""
    issues = []
    if artifact.get("artifact_class") != "BOUNDED_STRUCTURAL_INFLUENCE_ARTIFACT_V1":
        issues.append("wrong_artifact_class")
    if artifact.get("materialization_class") != "MATERIALIZE_AUTHORIZED_STRUCTURAL_INFLUENCE_SET_V1":
        issues.append("wrong_materialization_class")
    if artifact.get("target_domain_class") != "GRID81_STRUCTURAL_PROPOSAL_DOMAIN_V1":
        issues.append("wrong_target_domain_class")
    if artifact.get("application_state") != "UNAPPLIED":
        issues.append("artifact_not_unapplied")
    if artifact.get("consumer_class") != "STRUCTURAL_INFLUENCE_COMPILER_V1":
        issues.append("wrong_consumer_class")
    # Check for forbidden fields recursively
    forbidden = check_forbidden_fields(artifact)
    if forbidden:
        issues.extend(forbidden)
    return len(issues) == 0, issues


def check_forbidden_fields(obj, path="") -> list[str]:
    """Recursively check for forbidden field names."""
    found = []
    if isinstance(obj, dict):
        for key in obj:
            current_path = f"{path}.{key}" if path else key
            if key.lower() in {f.lower() for f in FORBIDDEN_FIELDS}:
                found.append(f"forbidden_field:{current_path}")
            found.extend(check_forbidden_fields(obj[key], current_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(check_forbidden_fields(item, f"{path}[{i}]"))
    return found


def validate_receipt(receipt: dict) -> tuple[bool, list[str]]:
    """Validate receipt structure and digest integrity."""
    issues = []
    if receipt.get("schema_version") != "capability-consumption-receipt.v1":
        issues.append("invalid_receipt_schema")
    if not check_hex64(receipt.get("receipt_digest", "")):
        issues.append("missing_receipt_digest")
    # Verify digest is actually correct (not just syntactically valid)
    digest_fields = {k: v for k, v in receipt.items() if k != "receipt_digest"}
    expected_digest = canonical_digest(digest_fields)
    if receipt.get("receipt_digest") != expected_digest:
        issues.append("receipt_digest_mismatch")
    if receipt.get("consumption_outcome") not in VALID_LIFECYCLE_STATES | {ACCEPTED_OUTCOME,
        REJECTION_REPLAY, REJECTION_REVOKED, REJECTION_EXPIRED,
        REJECTION_CONSUMER_MISMATCH, REJECTION_SCOPE_MISMATCH, REJECTION_INVALID_CAPABILITY}:
        issues.append("invalid_consumption_outcome")
    return len(issues) == 0, issues


def validate_transaction(capability: dict, lifecycle: dict, request: dict,
                          policy: dict, compiler_contract: dict) -> tuple[str, list[str]]:
    """Full transaction validation with rejection precedence."""
    # 1. Schema and identity
    outcome, reasons = validate_schema_and_identity(request)
    if outcome != ACCEPTED_OUTCOME:
        return outcome, reasons

    # 2. Capability identity
    outcome, reasons = validate_capability_identity(capability, request)
    if outcome != ACCEPTED_OUTCOME:
        return outcome, reasons

    # 3. Lifecycle and consumption count
    outcome, reasons = validate_lifecycle(lifecycle)
    if outcome != ACCEPTED_OUTCOME:
        return outcome, reasons

    # 4. Revocation
    outcome, reasons = validate_revocation(lifecycle)
    if outcome != ACCEPTED_OUTCOME:
        return outcome, reasons

    # 5. Logical validity
    outcome, reasons = validate_logical_validity(request)
    if outcome != ACCEPTED_OUTCOME:
        return outcome, reasons

    # 6. Nonce
    outcome, reasons = validate_nonce(capability, request)
    if outcome != ACCEPTED_OUTCOME:
        return outcome, reasons

    # 7. Consumer
    outcome, reasons = validate_consumer(request, policy)
    if outcome != ACCEPTED_OUTCOME:
        return outcome, reasons

    # 8. Operation
    outcome, reasons = validate_operation(request, policy)
    if outcome != ACCEPTED_OUTCOME:
        return outcome, reasons

    # 9. Scope
    outcome, reasons = validate_scope(capability, request)
    if outcome != ACCEPTED_OUTCOME:
        return outcome, reasons

    # 10. Artifact contract and atomicity (checked at artifact creation time)
    # 11. Acceptance
    return ACCEPTED_OUTCOME, []
