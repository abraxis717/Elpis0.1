"""Adapter-side draft-state lease contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from Artifacts.content_identity import IdentityTuple, identity_of_payload

from ._validation import require_digest, require_nonnegative_int, require_positive_int


class LeaseInvalidationReason(str, Enum):
    STATE_DIGEST_MISMATCH = "STATE_DIGEST_MISMATCH"
    HOST_IDENTITY_MISMATCH = "HOST_IDENTITY_MISMATCH"
    AGE_EXCEEDED = "AGE_EXCEEDED"
    ACTUATION_OCCURRED = "ACTUATION_OCCURRED"
    SEAL_VETO = "SEAL_VETO"


class InvalidDraftLeaseError(RuntimeError):
    def __init__(self, reason: LeaseInvalidationReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class DraftStateLease:
    """Zero-authority permission to read one sealed Header state for drafting."""

    SCHEMA: ClassVar[str] = "elpis.header.draft-state-lease.v1"

    epoch_ordinal: int
    lease_ordinal: int
    state_digest: str
    host_identity_digest: str
    sealed_at_target_position: int
    max_draft_token_age: int
    actuation_ordinal_at_issue: int

    refresh_policy_digest: str
    lease_policy_digest: str
    boundary_detector_policy_digest: str

    def __post_init__(self) -> None:
        require_nonnegative_int("epoch_ordinal", self.epoch_ordinal)
        require_nonnegative_int("lease_ordinal", self.lease_ordinal)
        require_nonnegative_int(
            "sealed_at_target_position", self.sealed_at_target_position
        )
        require_positive_int("max_draft_token_age", self.max_draft_token_age)
        require_nonnegative_int(
            "actuation_ordinal_at_issue", self.actuation_ordinal_at_issue
        )
        for name in (
            "state_digest",
            "host_identity_digest",
            "refresh_policy_digest",
            "lease_policy_digest",
            "boundary_detector_policy_digest",
        ):
            require_digest(name, getattr(self, name))

    def as_dict(self) -> dict[str, Any]:
        return {
            "__record__": "DraftStateLease",
            "schema": self.SCHEMA,
            "epoch_ordinal": self.epoch_ordinal,
            "lease_ordinal": self.lease_ordinal,
            "state_digest": self.state_digest,
            "host_identity_digest": self.host_identity_digest,
            "sealed_at_target_position": self.sealed_at_target_position,
            "max_draft_token_age": self.max_draft_token_age,
            "actuation_ordinal_at_issue": self.actuation_ordinal_at_issue,
            "refresh_policy_digest": self.refresh_policy_digest,
            "lease_policy_digest": self.lease_policy_digest,
            "boundary_detector_policy_digest": self.boundary_detector_policy_digest,
        }

    def identity(self) -> IdentityTuple:
        return identity_of_payload(
            self.as_dict(),
            parent_primaries=(
                self.state_digest,
                self.host_identity_digest,
                self.refresh_policy_digest,
                self.lease_policy_digest,
                self.boundary_detector_policy_digest,
            ),
        )

    def validate_context(
        self,
        *,
        current_target_position: int,
        current_state_digest: str,
        current_host_identity_digest: str,
        current_actuation_ordinal: int,
    ) -> None:
        require_nonnegative_int("current_target_position", current_target_position)
        require_nonnegative_int("current_actuation_ordinal", current_actuation_ordinal)
        require_digest("current_state_digest", current_state_digest)
        require_digest("current_host_identity_digest", current_host_identity_digest)

        if current_state_digest != self.state_digest:
            raise InvalidDraftLeaseError(
                LeaseInvalidationReason.STATE_DIGEST_MISMATCH
            )
        if current_host_identity_digest != self.host_identity_digest:
            raise InvalidDraftLeaseError(
                LeaseInvalidationReason.HOST_IDENTITY_MISMATCH
            )
        if current_actuation_ordinal != self.actuation_ordinal_at_issue:
            raise InvalidDraftLeaseError(
                LeaseInvalidationReason.ACTUATION_OCCURRED
            )

        age = current_target_position - self.sealed_at_target_position
        if age < 0 or age > self.max_draft_token_age:
            raise InvalidDraftLeaseError(LeaseInvalidationReason.AGE_EXCEEDED)
