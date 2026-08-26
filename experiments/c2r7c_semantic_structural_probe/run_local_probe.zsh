#!/bin/zsh
set -euo pipefail

ELPIS_EXP_DIR="${0:A:h}"
ELPIS_REPO="${ELPIS_EXP_DIR:h:h}"
ELPIS_VENV="/Users/abraxis/Elpis/Elpis_Qualification/work/.venv_C2R7C_STRUCTURAL_PROBE"
ELPIS_PY="$ELPIS_VENV/bin/python"

ELPIS_CANONICAL_SOURCE_PATH="$ELPIS_REPO/runtime/R0/src:$ELPIS_REPO/components/TRMFractalSpine/src:$ELPIS_REPO/components/Grid81DeterministicStructuralAdjudicator/src:$ELPIS_REPO/components/Grid81StructuralSemantics/src:$ELPIS_REPO/components/Pipeline/P0ControlProtocol/src:$ELPIS_REPO/components:$ELPIS_REPO/src"

[[ -x "$ELPIS_PY" ]] || {
  print -u2 -- "probe venv missing: $ELPIS_VENV"
  exit 1
}

"$ELPIS_PY" -m py_compile   "$ELPIS_EXP_DIR/source/structural_residual.py"   "$ELPIS_EXP_DIR/source/redteam_c2r7c_residual_probe.py"

print -- "syntax=PASS"
print -- "canonical_import_path=PASS"

PYTHONPATH="$ELPIS_EXP_DIR/source:$ELPIS_CANONICAL_SOURCE_PATH:${PYTHONPATH:-}"   "$ELPIS_PY" "$ELPIS_EXP_DIR/source/redteam_c2r7c_residual_probe.py"
