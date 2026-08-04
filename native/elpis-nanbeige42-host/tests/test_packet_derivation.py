import pytest

from elpis_nanbeige42_host.digest import validate_digest
from elpis_nanbeige42_host.errors import (
    Grid81DerivationForbidden,
    PacketDerivationInputMismatch,
    RegistryDerivationUnavailable,
)
from elpis_nanbeige42_host.packet_derivation import (
    CodingTickSeed,
    ExplicitControlVector,
    FrozenV01PacketDerivation,
    PacketDerivationMethod,
    PacketDerivationRequest,
    default_packet_derivation_policy,
    finalize_tick,
)
from elpis_nanbeige42_host.schemas import (
    CodingTask,
    ControlMode,
    GenerationShape,
    WorkspaceState,
)


def seed(mode: ControlMode = ControlMode.DOCK) -> CodingTickSeed:
    return CodingTickSeed(
        schema="elpis.nanbeige42.coding-tick-seed.v1",
        tick_id="tick-1",
        parent_tick_id=None,
        logical_time=7,
        task=CodingTask(
            task_id="task-1",
            objective="repair the focused fixture",
            constraints=("no network",),
            acceptance_condition_ids=("pytest-fixture",),
            prohibited_action_ids=("git-push",),
        ),
        workspace=WorkspaceState(
            repo_root="/mnt/primesauce/Elpis_Canon",
            branch="p14",
            head_commit="deadbeef",
            tracked_file_manifest_digest="sha256:files",
            dirty_patch_digest=None,
            relevant_file_ids=("fixture.py",),
            recent_result_ids=(),
        ),
        evidence=(),
        control_mode=mode,
        generation_shape=GenerationShape(2, 32, 1),
    ).with_digest()


def explicit_vector() -> ExplicitControlVector:
    return ExplicitControlVector(
        schema="elpis.explicit-control-vector.v1",
        common=0.125,
        structural=tuple((i - 10) / 10 for i in range(21)),
        gain=1.0,
        producer_id="p14.1.diagnostic-vector-registry",
        producer_state_digest="sha256:producer-state",
        purpose="runtime_qualification_diagnostic",
    ).with_digest()


def request(method, *, vector=None, registry_key=None):
    return PacketDerivationRequest(
        schema="elpis.packet-derivation-request.v1",
        method=method,
        explicit_vector=vector,
        registry_key=registry_key,
    ).with_digest()


def test_policy_has_no_coding_utility_eligible_method():
    policy = default_packet_derivation_policy()
    assert policy.grid81_allowed is False
    assert policy.registry_lookup_available is False
    assert policy.coding_utility_eligible_methods == ()
    assert validate_digest(policy, digest_field="policy_digest")


def test_none_derivation_constructs_non_actuating_tick():
    s = seed(ControlMode.OBSERVE)
    result = FrozenV01PacketDerivation().derive(
        s, request(PacketDerivationMethod.NONE)
    )
    assert result.packet is None
    assert result.receipt.grid81_used is False
    tick = finalize_tick(s, result)
    assert tick.schema == "elpis.nanbeige42.coding-tick.v2"
    assert tick.control is None
    assert tick.packet_derivation_receipt_digest == result.receipt.receipt_digest
    assert validate_digest(tick, digest_field="input_digest")


def test_neutral_stub_is_deterministic_zero_and_not_utility_eligible():
    s = seed(ControlMode.DOCK)
    deriver = FrozenV01PacketDerivation()
    r1 = deriver.derive(s, request(PacketDerivationMethod.NEUTRAL_STUB))
    r2 = deriver.derive(s, request(PacketDerivationMethod.NEUTRAL_STUB))
    assert r1 == r2
    assert r1.packet is not None
    assert r1.packet.common == 0.0
    assert r1.packet.structural == (0.0,) * 21
    assert r1.packet.gain == 0.0
    assert r1.receipt.semantic_mapper_qualified is False
    assert r1.receipt.coding_utility_eligible is False


def test_explicit_vector_is_bound_without_claiming_semantic_derivation():
    s = seed(ControlMode.HYBRID)
    vector = explicit_vector()
    result = FrozenV01PacketDerivation().derive(
        s,
        request(PacketDerivationMethod.EXPLICIT_SEALED_VECTOR, vector=vector),
    )
    assert result.packet is not None
    assert result.packet.source_state_digest == vector.producer_state_digest
    assert result.receipt.producer_id == vector.producer_id
    assert result.receipt.grid81_used is False
    assert result.receipt.semantic_mapper_qualified is False
    assert result.receipt.coding_utility_eligible is False
    tick = finalize_tick(s, result)
    assert tick.control.packet_digest == result.receipt.packet_digest


def test_grid81_is_explicitly_forbidden():
    with pytest.raises(Grid81DerivationForbidden):
        FrozenV01PacketDerivation().derive(
            seed(ControlMode.DOCK), request(PacketDerivationMethod.GRID81)
        )


def test_registry_is_reserved_until_frozen_task_registry_exists():
    with pytest.raises(RegistryDerivationUnavailable):
        FrozenV01PacketDerivation().derive(
            seed(ControlMode.DOCK),
            request(PacketDerivationMethod.REGISTRY_LOOKUP, registry_key="task-1"),
        )


def test_actuating_mode_cannot_use_none_derivation():
    with pytest.raises(PacketDerivationInputMismatch):
        FrozenV01PacketDerivation().derive(
            seed(ControlMode.DOCK), request(PacketDerivationMethod.NONE)
        )


def test_non_actuating_mode_cannot_carry_explicit_packet():
    with pytest.raises(PacketDerivationInputMismatch):
        FrozenV01PacketDerivation().derive(
            seed(ControlMode.OBSERVE),
            request(
                PacketDerivationMethod.EXPLICIT_SEALED_VECTOR,
                vector=explicit_vector(),
            ),
        )


def test_receipt_cannot_be_rebound_to_another_seed():
    first = seed(ControlMode.DOCK)
    result = FrozenV01PacketDerivation().derive(
        first, request(PacketDerivationMethod.NEUTRAL_STUB)
    )
    second = CodingTickSeed(
        schema=first.schema,
        tick_id="tick-2",
        parent_tick_id=first.parent_tick_id,
        logical_time=first.logical_time,
        task=first.task,
        workspace=first.workspace,
        evidence=first.evidence,
        control_mode=first.control_mode,
        generation_shape=first.generation_shape,
    ).with_digest()
    with pytest.raises(PacketDerivationInputMismatch):
        finalize_tick(second, result)
