"""Independent differential qualification; frozen Furyan is test-only evidence."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from elpis_reference.structural_guidance._authority.c2r6p0.contracts import ProjectionInputV1
from elpis_reference.structural_guidance._authority.c2r6p0.projector import project
from elpis_reference.structural_guidance._authority.elpis_p0.semantic_ir import (
    SemanticOperationV1, SemanticRelationV1, SemanticDependencyV1,
    build_semantic_request_v1,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'components/FuryanLocusOracle'))
sys.path.insert(0, str(ROOT / 'components/FuryanLocusOracle/tests'))
import FuryanLocusOracle as oracle
import certificate_validator
import contract
import corpus


def production(raw):
    request = build_semantic_request_v1(
        request_id='joint', entities=(),
        operations=tuple(SemanticOperationV1(o, 'step') for o in raw['operations']),
        relations=tuple(SemanticRelationV1(f'r{i}', a, k, b)
                        for i, (k, a, b) in enumerate(raw['edges']) if k != 'precedes'),
        dependencies=tuple(SemanticDependencyV1(f'd{i}', a, b)
                           for i, (k, a, b) in enumerate(raw['edges']) if k == 'precedes'),
    )
    return project(ProjectionInputV1.from_signed(request))


@pytest.mark.parametrize('edges', [
    [('route', 'A', 'B'), ('route', 'C', 'B')],
    [('state_feeds', 'A', 'B'), ('state_feeds', 'A', 'C')],
])
def test_qualified_counterexamples(edges):
    raw = corpus.instance('ABC', edges)
    expected = oracle.solve(raw)
    certificate_validator.validate_result(raw, expected)
    result = production(raw)
    assert result.status == 'PROJECTED', result.error
    assert {o.semantic_id: o.rank for o in result.bindings.op_bindings} == expected['certificate']['operations']
    assert not result.residual_ids


def assignment(raw):
    from elpis_reference.structural_guidance._authority.c2r6p0.allocator import _joint_assignment
    edges = [(a, b, 1 if k == 'precedes' else 2) for k, a, b in raw['edges']]
    demands = [(f'edge:{k}:{a}:{b}', b if k == 'route' else a, a, b)
               for k, a, b in raw['edges'] if k != 'precedes']
    demands += [(f"tail:{t['id']}", t['lane'], t['after'], None) for t in raw['tails']]
    result = _joint_assignment(raw['operations'], edges, demands)
    assert result.status != 'SEARCH_BUDGET_EXHAUSTED', raw
    return result.assignments[0] if result.status == 'SAT' else None


def check_differential(raw, *, project_core=False):
    expected = oracle.solve(raw)
    found = assignment(raw)
    assert (found is not None) == (expected['status'] == 'SAT'), raw
    if found is not None:
        certificate_validator.validate_result(raw, expected)
        assert found[0] == expected['certificate']['operations'], raw
        assert found[1] == {l['id']: l['rank'] for l in expected['certificate']['loci']}, raw
    if project_core:
        from elpis_reference.structural_guidance._authority.elpis_p0.semantic_ir import P0SemanticRequestContractError
        try:
            result = production(raw)
        except P0SemanticRequestContractError as exc:
            # The typed ingress rejects cyclic precedes graphs even before allocation.
            assert 'acyclic' in str(exc) and expected['status'] == 'UNSAT', raw
        else:
            assert (result.status == 'PROJECTED') == (expected['status'] == 'SAT'), (raw, result.error)
            if result.status == 'PROJECTED':
                assert not result.residual_ids
                assert {o.semantic_id: o.rank for o in result.bindings.op_bindings} == found[0]
                # Independently validate the actual emitted loci, including
                # distinct witnesses; production residuals alone are weaker.
                by_id = {e.semantic_id: e for e in result.bindings.edge_bindings}
                loci = []
                for i, (kind, a, b) in enumerate(raw['edges']):
                    if kind == 'precedes':
                        continue
                    edge = by_id[f'r{i}']
                    key = 'route' if kind == 'route' else 'memory'
                    locus_cell = edge.payload[f'{key}_cell']
                    owner = b if kind == 'route' else a
                    op = next(o for o in result.bindings.op_bindings if o.semantic_id == owner)
                    assert locus_cell % 9 == op.lane
                    assert result.grid81[locus_cell] == (7 if kind == 'route' else 4)
                    loci.append({'id': f'edge:{kind}:{a}:{b}',
                                 'kind': 'ROUTE' if kind == 'route' else 'MEMORY',
                                 'lane': owner, 'rank': locus_cell // 9})
                certificate = {**expected['certificate'], 'operations': found[0],
                               'loci': sorted(loci, key=lambda x: x['id'])}
                certificate_validator.validate(raw, certificate, contract.certificate_digest(certificate))
    return expected['status']


def test_exhaustive_core_differential():
    counts = {'SAT': 0, 'UNSAT': 0}
    labeled = 0
    for n in (1, 2, 3):
        for raw, orbit in corpus.canonical_core(n):
            counts[check_differential(raw, project_core=True)] += 1
            labeled += orbit
    assert counts == {'SAT': 465, 'UNSAT': 43540}
    assert labeled == 262209


def test_tails_and_larger_audited_instances():
    for raw in (*corpus.single_tails(), *corpus.small_tail_minimality(), *corpus.stress()):
        check_differential(raw)


def test_fresh_process_projection_identity():
    script = '''
import json
from dataclasses import asdict
from test_joint_allocator import production, corpus
raw = corpus.instance('ABC', [('route', 'A', 'B'), ('route', 'C', 'B')])
print(json.dumps(asdict(production(raw)), sort_keys=True, separators=(',', ':')))
'''
    outputs = []
    for seed in ('1', '97', 'random'):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        env['PYTHONPATH'] = str(ROOT / 'tests') + os.pathsep + env.get('PYTHONPATH', '')
        outputs.append(subprocess.check_output([sys.executable, '-c', script], cwd=ROOT, env=env))
    assert outputs[0] == outputs[1] == outputs[2]


def test_production_executes_with_furyan_imports_blocked():
    script = '''
import importlib.abc, sys
class NoOracle(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'FuryanLocusOracle', 'contract', 'corpus', 'certificate_validator'}:
            raise AssertionError('production tried to load Furyan')
sys.meta_path.insert(0, NoOracle())
from elpis_reference.structural_guidance._authority.c2r6p0.projector import project
from elpis_reference.structural_guidance._authority.c2r6p0.contracts import ProjectionInputV1
from elpis_reference.structural_guidance._authority.elpis_p0.semantic_ir import (
    SemanticOperationV1, SemanticRelationV1, build_semantic_request_v1)
request = build_semantic_request_v1(request_id='independent', entities=(),
    operations=tuple(SemanticOperationV1(o, 'step') for o in 'ABC'),
    relations=(SemanticRelationV1('r1', 'A', 'route', 'B'),
               SemanticRelationV1('r2', 'C', 'route', 'B')))
assert project(ProjectionInputV1.from_signed(request)).status == 'PROJECTED'
assert not any('FuryanLocusOracle' in str(getattr(m, '__file__', '')) for m in sys.modules.values())
'''
    subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=os.environ.copy(), check=True)
