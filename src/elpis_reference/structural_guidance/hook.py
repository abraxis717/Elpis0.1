from __future__ import annotations

from dataclasses import dataclass

from .admission import (
    StructuralGuidanceAdmissionConfig,
    StructuralGuidanceAdmissionResult,
    admit_projection,
)
from ._authority.c2r6p0.contracts import (
    ProjectionInputV1,
    ProjectionResultV1,
)
from ._authority.c2r6p0.projector import (
    project,
)
from ._authority.elpis_p0.semantic_ir import (
    P0SemanticRequestV1,
)


@dataclass(frozen=True)
class ProjectAndAdmitResultV1:
    projection: ProjectionResultV1
    admission: StructuralGuidanceAdmissionResult

    @property
    def admitted(self) -> bool:
        return self.admission.admitted

    @property
    def fallback_required(self) -> bool:
        return self.admission.fallback_required


def project_and_admit(
    projection_input: ProjectionInputV1,
    config: StructuralGuidanceAdmissionConfig = (
        StructuralGuidanceAdmissionConfig()
    ),
) -> ProjectAndAdmitResultV1:
    """Execute the production C2R6 projector, then the bounded admission gate.

    This is the public structural-guidance composition boundary.

    Projection remains deterministic C2R6-P0 authority.
    Guidance remains C2R6-P1 constrained with TRM authority zero.
    The request-level learned-guidance gate defaults OFF.
    """
    if not isinstance(
        projection_input,
        ProjectionInputV1,
    ):
        raise TypeError(
            "projection_input must be production ProjectionInputV1"
        )

    projection = project(
        projection_input
    )

    if not isinstance(
        projection,
        ProjectionResultV1,
    ):
        raise RuntimeError(
            "production projector returned wrong result type"
        )

    admission = admit_projection(
        projection,
        config,
    )

    if (
        admission.receipt.projection_digest
        != projection.projection_digest
    ):
        raise RuntimeError(
            "structural-guidance receipt projection identity mismatch"
        )

    return ProjectAndAdmitResultV1(
        projection=projection,
        admission=admission,
    )


def project_semantic_request_and_admit(
    semantic_request: P0SemanticRequestV1,
    config: StructuralGuidanceAdmissionConfig = (
        StructuralGuidanceAdmissionConfig()
    ),
    *,
    request_id: str = "",
    debug_tag: str = "",
) -> ProjectAndAdmitResultV1:
    """Public signed Semantic-IR -> Projector -> guidance composition."""
    if not isinstance(
        semantic_request,
        P0SemanticRequestV1,
    ):
        raise TypeError(
            "semantic_request must be production P0SemanticRequestV1"
        )

    projection_input = (
        ProjectionInputV1.from_signed(
            semantic_request,
            request_id=request_id,
            debug_tag=debug_tag,
        )
    )

    return project_and_admit(
        projection_input,
        config,
    )
