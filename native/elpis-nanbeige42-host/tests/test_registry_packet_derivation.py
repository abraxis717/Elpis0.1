
import pytest
from elpis_nanbeige42_host.coding_registry import RegistryPacketDerivation, TaskPartition
from elpis_nanbeige42_host.packet_derivation import (
    CodingTickSeed, PacketDerivationMethod, PacketDerivationRequest,
)
from elpis_nanbeige42_host.schemas import CodingTask, ControlMode, GenerationShape, WorkspaceState
from elpis_nanbeige42_host.errors import PacketDerivationInputMismatch, RegistryDerivationUnavailable
from test_coding_registry import registry


def seed(entry, mode=ControlMode.DOCK):
    return CodingTickSeed(
        'elpis.nanbeige42.coding-tick-seed.v1','tick',None,0,
        CodingTask(entry.task_id,entry.objective,(),(),()),
        WorkspaceState(entry.workspace_root,'frozen','frozen',entry.workspace_snapshot_digest,None,(),()),
        (),mode,GenerationShape(2,4,1)
    ).with_digest()

def request(key):
    return PacketDerivationRequest(
        'elpis.packet-derivation-request.v1',PacketDerivationMethod.REGISTRY_LOOKUP,
        registry_key=key
    ).with_digest()

def test_registry_lookup_derives_bound_packet():
    r=registry(); e=r.entries[1]; out=RegistryPacketDerivation(r).derive(seed(e),request(e.task_id))
    assert out.receipt.registry_digest==r.registry_digest
    assert out.packet.packet_digest==r.binding_map()[e.task_id].packet.packet_digest

def test_pilot_receipt_is_utility_eligible():
    r=registry(); e=next(x for x in r.entries if x.partition is TaskPartition.SEALED_PILOT)
    assert RegistryPacketDerivation(r).derive(seed(e),request(e.task_id)).receipt.coding_utility_eligible

def test_canary_receipt_not_utility_eligible():
    r=registry(); e=next(x for x in r.entries if x.partition is TaskPartition.OPEN_CANARY)
    assert not RegistryPacketDerivation(r).derive(seed(e),request(e.task_id)).receipt.coding_utility_eligible

def test_workspace_snapshot_drift_rejected():
    r=registry(); e=r.entries[1]; s=seed(e)
    bad=WorkspaceState(s.workspace.repo_root,s.workspace.branch,s.workspace.head_commit,'sha256:'+'9'*64,None,(),())
    from dataclasses import replace
    with pytest.raises(PacketDerivationInputMismatch): RegistryPacketDerivation(r).derive(replace(s,workspace=bad).with_digest(),request(e.task_id))
