"""
Grid81 Canonical Reducer — Elpis Header observer for Grid81 canonical state.

Production runtime boundary: loads Grid81 canonical state through the
reusable canonical reader and reduces it to a runtime-consumable form
for downstream Elpis components.

This module is the normal entry point for Elpis runtime components that
need Grid81 canonical topology — NOT a verification or test module.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Runtime representation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Grid81RuntimeState:
    """Runtime-consumable Grid81 state derived from canonical reader.

    Carries generation, digest, transaction, and capability identity
    for downstream runtime configuration.
    """

    generation_number: int
    generation_raw_sha256: str
    generation_semantic_digest: str
    transaction_id: str
    capability_id: str
    capability_state: str
    canonical_digest: str

    # Derived metadata — computed in __post_init__
    runtime_projection_digest: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        """Compute deterministic runtime projection digest."""
        import hashlib
        payload = f"gen={self.generation_number}|raw={self.generation_raw_sha256}"
        payload += f"|sem={self.generation_semantic_digest}|txn={self.transaction_id}"
        payload += f"|cap={self.capability_id}|state={self.capability_state}"
        obj = hashlib.sha256(payload.encode()).hexdigest()
        object.__setattr__(self, "runtime_projection_digest", obj)


# ---------------------------------------------------------------------------
# Runtime loader
# ---------------------------------------------------------------------------

def load_grid81_runtime_state(
    project_root: pathlib.Path,
) -> Grid81RuntimeState:
    """Load Grid81 canonical state and reduce to runtime representation.

    This is the production runtime entry point. It:
    1. Calls the reusable canonical reader (HEAD-first)
    2. Reduces the frozen canonical state to a runtime form
    3. Returns an immutable runtime object with generation/digest identity

    Parameters
    ----------
    project_root : pathlib.Path
        Absolute path to the Elpis project root.

    Returns
    -------
    Grid81RuntimeState
        Frozen runtime state ready for downstream consumption.

    Raises
    ------
    CanonicalReadError
        If canonical state cannot be loaded or verified.
    """
    # Import the production reader — no verification harness, no report gen.
    # Ensure project root is on sys.path so Grid81 package is importable.
    import sys
    import importlib

    root_str = str(project_root.resolve())
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    reader_module = importlib.import_module("Grid81.canonical_reader")
    load_fn = reader_module.load_current_grid81

    canonical = load_fn(project_root)

    return Grid81RuntimeState(
        generation_number=canonical.generation_number,
        generation_raw_sha256=canonical.generation_raw_sha256,
        generation_semantic_digest=canonical.generation_semantic_digest,
        transaction_id=canonical.transaction_id,
        capability_id=canonical.capability_id,
        capability_state=canonical.capability_state,
        canonical_digest=canonical.canonical_digest,
    )
