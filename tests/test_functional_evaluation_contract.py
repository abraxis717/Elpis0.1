"""Contract tests only: no candidate source is executed in this process."""
import json
from copy import deepcopy

import pytest

from elpis_reference.functional_evaluation import (
    prepare_merge_intervals_evaluation, compare_unverified_observations,
)

BAD = 'def merge_intervals(intervals):\n    return None\n'
GOOD = '''def merge_intervals(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
'''


@pytest.mark.parametrize('source', [BAD, GOOD])
def test_static_validity_never_claims_functional_success(source):
    request = prepare_merge_intervals_evaluation(source)
    assert request['static_policy']['passed']
    assert request['status'] == 'EXECUTION_BLOCKED'
    assert request['functional_pass'] is None
    assert request['execution_authorized'] is False
    assert request['authority_granted'] == 0
    assert len(request['cases']) == 7
    assert json.loads(json.dumps(request)) == request


@pytest.mark.parametrize('positive', [True, False])
def test_positive_and_negative_observation_contract(positive):
    request = prepare_merge_intervals_evaluation(GOOD if positive else BAD)
    # Explicit synthetic observations, not a claim to have run either candidate.
    outputs = [case['expected'] for case in request['cases']] if positive else [None] * 7
    report = compare_unverified_observations(request, request_digest=request['request_digest'], outputs=outputs)
    assert report['matched_cases'] == (7 if positive else 0)
    assert report['failed_cases'] == (0 if positive else 7)
    assert report['functional_pass'] is None
    assert report['execution_verified'] is False
    assert report['authority_granted'] == 0


def test_statically_rejected_source_cannot_enter_observation_comparison():
    request = prepare_merge_intervals_evaluation('def merge_intervals(xs):\n    return eval(xs)\n')
    assert request['status'] == 'STATIC_REJECTED'
    with pytest.raises(ValueError, match='statically rejected'):
        compare_unverified_observations(request, request_digest=request['request_digest'], outputs=[None] * 7)


@pytest.mark.parametrize('field,value', [('source', GOOD), ('execution_authorized', True), ('authority_granted', 1)])
def test_request_cannot_be_retargeted_or_widen_authority(field, value):
    request = prepare_merge_intervals_evaluation(BAD)
    request[field] = value
    with pytest.raises(ValueError, match='binding mismatch'):
        compare_unverified_observations(request, request_digest=request['request_digest'], outputs=[None] * 7)


def test_exact_case_coverage_and_suite_immutability():
    request = prepare_merge_intervals_evaluation(BAD)
    with pytest.raises(ValueError, match='one output per case'):
        compare_unverified_observations(request, request_digest=request['request_digest'], outputs=[])
    changed = deepcopy(request)
    changed['cases'][0]['expected'] = None
    with pytest.raises(ValueError, match='binding mismatch'):
        compare_unverified_observations(changed, request_digest=request['request_digest'], outputs=[None] * 7)
    assert prepare_merge_intervals_evaluation(BAD) == request
