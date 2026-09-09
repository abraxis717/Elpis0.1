"""Checkpoint bytes, cache separation, and restricted-deserialization boundaries."""
import hashlib
import io
import pickle
from pathlib import Path

import pytest

from elpis_reference import model as fprm
from elpis_reference.structural_guidance._authority import core
from elpis_reference.structural_guidance.errors import AdmissionIntegrityViolation


@pytest.fixture(autouse=True)
def isolated_cache():
    core._PROPOSAL_SOURCE_CACHE.clear()
    yield
    core._PROPOSAL_SOURCE_CACHE.clear()


def test_source_hashes_and_loads_same_bytes_and_caches(tmp_path, monkeypatch):
    path = tmp_path / 'checkpoint'
    original = b'original bytes'
    path.write_bytes(original)
    calls = []

    def load(data):
        path.write_bytes(b'replacement bytes')
        calls.append(data)
        return object(), {'epoch': 3}

    monkeypatch.setattr(core, '_load_model', load)
    digest = hashlib.sha256(original).hexdigest()
    source = core.FrozenTRM0ProposalSource.from_checkpoint(path, expected_sha256=digest)
    path.unlink()
    assert core.FrozenTRM0ProposalSource.from_checkpoint(path, expected_sha256=digest) is source
    assert calls == [original]
    assert source.checkpoint_sha256 == digest
    monkeypatch.setattr(core, '_LOADER_SCHEMA', 'test-successor')
    with pytest.raises(AdmissionIntegrityViolation, match='required checkpoint'):
        core.FrozenTRM0ProposalSource.from_checkpoint(path, expected_sha256=digest)


def test_checkpoint_mismatch_never_loads(tmp_path, monkeypatch):
    path = tmp_path / 'checkpoint'
    path.write_bytes(b'wrong')
    monkeypatch.setattr(core, '_load_model', lambda data: pytest.fail('unverified bytes loaded'))
    with pytest.raises(AdmissionIntegrityViolation, match='identity mismatch'):
        core.FrozenTRM0ProposalSource.from_checkpoint(path, expected_sha256='a' * 64)


def test_cache_separates_checkpoint_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(core, '_load_model', lambda data: (object(), {'epoch': 1}))
    sources = []
    for payload in (b'first', b'second'):
        path = tmp_path / 'checkpoint'
        path.write_bytes(payload)
        sources.append(core.FrozenTRM0ProposalSource.from_checkpoint(
            path, expected_sha256=hashlib.sha256(payload).hexdigest()))
    assert sources[0] is not sources[1]


def test_fprm_load_uses_verified_bytes(tmp_path, monkeypatch):
    torch = pytest.importorskip('torch', reason='checkpoint tensor loading requires optional torch')
    path = tmp_path / 'checkpoint'
    torch.save({'weight': torch.tensor([1., 2.])}, path)
    data = path.read_bytes()
    monkeypatch.setattr(fprm, 'MODEL_SHA256', hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(fprm, 'STATE_KEY_COUNT', 1)
    monkeypatch.setattr(fprm, 'STATE_ELEMENTS', 2)
    original_load = torch.load

    def load(source, **kwargs):
        assert isinstance(source, io.BytesIO)
        assert source.getvalue() == data
        assert kwargs == {'map_location': 'cpu', 'weights_only': True}
        path.write_bytes(b'replaced after verification')
        return original_load(source, **kwargs)

    monkeypatch.setattr(torch, 'load', load)
    state = fprm._load_checkpoint_state(path)
    assert state['weight'].tolist() == [1., 2.]


class UnapprovedCheckpointObject:
    pass


def test_structural_loader_rejects_unapproved_objects():
    torch = pytest.importorskip('torch', reason='restricted deserialization requires optional torch')
    data = io.BytesIO()
    torch.save({'config': UnapprovedCheckpointObject()}, data)
    with pytest.raises(pickle.UnpicklingError, match='Unsupported global'):
        core._load_model(data.getvalue())
