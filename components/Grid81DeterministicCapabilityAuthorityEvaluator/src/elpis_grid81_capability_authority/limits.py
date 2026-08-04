"""G5.2B Capability Limits.

CapabilityLimitV1 — bounded limits on a capability's validity and consumption.
"""
from .canonical import canonical_digest


def create_capability_limit(valid_from: int = 0, valid_through: int = 0) -> dict:
    """Create a capability limit record.

    max_consumptions = 1, single_use = true for all canonical capabilities.
    """
    limit_body = {
        "max_consumptions": 1,
        "schema_version": "capability-limit.v1",
        "single_use": True,
        "valid_from_logical_tick": valid_from,
        "valid_through_logical_tick": valid_through,
    }
    limit_body["limit_digest"] = canonical_digest(limit_body)
    return limit_body


def validate_limit(limit: dict) -> bool:
    """Validate a capability limit record."""
    required = ["schema_version", "max_consumptions", "valid_from_logical_tick",
                "valid_through_logical_tick", "single_use", "limit_digest"]
    for field in required:
        if field not in limit:
            return False

    if limit.get("max_consumptions") != 1:
        return False
    if limit.get("single_use") is not True:
        return False
    if limit.get("valid_from_logical_tick", -1) < 0:
        return False
    if limit.get("valid_through_logical_tick", -1) < 0:
        return False

    # Verify digest
    expected = canonical_digest({k: v for k, v in limit.items() if k != "limit_digest"})
    if expected != limit.get("limit_digest"):
        return False

    return True
