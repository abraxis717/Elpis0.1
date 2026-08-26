#!/bin/zsh
set -euo pipefail

ELPIS_EXP_DIR="${0:A:h}"
ELPIS_REPO="${ELPIS_EXP_DIR:h:h}"
ELPIS_VENV="/Users/abraxis/Elpis/Elpis_Qualification/work/.venv_C2R7C_STRUCTURAL_PROBE"
ELPIS_PY="$ELPIS_VENV/bin/python"

ELPIS_OVERLAY_P0="$ELPIS_EXP_DIR/source/elpis_p0"
ELPIS_CANON_P0="$ELPIS_REPO/components/Pipeline/P0ControlProtocol/src/elpis_p0"
ELPIS_CANON_SPINE="$ELPIS_REPO/components/TRMFractalSpine/src/elpis_fractal_spine"

"$ELPIS_PY" -m py_compile \
  "$ELPIS_EXP_DIR/source/elpis_p0/structural_residual.py" \
  "$ELPIS_EXP_DIR/source/redteam_c2r7c_residual_probe.py"

print -- "syntax=PASS"
print -- "canonical_import_path=PASS"
print -- "eager_package_init_bypass=PASS"
print -- "claude_package_layout=PASS"

ELPIS_EXP_DIR="$ELPIS_EXP_DIR" \
ELPIS_OVERLAY_P0="$ELPIS_OVERLAY_P0" \
ELPIS_CANON_P0="$ELPIS_CANON_P0" \
ELPIS_CANON_SPINE="$ELPIS_CANON_SPINE" \
"$ELPIS_PY" - <<'PY_RUN'
from __future__ import annotations

import os
from pathlib import Path
import runpy
import sys
import types

exp_dir = Path(os.environ["ELPIS_EXP_DIR"])
overlay_p0 = Path(os.environ["ELPIS_OVERLAY_P0"])
canon_p0 = Path(os.environ["ELPIS_CANON_P0"])
canon_spine = Path(os.environ["ELPIS_CANON_SPINE"])

for required in (
    overlay_p0 / "structural_residual.py",
    canon_p0 / "contracts.py",
    canon_p0 / "semantic_ir.py",
    canon_spine / "structural_refinement.py",
):
    if not required.is_file():
        raise SystemExit(f"missing required source: {required}")

p0_pkg = types.ModuleType("elpis_p0")
p0_pkg.__path__ = [str(overlay_p0), str(canon_p0)]
p0_pkg.__package__ = "elpis_p0"
p0_pkg.__file__ = str(canon_p0 / "__init__.py")
sys.modules["elpis_p0"] = p0_pkg

spine_pkg = types.ModuleType("elpis_fractal_spine")
spine_pkg.__path__ = [str(canon_spine)]
spine_pkg.__package__ = "elpis_fractal_spine"
spine_pkg.__file__ = str(canon_spine / "__init__.py")
sys.modules["elpis_fractal_spine"] = spine_pkg

from elpis_p0.contracts import BasisToken  # noqa: F401
from elpis_p0.structural_residual import __file__ as residual_file
from elpis_fractal_spine.structural_refinement import (
    StructuralRefinementInputV1,  # noqa: F401
)

if Path(residual_file).resolve() != (overlay_p0 / "structural_residual.py").resolve():
    raise SystemExit(
        "elpis_p0.structural_residual did not resolve to experiment overlay"
    )

print("direct_contract_import=PASS")
print("structural_residual_overlay_import=PASS")
print("torch_required_for_probe_import=false")

probe = exp_dir / "source" / "redteam_c2r7c_residual_probe.py"
runpy.run_path(str(probe), run_name="__main__")
PY_RUN
