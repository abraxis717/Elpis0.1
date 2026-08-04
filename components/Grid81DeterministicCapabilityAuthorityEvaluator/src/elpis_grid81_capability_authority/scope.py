"""G5.2B Capability Scope.

CapabilityScopeV1 — explicit scope binding for a capability.
The authorized set must equal the complete referred set in the canonical corpus.
"""
from .canonical import canonical_digest


def create_capability_scope(authorized_proposal_digests: list) -> dict:
    """Create a capability scope record.

    authorized_proposal_digests must be sorted, unique, nonempty.
    """
    sorted_digests = sorted(set(authorized_proposal_digests))

    scope_body = {
        "authorized_consumer_class": "STRUCTURAL_INFLUENCE_COMPILER_V1",
        "authorized_operation_class": "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
        "authorized_proposal_digests": sorted_digests,
        "capability_class": "STRUCTURAL_INFLUENCE_CAPABILITY_V1",
        "schema_version": "capability-scope.v1",
    }
    scope_body["scope_digest"] = canonical_digest(scope_body)
    return scope_body


def validate_scope(scope: dict) -> bool:
    """Validate a capability scope record."""
    required = ["schema_version", "capability_class", "authorized_proposal_digests",
                "authorized_operation_class", "authorized_consumer_class", "scope_digest"]
    for field in required:
        if field not in scope:
            return False

    digests = scope.get("authorized_proposal_digests", [])
    if len(digests) == 0:
        return False

    # Check uniqueness and sorting
    if digests != sorted(set(digests)):
        return False

    # Verify digest
    expected = canonical_digest({k: v for k, v in scope.items() if k != "scope_digest"})
    if expected != scope.get("scope_digest"):
        return False

    return True
