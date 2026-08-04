"""Phase D — Envelope construction from scope decision.

Builds P0RefinementInputV1 from an explicit scope decision, verifying
exact identity across request, tick, and snapshot fields.
"""
from __future__ import annotations

from .contracts import (
    P0RefinementInputV1,
    P0RefinementError,
    RequestContext,
    StructuralProjection,
    build_refinement_input,
)
from .refinement_scope import RefinementScopeDecisionV1


def build_refinement_input_from_scope(
    *,
    request: RequestContext,
    projection: StructuralProjection,
    scope_decision: RefinementScopeDecisionV1,
    logical_tick: int,
    snapshot_digest: str,
) -> P0RefinementInputV1:
    """Build P0RefinementInputV1 from controller-owned scope decision.

    Verifies exact equality between request/tick/snapshot and the scope
    decision's bound values. Falls closed on any mismatch.

    Args:
        request: The P0 RequestContext.
        projection: The StructuralProjection.
        scope_decision: Controller-owned scope authority decision.
        logical_tick: The current logical tick.
        snapshot_digest: The current snapshot identity.

    Returns:
        P0RefinementInputV1 with scope_decision mask exactly preserved.

    Raises:
        P0RefinementError: On any identity mismatch or absent scope.
    """
    # 1. Check scope decision presence
    if scope_decision is None:
        raise P0RefinementError(
            "BLOCKED_P0_REFINEMENT_SCOPE_ABSENT: "
            "scope decision is None"
        )

    # 2. Verify request_id identity
    if request.request_id != scope_decision.request_id:
        raise P0RefinementError(
            f"BLOCKED_P0_REFINEMENT_SCOPE_REQUEST_MISMATCH: "
            f"request {request.request_id!r} != scope {scope_decision.request_id!r}"
        )

    # 3. Verify logical_tick identity
    if logical_tick != scope_decision.logical_tick:
        raise P0RefinementError(
            f"BLOCKED_P0_REFINEMENT_SCOPE_TICK_MISMATCH: "
            f"tick {logical_tick} != scope {scope_decision.logical_tick}"
        )

    # 4. Verify snapshot_digest identity
    if snapshot_digest != scope_decision.snapshot_digest:
        raise P0RefinementError(
            f"BLOCKED_P0_REFINEMENT_SCOPE_SNAPSHOT_MISMATCH: "
            f"snapshot {snapshot_digest!r} != scope {scope_decision.snapshot_digest!r}"
        )

    # 5. Verify mask digest matches the scope decision's computed digest
    from .refinement_scope import _mask_canonical
    computed_mask_digest = _mask_canonical(scope_decision.writable_mask81)
    if computed_mask_digest != scope_decision.mask_digest:
        raise P0RefinementError(
            f"BLOCKED_P0_REFINEMENT_SCOPE_DIGEST_MISMATCH: "
            f"computed {computed_mask_digest!r} != scope {scope_decision.mask_digest!r}"
        )

    # 6. Call existing sealed build_refinement_input with exact mask
    result = build_refinement_input(
        projection=projection,
        writable_mask81=scope_decision.writable_mask81,
        request_id=request.request_id,
        logical_tick=logical_tick,
        snapshot_digest=snapshot_digest,
    )

    # 7. Verify the mask was preserved exactly
    if result.structural_input.writable_mask81 != scope_decision.writable_mask81:
        raise P0RefinementError(
            "BLOCKED_P0_REFINEMENT_SCOPE_DIGEST_MISMATCH: "
            "mask was not preserved in envelope"
        )

    return result
