"""Elpis2.1.9 checkpoint digest fixtures, recorded before loader edits."""
import pytest
from elpis_reference.model import _sha256
from elpis_reference.structural_guidance._authority.core import sha256_file


@pytest.mark.parametrize('payload, expected', [
    (b'', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    (b'abc', 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'),
])
def test_elpis219_checkpoint_sha256(tmp_path, payload, expected):
    path = tmp_path / 'checkpoint'
    path.write_bytes(payload)
    assert sha256_file(path) == expected
    assert _sha256(path) == expected
