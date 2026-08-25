from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import platform
from pathlib import Path
import shutil
import sys
from typing import Literal


SetupProfile = Literal["reference", "full"]
NativeMode = Literal["auto", "on", "off"]


@dataclass(frozen=True)
class PlatformProfile:
    system: str
    architecture: str
    python_version: str
    cpu_available: bool
    mps_candidate: bool
    cuda_candidate: bool
    cmake_available: bool
    native_hacf_qualified: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class BuildPlan:
    profile: str
    package_spec: str
    device_preference: tuple[str, ...]
    build_native_hacf: bool
    native_reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def detect_platform() -> PlatformProfile:
    system = platform.system().lower()
    architecture = platform.machine().lower()

    mps_candidate = (
        system == "darwin"
        and architecture in {"arm64", "aarch64"}
    )

    cuda_candidate = any(
        (
            shutil.which("nvidia-smi") is not None,
            shutil.which("nvcc") is not None,
            bool(os.environ.get("CUDA_HOME")),
            bool(os.environ.get("CUDA_PATH")),
        )
    )

    return PlatformProfile(
        system=system,
        architecture=architecture,
        python_version=(
            f"{sys.version_info.major}."
            f"{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        ),
        cpu_available=True,
        mps_candidate=mps_candidate,
        cuda_candidate=cuda_candidate,
        cmake_available=shutil.which("cmake") is not None,
        native_hacf_qualified=system in {"darwin", "linux"},
    )


def build_plan(
    profile: SetupProfile = "reference",
    *,
    native: NativeMode = "auto",
    detected: PlatformProfile | None = None,
) -> BuildPlan:
    detected = detected or detect_platform()

    if profile not in {"reference", "full"}:
        raise ValueError(f"unknown setup profile {profile!r}")

    devices = ["cpu"]

    if detected.mps_candidate:
        devices.insert(0, "mps")

    if detected.cuda_candidate:
        devices.insert(0, "cuda")

    if native == "off":
        build_native = False
        reason = "native build disabled by user"
    elif profile != "full":
        build_native = False
        reason = "reference profile does not require native HACF"
    elif not detected.native_hacf_qualified:
        if native == "on":
            raise RuntimeError(
                "native HACF explicitly requested on an unqualified platform"
            )
        build_native = False
        reason = "native HACF is not yet qualified on this platform"
    elif not detected.cmake_available:
        if native == "on":
            raise RuntimeError(
                "native HACF explicitly requested but CMake is unavailable"
            )
        build_native = False
        reason = "CMake unavailable; native HACF skipped"
    else:
        build_native = True
        reason = "platform and build prerequisites support native HACF"

    return BuildPlan(
        profile=profile,
        package_spec=".",
        device_preference=tuple(devices),
        build_native_hacf=build_native,
        native_reason=reason,
    )


def native_build_commands(
    repo: Path,
    build_root: Path,
) -> tuple[tuple[str, ...], ...]:
    detected = detect_platform()

    if not detected.native_hacf_qualified:
        raise RuntimeError(
            "native HACF is not qualified on this platform"
        )

    cmake = shutil.which("cmake")
    if cmake is None:
        raise RuntimeError("CMake is required for native HACF")

    repo = repo.resolve()
    build_root = build_root.resolve()

    hacf_build = build_root / "hacf"
    bridge_build = build_root / "hacf_bridge"

    return (
        (
            cmake,
            "-S",
            str(repo / "native" / "hacf"),
            "-B",
            str(hacf_build),
            "-DCMAKE_BUILD_TYPE=Release",
            "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
        ),
        (
            cmake,
            "--build",
            str(hacf_build),
            "--config",
            "Release",
        ),
        (
            cmake,
            "-S",
            str(repo / "native" / "hacf_bridge"),
            "-B",
            str(bridge_build),
            "-DCMAKE_BUILD_TYPE=Release",
            f"-DHACF_INCLUDE_DIR={repo / 'native' / 'hacf' / 'include'}",
            f"-DHACF_LIB_DIR={hacf_build}",
        ),
        (
            cmake,
            "--build",
            str(bridge_build),
            "--config",
            "Release",
        ),
    )
