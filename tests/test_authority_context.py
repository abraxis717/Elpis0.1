"""Caller issuance, fixed stage consumers, and request-boundary expiry.

Admission/topology are fixed fixtures here. All five downstream production
stages, capability state machines, and static validation execute normally.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, replace
import hashlib
import inspect
from types import SimpleNamespace

import pytest

from elpis_reference.structural_guidance import runtime
from elpis_reference.structural_guidance import (
    materialization_authority, planning_authority, decoding_authority,
    source_emission_authority, validation_authority,
)
from elpis_reference.structural_guidance.resolved import ResolvedStructuralTopologyV1
from elpis_reference.structural_guidance._authority.elpis_p0.semantic_ir import (
    SemanticEntityV1, SemanticOperationV1, build_semantic_request_v1,
)


STAGES = (
    ('materialization', materialization_authority._ResolvedTopologyMaterializationAuthority),
    ('planning', planning_authority._PlanningAuthority),
    ('decoding', decoding_authority._DecodingAuthority),
    ('source_emission', source_emission_authority._SourceEmissionAuthority),
    ('validation', validation_authority._ValidationAuthority),
)


@dataclass(frozen=True)
class _Schema:
    schema_digest: str


def _topology():
    unsigned = ResolvedStructuralTopologyV1(
        schema='elpis.structural-guidance.resolved-topology.v1',
        grid81=(0,) * 81, frozen_mask=(0,) * 81, writable_mask=(1,) * 81,
        invariants=(), lane_bindings=(), structural_schema=_Schema('1' * 64),
        declared_features=(0,) * 529, active_residual=(0,) * 529,
        residual_ids=(), structural_bindings_json='{}',
        structural_bindings_digest=hashlib.sha256(b'{}').hexdigest(),
        semantic_input_digest='2' * 64, rule_set_digest='3' * 64,
        projection_structural_schema_digest='4' * 64,
        refiner_structural_schema_digest='5' * 64,
        projection_digest='6' * 64, projection_trace_digest='7' * 64,
        projection_fingerprint='8' * 64, refinement_state_fingerprint='9' * 64,
        refiner_input_digest='a' * 64, envelope_digest='b' * 64,
        receipt_digest='c' * 64, checkpoint_sha256='d' * 64,
        best_cost=0, iterations=0, applied_moves=0, authority_granted=0,
        topology_digest='',
    )
    result = replace(unsigned, topology_digest=unsigned.topology_digest_computed())
    result.validate()
    return result


def _context(*, owners=None, overrides=None, calls=None):
    owners = owners if owners is not None else {name: cls() for name, cls in STAGES}
    callbacks = {}
    for name, owner in owners.items():
        def issue(*args, _name=name, _owner=owner, **kwargs):
            if calls is not None:
                calls[_name] = (args, kwargs)
            intent = _owner._precommit_from_owner(*args, **kwargs)
            return _owner._reveal_from_owner(intent)
        callbacks['issue_' + name] = issue
    callbacks.update(overrides or {})
    return runtime.AuthorityContext(**owners, **callbacks), owners


def _run(context):
    request = build_semantic_request_v1(
        request_id='caller-owned',
        entities=(SemanticEntityV1('value', 'value', 'one', 'int'),),
        operations=(SemanticOperationV1('return_value', 'return', output_entity_ids=('value',)),),
        output_entity_ids=('value',),
    )
    return runtime.run_structural_guidance_runtime(
        request, runtime.StructuralGuidanceAdmissionConfig(enabled=True),
        authorities=context, request_id='caller-owned', prompt='write typed tests',
        entrypoint='solve', parameters=('value',),
        decoder_hints=(('body', 'return None'),),
    )


@pytest.fixture
def fixed_admission(monkeypatch):
    monkeypatch.setattr(runtime, 'project_semantic_request_and_admit',
                        lambda *a, **k: SimpleNamespace(fallback_required=False, admitted=True))
    monkeypatch.setattr(runtime, 'build_resolved_structural_topology', lambda p: _topology())


@pytest.fixture
def stage_inputs(fixed_admission):
    calls = {}
    context, _ = _context(calls=calls)
    result = _run(context)
    assert result.validation_passed and result.validation_code == 'AST_VALID'
    assert set(calls) == {name for name, _ in STAGES}
    return calls


def test_runtime_requires_caller_authority():
    parameter = inspect.signature(runtime.run_structural_guidance_runtime).parameters['authorities']
    assert parameter.default is inspect.Parameter.empty
    with pytest.raises(TypeError, match='authorities'):
        runtime.run_structural_guidance_runtime(None, None, request_id='r', prompt='p')
    with pytest.raises(TypeError, match='issue_materialization'):
        runtime.AuthorityContext(**{name: cls() for name, cls in STAGES})


def test_runtime_never_constructs_or_issues_authority(fixed_admission, monkeypatch):
    calls = {}
    context, _ = _context(calls=calls)
    def forbidden(*args, **kwargs):
        raise AssertionError('execution attempted to construct its own authority')
    for _, cls in STAGES:
        monkeypatch.setattr(cls, '__init__', forbidden)
    result = _run(context)
    assert result.schema == 'elpis.structural-guidance.runtime-result.v2'
    assert result.validate_digest() and result.authority_granted == 0
    assert result.validation_code == 'AST_VALID' and not result.execution_authorized
    assert list(calls) == [name for name, _ in STAGES]
    tree = ast.parse(inspect.getsource(runtime))
    assert not any(isinstance(n, ast.Attribute) and n.attr in
                   {'_precommit_from_owner', '_reveal_from_owner'} for n in ast.walk(tree))


@pytest.mark.parametrize('stage', [name for name, _ in STAGES])
def test_context_b_cannot_consume_context_a(stage, stage_inputs):
    a, owners_a = _context()
    args, kwargs = stage_inputs[stage]
    owner_a = owners_a[stage]
    intent = owner_a._precommit_from_owner(*args, **kwargs)
    handle = owner_a._reveal_from_owner(intent)
    b, _ = _context(overrides={'issue_' + stage: lambda *a, **k: handle})
    with pytest.raises(ValueError, match='another.*authority|another .*instance'):
        with b.boundary():
            getattr(b, 'consume_' + stage)(*args, **kwargs)
    # Rejection under B did not spend the genuine capability under A.
    consumption = owner_a._consume_from_owner(handle)
    assert consumption.receipt_digest == handle.receipt.receipt_digest
    with a.boundary():
        pass


@pytest.mark.parametrize('stage', [name for name, _ in STAGES])
@pytest.mark.parametrize('terminal', ['success', 'invalid_request', 'issuer_refusal'])
def test_unconsumed_and_unrevealed_handles_expire(stage, terminal, stage_inputs):
    overrides = {}
    if terminal == 'issuer_refusal':
        def refuse(*args, **kwargs):
            raise PermissionError('owner declined materialization')
        overrides['issue_materialization'] = refuse
    context, owners = _context(overrides=overrides)
    owner = owners[stage]
    args, kwargs = stage_inputs[stage]
    extra = dict(kwargs)
    version = next(k for k in extra if k.endswith('_version'))
    extra[version] = 'unconsumed-v2'
    handle = owner._reveal_from_owner(owner._precommit_from_owner(*args, **extra))
    extra[version] = 'unrevealed-v2'
    pending = owner._precommit_from_owner(*args, **extra)
    if terminal == 'success':
        assert _run(context).validation_passed
    elif terminal == 'invalid_request':
        with pytest.raises(TypeError, match='semantic_request'):
            runtime.run_structural_guidance_runtime(
                None, None, authorities=context, request_id='r', prompt='p',
            )
    else:
        with pytest.raises(PermissionError, match='owner declined materialization'):
            _run(context)
    with pytest.raises(ValueError, match='boundary is closed'):
        owner._consume_from_owner(handle)
    with pytest.raises(ValueError, match='boundary is closed'):
        owner._reveal_from_owner(pending)
    with pytest.raises(runtime.StructuralGuidanceRuntimeError, match='already been used'):
        _run(context)


@pytest.mark.parametrize('stage', [name for name, _ in STAGES])
def test_successor_intent_uses_content_not_object_address(stage, stage_inputs):
    cls = dict(STAGES)[stage]
    owner = cls()
    args, kwargs = stage_inputs[stage]
    intent = owner._precommit_from_owner(*args, **kwargs)
    assert intent.schema.endswith('.v2')
    with pytest.raises(ValueError, match='already precommitted'):
        owner._precommit_from_owner(*args, **kwargs)
    equivalent = replace(intent)
    assert equivalent is not intent
    handle = owner._reveal_from_owner(equivalent)
    assert handle.receipt.schema.endswith('.v2')
    consumption = owner._consume_from_owner(handle)
    assert consumption.schema.endswith('.v2')
    with pytest.raises(ValueError, match='not active'):
        owner._consume_from_owner(handle)
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == 'id' for n in ast.walk(ast.parse(inspect.getsource(cls))))


def test_owner_cannot_be_shared_between_contexts():
    a, owners = _context()
    with pytest.raises(ValueError, match='already bound'):
        _context(owners=owners)
    with a.boundary():
        pass


def test_consumption_outside_runtime_boundary_is_rejected():
    context, _ = _context()
    with pytest.raises(runtime.StructuralGuidanceRuntimeError, match='active runtime boundary'):
        context.consume_materialization()
    with context.boundary():
        pass

@pytest.mark.parametrize('stage', [name for name, _ in STAGES])
def test_trusted_owner_reissue_is_distinct_one_shot_capability(stage, stage_inputs):
    # Repeated semantic content requires a new explicit trusted-owner issuance.
    # One-shot uniqueness is per capability/runtime boundary, not a global
    # prohibition on the trusted owner deliberately issuing the same content twice.
    cls = dict(STAGES)[stage]
    owner = cls()
    args, kwargs = stage_inputs[stage]

    first_intent = owner._precommit_from_owner(*args, **kwargs)
    first = owner._reveal_from_owner(first_intent)

    second_intent = owner._precommit_from_owner(*args, **kwargs)
    assert second_intent.intent_digest == first_intent.intent_digest
    second = owner._reveal_from_owner(second_intent)

    assert second.receipt.capability_id != first.receipt.capability_id
    assert second.receipt.receipt_digest != first.receipt.receipt_digest

    first_consumption = owner._consume_from_owner(first)
    second_consumption = owner._consume_from_owner(second)
    assert first_consumption.consumption_digest != second_consumption.consumption_digest

    with pytest.raises(ValueError, match='not active'):
        owner._consume_from_owner(first)
    with pytest.raises(ValueError, match='not active'):
        owner._consume_from_owner(second)
