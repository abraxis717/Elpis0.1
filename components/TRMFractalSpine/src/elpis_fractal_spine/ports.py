"""Protocol interfaces (ports) for Elpis Canon FS0.1.

These define the boundaries between components. Each port is a
protocol that implementations must satisfy.
"""

from typing import Optional, Protocol

import numpy as np

from .contracts import ModelEvidencePacket


class ModelRegistryPort(Protocol):
    """Interface for model registry operations."""

    def lookup_model(self, model_id: str) -> Optional[dict]:
        """Look up a model by ID. Returns entry dict or None."""
        ...

    def get_all_models(self) -> list[dict]:
        """Return all registered models."""
        ...

    def validate_admission(self, model_id: str) -> bool:
        """Check if a model is admitted for evidence emission."""
        ...


class EvidenceCodecPort(Protocol):
    """
    Interface for encoding native model output into ModelEvidencePacket.

    codec_id: unique identifier
    input_space: native model output space
    output_space: canonical latent space
    """

    codec_id: str
    input_space: str
    output_space: str

    def encode(self, raw_evidence: np.ndarray) -> ModelEvidencePacket:
        """
        Transform raw model output into a validated ModelEvidencePacket.

        Args:
            raw_evidence: Native model output array.

        Returns:
            ModelEvidencePacket with validated latent vector.
        """
        ...


class OrthogonalizerPort(Protocol):
    """Interface for orthogonal evidence computation."""

    def orthogonalize(
        self,
        evidence: ModelEvidencePacket,
        trm_anchor_digest: str,
        exclusion_basis: Optional[list] = None,
        accepted_evidence: Optional[list] = None,
    ) -> dict:
        """
        Orthogonalize evidence against structural and exclusion basis.

        Returns proposal dict with status and metrics.
        """
        ...


class RecursiveEmbeddingStorePort(Protocol):
    """Interface for node/evidence storage."""

    def add_anchor(self, anchor: dict):
        ...

    def get_anchor(self, node_id: str) -> Optional[dict]:
        ...

    def add_node(self, node: dict):
        ...

    def get_node(self, node_id: str) -> Optional[dict]:
        ...

    def add_proposal(self, proposal: dict):
        ...


class StructuralProposalSourcePort(Protocol):
    """Interface for providing TRM structural proposals."""

    def get_proposal(self, request_id: str, node_id: str) -> Optional[dict]:
        """
        Get a TRM structural proposal (grid81 + residual81).

        Returns dict with grid81 and residual81 arrays, or None.
        """
        ...
