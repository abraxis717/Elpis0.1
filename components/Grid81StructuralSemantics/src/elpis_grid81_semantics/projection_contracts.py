"""Grid81GroupProjectionV1 and GroupSelectionEvidenceV1 — passive contracts (G4.0B Phase 13).

These are data contracts only. No activation, no model loading, no ECS mutation.
Mandatory status for GroupSelectionEvidenceV1: EVIDENCE_ONLY.

Forbidden fields:
  model_path, checkpoint_handle, lora_handle, cuda_device, activation_command,
  executor_command, temperature, hebbian_write, state_commit
"""

from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

FORBIDDEN_FIELDS = frozenset([
    "model_path", "checkpoint_handle", "lora_handle", "cuda_device",
    "activation_command", "executor_command", "temperature",
    "hebbian_write", "state_commit",
])


@dataclass(frozen=True)
class Grid81GroupProjectionV1:
    grid_digest: str
    registry_digest: str
    factor_topology_digest: str
    per_cell_memberships: dict[int, list[str]]
    per_factor_memberships: dict[str, list[int]]
    motif_identities: list[str]
    group_counts: dict[str, int]
    projection_digest: str

    def to_dict(self) -> dict:
        return {
            "grid_digest": self.grid_digest,
            "registry_digest": self.registry_digest,
            "factor_topology_digest": self.factor_topology_digest,
            "per_cell_memberships": self.per_cell_memberships,
            "per_factor_memberships": self.per_factor_memberships,
            "motif_identities": self.motif_identities,
            "group_counts": self.group_counts,
            "projection_digest": self.projection_digest,
        }

    def audit_forbidden(self) -> list[str]:
        """Check that no forbidden fields exist in the projection dict."""
        d = self.to_dict()
        found = []
        for key in d:
            if key in FORBIDDEN_FIELDS:
                found.append(key)
        return found


@dataclass(frozen=True)
class GroupSelectionEvidenceV1:
    eligible_group_ids: set[str]
    ineligible_group_ids: set[str]
    supporting_motif_digests: list[str]
    selection_policy_digest: str
    status: str  # Must be EVIDENCE_ONLY

    def __post_init__(self):
        if self.status != "EVIDENCE_ONLY":
            raise ValueError(f"GroupSelectionEvidenceV1 status must be EVIDENCE_ONLY, got: {self.status}")

    def to_dict(self) -> dict:
        return {
            "eligible_group_ids": sorted(self.eligible_group_ids),
            "ineligible_group_ids": sorted(self.ineligible_group_ids),
            "supporting_motif_digests": self.supporting_motif_digests,
            "selection_policy_digest": self.selection_policy_digest,
            "status": self.status,
        }

    def audit_forbidden(self) -> list[str]:
        """Check that no forbidden fields exist."""
        d = self.to_dict()
        found = []
        for key in d:
            if key in FORBIDDEN_FIELDS:
                found.append(key)
        return found


def audit_passive_contracts(projection: Grid81GroupProjectionV1 | None, evidence: GroupSelectionEvidenceV1 | None) -> list[str]:
    """Audit passive contracts for forbidden activation fields."""
    violations = []
    if projection:
        violations.extend(projection.audit_forbidden())
    if evidence:
        violations.extend(evidence.audit_forbidden())
    return violations
