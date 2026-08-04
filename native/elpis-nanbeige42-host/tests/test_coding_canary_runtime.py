from dataclasses import asdict, replace
from pathlib import Path
import json

import pytest

from elpis_nanbeige42_host.coding_canary_runtime import (
    CanaryRuntimeError,
    binding_from_mapping,
    bounded_text,
    build_bwrap_acceptance_command,
    derive_open_canary_packet,
    deterministic_run_projection,
    normalize_acceptance_output,
    sha256_text,
)
from elpis_nanbeige42_host.coding_registry import (
    AcceptanceCommandSpec,
    CodingRegistryEntry,
    RegistryPacketBinding,
    TaskPartition,
)
from elpis_nanbeige42_host.packet_derivation import (
    CodingTickSeed,
    PacketDerivationMethod,
    PacketDerivationRequest,
)
from elpis_nanbeige42_host.schemas import (
    CodingTask,
    CollapseControlPacket,
    ControlMode,
    GenerationShape,
    WorkspaceState,
)


def objects(tmp_path: Path):
    packet = CollapseControlPacket(
        "elpis.collapse-control.v1", 0.1, (0.2,) * 21, "sha256:" + "1" * 64, 1.0
    ).with_digest()
    binding = RegistryPacketBinding(
        "elpis.nanbeige42.registry-packet-binding.v1",
        "task", "task", "family", "class", "train",
        "sha256:" + "2" * 64, packet.packet_digest, packet,
    ).with_digest()
    command = AcceptanceCommandSpec(
        "elpis.nanbeige42.acceptance-command.v1", "pytest_registry",
        ("-q", str(tmp_path / "test.py")), 60,
    ).with_digest()
    entry = CodingRegistryEntry(
        "elpis.nanbeige42.coding-registry-entry.v1",
        "task", TaskPartition.OPEN_CANARY, "family", "objective",
        ("modify only solution.py",), str(tmp_path), "sha256:" + "3" * 64,
        (str(tmp_path / "solution.py"),), "sha256:" + "4" * 64,
        command, binding.binding_digest,
        (ControlMode.NONE, ControlMode.OBSERVE, ControlMode.DOCK),
        4, 16384, "task", True, False,
    ).with_digest()
    task = CodingTask("task", "objective", ("constraint",), ("accept",), ("network",))
    workspace = WorkspaceState(
        str(tmp_path), "branch", "head", entry.workspace_snapshot_digest,
        None, (), (),
    )
    seed = CodingTickSeed(
        "elpis.nanbeige42.coding-tick-seed.v1", "tick", None, 1,
        task, workspace, (), ControlMode.DOCK, GenerationShape(2, 10, 20),
    ).with_digest()
    request = PacketDerivationRequest(
        "elpis.packet-derivation-request.v1",
        PacketDerivationMethod.REGISTRY_LOOKUP,
        registry_key="task",
    ).with_digest()
    return entry, binding, seed, request


def test_bounded_text_preserves_short_and_bounds_long():
    assert bounded_text("abc", 3) == "abc"
    assert len(bounded_text("x" * 200, 64).encode()) <= 64
    assert "TRUNCATED" in bounded_text("x" * 200, 64)


def test_normalize_acceptance_output_removes_shadow_and_time(tmp_path: Path):
    value = f"{tmp_path}/test.py failed in 0.17s"
    normalized = normalize_acceptance_output(value, tmp_path)
    assert str(tmp_path) not in normalized
    assert "<SHADOW_ROOT>" in normalized
    assert "in <SECONDS>s" in normalized


def test_binding_from_mapping_roundtrip(tmp_path: Path):
    _, binding, _, _ = objects(tmp_path)
    rebuilt = binding_from_mapping(asdict(binding))
    assert rebuilt == binding


def test_open_canary_derivation_matches_binding(tmp_path: Path):
    entry, binding, seed, request = objects(tmp_path)
    result = derive_open_canary_packet(
        seed=seed, request=request, entry=entry, binding=binding,
        registry_digest="sha256:" + "5" * 64,
    )
    assert result.packet == binding.packet
    assert result.receipt.coding_utility_eligible is False
    assert result.receipt.registry_digest == "sha256:" + "5" * 64


def test_open_canary_derivation_rejects_observe(tmp_path: Path):
    entry, binding, seed, request = objects(tmp_path)
    seed = replace(seed, control_mode=ControlMode.OBSERVE).with_digest()
    with pytest.raises(Exception, match="DOCK"):
        derive_open_canary_packet(
            seed=seed, request=request, entry=entry, binding=binding,
            registry_digest="sha256:" + "5" * 64,
        )


def test_open_canary_derivation_rejects_utility_entry(tmp_path: Path):
    entry, binding, seed, request = objects(tmp_path)
    object.__setattr__(entry, "coding_utility_eligible", True)
    with pytest.raises(Exception, match="open canary"):
        derive_open_canary_packet(
            seed=seed, request=request, entry=entry, binding=binding,
            registry_digest="sha256:" + "5" * 64,
        )


def test_bwrap_command_is_no_network_and_shadow_bound(tmp_path: Path):
    bwrap = tmp_path / "bwrap"; bwrap.write_text("")
    repo = tmp_path / "repo"; repo.mkdir()
    canonical = repo / "tasks"; canonical.mkdir()
    provenance = repo / "provenance"; provenance.mkdir()
    shadow = tmp_path / "shadow"; shadow.mkdir()
    python = tmp_path / "python"; python.write_text("")
    argv = build_bwrap_acceptance_command(
        bwrap=bwrap, repo_root=repo, canonical_task_root=canonical,
        provenance_root=provenance, shadow_root=shadow, python=python,
        pythonpath="X", relocated_argv=("-q", "test.py"),
    )
    assert "--unshare-all" in argv
    assert ("--bind", str(shadow), str(shadow)) == argv[argv.index("--bind"):argv.index("--bind")+3]
    assert "pytest" in argv


def test_bwrap_command_requires_paths(tmp_path: Path):
    with pytest.raises(CanaryRuntimeError, match="missing"):
        build_bwrap_acceptance_command(
            bwrap=tmp_path/"missing", repo_root=tmp_path,
            canonical_task_root=tmp_path, provenance_root=tmp_path,
            shadow_root=tmp_path, python=tmp_path, pythonpath="X",
            relocated_argv=("-q", "x"),
        )


def test_deterministic_projection_excludes_capability_nonce():
    base = {
        "run_id": "run", "task_id": "task", "family": "f", "lane": "lane_a",
        "mode": "dock", "maximum_ticks": 1, "model_runtime_manifest_digest": "m",
        "first_patch_accepted": False, "completed": False, "blocker_reported": False,
        "capability_receipt": {"capability_id": "random"},
        "ticks": [{"tick_index": 0, "prompt_digest": "p", "capability_receipt": {"capability_id":"random"}}],
    }
    first = deterministic_run_projection(base)
    base["capability_receipt"] = {"capability_id": "other"}
    base["ticks"][0]["capability_receipt"] = {"capability_id":"other"}
    second = deterministic_run_projection(base)
    assert first == second


def test_sha256_text_prefix():
    assert sha256_text("x").startswith("sha256:")


def test_post_logit_modes_not_supported_by_live_helper():
    from elpis_nanbeige42_host.coding_canary_runtime import CanaryRuntimeHookSession
    with pytest.raises(CanaryRuntimeError):
        CanaryRuntimeHookSession(model=object(), mode=ControlMode.POST_LOGIT)


def test_generation_result_digest_schema_is_stable():
    from elpis_nanbeige42_host.coding_canary_runtime import GenerationResult
    value = GenerationResult(
        "elpis.p14.2b.generation-result.v1", "none", 1, (2,), "x",
        sha256_text("x"), True, 0, "a", "b", None, None, {}, (), (), None,
    ).with_digest()
    assert value.generation_result_digest.startswith("sha256:")
