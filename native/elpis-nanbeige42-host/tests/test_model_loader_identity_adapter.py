from pathlib import Path

import pytest

from elpis_nanbeige42_host.digest import canonical_digest
from elpis_nanbeige42_host.errors import ModelIdentityDrift
from elpis_nanbeige42_host.model_loader import _identity_record


def test_config_identity_adapter_normalizes_nested_non_string_keys():
    raw = {
        "id2label": {0: "zero", 1: "one"},
        "nested": {2: {3: "three"}},
    }
    normalized = _identity_record(raw)
    assert normalized == {
        "id2label": {"0": "zero", "1": "one"},
        "nested": {"2": {"3": "three"}},
    }
    assert canonical_digest(normalized).startswith("sha256:")


def test_config_identity_adapter_rejects_string_key_collisions():
    with pytest.raises(ModelIdentityDrift, match="key collision"):
        _identity_record({1: "integer", "1": "string"})


def test_model_loader_adapts_config_before_canonical_digest():
    source = Path(__file__).parents[1] / "src/elpis_nanbeige42_host/model_loader.py"
    text = source.read_text(encoding="utf-8")
    assert 'canonical_digest(_identity_record(model.config.to_dict()))' in text
    assert 'canonical_digest(model.config.to_dict())' not in text
