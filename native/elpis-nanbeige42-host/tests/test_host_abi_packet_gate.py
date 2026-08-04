import pytest

from elpis_nanbeige42_host.errors import RuntimeQualificationRequired
from elpis_nanbeige42_host.executor_policy import default_policy
from elpis_nanbeige42_host.hooks import default_registry
from elpis_nanbeige42_host.host_abi import ElpisNanbeige42HostABI
from elpis_nanbeige42_host.manifest import build_manifest
from elpis_nanbeige42_host.packet_derivation import (
    FrozenV01PacketDerivation,
    default_packet_derivation_policy,
)
from elpis_nanbeige42_host.schemas import ControlMode


class StubHost(ElpisNanbeige42HostABI):
    def load(self): pass
    def validate_runtime(self): raise NotImplementedError
    def prepare_tick(self, tick): return tick
    def run_tick(self, prepared_tick): return prepared_tick
    def parse_action(self, generated_output): raise NotImplementedError
    def emit_evidence(self, execution): raise NotImplementedError
    def close(self): pass


def host():
    hooks = default_registry()
    executor = default_policy()
    packet_policy = default_packet_derivation_policy()
    instance = StubHost()
    instance.packet_derivation = FrozenV01PacketDerivation(packet_policy)
    instance.manifest = build_manifest(
        hook_registry_digest=hooks.registry_digest,
        executor_policy_digest=executor.policy_digest,
        packet_derivation_policy_digest=packet_policy.policy_digest,
    )
    return instance


def test_packet_contract_does_not_enable_actuation_before_p14_1():
    instance = host()
    instance.assert_mode_enabled(ControlMode.OBSERVE)
    with pytest.raises(RuntimeQualificationRequired):
        instance.assert_mode_enabled(ControlMode.DOCK)
