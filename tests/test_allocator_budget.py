from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from _support.allocator_fixtures import SPECS, projection_input
from elpis_reference.structural_guidance._authority.c2r6p0.allocator import _joint_assignment, SearchStatus
from elpis_reference.structural_guidance._authority.c2r6p0.rules import Ruleset, load_ruleset, MAX_NODE_BUDGET
from elpis_reference.structural_guidance._authority.c2r6p0.projector import project
from elpis_reference.structural_guidance._authority.c2r6p0.contracts import ProjectionSearchBudgetExhausted
from elpis_reference.structural_guidance.admission import admit_projection

FIXTURES = Path(__file__).parent / 'fixtures'


def test_historical_exact_digest_fixtures():
    data = (FIXTURES / 'allocator_elpis219.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == 'a5647365a046113a7dee32b54651d4a2ad4eab0d133736339b5849a0724c18e6'
    historical = json.loads(data)
    assert Ruleset(**historical['ruleset']).digest() == historical['ruleset_digest']
    for result in historical['projections']:
        expected = result.pop('projection_digest')
        encoded = json.dumps(result, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
        assert hashlib.sha256(b'elpis.c2r6p0.projection-result.v1\0' + encoded).hexdigest() == expected
        trace = result['trace']
        payload = {'schema': trace['schema'], 'semantic_input_digest': result['semantic_input_digest'],
                   'rule_set_digest': result['rule_set_digest'], 'events': trace['events']}
        assert hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest() == trace['trace_digest']


def test_successor_exact_digest_fixtures():
    expected = json.loads((FIXTURES / 'allocator_successor_v2.json').read_text())
    rules = load_ruleset()
    assert rules.digest() == expected['ruleset_digest']
    assert [project(projection_input(spec), rules).to_dict() for spec in SPECS] == expected['projections']
    assert project(projection_input(SPECS[0]), replace(rules, node_budget=1)).to_dict() == expected['exhausted']


def test_budget_is_not_unsat_or_decomposition():
    cut = _joint_assignment(('A',), (), (), node_budget=1)
    assert cut.status is SearchStatus.SEARCH_BUDGET_EXHAUSTED
    assert cut.search_entries == 1 and cut.assignments == ()
    sat = _joint_assignment(('A',), (), (), node_budget=2)
    assert sat.status is SearchStatus.SAT and sat.search_entries == 2
    unsat = _joint_assignment(('A', 'B'), [('A', 'B', 9)], (), node_budget=1)
    assert unsat.status is SearchStatus.UNSAT and unsat.search_entries == 1


def test_exhaustion_survives_projection_and_admission():
    result = project(projection_input(SPECS[0]), replace(load_ruleset(), node_budget=1))
    assert result.status == result.error.status == 'SEARCH_BUDGET_EXHAUSTED'
    assert result.error.code == 'ERR.SEARCH_BUDGET_EXHAUSTED'
    assert result.trace.node_budget == result.trace.search_entries[0] == 1
    assert 'grid81' not in result.to_dict()
    with pytest.raises(ProjectionSearchBudgetExhausted) as caught:
        admit_projection(result)
    assert caught.value.projection is result
    assert caught.value.status == 'SEARCH_BUDGET_EXHAUSTED'


@pytest.mark.parametrize('budget', [0, -1, True, 1.5, MAX_NODE_BUDGET + 1, 10**100])
def test_ruleset_enforces_finite_maximum(budget):
    with pytest.raises(ValueError):
        replace(load_ruleset(), node_budget=budget)
    with pytest.raises(ValueError):
        _joint_assignment(('A',), (), (), node_budget=budget)


def test_old_ruleset_cannot_restore_unbounded_production_search():
    fixture = json.loads((FIXTURES / 'allocator_elpis219.json').read_text())
    with pytest.raises(TypeError, match='BudgetedRulesetV2'):
        project(projection_input(SPECS[0]), Ruleset(**fixture['ruleset']))


def test_budget_changes_rules_and_trace_identity_only_not_witness():
    pin = projection_input(SPECS[1])
    a = project(pin, load_ruleset())
    b = project(pin, replace(load_ruleset(), node_budget=85))
    assert a.grid81 == b.grid81 and a.bindings == b.bindings
    assert a.rule_set_digest != b.rule_set_digest
    assert a.trace.trace_digest != b.trace.trace_digest
    assert a.projection_digest != b.projection_digest


def test_composition_preserves_exhaustion(monkeypatch):
    from elpis_reference.structural_guidance import hook
    result = project(projection_input(SPECS[0]), replace(load_ruleset(), node_budget=1))
    monkeypatch.setattr(hook, 'project', lambda pin: result)
    with pytest.raises(ProjectionSearchBudgetExhausted) as caught:
        hook.project_and_admit(projection_input(SPECS[0]))
    assert caught.value.projection is result
