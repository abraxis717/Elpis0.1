"""Only this test imports the actual shipped Elpis allocator."""
from dataclasses import asdict
from pathlib import Path
import sys
from contract import canonical, digest
from guards import TARGET, check
from certificate_validator import validate_result


def run(solver):
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / 'src'))
    from elpis_reference.structural_guidance._authority.elpis_p0.semantic_ir import (
        SemanticOperationV1, SemanticRelationV1, build_semantic_request_v1,
        semantic_request_payload)
    from elpis_reference.structural_guidance._authority.c2r6p0.contracts import ProjectionInputV1
    from elpis_reference.structural_guidance._authority.c2r6p0.projector import project
    request = build_semantic_request_v1(
        request_id='FuryanFanIn', entities=(),
        operations=tuple(SemanticOperationV1(o, 'step') for o in 'ABC'),
        relations=(SemanticRelationV1('rAC', 'A', 'route', 'C'),
                   SemanticRelationV1('rBC', 'B', 'route', 'C')))
    request.validate()
    payload = semantic_request_payload(request)
    # Explicit audited projection to Furyan; not an automatic P0 translator.
    mapped = {'operations': [o['operation_id'] for o in payload['operations']],
              'edges': [[r['predicate'], r['source_id'], r['target_id']] for r in payload['relations']],
              'tails': []}
    check(mapped == TARGET, 'production_input_correspondence')
    result = project(ProjectionInputV1.from_signed(request))
    oracle = solver.solve(mapped)
    check(oracle['status'] == 'SAT', 'production_target_oracle_sat')
    validate_result(mapped, oracle)
    check(result.status == 'DECOMPOSITION_REQUIRED', 'production_decomposition')
    check(result.error.rule == 'R9.ROUTE_RANK', 'production_route_rule')
    check(result.error.detail['reason'] == 'no_free_rank_for_route_in_consumer_lane', 'production_route_capacity_reason')
    check(result.error.detail['rank_span'] == [1, 1], 'production_target_interval')
    # Also embed the independent feasible certificate in the shipped residual
    # vocabulary, demonstrating the shifted ranks satisfy its core invariants.
    from elpis_reference.structural_guidance._authority.elpis_p0.contracts import BasisToken
    from elpis_reference.structural_guidance._authority.elpis_p0.structural_residual import StructuralInvariantV1, residual
    grid = [0]*81
    lane = dict(zip('ABC', range(3)))
    for op, rank in oracle['certificate']['operations'].items():
        grid[9*rank+lane[op]] = int(BasisToken.OUTPUT if op == 'C' else BasisToken.INPUT)
    for locus in oracle['certificate']['loci']:
        grid[9*locus['rank']+lane[locus['lane']]] = int(BasisToken.ROUTE)
    grid[80] = int(BasisToken.RESOLUTION)
    invariants = [StructuralInvariantV1(f'occupy.{o}', 'LANE_SINGLE_OCCUPANCY', (lane[o],)) for o in 'ABC']
    invariants += [StructuralInvariantV1(f'route.{a}.C', 'CROSS_LANE_ROUTE', (lane[a], lane['C'])) for a in 'AB']
    invariants += [StructuralInvariantV1(f'precedes.{a}.C', 'PRECEDES', (lane[a], lane['C'])) for a in 'AB']
    invariants.append(StructuralInvariantV1('terminal', 'TERMINAL_RESOLUTION', ()))
    check(residual(tuple(grid), tuple(invariants)) == (), 'production_residual_embedding')
    return {'status': 'PRODUCTION_ALLOCATOR_COUNTEREXAMPLE_CONFIRMED',
            'scope': 'shipped structural-guidance C2R6-P0 allocation strategy, audited core subset',
            'production_input_utf8': canonical(asdict(request)).decode(),
            'production_input_sha256': digest(asdict(request)),
            'production_semantic_digest': request.digest,
            'furyan_input_utf8': canonical(mapped).decode(), 'furyan_input_digest': digest(mapped),
            'production_result': asdict(result), 'production_diagnostic': asdict(result.error),
            'furyan_result': oracle, 'validator_result': 'PASS',
            'shifted_certificate_grid81': grid, 'shifted_grid_production_residual': []}
