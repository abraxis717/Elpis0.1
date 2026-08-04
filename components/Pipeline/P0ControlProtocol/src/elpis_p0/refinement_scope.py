"""Phase C — Controller-owned scope authority contract.

Scope is an authority decision. The model may consume a mask but may not
generate, widen, narrow, reinterpret, replace, or infer it.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from .contracts import RequestContext, StructuralProjection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mask_canonical(mask: tuple[int, ...]) -> str:
    """Canonical mask serialization for digest binding."""
    return _sha256_hex(_canonical_bytes({"writable_mask81": list(mask)}))


# ---------------------------------------------------------------------------
# RefinementScopeDecisionV1
# ---------------------------------------------------------------------------

SCOPE_SCHEMA_VERSION = "p0.refinement.scope.v1"


class RefinementScopeError(ValueError):
    """Raised when scope decision validation fails."""

    pass


@dataclass(frozen=True, slots=True)
class RefinementScopeDecisionV1:
    """Controller-owned scope authority decision.

    Owns permission only. Does not own semantics or transition selection.
    """

    schema_version: str = SCOPE_SCHEMA_VERSION
    request_id: str = ""
    logical_tick: int = -1
    snapshot_digest: str = ""
    scope_policy_id: str = ""
    scope_policy_version: str = ""
    writable_mask81: tuple[int, ...] = ()
    mask_digest: str = ""
    decision_digest: str = ""

    def __post_init__(self) -> None:
        # Schema version
        if self.schema_version != SCOPE_SCHEMA_VERSION:
            raise RefinementScopeError(
                f"schema_version must be {SCOPE_SCHEMA_VERSION!r}, "
                f"got {self.schema_version!r}"
            )

        # request_id nonempty
        if not self.request_id:
            raise RefinementScopeError("request_id must be non-empty")

        # logical_tick >= 0
        if self.logical_tick < 0:
            raise RefinementScopeError(
                f"logical_tick must be >= 0, got {self.logical_tick}"
            )

        # snapshot_digest is lowercase SHA-256 hex
        if len(self.snapshot_digest) != 64:
            raise RefinementScopeError(
                f"snapshot_digest must be 64 hex chars, "
                f"got {len(self.snapshot_digest)}"
            )
        try:
            int(self.snapshot_digest, 16)
        except ValueError:
            raise RefinementScopeError(
                "snapshot_digest contains non-hex characters"
            )

        # scope_policy_id nonempty
        if not self.scope_policy_id:
            raise RefinementScopeError("scope_policy_id must be non-empty")

        # scope_policy_version nonempty
        if not self.scope_policy_version:
            raise RefinementScopeError("scope_policy_version must be non-empty")

        # mask length
        if len(self.writable_mask81) != 81:
            raise RefinementScopeError(
                f"writable_mask81 must have length 81, "
                f"got {len(self.writable_mask81)}"
            )

        # mask binary
        for i, v in enumerate(self.writable_mask81):
            if v not in (0, 1):
                raise RefinementScopeError(
                    f"writable_mask81[{i}] = {v} not in {{0, 1}}"
                )

        # mask digest
        expected_mask_digest = _mask_canonical(self.writable_mask81)
        if self.mask_digest and self.mask_digest != expected_mask_digest:
            raise RefinementScopeError(
                f"mask_digest mismatch: "
                f"supplied {self.mask_digest!r} != computed {expected_mask_digest!r}"
            )
        object.__setattr__(self, "mask_digest", expected_mask_digest)

        # decision_digest binds every field
        payload = {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "logical_tick": self.logical_tick,
            "snapshot_digest": self.snapshot_digest,
            "scope_policy_id": self.scope_policy_id,
            "scope_policy_version": self.scope_policy_version,
            "mask_digest": expected_mask_digest,
        }
        expected_decision = _sha256_hex(_canonical_bytes(payload))
        if self.decision_digest and self.decision_digest != expected_decision:
            raise RefinementScopeError(
                f"decision_digest mismatch: "
                f"supplied {self.decision_digest!r} != computed {expected_decision!r}"
            )
        object.__setattr__(self, "decision_digest", expected_decision)


# ---------------------------------------------------------------------------
# Scope-provider port (abstract)
# ---------------------------------------------------------------------------

class RefinementScopeProvider(Protocol):
    """Abstract scope authority port.

    The controller owns scope. This port formalizes the boundary:
    scope decisions come from outside the model path.

    Do NOT provide a production policy implementation in this package.
    A fixture-only explicit provider may exist under tests/.
    """

    def decide_scope(
        self,
        *,
        request: RequestContext,
        projection: StructuralProjection,
        logical_tick: int,
        snapshot_digest: str,
    ) -> RefinementScopeDecisionV1:
        ...
