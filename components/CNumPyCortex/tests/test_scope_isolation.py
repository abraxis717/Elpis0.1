"""Test scope isolation — CNumPyCortex imports no forbidden packages."""
from __future__ import annotations

import pytest


def test_no_pipeline_import():
    """CNumPyCortex imports no Pipeline controller."""
    import c_numpy_cortex
    import c_numpy_cortex.contracts
    import c_numpy_cortex.encoding
    import c_numpy_cortex.entropy
    import c_numpy_cortex.runtime
    import c_numpy_cortex.sensors
    import c_numpy_cortex.chronos2

    # Check no forbidden imports in module namespaces
    for mod in [
        c_numpy_cortex.contracts,
        c_numpy_cortex.encoding,
        c_numpy_cortex.entropy,
    ]:
        mod_name = mod.__name__
        assert "Pipeline" not in dir(mod), (
            f"{mod_name} exports Pipeline"
        )


def test_no_geodesic_import():
    """CNumPyCortex imports no GeodesicWorldModel."""
    import c_numpy_cortex.contracts
    import c_numpy_cortex.encoding
    import c_numpy_cortex.entropy

    for mod in [
        c_numpy_cortex.contracts,
        c_numpy_cortex.encoding,
        c_numpy_cortex.entropy,
    ]:
        assert "GeodesicWorldModel" not in dir(mod)
        assert "GeodesicEngine" not in dir(mod)


def test_no_trm_import():
    """CNumPyCortex imports no TRM recursion package."""
    import c_numpy_cortex.contracts
    import c_numpy_cortex.encoding
    import c_numpy_cortex.entropy

    for mod in [
        c_numpy_cortex.contracts,
        c_numpy_cortex.encoding,
        c_numpy_cortex.entropy,
    ]:
        assert "TRMFractalSpine" not in dir(mod)
        assert "TRMRecursion" not in dir(mod)


def test_no_hebbian_import():
    """CNumPyCortex imports no HebbianBrain."""
    import c_numpy_cortex.contracts
    import c_numpy_cortex.encoding
    import c_numpy_cortex.entropy

    for mod in [
        c_numpy_cortex.contracts,
        c_numpy_cortex.encoding,
        c_numpy_cortex.entropy,
    ]:
        assert "HebbianBrain" not in dir(mod)
        assert "LoRAManifold" not in dir(mod)


def test_no_telemetry_codec():
    """No telemetry-to-force codec exists."""
    import c_numpy_cortex.contracts
    import c_numpy_cortex.encoding
    import c_numpy_cortex.entropy

    for mod in [
        c_numpy_cortex.contracts,
        c_numpy_cortex.encoding,
        c_numpy_cortex.entropy,
    ]:
        assert "TelemetryWorldFieldCodec" not in dir(mod)


def test_no_logic_import():
    """CNumPyCortex imports no Logic."""
    import c_numpy_cortex.contracts
    import c_numpy_cortex.encoding

    for mod in [
        c_numpy_cortex.contracts,
        c_numpy_cortex.encoding,
    ]:
        assert "Logic" not in dir(mod)


def test_no_authority_import():
    """CNumPyCortex imports no authority package."""
    import c_numpy_cortex.contracts
    import c_numpy_cortex.encoding

    for mod in [
        c_numpy_cortex.contracts,
        c_numpy_cortex.encoding,
    ]:
        assert "BlackCore" not in dir(mod)
        assert "Lumen" not in dir(mod)


def test_no_needle_hrm():
    """CNumPyCortex imports no Needle or HRM."""
    import c_numpy_cortex.contracts
    import c_numpy_cortex.encoding

    for mod in [
        c_numpy_cortex.contracts,
        c_numpy_cortex.encoding,
    ]:
        assert "Needle" not in dir(mod)
        assert "HRM" not in dir(mod)
