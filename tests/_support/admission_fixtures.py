"""Real production input fixtures for admission boundary qualification."""
from elpis_reference.structural_guidance._authority.c2r6p0.contracts import ProjectionInputV1
from elpis_reference.structural_guidance._authority.c2r6p0.projector import project
from elpis_reference.structural_guidance._authority.elpis_p0.semantic_ir import (
    SemanticOperationV1, build_semantic_request_v1,
)


def projection_fixture():
    request = build_semantic_request_v1(
        request_id='admission-fixture', entities=(),
        operations=(SemanticOperationV1('A', 'step'),),
    )
    return project(ProjectionInputV1.from_signed(request))
