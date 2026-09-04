"""SHA-verified frozen archive of the D0.1 structural ABI authority.

The D0.1 refiner machinery (529-bit lossless packer + legal-move decoder)
lives in ``experiments/c2r7d_trm5m_core_transplant/`` at authority commit
``32519c5521dcc1efab3a4aeadbfdab11ff5ea864``. That directory is NOT part of
the C2R6-P0 tree (``565582c``) this experiment is based on, so it is vendored
here, byte-for-byte, from the pinned commit.

The vendored files are FROZEN: the bridge imports them through this module
and never edits them. Every vendored file carries its content SHA-256 and its
source git blob SHA; verification is re-run on every import (see
``verify_vendor()``) so a tampered archive fails closed.

No file here is modified by the bridge. The D0.1 worktree itself is never
touched either.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

VENDOR_AUTHORITY_COMMIT = (
    "32519c5521dcc1efab3a4aeadbfdab11ff5ea864"
)  # D0.1 authority (exp/c2r7d0-trm5m-core-transplant)

# Relative path inside the D0.1 authority tree -> (content sha256, blob sha)
# The content SHA-256 is what protects the bytes actually imported; the git
# blob SHA is the provenance anchor in the D0.1 history.
VENDORED_FILES: dict[str, tuple[str, str]] = {
    "c2r7d0_constants.py": (
        "cfd7bace32253eeb2d7e65cf3549d85272c7de8b296c6d47771eda8c724a9981",
        "c07e28bcfcb786f9c61edbbbebcbf06b0f600f54",
    ),
    "structural_context_packer.py": (
        "e2c69920b1a91674235fc9fe76d3f4bddb481fc08e350032c1f490a987f2cf0b",
        "c6b2421fdd757321c96cafc0592c9c044933faf5",
    ),
    "legal_decoder.py": (
        "a95bbbe4929ee0cf8018e3ff52bd294503a9a2633fb3747be095903ffa34ed07",
        "d70319600cb9fbf0440c5601efc65542b2d3745f",
    ),
    "grid81_adapter.py": (
        "0e600afed39b27e7c8b225165bca08b924bf6a5fdfbd63591fa8444f7148a086",
        "f0c0e0a5111b9be53a6229a74658522bc605234f",
    ),
    "grid81_trm_core.py": (
        "e88772a2563e98b2177f7c143197e7770bd78c9cd7615302b8b465f8300b9947",
        "c6964ad32f2fe59069c40fef6f89b5481b4d40a5",
    ),
}

_PKG_DIR = Path(__file__).resolve().parent
VENDOR_DIR = _PKG_DIR / "_vendor_d01"


class VendorError(RuntimeError):
    """A vendored authority file is missing or its bytes changed."""


def verify_vendor() -> dict[str, str]:
    """Verify every vendored file's content SHA-256; return {file: sha256}.

    Raises VendorError on any mismatch. Pure file read + hash; no execution
    of the vendored code.
    """
    report: dict[str, str] = {}
    for name, (expected, _blob) in sorted(VENDORED_FILES.items()):
        path = VENDOR_DIR / name
        if not path.is_file():
            raise VendorError(f"vendored authority file missing: {path}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise VendorError(
                f"vendored authority file changed: {name}\n"
                f"  expected {expected}\n  actual   {actual}"
            )
        report[name] = actual
    return report


def import_vendored(name: str):
    """Import a vendored module (cached in sys.modules), verified first.

    The vendored modules import each other flat-style (``from
    c2r7d0_constants import ...``), so the vendor directory must be on
    sys.path; it is appended (not inserted) to avoid shadowing the live
    repository modules.
    """
    verify_vendor()
    vendor_path = str(VENDOR_DIR)
    if vendor_path not in sys.path:
        sys.path.append(vendor_path)
    import importlib

    return importlib.import_module(name)


# Convenience handles (lazy: import only when the torch-based packer or the
# legal decoder is actually needed).
def packer():
    return import_vendored("structural_context_packer")


def decoder():
    return import_vendored("legal_decoder")


def d01_constants():
    return import_vendored("c2r7d0_constants")
