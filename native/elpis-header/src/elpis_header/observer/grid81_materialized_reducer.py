#!/usr/bin/env python3
"""Header runtime reducer for optional materialized Grid81 state."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np

from Grid81.materialized_state_reader import (
    Grid81CanonicalSnapshot,
    load_current_grid81_snapshot,
)


@dataclass(frozen=True, slots=True)
class Grid81MaterializedRuntimeState:
    generation_number: int
    authority_canonical_digest: str
    identity_runtime_projection_digest: str
    canonical_snapshot_digest: str
    materialized_state_available: bool
    materialization_generation: int | None
    state_sha256: str | None
    state_projection_digest: str | None
    active_cell_count: int | None
    void_cell_count: int | None
    combined_runtime_projection_digest: str


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _state_projection_digest(tensor: np.ndarray) -> str:
    array = np.asarray(tensor, dtype="<f4", order="C")
    digest = hashlib.sha256()
    digest.update(b"elpis.grid81.materialized-state-projection.v1\0")
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def load_grid81_materialized_runtime_state(
    project_root: Path,
    *,
    snapshot_loader: Callable[[Path], Grid81CanonicalSnapshot] | None = None,
    identity_runtime_loader: Callable[[Path], Any] | None = None,
) -> Grid81MaterializedRuntimeState:
    project_root = Path(project_root)
    if snapshot_loader is None:
        snapshot_loader = load_current_grid81_snapshot
    if identity_runtime_loader is None:
        from elpis_header.observer.grid81_reducer import load_grid81_runtime_state

        identity_runtime_loader = load_grid81_runtime_state

    snapshot = snapshot_loader(project_root)
    identity_runtime = identity_runtime_loader(project_root)
    authority = snapshot.authority

    generation_number = int(getattr(authority, "generation_number"))
    authority_canonical_digest = str(getattr(authority, "canonical_digest"))
    identity_projection = str(
        getattr(identity_runtime, "runtime_projection_digest")
    )
    if generation_number != int(getattr(identity_runtime, "generation_number")):
        raise RuntimeError("materialized reducer authority generation mismatch")
    if authority_canonical_digest != str(getattr(identity_runtime, "canonical_digest")):
        raise RuntimeError("materialized reducer authority digest mismatch")

    if snapshot.materialized is None:
        materialization_generation = None
        state_sha256 = None
        state_projection = None
        active = None
        void = None
    else:
        materialized = snapshot.materialized
        channels = np.argmax(materialized.tensor, axis=2)
        active = int(np.count_nonzero(channels != 0))
        void = int(np.count_nonzero(channels == 0))
        if active + void != 81:
            raise RuntimeError("materialized reducer cell count drift")
        materialization_generation = materialized.materialization_generation
        state_sha256 = materialized.state_sha256
        state_projection = _state_projection_digest(materialized.tensor)

    combined = _digest(
        {
            "schema": "elpis.grid81.materialized-runtime-projection.v1",
            "generation_number": generation_number,
            "authority_canonical_digest": authority_canonical_digest,
            "identity_runtime_projection_digest": identity_projection,
            "canonical_snapshot_digest": snapshot.snapshot_digest,
            "materialized_state_available": snapshot.materialized_state_available,
            "materialization_generation": materialization_generation,
            "state_sha256": state_sha256,
            "state_projection_digest": state_projection,
            "active_cell_count": active,
            "void_cell_count": void,
        }
    )
    return Grid81MaterializedRuntimeState(
        generation_number=generation_number,
        authority_canonical_digest=authority_canonical_digest,
        identity_runtime_projection_digest=identity_projection,
        canonical_snapshot_digest=snapshot.snapshot_digest,
        materialized_state_available=snapshot.materialized_state_available,
        materialization_generation=materialization_generation,
        state_sha256=state_sha256,
        state_projection_digest=state_projection,
        active_cell_count=active,
        void_cell_count=void,
        combined_runtime_projection_digest=combined,
    )
