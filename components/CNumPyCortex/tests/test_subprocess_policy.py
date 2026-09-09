"""Test enforced CNumPyCortex subprocess creation policy."""
from __future__ import annotations

import subprocess

import pytest

import c_numpy_cortex.airgap as airgap
from c_numpy_cortex.airgap import (
    ALLOWED_EXECUTABLES,
    SubprocessPolicyError,
    check_subprocess_allowed,
    run_allowed_subprocess,
)


def test_nvidia_smi_allowed(monkeypatch):
    monkeypatch.setattr(airgap.shutil, "which", lambda exe: "/usr/bin/nvidia-smi")
    assert check_subprocess_allowed(["nvidia-smi", "--query"]) is True


def test_nvidia_smi_with_flags(monkeypatch):
    monkeypatch.setattr(airgap.shutil, "which", lambda exe: "/usr/bin/nvidia-smi")
    assert check_subprocess_allowed([
        "nvidia-smi",
        "--query-gpu=temperature.gpu",
        "--format=csv",
    ]) is True


def test_absolute_path_nvidia_smi_allowed(monkeypatch):
    monkeypatch.setattr(airgap.os.path, "realpath", lambda p: "/usr/bin/nvidia-smi")
    assert check_subprocess_allowed([
        "/usr/bin/nvidia-smi",
        "--query",
    ]) is True


def test_arbitrary_executable_rejected():
    assert check_subprocess_allowed(["python", "-c", "print(1)"]) is False
    assert check_subprocess_allowed(["bash", "-c", "ls"]) is False
    assert check_subprocess_allowed(["curl", "http://example.com"]) is False
    assert check_subprocess_allowed(["git", "status"]) is False
    assert check_subprocess_allowed(["pip", "install", "something"]) is False


def test_shell_true_rejected_before_creation(monkeypatch):
    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("subprocess must not be created")

    monkeypatch.setattr(airgap, "_original_subprocess_run", forbidden)

    with pytest.raises(SubprocessPolicyError, match="shell=True"):
        run_allowed_subprocess(["nvidia-smi"], shell=True)

    assert called is False


def test_disallowed_executable_rejected_before_creation(monkeypatch):
    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("subprocess must not be created")

    monkeypatch.setattr(airgap, "_original_subprocess_run", forbidden)

    with pytest.raises(SubprocessPolicyError, match="not admitted"):
        run_allowed_subprocess(["curl", "http://example.com"])

    assert called is False


def test_allowed_wrapper_is_creation_boundary(monkeypatch):
    monkeypatch.setattr(airgap.shutil, "which", lambda exe: "/usr/bin/nvidia-smi")
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="ok")

    monkeypatch.setattr(airgap, "_original_subprocess_run", fake_run)

    result = run_allowed_subprocess(
        ["nvidia-smi", "--query"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert calls
    assert calls[0][0][0] == "nvidia-smi"
    assert calls[0][1]["shell"] is False


def test_empty_argv_rejected():
    assert check_subprocess_allowed([]) is False


def test_only_allowed_executables():
    assert "nvidia-smi" in ALLOWED_EXECUTABLES
    assert "python" not in ALLOWED_EXECUTABLES
    assert "bash" not in ALLOWED_EXECUTABLES
    assert "curl" not in ALLOWED_EXECUTABLES


def test_production_subprocess_creation_is_forced_through_boundary():
    component_src = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "src"
        / "c_numpy_cortex"
    )
    offenders = []

    for path in component_src.glob("*.py"):
        if path.name == "airgap.py":
            continue
        text = path.read_text()
        for forbidden in (
            "subprocess.run(",
            "subprocess.Popen(",
            "asyncio.create_subprocess_exec(",
            "asyncio.create_subprocess_shell(",
            "os.system(",
        ):
            if forbidden in text:
                offenders.append(f"{path.name}:{forbidden}")

    assert offenders == []
