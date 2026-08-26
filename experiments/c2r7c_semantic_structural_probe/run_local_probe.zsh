#!/bin/zsh
set -euo pipefail
ELPIS_EXP_DIR="${0:A:h}"
ELPIS_PY="/usr/local/bin/python3.11"

"$ELPIS_PY" -m py_compile   "$ELPIS_EXP_DIR/source/structural_residual.py"   "$ELPIS_EXP_DIR/source/redteam_c2r7c_residual_probe.py"

print -- "syntax=PASS"

PYTHONPATH="$ELPIS_EXP_DIR/source:${PYTHONPATH:-}"   "$ELPIS_PY" "$ELPIS_EXP_DIR/source/redteam_c2r7c_residual_probe.py"
