"""G5.3C Shadow capability state management.

Immutable shadow copies of capability records. Digest-tracked for compare-and-swap.
"""
from dataclasses import dataclass, asdict
import copy

from .canonical import canonical_digest, canonical_json


@dataclass(frozen=True)
class ShadowCapabilityState:
    """Immutable shadow capability state with self-computed digest."""
    capability_digest: str
    application_state: str  # "UNAPPLIED", "APPLIED"
    consumption_count: int
    current_lifecycle_state: str
    applied_artifact_digest: str | None

    @property
    def state_digest(self) -> str:
        """SHA-256 digest of all state fields."""
        payload = {
            "capability_digest": self.capability_digest,
            "application_state": self.application_state,
            "consumption_count": self.consumption_count,
            "current_lifecycle_state": self.current_lifecycle_state,
            "applied_artifact_digest": self.applied_artifact_digest,
        }
        return canonical_digest(payload)

    def to_dict(self) -> dict:
        """Serialize to dict for canonical JSON."""
        d = asdict(self)
        d["state_digest"] = self.state_digest
        return d

    def apply_artifact(self, artifact_digest: str) -> "ShadowCapabilityState":
        """Transition from APPLIED -> consumed+applied state.

        Returns new immutable state. Original is unchanged.
        """
        if self.application_state == "APPLIED":
            raise ValueError("Artifact already applied to this state")
        return ShadowCapabilityState(
            capability_digest=self.capability_digest,
            application_state="APPLIED",
            consumption_count=self.consumption_count + 1,
            current_lifecycle_state=self.current_lifecycle_state,
            applied_artifact_digest=artifact_digest,
        )

    @staticmethod
    def from_capability_record(cap: dict) -> "ShadowCapabilityState":
        """Create shadow state from a G5.3B capability record."""
        return ShadowCapabilityState(
            capability_digest=cap["capability_digest"],
            application_state="UNAPPLIED",
            consumption_count=cap.get("consumption_count", 0),
            current_lifecycle_state=cap.get("current_lifecycle_state", "CONSUMED"),
            applied_artifact_digest=None,
        )


def deep_copy_state(state: ShadowCapabilityState) -> ShadowCapabilityState:
    """Create a deep copy of shadow state (for atomicity checks)."""
    return ShadowCapabilityState(
        capability_digest=state.capability_digest,
        application_state=state.application_state,
        consumption_count=state.consumption_count,
        current_lifecycle_state=state.current_lifecycle_state,
        applied_artifact_digest=state.applied_artifact_digest,
    )
