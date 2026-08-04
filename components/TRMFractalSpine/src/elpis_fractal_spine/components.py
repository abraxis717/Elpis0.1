"""Frozen dataclass components for Elpis Canon FS1.0 ECS spine runtime.

All components are frozen dataclasses unless explicitly noted.
These define the ECS blueprint for the spine world.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Request components
# ---------------------------------------------------------------------------

class RequestLifecycle(str, Enum):
    RECEIVED = "RECEIVED"
    PROJECTED = "PROJECTED"
    RUNNING = "RUNNING"
    WAITING_FOR_CHILD = "WAITING_FOR_CHILD"
    FOLDING = "FOLDING"
    VALIDATING = "VALIDATING"
    GOVERNANCE_PENDING = "GOVERNANCE_PENDING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


@dataclass(frozen=True)
class RequestEnvelope:
    request_id: str
    source: str
    priority: int
    created_tick: int
    metadata: tuple


@dataclass(frozen=True)
class RequestBudget:
    request_id: str
    authority_class: str
    steps_limit: int
    steps_consumed: int
    reference_only: bool = True


@dataclass(frozen=True)
class RuntimeFrame:
    tick: int
    phase: str
    invocation_sequence: int
    wall_ns: int = 0
    monotonic_ns: int = 0


# ---------------------------------------------------------------------------
# Observation / Cortex (diagnostic only)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ObservationCorrelation:
    request_id: str
    generation: Optional[int] = None
    lifecycle_stage: Optional[str] = None
    packet_digest: Optional[str] = None
    forecast_eval_status: Optional[str] = None
    status: str = "ABSENT"


# ---------------------------------------------------------------------------
# Structural components
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StructuralProjection:
    request_id: str
    node_id: str
    grid81: tuple
    residual81: tuple
    proposal_digest: str


@dataclass(frozen=True)
class TRMProposal:
    request_id: str
    node_id: str
    proposal_digest: str
    admitted: bool


@dataclass(frozen=True)
class TRMTrajectory:
    status: str = "NOT_EXPOSED"


@dataclass(frozen=True)
class TRMAnchor:
    request_id: str
    node_id: str
    anchor_digest: str
    basis_digest: str


# ---------------------------------------------------------------------------
# Expansion / Fold components
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExpansionProposal:
    request_id: str
    parent_node_id: str
    proposed_child_node_id: str
    proposed_cell: int
    priority: int
    digest: str


@dataclass(frozen=True)
class ExpansionAdmission:
    request_id: str
    parent_node_id: str
    child_node_id: str
    admitted_cell: int
    admission_receipt: str
    depth: int


@dataclass(frozen=True)
class ChildLease:
    request_id: str
    parent_node_id: str
    child_node_id: str
    lease_state: str
    refinement_charge: int


@dataclass(frozen=True)
class Fold:
    request_id: str
    parent_node_id: str
    child_node_id: str
    folded_grid81: tuple
    fold_digest: str


# ---------------------------------------------------------------------------
# Evidence components
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvidenceInbox:
    request_id: str
    node_id: str
    packet_digests: tuple
    source_model_ids: tuple


@dataclass(frozen=True)
class OrthogonalBasis:
    request_id: str
    node_id: str
    basis_digest: str
    basis_vectors: tuple
    dim: int


@dataclass(frozen=True)
class OrthogonalEvidence:
    request_id: str
    node_id: str
    source_model_id: str
    vector81: Optional[tuple]
    status: str
    rationale: str
    digest: str
    retained_fraction: float
    projection_coefficients: tuple


@dataclass(frozen=True)
class RecursiveEvidence:
    request_id: str
    node_id: str
    local_summary81: Optional[tuple]
    recursive_summary81: Optional[tuple]
    summary_digest: str
    compression_type: str = "rank-one"


@dataclass(frozen=True)
class EvidencePriority:
    evidence_types: tuple
    owned_by_config: bool = True


# ---------------------------------------------------------------------------
# Cascade / Activation components
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CascadeState:
    request_id: str
    node_id: str
    round_number: int
    status: str
    proposals_count: int
    admitted_count: int


@dataclass(frozen=True)
class ActivationInbox:
    request_id: str
    model_id: str
    proposal_digest: str
    rule_id: str


# ---------------------------------------------------------------------------
# Regime component
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Regime:
    request_id: str
    node_id: str
    regime_id: str
    temperature: float
    digest: str


# ---------------------------------------------------------------------------
# Model registry / residency components
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelRegistry:
    model_id: str
    display_name: str
    role: str
    admission_status: str
    authority_class: str
    residency_tier: str


class ModelResidency(str, Enum):
    DISABLED = "DISABLED"
    PINNED_CPU = "PINNED_CPU"
    PINNED_GPU = "PINNED_GPU"
    FAULTED = "FAULTED"
    QUARANTINED = "QUARANTINED"


class ModelLifecycle(str, Enum):
    STANDBY = "STANDBY"
    ACTIVATION_PROPOSED = "ACTIVATION_PROPOSED"
    ADMITTED = "ADMITTED"
    RUNNING = "RUNNING"
    OUTPUT_READY = "OUTPUT_READY"
    COOLDOWN = "COOLDOWN"
    FAULTED = "FAULTED"


@dataclass(frozen=True)
class ModelHealth:
    model_id: str
    status: str
    last_check_tick: int
    error_message: Optional[str] = None


@dataclass(frozen=True)
class ModelOutput:
    request_id: str
    node_id: str
    model_id: str
    output_type: str
    vector81: Optional[tuple]
    metadata: tuple
    digest: str


# ---------------------------------------------------------------------------
# Validation / Governance / Fault / Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Validation:
    request_id: str
    node_id: str
    status: str
    details: tuple


@dataclass(frozen=True)
class Governance:
    status: str = "NOT_ACTIVE"


@dataclass(frozen=True)
class Fault:
    request_id: str
    source: str
    message: str
    tick: int


@dataclass(frozen=True)
class Result:
    request_id: str
    status: str
    output_digest: str
    seal_tick: int


# ---------------------------------------------------------------------------
# FS1.1 — Codec evidence components
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NativeEvidenceEntry:
    """Native evidence classification entry — result of classification system."""
    request_id: str
    node_id: str
    source_model_id: str
    evidence_kind: str
    payload_digest: str
    classified: bool


@dataclass(frozen=True)
class CodecEmissionEntry:
    """Codec emission result — stored after codec execution."""
    request_id: str
    node_id: str
    codec_id: str
    emission_status: str
    target_space: str
    vector: Optional[tuple]
    emission_digest: str
    quality_flags: tuple


@dataclass(frozen=True)
class CellAlignedAdmission:
    """Cell-aligned evidence admitted for orthogonalization."""
    request_id: str
    node_id: str
    codec_id: str
    vector81: tuple
    retained_fraction: float
    admission_status: str
    quality_report_digest: str
    source_packet_digest: str
    codec_manifest_digest: str


@dataclass(frozen=True)
class NativeVectorStore:
    """Native vector evidence stored in native space — never orthogonalized."""
    request_id: str
    node_id: str
    codec_id: str
    target_space: str
    vector_digest: str
    stored: bool


@dataclass(frozen=True)
class StructuredProposalEntry:
    """Structured proposal in typed lane — no Gram-Schmidt."""
    request_id: str
    node_id: str
    proposal_id: str
    proposal_kind: str
    schema_version: str
    payload_digest: str
    proposal_digest: str
    proposal_status: str


@dataclass(frozen=True)
class DiagnosticEvidenceEntry:
    """Diagnostic evidence — journal only, no cascade/trigger."""
    request_id: str
    node_id: str
    source_model_id: str
    payload_digest: str
    journal_entry: str


@dataclass(frozen=True)
class RejectedNativeEntry:
    """Rejected native output — fault evidence only."""
    request_id: str
    node_id: str
    source_model_id: str
    rejection_reason: str
    payload_digest: str
