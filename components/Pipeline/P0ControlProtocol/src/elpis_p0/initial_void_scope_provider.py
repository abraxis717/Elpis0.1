"""G3.0 — Initial-void scope provider.

Deterministic scope derivation policy:
  A cell is writable if and only if its current Grid81 value is 0.

This is the initial-void policy. Nonzero cells are locked regardless of
provenance. This is NOT a recursive mutability policy.

Policy identity:
  scope_policy_id     = "p0.initial_void_cells"
  scope_policy_version = "1"
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .contracts import (
    P0RefinementError,
    RequestContext,
    StructuralProjection,
)
from .refinement_scope import (
    RefinementScopeDecisionV1,
    RefinementScopeProvider,
    _canonical_bytes,
    _mask_canonical,
    _sha256_hex,
)


# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

INITIAL_VOID_SCOPE_POLICY_ID = "p0.initial_void_cells"
INITIAL_VOID_SCOPE_POLICY_VERSION = "1"


# ---------------------------------------------------------------------------
# Pure policy function
# ---------------------------------------------------------------------------


def derive_initial_void_mask81(
    grid81: tuple[int, ...],
) -> tuple[int, ...]:
    """Derive writable mask from grid81 using initial-void policy.

    A cell is writable iff its value is 0.

    Args:
        grid81: Structural grid of exactly 81 cells, values in 0..9.

    Returns:
        Binary mask tuple of length 81. 1 = writable (cell is 0),
        0 = locked (cell is nonzero).

    Raises:
        ValueError: If grid81 shape or token domain is invalid.
    """
    if len(grid81) != 81:
        raise ValueError(
            f"grid81 must have length 81, got {len(grid81)}"
        )
    for i, v in enumerate(grid81):
        if not isinstance(v, int) or isinstance(v, bool):
            raise ValueError(
                f"grid81[{i}] = {v!r} is not a structural int"
            )
        if v < 0 or v > 9:
            raise ValueError(
                f"grid81[{i}] = {v} outside structural domain 0..9"
            )
    return tuple(1 if cell == 0 else 0 for cell in grid81)


# ---------------------------------------------------------------------------
# ScopeDerivationRecordV1 — Provenance record
# ---------------------------------------------------------------------------

DERIVATION_RECORD_SCHEMA = "p0.scope.derivation.record.v1"


@dataclass(frozen=True, slots=True)
class ScopeDerivationRecordV1:
    """Immutable provenance record for a scope derivation.

    Binds every derivation parameter and identity digest for audit.
    Does not contain target values, oracle output, model output,
    features, semantic rows, decoder hints, rationale, or raw prompt.
    """

    schema_version: str = DERIVATION_RECORD_SCHEMA
    provider_id: str = ""
    provider_version: str = ""
    scope_policy_id: str = ""
    scope_policy_version: str = ""
    request_id: str = ""
    logical_tick: int = -1
    snapshot_digest: str = ""
    projection_digest: str = ""
    grid_digest: str = ""
    decision_digest: str = ""
    mask_digest: str = ""
    writable_count: int = 0
    locked_count: int = 0
    derivation_status: str = ""
    derivation_digest: str = ""

    def __post_init__(self) -> None:
        # Validate schema
        if self.schema_version != DERIVATION_RECORD_SCHEMA:
            raise ValueError(
                f"schema_version must be {DERIVATION_RECORD_SCHEMA!r}, "
                f"got {self.schema_version!r}"
            )

        # Validate required non-empty fields
        for field_name in (
            "provider_id",
            "provider_version",
            "scope_policy_id",
            "scope_policy_version",
            "request_id",
            "snapshot_digest",
            "projection_digest",
            "grid_digest",
            "decision_digest",
            "mask_digest",
            "derivation_status",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")

        # Validate logical_tick
        if self.logical_tick < 0:
            raise ValueError(
                f"logical_tick must be >= 0, got {self.logical_tick}"
            )

        # Validate counts
        if self.writable_count < 0 or self.locked_count < 0:
            raise ValueError("writable_count and locked_count must be >= 0")

        # Validate derivation_status
        if self.derivation_status not in (
            "WRITABLE_INITIAL_VOID_CELLS",
            "NO_WRITABLE_INITIAL_VOID_CELLS",
        ):
            raise ValueError(
                f"derivation_status must be one of the allowed statuses, "
                f"got {self.derivation_status!r}"
            )

        # Compute derivation digest
        payload = {
            "schema_version": self.schema_version,
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "scope_policy_id": self.scope_policy_id,
            "scope_policy_version": self.scope_policy_version,
            "request_id": self.request_id,
            "logical_tick": self.logical_tick,
            "snapshot_digest": self.snapshot_digest,
            "projection_digest": self.projection_digest,
            "grid_digest": self.grid_digest,
            "decision_digest": self.decision_digest,
            "mask_digest": self.mask_digest,
            "writable_count": self.writable_count,
            "locked_count": self.locked_count,
            "derivation_status": self.derivation_status,
        }
        computed = _sha256_hex(_canonical_bytes(payload))
        if self.derivation_digest and self.derivation_digest != computed:
            raise ValueError(
                f"derivation_digest mismatch: "
                f"supplied {self.derivation_digest!r} != computed {computed!r}"
            )
        object.__setattr__(self, "derivation_digest", computed)


# ---------------------------------------------------------------------------
# Provider implementation
# ---------------------------------------------------------------------------


class InitialVoidScopeProvider:
    """Controller-owned scope provider implementing initial-void policy.

    Derives a writable-cell mask from the validated structural grid only.
    Zero-valued cells are writable; nonzero cells are locked.
    """

    provider_id: str = "initial-void-scope.v1"
    provider_version: str = "g3.0.production"

    def decide_scope(
        self,
        *,
        request: RequestContext,
        projection: StructuralProjection,
        logical_tick: int,
        snapshot_digest: str,
    ) -> RefinementScopeDecisionV1:
        """Derive scope decision from projection grid only.

        Returns only the decision; the full derivation record is available
        via `derive_scope`.

        Validates:
        - request identity (non-empty request_id)
        - logical tick (non-negative)
        - snapshot digest (64 hex chars)
        - grid81 shape and token domain

        Raises:
            ValueError: On any validation failure.
        """
        decision, _record = derive_scope(
            request=request,
            projection=projection,
            logical_tick=logical_tick,
            snapshot_digest=snapshot_digest,
            policy_id=INITIAL_VOID_SCOPE_POLICY_ID,
            policy_version=INITIAL_VOID_SCOPE_POLICY_VERSION,
            provider_id=self.provider_id,
            provider_version=self.provider_version,
        )
        return decision


# ---------------------------------------------------------------------------
# Module-level derive_scope — returns decision + record
# ---------------------------------------------------------------------------


def derive_scope(
    *,
    request: RequestContext,
    projection: StructuralProjection,
    logical_tick: int,
    snapshot_digest: str,
    policy_id: str = INITIAL_VOID_SCOPE_POLICY_ID,
    policy_version: str = INITIAL_VOID_SCOPE_POLICY_VERSION,
    provider_id: str = "initial-void-scope.v1",
    provider_version: str = "g3.0.production",
) -> tuple[RefinementScopeDecisionV1, ScopeDerivationRecordV1]:
    """Derive scope decision and provenance record.

    Pure derivation path:
    1. Validate request identity
    2. Validate logical tick
    3. Validate snapshot digest
    4. Validate projection (grid81 shape and token domain)
    5. Derive mask from grid81 only
    6. Construct RefinementScopeDecisionV1
    7. Construct ScopeDerivationRecordV1
    8. Return (decision, record)

    Does not mutate request or projection.
    Does not access target grids, oracle, features, semantic rows,
    decoder hints, model output, or rationale.

    Returns:
        Tuple of (RefinementScopeDecisionV1, ScopeDerivationRecordV1).

    Raises:
        ValueError: On validation failure.
    """
    # 1. Validate request identity
    if not request.request_id:
        raise ValueError("request.request_id must be non-empty")

    # 2. Validate logical tick
    if logical_tick < 0:
        raise ValueError(
            f"logical_tick must be >= 0, got {logical_tick}"
        )

    # 3. Validate snapshot digest
    if len(snapshot_digest) != 64:
        raise ValueError(
            f"snapshot_digest must be 64 hex chars, "
            f"got {len(snapshot_digest)}"
        )
    try:
        int(snapshot_digest, 16)
    except ValueError:
        raise ValueError(
            "snapshot_digest contains non-hex characters"
        )

    # 4. Validate projection
    projection.validate()

    # 5. Derive mask from grid81 only
    grid81 = projection.grid81
    writable_mask81 = derive_initial_void_mask81(grid81)

    # 6. Compute grid digest
    grid_payload = {"grid81": list(grid81)}
    grid_digest = _sha256_hex(_canonical_bytes(grid_payload))

    # 7. Compute mask digest
    mask_digest = _mask_canonical(writable_mask81)

    # 8. Determine derivation status
    writable_count = sum(writable_mask81)
    locked_count = 81 - writable_count
    if writable_count == 0:
        derivation_status = "NO_WRITABLE_INITIAL_VOID_CELLS"
    else:
        derivation_status = "WRITABLE_INITIAL_VOID_CELLS"

    # 9. Construct scope decision
    decision = RefinementScopeDecisionV1(
        request_id=request.request_id,
        logical_tick=logical_tick,
        snapshot_digest=snapshot_digest,
        scope_policy_id=policy_id,
        scope_policy_version=policy_version,
        writable_mask81=writable_mask81,
    )

    # 10. Construct derivation record
    record = ScopeDerivationRecordV1(
        provider_id=provider_id,
        provider_version=provider_version,
        scope_policy_id=policy_id,
        scope_policy_version=policy_version,
        request_id=request.request_id,
        logical_tick=logical_tick,
        snapshot_digest=snapshot_digest,
        projection_digest=projection.digest,
        grid_digest=grid_digest,
        decision_digest=decision.decision_digest,
        mask_digest=mask_digest,
        writable_count=writable_count,
        locked_count=locked_count,
        derivation_status=derivation_status,
    )

    return decision, record
