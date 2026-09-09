"""Fixed projection inputs shared by historical and successor digest fixtures."""
from elpis_reference.structural_guidance._authority.c2r6p0.contracts import ProjectionInputV1
from elpis_reference.structural_guidance._authority.elpis_p0.semantic_ir import (
    SemanticOperationV1, SemanticRelationV1, build_semantic_request_v1,
)


SPECS = (
    ('A', ()),
    ('ABC', (('A', 'route', 'B'), ('C', 'route', 'B'))),
    ('ABCDEFGHI', ()),
)


def projection_input(spec):
    operations, relations = spec
    request = build_semantic_request_v1(
        request_id='allocator-golden', entities=(),
        operations=tuple(SemanticOperationV1(op, 'step') for op in operations),
        relations=tuple(SemanticRelationV1(f'r{i}', a, kind, b)
                        for i, (a, kind, b) in enumerate(relations)),
    )
    return ProjectionInputV1.from_signed(request)
