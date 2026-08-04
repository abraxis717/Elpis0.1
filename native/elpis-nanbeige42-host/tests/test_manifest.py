from pathlib import Path

from elpis_nanbeige42_host.executor_policy import default_policy
from elpis_nanbeige42_host.hooks import default_registry
from elpis_nanbeige42_host.manifest import build_manifest
from elpis_nanbeige42_host.packet_derivation import default_packet_derivation_policy
from elpis_nanbeige42_host.schemas import ControlMode


def test_p14_0b_manifest_freezes_contract_but_not_runtime():
    hooks = default_registry()
    policy = default_policy()
    packet_policy = default_packet_derivation_policy()
    manifest = build_manifest(
        hook_registry_digest=hooks.registry_digest,
        executor_policy_digest=policy.policy_digest,
        packet_derivation_policy_digest=packet_policy.policy_digest,
    )
    assert manifest.enabled_control_modes == (ControlMode.NONE, ControlMode.OBSERVE)
    assert manifest.packet_derivation_status == "CONTRACT_FROZEN_DIAGNOSTIC_PRODUCERS_ONLY"
    assert manifest.grid81_packet_derivation == "FORBIDDEN_UNLESS_SEPARATELY_QUALIFIED"
    assert manifest.registry_packet_derivation == "RESERVED_NOT_IMPLEMENTED"
    assert manifest.model_runtime_qualified is False
    assert manifest.coding_utility_status == "UNDEMONSTRATED"


def test_runtime_package_does_not_import_phase_scripts():
    source_root = Path(__file__).parents[1] / "src" / "elpis_nanbeige42_host"
    for path in source_root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "experiments.markov_header" not in text
        assert "p13_phase4" not in text
