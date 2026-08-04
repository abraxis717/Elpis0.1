from __future__ import annotations

from dataclasses import dataclass
import math

from .identity import require_hex


class ObservationContractError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LatentSummary:
    count: int
    minimum: float
    maximum: float
    mean: float
    variance: float
    l2_norm: float

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ObservationContractError("latent count must be positive")
        for name, value in (
            ("minimum", self.minimum),
            ("maximum", self.maximum),
            ("mean", self.mean),
            ("variance", self.variance),
            ("l2_norm", self.l2_norm),
        ):
            if not math.isfinite(value):
                raise ObservationContractError(f"{name} must be finite")
        if self.variance < 0 or self.l2_norm < 0:
            raise ObservationContractError(
                "variance and l2_norm must be non-negative"
            )
        if self.minimum > self.maximum:
            raise ObservationContractError(
                "minimum cannot exceed maximum"
            )


@dataclass(frozen=True, slots=True)
class ProjectionObservation:
    """
    Privacy-minimal future Y1 record.

    No raw prompt, Context object, hidden state or unrestricted model output is
    representable in this contract.
    """

    occurrence_id: str
    request_id_hash: str
    projection_checksum: str
    schema_chi: str
    grid_signature_chi: str | None
    latent_summary: LatentSummary
    latent_blob_ref: str | None
    route_family: str
    artifact_ref: str | None
    validation_ref: str | None
    governance_ref: str | None
    provenance_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.occurrence_id:
            raise ObservationContractError("occurrence_id is required")
        require_hex(
            self.request_id_hash,
            field_name="request_id_hash",
            exact_length=64,
        )
        require_hex(
            self.projection_checksum,
            field_name="projection_checksum",
            exact_length=64,
        )
        require_hex(self.schema_chi, field_name="schema_chi")
        if self.grid_signature_chi is not None:
            require_hex(
                self.grid_signature_chi,
                field_name="grid_signature_chi",
            )
        if not self.route_family:
            raise ObservationContractError("route_family is required")
