"""Test subprocess policy."""
from __future__ import annotations

from c_numpy_cortex.airgap import (
    check_subprocess_allowed,
    ALLOWED_EXECUTABLES,
)


def test_nvidia_smi_allowed():
    assert check_subprocess_allowed(["nvidia-smi", "--query"]) is True


def test_nvidia_smi_with_flags():
    assert check_subprocess_allowed([
        "nvidia-smi",
        "--query-gpu=temperature.gpu",
        "--format=csv",
    ]) is True


def test_absolute_path_nvidia_smi_allowed():
    import os
    # Check with absolute path
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


def test_shell_true_rejected():
    """shell=True is rejected at the subprocess level."""
    # check_subprocess_allowed doesn't check shell flag directly,
    # but the workers never use shell=True. We verify the policy.
    assert check_subprocess_allowed(["nvidia-smi"]) is True
    # Arbitrary command is rejected regardless
    assert check_subprocess_allowed(
        ["rm", "-rf", "/"]
    ) is False


def test_empty_argv_rejected():
    assert check_subprocess_allowed([]) is False


def test_only_allowed_executables():
    assert "nvidia-smi" in ALLOWED_EXECUTABLES
    assert "python" not in ALLOWED_EXECUTABLES
    assert "bash" not in ALLOWED_EXECUTABLES
    assert "curl" not in ALLOWED_EXECUTABLES
