from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from _support.admission_fixtures import projection_fixture
from elpis_reference.structural_guidance import admission as admission
from elpis_reference.structural_guidance.errors import AdmissionIntegrityViolation
from elpis_reference.structural_guidance.inactive_receipt import (
    InactiveGuidanceReceiptV2, UnavailableDetail,
)


@pytest.fixture
def gate(monkeypatch):
    monkeypatch.setattr(admission.FrozenTRM0ProposalSource, 'from_checkpoint',
                        lambda *args, **kwargs: SimpleNamespace(checkpoint_sha256='a' * 64))
    return projection_fixture(), admission.StructuralGuidanceAdmissionConfig(
        enabled=True, checkpoint_path='test-owned-checkpoint')


def result_for(ri):
    return admission.RefinerResult(final_input=ri, chosen_path=(), iterations=0,
                                  best_cost=0, stats={}, authority_granted=0)


@pytest.mark.parametrize('field', ['frozen_mask', 'writable_mask', 'invariants'])
def test_changed_contract_never_falls_back(gate, monkeypatch, field):
    def refine(self, ri):
        changed = deepcopy(ri)
        value = getattr(changed, field)
        object.__setattr__(changed, field, () if field == 'invariants' else tuple(1-x for x in value))
        assert getattr(changed, field) != getattr(ri, field)
        return result_for(changed)
    monkeypatch.setattr(admission.TRM0GuidedRefiner, 'refine', refine)
    with pytest.raises(AdmissionIntegrityViolation):
        admission.admit_projection(*gate)


def test_widened_authority_never_falls_back(gate, monkeypatch):
    monkeypatch.setattr(admission.TRM0GuidedRefiner, 'refine',
                        lambda self, ri: replace(result_for(ri), authority_granted=1))
    with pytest.raises(AdmissionIntegrityViolation, match='authority widened'):
        admission.admit_projection(*gate)


@pytest.mark.parametrize('field', ['authority_granted', 'iterations', 'best_cost'])
def test_missing_required_result_field_raises(gate, monkeypatch, field):
    def refine(self, ri):
        result = result_for(ri)
        object.__delattr__(result, field)
        return result
    monkeypatch.setattr(admission.TRM0GuidedRefiner, 'refine', refine)
    with pytest.raises(AttributeError):
        admission.admit_projection(*gate)


def test_input_mutation_raises(gate, monkeypatch):
    def refine(self, ri):
        object.__setattr__(ri, 'invariants', ())
        return result_for(ri)
    monkeypatch.setattr(admission.TRM0GuidedRefiner, 'refine', refine)
    with pytest.raises(AdmissionIntegrityViolation, match='mutated'):
        admission.admit_projection(*gate)


def test_replay_mismatch_raises(gate, monkeypatch):
    def refine(self, ri):
        result = deepcopy(ri)
        object.__setattr__(result, 'refinement_state_fingerprint', '0'*64)
        return result_for(result)
    monkeypatch.setattr(admission.TRM0GuidedRefiner, 'refine', refine)
    with pytest.raises(AdmissionIntegrityViolation, match='fingerprint mismatch'):
        admission.admit_projection(*gate)


@pytest.mark.parametrize('enabled', [False, True])
def test_projection_type_required_before_any_receipt(enabled):
    with pytest.raises(TypeError, match='ProjectionResultV1'):
        admission.admit_projection(SimpleNamespace(), admission.StructuralGuidanceAdmissionConfig(enabled=enabled))


def test_unavailable_receipt_has_only_stable_public_error(gate, monkeypatch):
    def missing(*args, **kwargs):
        raise ModuleNotFoundError('/private/host/path and arbitrary text', name='torch')
    monkeypatch.setattr(admission.FrozenTRM0ProposalSource, 'from_checkpoint', missing)
    result = admission.admit_projection(*gate)
    assert result.fallback_required and not result.admitted
    assert result.receipt.payload()['errors'] == [{
        'error_code': 'TORCH_UNAVAILABLE', 'error_class': 'AdmissionUnavailable',
        'detail': 'Optional torch runtime is unavailable.',
    }]
    assert '/private' not in str(result.receipt.payload())
    assert not {'iterations', 'best_cost', 'checkpoint_sha256', 'envelope_digest'} & result.receipt.payload().keys()


@pytest.mark.parametrize('error', [RuntimeError('unexpected'), ModuleNotFoundError('other', name='other')])
def test_unclassified_errors_propagate(gate, monkeypatch, error):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(admission.FrozenTRM0ProposalSource, 'from_checkpoint', fail)
    with pytest.raises(type(error)) as caught:
        admission.admit_projection(*gate)
    assert caught.value is error


def test_required_checkpoint_absent_is_integrity_failure(tmp_path):
    with pytest.raises(AdmissionIntegrityViolation, match='required checkpoint'):
        admission.admit_projection(projection_fixture(), admission.StructuralGuidanceAdmissionConfig(
            enabled=True, checkpoint_path=str(tmp_path / 'absent')))
