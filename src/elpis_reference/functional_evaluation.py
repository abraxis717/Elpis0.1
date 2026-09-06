"""Non-executing merge_intervals evaluation contract.

Source remains untrusted data. Static acceptance grants no execution authority.
A separately authorized external runner must isolate processes, filesystem and
network and enforce the resource limits below. No such runner is installed by
this module. Observations can be compared here, but are not execution evidence.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json

from elpis.python_ast_policy import evaluate_python_ast_policy


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()


# Closed integer intervals: sort, then merge overlapping or touching endpoints.
# Each call receives one list of [start, end] pairs; result is a JSON list.
_CASES = (
    ('empty', [], []),
    ('single', [[2, 4]], [[2, 4]]),
    ('overlap', [[1, 3], [2, 6], [8, 10], [15, 18]], [[1, 6], [8, 10], [15, 18]]),
    ('touching', [[1, 4], [4, 5]], [[1, 5]]),
    ('unsorted', [[8, 10], [1, 3], [2, 6]], [[1, 6], [8, 10]]),
    ('nested', [[1, 10], [2, 3], [4, 8]], [[1, 10]]),
    ('negative_and_point', [[-3, -1], [-2, 2], [2, 2], [5, 5]], [[-3, 2], [5, 5]]),
)


def prepare_merge_intervals_evaluation(source: str) -> dict:
    """Return a digest-bound request and an honest, non-executed status."""
    if not isinstance(source, str):
        raise TypeError('candidate source must be text')
    if len(source.encode('utf-8')) > 65536:
        raise ValueError('candidate exceeds 65536 bytes')
    decision = evaluate_python_ast_policy(
        language='python', source=source, entrypoint='merge_intervals',
    )
    cases = [
        {'id': name, 'args': [intervals], 'expected': expected}
        for name, intervals, expected in _CASES
    ]
    request = {
        'schema': 'elpis.merge-intervals-evaluation-request.v1',
        'source': source,
        'source_sha256': hashlib.sha256(source.encode('utf-8')).hexdigest(),
        'entrypoint': 'merge_intervals',
        'cases': cases,
        'suite_digest': _digest(cases),
        'static_policy': asdict(decision),
        'limits': {'wall_seconds': 2, 'memory_bytes': 134217728, 'output_bytes': 65536},
        'required_isolation': ['process', 'filesystem', 'network', 'resource_limits'],
        'required_authorization': 'separate_external_grant_bound_to_request_digest',
        'execution_authorized': False,
        'authority_granted': 0,
        'status': 'EXECUTION_BLOCKED' if decision.passed else 'STATIC_REJECTED',
        'functional_pass': None,
    }
    # Normalize tuples and detach all nested values from the fixed suite.
    return json.loads(_canonical({**request, 'request_digest': _digest(request)}))


def compare_unverified_observations(request: dict, *, request_digest: str, outputs: list) -> dict:
    """Compare external JSON values without asserting that source was executed.

    The report is deliberately incapable of certifying functional correctness
    or granting authority. The external execution primitive is still required.
    """
    expected_request = prepare_merge_intervals_evaluation(request['source'])
    if _canonical(request) != _canonical(expected_request) or request_digest != expected_request['request_digest']:
        raise ValueError('evaluation request binding mismatch')
    if not request['static_policy']['passed']:
        raise ValueError('statically rejected candidate cannot be evaluated')
    if type(outputs) is not list or len(outputs) != len(request['cases']):
        raise ValueError('exactly one output per case is required')
    encoded = _canonical(outputs)
    if len(encoded.encode('utf-8')) > request['limits']['output_bytes']:
        raise ValueError('observation output limit exceeded')
    matches = [
        _canonical(output) == _canonical(case['expected'])
        for case, output in zip(request['cases'], outputs)
    ]
    return {
        'schema': 'elpis.merge-intervals-unverified-observations.v1',
        'request_digest': request_digest,
        'status': 'UNVERIFIED_OBSERVATIONS',
        'case_matches': matches,
        'matched_cases': sum(matches),
        'failed_cases': len(matches) - sum(matches),
        'execution_verified': False,
        'functional_pass': None,
        'authority_granted': 0,
    }
