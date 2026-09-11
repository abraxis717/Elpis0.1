"""Explicit authority bridge from advisory G5.3E review to canonical promotion."""

from .authority import (
    AUTHORITY_POLICY_DIGEST,
    AUTHORIZED_PUBLISHER_CLASS,
    PromotionAuthorityError,
    issue_promotion_capability,
    require_promotion_capability,
    validate_promotion_capability,
)

__all__ = [
    "AUTHORITY_POLICY_DIGEST",
    "AUTHORIZED_PUBLISHER_CLASS",
    "PromotionAuthorityError",
    "issue_promotion_capability",
    "require_promotion_capability",
    "validate_promotion_capability",
]
