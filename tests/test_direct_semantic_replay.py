"""Replay semantics stay stable while bearer capabilities remain ephemeral."""
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_p0_validator_ingress import rejected, diagnose
from elpis_p0.lineage_authority import P0LineageAuthorityError, P0LineageAuthorityReceiptV1

ROOT = Path(__file__).resolve().parents[1]


def run_direct():
    _, ingress, result, authorized, trace = rejected('direct-semantic-replay')
    diagnostic = diagnose(ingress, result, authorized, trace)
    residual = diagnostic.to_task_residual()
    resolved = trace.reverse_trace_index().resolve(residual)
    with pytest.raises(P0LineageAuthorityError, match='not active'):
        diagnose(ingress, result, authorized, trace)
    return {
        'semantic': {
            'p0': asdict(result),
            'diagnostic': diagnostic.payload(),
            'diagnostic_digest': diagnostic.digest(),
            'residual': residual.payload(),
            'residual_digest': residual.digest(),
            'resolved': asdict(resolved),
        },
        'security': asdict(authorized.receipt),
    }


def fresh(seed):
    env = dict(os.environ, PYTHONHASHSEED=seed)
    env['PYTHONPATH'] = str(ROOT / 'tests') + os.pathsep + env.get('PYTHONPATH', '')
    code = 'import json; from test_direct_semantic_replay import run_direct; print(json.dumps(run_direct(), sort_keys=True))'
    return json.loads(subprocess.check_output([sys.executable, '-c', code], cwd=ROOT, env=env))


def test_fresh_process_semantics_equal_security_distinct():
    outputs = [fresh(seed) for seed in ('1', '77', 'random')]
    semantic = [json.dumps(o['semantic'], sort_keys=True, separators=(',', ':')).encode() for o in outputs]
    assert semantic[0] == semantic[1] == semantic[2]
    for field in ('authority_instance_id', 'capability_id', 'receipt_digest'):
        assert len({o['security'][field] for o in outputs}) == 3


def test_foreign_process_receipt_cannot_authorize():
    foreign = fresh('2')['security']
    _, ingress, result, authorized, trace = rejected('direct-semantic-replay')
    substituted = replace(authorized, receipt=P0LineageAuthorityReceiptV1(**foreign))
    with pytest.raises(P0LineageAuthorityError, match='another authority instance'):
        diagnose(ingress, result, substituted, trace)
    diagnose(ingress, result, authorized, trace)


def test_security_binding_retained_and_bound_to_semantics():
    _, ingress, result, authorized, trace = rejected('direct-semantic-replay')
    diagnostic = diagnose(ingress, result, authorized, trace)
    binding = diagnostic.security_binding
    assert binding.authority_instance_id == authorized.receipt.authority_instance_id
    assert binding.capability_id == authorized.receipt.capability_id
    assert binding.receipt_digest == authorized.receipt.receipt_digest
    assert binding.lineage_digest == authorized.lineage.lineage_digest
    assert binding.diagnostic_digest == diagnostic.digest()
    assert binding.consumption_digest
    assert 'security_binding' not in diagnostic.payload()
    with pytest.raises(ValueError, match='another diagnostic'):
        replace(diagnostic, details_digest='0' * 64)
    # The semantic replay record is not an authorization bearer.
    with pytest.raises((AttributeError, TypeError)):
        diagnose(ingress, result, replace(diagnostic, security_binding=None), trace)
