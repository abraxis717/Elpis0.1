"""Immutable canonical data structures for promotion planning."""

import hashlib
import json
from dataclasses import dataclass, field, replace
from typing import Any


def _sha256_str(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _canonical_json(obj: Any) -> str:
    """Produce deterministic JSON string for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _digest_of(obj: Any) -> str:
    """SHA-256 digest of canonical JSON representation."""
    return _sha256_str(_canonical_json(obj))


@dataclass(frozen=True)
class PhaseEvidence:
    """Evidence binding for a single phase (G5.3B.1, G5.3C, G5.3D)."""
    phase_id: str
    source_directory: str
    manifest_path: str
    manifest_digest: str
    disposition: str
    evidence_files: tuple  # tuple of (filename, sha256, size) sorted by filename
    artifact_digest: str | None = None
    capability_digest: str | None = None
    lifecycle_state: str | None = None
    shadow_receipt_digest: str | None = None
    resulting_state_digest: str | None = None
    resulting_ledger_head: str | None = None
    bundle_digest: str | None = None

    @property
    def digest(self) -> str:
        return _digest_of(self.__dict__)


@dataclass(frozen=True)
class SourceChain:
    """Complete promotion source chain binding."""
    g53b1: PhaseEvidence
    g53c: PhaseEvidence
    g53d: PhaseEvidence
    chain_version: str = "promotion-source-chain.v1"

    @property
    def chain_digest(self) -> str:
        payload = {
            "chain_version": self.chain_version,
            "g53b1_digest": self.g53b1.digest,
            "g53c_digest": self.g53c.digest,
            "g53d_digest": self.g53d.digest,
        }
        return _digest_of(payload)


@dataclass(frozen=True)
class GateResult:
    """Immutable result of a single promotion gate."""
    gate_id: str
    gate_ordinal: int
    gate_version: str
    passed: bool
    rejection_code: str | None
    evidence_bindings: tuple  # tuple of evidence tuples
    observed_value: str | None = None
    expected_value: str | None = None

    @property
    def digest(self) -> str:
        return _digest_of(self.__dict__)


@dataclass(frozen=True)
class PromotionDecision:
    """Advisory promotion decision."""
    decision: str  # READY_FOR_CANONICAL_REVIEW | NOT_READY_FOR_CANONICAL_REVIEW
    gate_vector: tuple  # tuple of GateResult digests in order
    source_chain_digest: str
    expected_canonical_preconditions: tuple  # tuple of precondition strings
    planner_version: str = "1.0.0"

    @property
    def digest(self) -> str:
        return _digest_of(self.__dict__)


@dataclass(frozen=True)
class PlanIntention:
    """A typed, non-executable intention for a future canonical transaction."""
    intention_type: str
    description: str
    precondition: str | None = None
    parameter_digest: str | None = None


@dataclass(frozen=True)
class CanonicalPromotionPlan:
    """Non-self-executing canonical promotion plan."""
    intentions: tuple  # tuple of PlanIntention digests in order
    decision_digest: str
    source_chain_digest: str
    planner_version: str = "1.0.0"
    executable: bool = False
    self_applying: bool = False
    authoritative: bool = False
    canonical_write_permitted: bool = False

    @property
    def digest(self) -> str:
        return _digest_of(self.__dict__)


@dataclass(frozen=True)
class AuthorityAudit:
    """Machine-readable authority boundary audit."""
    planner_authoritative_for_application: bool = False
    planner_authoritative_for_capability_consumption: bool = False
    planner_authoritative_for_canonical_state: bool = False
    promotion_plan_executable: bool = False
    promotion_plan_self_applying: bool = False
    canonical_write_permitted: bool = False
    canonical_capabilities_consumed: int = 0
    canonical_applications_committed: int = 0
    source_g53b1_modified: bool = False
    source_g53c_modified: bool = False
    source_g53d_modified: bool = False
    shadow_state_modified: bool = False
    canonical_state_modified: bool = False
    qubo_touched: bool = False
    darwinian_life_touched: bool = False
    production_trm_touched: bool = False
    network_used: bool = False

    @property
    def digest(self) -> str:
        return _digest_of(self.__dict__)


# Rejection codes in deterministic precedence order
REJECTION_PRECEDENCE = (
    "SOURCE_MANIFEST_INVALID",
    "SOURCE_HASH_MISMATCH",
    "SOURCE_CHAIN_INCOMPLETE",
    "SOURCE_DISPOSITION_MISSING",
    "ARTIFACT_IDENTITY_DISCONTINUITY",
    "CAPABILITY_IDENTITY_DISCONTINUITY",
    "COMPILER_IDENTITY_DISCONTINUITY",
    "SHADOW_APPLICATION_NOT_ACCEPTED",
    "RECEIPT_INVALID",
    "SHADOW_TRANSITION_INVALID",
    "LEDGER_CONTINUITY_INVALID",
    "REPLAY_QUALIFICATION_MISSING",
    "ATOMICITY_QUALIFICATION_MISSING",
    "CANONICAL_NONMUTATION_UNPROVEN",
    "AUTHORITY_BOUNDARY_INVALID",
    "DETERMINISM_UNPROVEN",
    "BUNDLE_CONSISTENCY_INVALID",
    "CAPABILITY_ALREADY_CONSUMED",
    "SOURCE_MUTATED",
    "PLANNER_AUTHORITY_VIOLATION",
)
