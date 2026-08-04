"""Frozen dataclass contracts for Elpis Canon FS0.1."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .semantic_spaces import LatentSpaceIdentity


# ---------------------------------------------------------------------------
# Admission status vocabulary
# ---------------------------------------------------------------------------

class ModelAdmissionStatus(str, Enum):
    INACTIVE = "INACTIVE"
    INTAKE = "INTAKE"
    PROBED = "PROBED"
    EVALUATED = "EVALUATED"
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"
    REFERENCE_ONLY = "REFERENCE_ONLY"
    INCOMPLETE = "INCOMPLETE"
    QUARANTINED = "QUARANTINED"

    @classmethod
    def all_values(cls) -> frozenset:
        return frozenset(m.value for m in cls)


# ---------------------------------------------------------------------------
# Orthogonal evidence status vocabulary
# ---------------------------------------------------------------------------

class OrthogonalEvidenceStatus(str, Enum):
    ORTHOGONALIZED = "ORTHOGONALIZED"
    DEPENDENT = "DEPENDENT"
    INVALID_INPUT = "INVALID_INPUT"
    SPACE_MISMATCH = "SPACE_MISMATCH"
    UNKNOWN_MODEL = "UNKNOWN_MODEL"
    CODEC_NOT_ADMITTED = "CODEC_NOT_ADMITTED"


# ---------------------------------------------------------------------------
# 1. ModelRegistryEntry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelRegistryEntry:
    model_id: str
    display_name: str
    path: str
    role: str
    residency_tier: str
    admission_status: ModelAdmissionStatus
    authority_class: str
    native_input_space: Optional[str]
    native_output_space: str
    canon_input_space: Optional[str]
    canon_output_space: str
    loader_import: Optional[str]
    checkpoint_format: Optional[str]
    checkpoint_sha256: Optional[str]
    config_sha256: Optional[str]
    codec_id: Optional[str]
    deterministic_mode: Optional[str]
    notes: str


# ---------------------------------------------------------------------------
# 2. (ModelAdmissionStatus — already defined as Enum above)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 3. LatentSpaceIdentity (already in semantic_spaces)
#    Re-export for contract completeness.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 4. ModelEvidencePacket
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelEvidencePacket:
    request_id: str
    node_id: str
    source_model_id: str
    source_output_space: str
    codec_id: str
    codec_digest: str
    output_digest: str
    latent_space: LatentSpaceIdentity
    vector81: tuple
    metadata: tuple
    digest: str

    def __post_init__(self):
        # Runtime validation (does not mutate frozen instance).
        if len(self.vector81) != 81:
            raise ValueError(f"vector81 length {len(self.vector81)} != 81")
        for v in self.vector81:
            if not isinstance(v, (int, float)):
                raise TypeError(f"vector81 element type {type(v)} is not numeric")
            import math
            if math.isnan(v) or math.isinf(v):
                raise ValueError("vector81 contains NaN or Inf")


# ---------------------------------------------------------------------------
# 5. TRMStructuralAnchor
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TRMStructuralAnchor:
    request_id: str
    node_id: str
    proposal_digest: str
    structural_space: str
    grid81: tuple
    residual81: tuple
    basis_id: str
    basis_vectors: tuple
    basis_digest: str
    digest: str

    def __post_init__(self):
        if self.structural_space != "grid81.structural.v1":
            raise ValueError(
                f"structural_space '{self.structural_space}' != 'grid81.structural.v1'"
            )
        if len(self.grid81) != 81:
            raise ValueError(f"grid81 length {len(self.grid81)} != 81")
        for t in self.grid81:
            if not (0 <= t <= 9):
                raise ValueError(f"grid81 token {t} outside 0..9")
        if len(self.residual81) != 81:
            raise ValueError(f"residual81 length {len(self.residual81)} != 81")


# ---------------------------------------------------------------------------
# 6. (OrthogonalEvidenceStatus — already defined as Enum above)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 7. OrthogonalEvidenceProposal
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OrthogonalEvidenceProposal:
    request_id: str
    node_id: str
    source_model_id: str
    input_packet_digest: str
    trm_anchor_digest: str
    basis_digest: str
    status: OrthogonalEvidenceStatus
    projection_coefficients: tuple
    input_norm: float
    residual_norm: float
    retained_fraction: float
    explained_fraction: float
    vector81: Optional[tuple]
    rationale: str
    digest: str


# ---------------------------------------------------------------------------
# 8. RecursiveEmbeddingNode
# ---------------------------------------------------------------------------

@dataclass(frozen=False)
class RecursiveEmbeddingNode:
    request_id: str
    node_id: str
    parent_node_id: Optional[str]
    depth: int
    parent_expansion_cell: Optional[int]
    trm_anchor_digest: str
    accepted_evidence_digests: list
    rejected_evidence_digests: list
    local_summary81: Optional[tuple]
    recursive_summary81: Optional[tuple]
    summary_digest: str
    sealed: bool

    def seal(self):
        """Seal the node. No further mutation permitted."""
        self.accepted_evidence_digests = tuple(self.accepted_evidence_digests)
        self.rejected_evidence_digests = tuple(self.rejected_evidence_digests)
        self.sealed = True

    def is_sealed(self) -> bool:
        return self.sealed


# ---------------------------------------------------------------------------
# 9. RecursiveEmbeddingTree
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RecursiveEmbeddingTree:
    request_id: str
    root_node_id: str
    nodes: tuple
    max_depth: int
    tree_digest: str


# ---------------------------------------------------------------------------
# 10. ModelInvocationFrame
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelInvocationFrame:
    request_id: str
    node_id: str
    parent_node_id: Optional[str]
    recursion_depth: int
    invocation_sequence: int
    observation_generation: Optional[int]
    created_monotonic_ns: int
    completed_monotonic_ns: Optional[int]
    source_model_id: str
    model_manifest_digest: str
    input_semantic_space: str
    output_semantic_space: str
    input_digest: str
    output_digest: str
    status: str
