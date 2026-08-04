"""R0 replay — determinism verification across processes."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile


def _canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replay_in_same_process(
    project_root: str,
    request: dict | None = None,
) -> tuple[str, str]:
    """Execute twice in the same process, return (hash1, hash2)."""
    from .transaction import execute_r0_transaction

    r1 = execute_r0_transaction(request=request, project_root=project_root)
    h1 = _sha256_hex(r1.receipt_bytes())

    r2 = execute_r0_transaction(request=request, project_root=project_root)
    h2 = _sha256_hex(r2.receipt_bytes())

    return h1, h2


def replay_in_fresh_process(
    project_root: str,
    python: str | None = None,
    request: dict | None = None,
) -> tuple[str, str]:
    """Execute once in-process, once in a fresh subprocess.

    Returns (in_process_hash, fresh_process_hash).
    """
    from .transaction import execute_r0_transaction

    r1 = execute_r0_transaction(request=request, project_root=project_root)
    h1 = _sha256_hex(r1.receipt_bytes())

    # Fresh process via subprocess
    if python is None:
        python = sys.executable

    request_json = json.dumps(request or {}, sort_keys=True)

    script = f"""
import os, sys, json

# Set up PYTHONPATH
src_dirs = [
    os.path.join("{project_root}", "TRMFractalSpine", "src"),
    os.path.join("{project_root}", "Pipeline", "P0ControlProtocol", "src"),
    os.path.join("{project_root}", "Grid81DeterministicStructuralAdjudicator", "src"),
    os.path.join("{project_root}", "Grid81StructuralSemantics", "src"),
    "{project_root}",
    "{os.path.dirname(os.path.dirname(__file__))}",
]
for d in src_dirs:
    if d not in sys.path:
        sys.path.insert(0, d)

os.environ["CUDA_VISIBLE_DEVICES"] = ""

from elpis_runtime_r0.transaction import execute_r0_transaction
receipt = execute_r0_transaction(
    request=json.loads('''{request_json}'''),
    project_root="{project_root}",
)
print(receipt.receipt_self_hash)
"""

    result = subprocess.run(
        [python, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Fresh process failed: {result.stderr[:500]}")

    h2 = result.stdout.strip()
    return h1, h2


def replay_in_temp_build_dir(
    project_root: str,
    python: str | None = None,
    request: dict | None = None,
) -> tuple[str, str]:
    """Execute with two different BUILD_DIR paths, compare receipts."""
    from .transaction import execute_r0_transaction
    import shutil

    h1, _ = replay_in_same_process(project_root=project_root, request=request)

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ELPIS_BUILD_DIR"] = tmp
        try:
            r2 = execute_r0_transaction(request=request, project_root=project_root)
            h2 = _sha256_hex(r2.receipt_bytes())
        finally:
            del os.environ["ELPIS_BUILD_DIR"]

    return h1, h2
