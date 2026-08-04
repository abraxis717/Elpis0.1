from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

from .identity import content_checksum, require_hex


class ProjectionContractError(ValueError):
    pass


class ProjectionMode(str, Enum):
    CONTINUOUS_PRIMARY_GRID_OBSERVATION = (
        "continuous_primary_grid_observation"
    )
    CONTINUOUS_ONLY = "continuous_only"
    LEGACY_GRID_PRIMARY = "legacy_grid_primary"


@dataclass(frozen=True, slots=True)
class TensorRef:
    """
    Exact reference to externally stored tensor content.

    The checksum identifies the stored bytes under the declared codec. It is
    not a semantic similarity hash and must not use LSH.
    """

    content_checksum: str
    dtype: str
    shape: tuple[int, ...]
    codec: str
    storage_ref: str | None = None

    def __post_init__(self) -> None:
        require_hex(
            self.content_checksum,
            field_name="content_checksum",
            exact_length=64,
        )
        if not self.dtype:
            raise ProjectionContractError("tensor dtype is required")
        if not self.codec:
            raise ProjectionContractError("tensor codec is required")
        if not self.shape or any(
            type(dimension) is not int or dimension <= 0
            for dimension in self.shape
        ):
            raise ProjectionContractError(
                "tensor shape must contain positive integer dimensions"
            )


@dataclass(frozen=True, slots=True)
class GridSignatureRef:
    schema_chi: str
    signature_chi: str

    def __post_init__(self) -> None:
        require_hex(self.schema_chi, field_name="schema_chi")
        require_hex(self.signature_chi, field_name="signature_chi")


@dataclass(frozen=True, slots=True)
class StructuralProjection:
    """
    Canonical structural boundary contract.

    `projection_checksum` identifies the projection product, not the complete
    request trajectory. Route, budget, hints, energy and confidence remain
    request-local control or telemetry.
    """

    request_id: str
    projection_mode: ProjectionMode
    continuous_latent: TensorRef
    grid_observation: GridSignatureRef | None
    projector_artifact_checksum: str
    projector_code_checksum: str
    projection_semantics_version: str

    route_family: str
    request_account_ref: str
    decoder_hint_refs: tuple[str, ...] = ()
    domain_context_ref: str | None = None

    energy: float | None = None
    confidence: float | None = None
    provenance_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ProjectionContractError("request_id is required")
        if not self.route_family:
            raise ProjectionContractError("route_family is required")
        if not self.request_account_ref:
            raise ProjectionContractError("request_account_ref is required")
        if not self.projection_semantics_version:
            raise ProjectionContractError(
                "projection_semantics_version is required"
            )

        require_hex(
            self.projector_artifact_checksum,
            field_name="projector_artifact_checksum",
            exact_length=64,
        )
        require_hex(
            self.projector_code_checksum,
            field_name="projector_code_checksum",
            exact_length=64,
        )

        for name, value in (
            ("energy", self.energy),
            ("confidence", self.confidence),
        ):
            if value is not None and not math.isfinite(value):
                raise ProjectionContractError(f"{name} must be finite")

        if (
            self.projection_mode
            is ProjectionMode.CONTINUOUS_PRIMARY_GRID_OBSERVATION
            and self.grid_observation is None
        ):
            raise ProjectionContractError(
                "continuous+grid mode requires a Grid signature reference"
            )

    def identity_view(self) -> dict[str, object]:
        """
        Identity-bearing projection content.

        Excludes request-local authority, route, budget, hints, telemetry,
        occurrence identity and provenance.
        """
        return {
            "projection_mode": self.projection_mode.value,
            "continuous_latent": {
                "content_checksum": self.continuous_latent.content_checksum,
                "dtype": self.continuous_latent.dtype,
                "shape": self.continuous_latent.shape,
                "codec": self.continuous_latent.codec,
            },
            "grid_observation": (
                None
                if self.grid_observation is None
                else {
                    "schema_chi": self.grid_observation.schema_chi,
                    "signature_chi": self.grid_observation.signature_chi,
                }
            ),
            "projector_artifact_checksum": (
                self.projector_artifact_checksum
            ),
            "projector_code_checksum": self.projector_code_checksum,
            "projection_semantics_version": (
                self.projection_semantics_version
            ),
        }

    @property
    def projection_checksum(self) -> str:
        return content_checksum(
            "elpis-structural-projection-v1",
            self.identity_view(),
        )
