"""Test operator-owned model endpoint configuration."""
from __future__ import annotations

from pathlib import Path

import pytest

from c_numpy_cortex.config import LlamaEndpoint, load_config
from c_numpy_cortex.schema import load_channel_schema


COMPONENT_ROOT = Path(__file__).resolve().parents[1]


def test_shipped_config_has_no_model_endpoint_authority():
    cfg = load_config(COMPONENT_ROOT / "config" / "cortex.toml")
    assert cfg.llama_endpoints == ()


def test_forbidden_destination_port_rejected():
    with pytest.raises(ValueError, match="forbidden destination port"):
        LlamaEndpoint(
            name="forbidden",
            url="http://127.0.0.1:8080",
        )


def test_hostname_endpoint_rejected_before_dns():
    with pytest.raises(ValueError, match="numeric loopback"):
        LlamaEndpoint(
            name="hostname",
            url="http://localhost:19001",
        )


def test_nonloopback_endpoint_rejected():
    with pytest.raises(ValueError, match="must use loopback"):
        LlamaEndpoint(
            name="remote",
            url="http://192.0.2.10:19001",
        )


def test_operator_loopback_endpoint_with_explicit_port_allowed():
    endpoint = LlamaEndpoint(
        name="operator_primary",
        url="http://127.0.0.1:19001",
    )
    assert endpoint.name == "operator_primary"


def test_shipped_schema_is_v2_and_endpoint_unconfigured():
    schema = load_channel_schema(
        COMPONENT_ROOT / "config" / "channel_schema.toml"
    )
    assert schema.schema_id == "cortex_default_v2"
    assert schema.version == "2.0"
    assert schema.digest == (
        "fb44bac1643cfa0c91fc2f4532a281ae3418a93fbc094c205a877afcc5c6abed"
    )
    assert all(
        not row.channel_id.startswith("llama.")
        for row in schema.rows
    )
