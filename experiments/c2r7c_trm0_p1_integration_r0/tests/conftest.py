from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve()
EXPERIMENTS = HERE.parents[2]

for path in (
    EXPERIMENTS / "c2r6p0_deterministic_projector",
    EXPERIMENTS / "c2r6p1_projector_refiner_abi",
    EXPERIMENTS / "c2r7c_semantic_structural_probe",
    EXPERIMENTS / "c2r7c_trm0_p1_integration_r0",
):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

PLUGIN_NAME = "_elpis_frozen_c2r6p1_conftest"

P1_CONFTEST = (
    EXPERIMENTS
    / "c2r6p1_projector_refiner_abi"
    / "tests"
    / "conftest.py"
)

spec = importlib.util.spec_from_file_location(
    PLUGIN_NAME,
    P1_CONFTEST,
)

if spec is None or spec.loader is None:
    raise RuntimeError(
        "cannot load frozen C2R6-P1 conftest"
    )

module = importlib.util.module_from_spec(spec)
sys.modules[PLUGIN_NAME] = module
spec.loader.exec_module(module)

pytest_plugins = (PLUGIN_NAME,)
