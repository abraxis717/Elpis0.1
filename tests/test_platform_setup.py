import pytest

from elpis_reference.platform_setup import (
    PlatformProfile,
    build_plan,
)


def _profile(
    *,
    system: str,
    architecture: str,
    mps: bool,
    cuda: bool,
    cmake: bool,
    native: bool,
) -> PlatformProfile:
    return PlatformProfile(
        system=system,
        architecture=architecture,
        python_version="3.11.0",
        cpu_available=True,
        mps_candidate=mps,
        cuda_candidate=cuda,
        cmake_available=cmake,
        native_hacf_qualified=native,
    )


def test_apple_silicon_prefers_mps():
    detected = _profile(
        system="darwin",
        architecture="arm64",
        mps=True,
        cuda=False,
        cmake=True,
        native=True,
    )
    assert build_plan(
        "reference",
        detected=detected,
    ).device_preference == ("mps", "cpu")
    assert build_plan(
        "full",
        detected=detected,
    ).build_native_hacf is True


def test_linux_cuda_prefers_cuda():
    detected = _profile(
        system="linux",
        architecture="x86_64",
        mps=False,
        cuda=True,
        cmake=True,
        native=True,
    )
    plan = build_plan(
        "full",
        detected=detected,
    )
    assert plan.device_preference == ("cuda", "cpu")
    assert plan.build_native_hacf is True


def test_windows_keeps_reference_surface_and_skips_native():
    detected = _profile(
        system="windows",
        architecture="amd64",
        mps=False,
        cuda=True,
        cmake=True,
        native=False,
    )
    plan = build_plan(
        "full",
        detected=detected,
    )
    assert plan.package_spec == "."
    assert plan.device_preference == ("cuda", "cpu")
    assert plan.build_native_hacf is False


def test_explicit_unqualified_native_fails_closed():
    detected = _profile(
        system="windows",
        architecture="amd64",
        mps=False,
        cuda=False,
        cmake=True,
        native=False,
    )
    with pytest.raises(
        RuntimeError,
        match="unqualified platform",
    ):
        build_plan(
            "full",
            native="on",
            detected=detected,
        )
