#!/bin/zsh
set -euo pipefail

ELPIS_EXP_DIR="${0:A:h}"
ELPIS_REPO="${ELPIS_EXP_DIR:h:h}"
ELPIS_VENV="/Users/abraxis/Elpis/Elpis_Qualification/work/.venv_C2R7C_STRUCTURAL_PROBE"
ELPIS_PY="$ELPIS_VENV/bin/python"

ELPIS_P0_SRC="$ELPIS_REPO/components/Pipeline/P0ControlProtocol/src/elpis_p0"
ELPIS_SPINE_SRC="$ELPIS_REPO/components/TRMFractalSpine/src/elpis_fractal_spine"

"$ELPIS_PY" -m py_compile   "$ELPIS_EXP_DIR/source/structural_residual.py"   "$ELPIS_EXP_DIR/source/redteam_c2r7c_residual_probe.py"

print -- "syntax=PASS"
print -- "canonical_import_path=PASS"
print -- "eager_package_init_bypass=PASS"

ELPIS_EXP_DIR="$ELPIS_EXP_DIR" ELPIS_P0_SRC="$ELPIS_P0_SRC" ELPIS_SPINE_SRC="$ELPIS_SPINE_SRC" "$ELPIS_PY" - <<'PY_RUN'
from __future__ import annotations

import os
from pathlib import Path
import runpy
import sys
import types

exp_dir = Path(os.environ["ELPIS_EXP_DIR"])
p0_src = Path(os.environ["ELPIS_P0_SRC"])
spine_src = Path(os.environ["ELPIS_SPINE_SRC"])

for required in (
    p0_src / "contracts.py",
    p0_src / "semantic_ir.py",
    spine_src / "structural_refinement.py",
):
    if not required.is_file():
        raise SystemExit(f"missing canonical source: {required}")

p0_pkg = types.ModuleType("elpis_p0")
p0_pkg.__path__ = [str(p0_src)]
p0_pkg.__package__ = "elpis_p0"
p0_pkg.__file__ = str(p0_src / "__init__.py")
sys.modules["elpis_p0"] = p0_pkg

spine_pkg = types.ModuleType("elpis_fractal_spine")
spine_pkg.__path__ = [str(spine_src)]
spine_pkg.__package__ = "elpis_fractal_spine"
spine_pkg.__file__ = str(spine_src / "__init__.py")
sys.modules["elpis_fractal_spine"] = spine_pkg

sys.path.insert(0, str(exp_dir / "source"))

from elpis_p0.contracts import BasisToken  # noqa: F401
from elpis_fractal_spine.structural_refinement import (
    StructuralRefinementInputV1,  # noqa: F401
)

print("direct_contract_import=PASS")
print("torch_required_for_probe_import=false")

probe = exp_dir / "source" / "redteam_c2r7c_residual_probe.py"
runpy.run_path(str(probe), run_name="__main__")
PY_RUN
