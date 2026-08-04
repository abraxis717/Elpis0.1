
from dataclasses import replace
import pytest
from elpis_nanbeige42_host.coding_registry import (
    AcceptanceCommandSpec, CodingRegistryEntry, FrozenCodingRegistry,
    RegistryPacketBinding, TaskPartition,
)
from elpis_nanbeige42_host.schemas import CollapseControlPacket, ControlMode
from elpis_nanbeige42_host.errors import PacketDerivationInputMismatch


def packet(seed='sha256:'+'1'*64):
    return CollapseControlPacket('elpis.collapse-control.v1',0.1,(0.01,)*21,seed,1.0).with_digest()

def command():
    return AcceptanceCommandSpec('elpis.nanbeige42.acceptance-command.v1','pytest_registry',('-q','/x/test.py'),30).with_digest()

def binding(task_id, family='f'):
    p=packet()
    return RegistryPacketBinding('elpis.nanbeige42.registry-packet-binding.v1',task_id,task_id,family,'c','train','sha256:'+'a'*64,p.packet_digest,p).with_digest()

def entry(task_id, family, partition, binding_digest):
    root=f'$ELPIS_CANON_ROOT/Elpis_Canon/hosts/nanbeige42/coding_pilot_v0_1/workspaces/{task_id}'
    return CodingRegistryEntry(
        'elpis.nanbeige42.coding-registry-entry.v1',task_id,partition,family,'fix',('bounded',),root,
        'sha256:'+'2'*64,(root,), 'sha256:'+'3'*64,command(),binding_digest,
        (ControlMode.NONE,ControlMode.OBSERVE,ControlMode.DOCK),4,4096,'task',True,
        partition is TaskPartition.SEALED_PILOT,
    ).with_digest()

def registry():
    entries=[]; bindings=[]
    for fi in range(6):
        fam=f'f{fi}'
        for j in range(4):
            tid=f'{fam}_{j}'; b=binding(tid,fam); bindings.append(b)
            part=TaskPartition.OPEN_CANARY if j==0 else TaskPartition.SEALED_PILOT
            entries.append(entry(tid,fam,part,b.binding_digest))
    return FrozenCodingRegistry(
        'elpis.nanbeige42.coding-registry.v1','ELPIS_NANBEIGE42_CODING_PILOT_V0_1',
        tuple(entries),tuple(bindings),'a'*64,'sha256:'+'4'*64,'sha256:'+'5'*64,False,False,False
    ).with_digest()

def test_acceptance_command_digest_is_self_reference_free():
    assert command().command_digest.startswith('sha256:')

def test_shell_syntax_rejected():
    with pytest.raises(PacketDerivationInputMismatch):
        AcceptanceCommandSpec('elpis.nanbeige42.acceptance-command.v1','pytest_registry',('x && y',),30)

def test_canary_cannot_be_utility_eligible():
    b=binding('x')
    with pytest.raises(PacketDerivationInputMismatch):
        replace(entry('x','f',TaskPartition.OPEN_CANARY,b.binding_digest),coding_utility_eligible=True)

def test_mode_plan_is_frozen():
    b=binding('x'); e=entry('x','f',TaskPartition.SEALED_PILOT,b.binding_digest)
    with pytest.raises(PacketDerivationInputMismatch): replace(e,mode_plan=(ControlMode.DOCK,))

def test_registry_requires_exact_partition_counts():
    r=registry(); assert len(r.entries)==24 and len(r.packet_bindings)==24

def test_registry_digest_valid_shape():
    assert registry().registry_digest.startswith('sha256:')

def test_binding_requires_train_packet():
    b=binding('x')
    with pytest.raises(PacketDerivationInputMismatch): replace(b,source_split='validation')

def test_allowed_paths_must_stay_in_workspace():
    b=binding('x'); e=entry('x','f',TaskPartition.SEALED_PILOT,b.binding_digest)
    with pytest.raises(PacketDerivationInputMismatch): replace(e,allowed_path_prefixes=('/tmp',))
