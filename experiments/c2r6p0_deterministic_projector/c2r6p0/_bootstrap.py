"""Import wiring for the C2R6-P0 deterministic projector.

The structural authority for C2R7-C lives in the *frozen* experimental copy
``experiments/c2r7c_semantic_structural_probe/source/`` (NOT in the canonical
``elpis_p0`` package, which has no ``structural_residual`` module). The C2R7-C
probe reaches it with a namespace overlay so that importing
``elpis_p0.structural_residual`` does not trigger the eager, torch-heavy
``elpis_p0.__init__``.

This module reproduces that overlay idempotently and pins the exact paths the
projector is allowed to read. It reads the pinned authority; it never writes it.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent.parent
# experiments/c2r6p0_deterministic_projector -> experiments -> repo root
REPO_ROOT = _PKG_DIR.parents[1]

# Pinned read-only authority surfaces.
CANON_P0_SRC = REPO_ROOT / "components/Pipeline/P0ControlProtocol/src/elpis_p0"
CANON_SPINE_SRC = REPO_ROOT / "components/TRMFractalSpine/src/elpis_fractal_spine"
C2R7C_SOURCE = REPO_ROOT / "experiments/c2r7c_semantic_structural_probe/source"
C2R7C_OVERLAY_P0 = C2R7C_SOURCE / "elpis_p0"  # holds structural_residual.py
C2R7C_PROBE_DIR = REPO_ROOT / "experiments/c2r7c_semantic_structural_probe"  # structural_trm_features

# The overlay structural_residual.py must be byte-identical to the frozen copy
# the probe ships (verified at build time in the test suite).
EXPECTED_STRUCTURAL_RESIDUAL_SHA256 = (
    "de6fa20b2cdfd2f80419b943c0245094d5975c8d835acf413b46e51284f1fec8"
)


def _ensure_pinned() -> None:
    """Verify the pinned authority files exist before importing."""
    required = (
        CANON_P0_SRC / "contracts.py",
        CANON_P0_SRC / "semantic_ir.py",
        CANON_P0_SRC / "semantic_binding.py",
        CANON_SPINE_SRC / "structural_refinement.py",
        C2R7C_OVERLAY_P0 / "structural_residual.py",
        C2R7C_PROBE_DIR / "structural_trm_features.py",
    )
    for path in required:
        if not path.is_file():
            raise RuntimeError(f"pinned authority source missing: {path}")


def install() -> None:
    """Install the authority namespace overlay idempotently."""
    _ensure_pinned()

    if "elpis_p0" not in sys.modules:
        import types

        p0 = types.ModuleType("elpis_p0")
        # Overlay first so structural_residual resolves to the frozen C2R7-C copy;
        # contracts/semantic_ir fall through to the canonical package.
        p0.__path__ = [str(C2R7C_OVERLAY_P0), str(CANON_P0_SRC)]
        p0.__package__ = "elpis_p0"
        sys.modules["elpis_p0"] = p0

    if "elpis_fractal_spine" not in sys.modules:
        import types

        spine = types.ModuleType("elpis_fractal_spine")
        spine.__path__ = [str(CANON_SPINE_SRC)]
        spine.__package__ = "elpis_fractal_spine"
        sys.modules["elpis_fractal_spine"] = spine

    probe_dir = str(C2R7C_PROBE_DIR)
    if probe_dir not in sys.path:
        sys.path.insert(0, probe_dir)
