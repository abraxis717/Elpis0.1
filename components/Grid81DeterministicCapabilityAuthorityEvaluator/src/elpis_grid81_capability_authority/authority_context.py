"""G5.2B Authority context.

Deterministic authority-context record for each evaluation.
No wall-clock, no model/adapter identifiers, no runtime state.
"""
from .canonical import canonical_digest, domain_digest


AUTHORITY_DOMAIN = "STRUCTURAL_INFLUENCE_AUTHORITY_V1"
EVALUATION_LOGICAL_TICK = 0
PERMITTED_CAPABILITY_CLASS = "STRUCTURAL_INFLUENCE_CAPABILITY_V1"
PERMITTED_OPERATION_CLASS = "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1"
PERMITTED_CONSUMER_CLASS = "STRUCTURAL_INFLUENCE_COMPILER_V1"
MAXIMUM_SCOPE_SIZE = 2


def create_authority_context(source_request_digest: str) -> dict:
    """Create a deterministic authority context bound to a source request."""
    context = {
        "authority_domain": AUTHORITY_DOMAIN,
        "authorized_consumer_class": PERMITTED_CONSUMER_CLASS,
        "authorized_operation_class": PERMITTED_OPERATION_CLASS,
        "evaluation_logical_tick": EVALUATION_LOGICAL_TICK,
        "maximum_scope_size": MAXIMUM_SCOPE_SIZE,
        "nontransferability_required": True,
        "permitted_capability_class": PERMITTED_CAPABILITY_CLASS,
        "revocation_policy_required": True,
        "schema_version": "authority-context.v1",
        "single_use_required": True,
        "source_request_digest": source_request_digest,
    }
    context["authority_context_digest"] = canonical_digest({
        k: v for k, v in context.items() if k != "authority_context_digest"
    })
    return context


def validate_authority_context(context: dict) -> bool:
    """Validate an authority context record."""
    required_fields = [
        "authority_domain", "evaluation_logical_tick",
        "permitted_capability_class", "permitted_operation_class",
        "permitted_consumer_class", "maximum_scope_size",
        "single_use_required", "nontransferability_required",
        "revocation_policy_required", "source_request_digest",
        "authority_context_digest",
    ]
    for field in required_fields:
        if field not in context:
            return False

    # Check forbidden fields
    forbidden = {"wall_clock", "timestamp", "model_id", "adapter_id",
                 "device", "port", "endpoint", "command", "process",
                 "score", "confidence", "activation"}
    for field in context:
        for fb in forbidden:
            if fb in field.lower():
                return False

    # Verify digest
    expected_digest = canonical_digest({
        k: v for k, v in context.items() if k != "authority_context_digest"
    })
    if expected_digest != context.get("authority_context_digest"):
        return False

    return True


def get_canonical_context() -> dict:
    """Get the canonical authority context template (without source binding)."""
    return {
        "authority_domain": AUTHORITY_DOMAIN,
        "evaluation_logical_tick": EVALUATION_LOGICAL_TICK,
        "permitted_capability_class": PERMITTED_CAPABILITY_CLASS,
        "permitted_operation_class": PERMITTED_OPERATION_CLASS,
        "permitted_consumer_class": PERMITTED_CONSUMER_CLASS,
        "maximum_scope_size": MAXIMUM_SCOPE_SIZE,
        "single_use_required": True,
        "nontransferability_required": True,
        "revocation_policy_required": True,
    }
