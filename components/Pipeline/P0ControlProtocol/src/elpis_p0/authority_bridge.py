"""P0.2 L0ExpansionAuthorityBridge - narrow adapter to admitted authority.

Delegates to the selected admitted authority implementation (elpis.logic.account).
Does not reproduce account state. Binds to exact admitted public signatures.
"""
from __future__ import annotations

import uuid
from typing import Optional, Tuple

from elpis.contracts.budget import BudgetVector, Charge
from elpis.logic.account import (
    RequestAccount,
    EnvelopeCapability,
    ChildLease,
    ChildCloseReason,
    ChildAllocation,
    ChildCloseReceipt,
    AccountSnapshot,
    AdvanceReceipt,
)
from elpis.logic.errors import (
    LogicError,
    EnvelopeConsumed,
    CapabilityForgery,
    LeaseConsumed,
    LeaseForgery,
    ChildNotSealed,
    OpenChildAccounts,
    AccountSealed,
)
from elpis.contracts.budget import (
    Exhausted,
    NotGranted,
    InvalidCharge,
)


# ---------------------------------------------------------------------------
# Envelope ID generation
# ---------------------------------------------------------------------------

def _make_envelope_id(prefix: str, base_id: str, seq: int) -> str:
    """Generate a deterministic-enough envelope ID with secure randomness."""
    return f"{prefix}_{base_id}_{seq}_{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# Authority bridge
# ---------------------------------------------------------------------------

class L0ExpansionAuthorityBridge:
    """Narrow adapter between P0.2 expansion protocol and L0 RequestAccount.

    Provides the exact operations needed for the one-child affine expansion:
      - open_parent
      - allocate_child
      - charge_child_refinement
      - seal_child
      - close_child
      - snapshot
      - assert_conservation
    """

    def __init__(
        self,
        parent_account: RequestAccount,
        parent_capability: EnvelopeCapability,
    ) -> None:
        self._parent = parent_account
        self._parent_capability = parent_capability

    @classmethod
    def open_parent(
        cls,
        request_id: str,
        initial_budget: BudgetVector,
        root_envelope_id: Optional[str] = None,
    ) -> Tuple["L0ExpansionAuthorityBridge", EnvelopeCapability]:
        """Open a new parent account and return the bridge + root capability."""
        if root_envelope_id is None:
            root_envelope_id = f"root_{request_id}_{uuid.uuid4().hex}"
        account, root_cap = RequestAccount.open(
            request_id=request_id,
            initial_budget=initial_budget,
            root_envelope_id=root_envelope_id,
        )
        bridge = cls(account, root_cap)
        return bridge, root_cap

    def _next_envelope_id(self, prefix: str) -> str:
        snap = self._parent.snapshot()
        return _make_envelope_id(prefix, snap.request_id, snap.sequence)

    def allocate_child(
        self,
        child_request_id: str,
        allocation: Charge,
        spawn_cost: Charge,
    ) -> ChildAllocation:
        """Allocate one child account.

        Atomically:
          - Consumes the parent predecessor capability.
          - Charges positive spawn cost.
          - Reserves positive child allocation.
          - Issues a parent successor capability.
          - Creates the child account.
          - Issues the child root capability.
          - Issues the parent-owned child lease.
        """
        successor_id = self._next_envelope_id("parent_succ")
        child_root_id = self._next_envelope_id("child_root")

        child_alloc = self._parent.allocate_child(
            self._parent_capability,
            successor_envelope_id=successor_id,
            child_request_id=child_request_id,
            child_root_envelope_id=child_root_id,
            allocation=allocation,
            spawn_cost=spawn_cost,
        )

        # Update parent capability to successor
        self._parent_capability = child_alloc.parent_successor
        return child_alloc

    def charge_child_refinement(
        self,
        child_account: RequestAccount,
        child_capability: EnvelopeCapability,
        charge: Charge,
    ) -> Tuple[AdvanceReceipt, EnvelopeCapability]:
        """Consume child root capability through a positive refinement charge.

        Child inference must never run before this charge succeeds.
        """
        successor_id = f"child_ref_{child_account._state.account_id}_{uuid.uuid4().hex}"
        receipt, successor_cap = child_account.advance(
            child_capability,
            successor_envelope_id=successor_id,
            charge=charge,
        )
        return receipt, successor_cap

    def seal_child(
        self,
        child_account: RequestAccount,
    ) -> AccountSnapshot:
        """Seal the child account after inference."""
        return child_account.seal()

    def close_child(
        self,
        lease: ChildLease,
        reason: ChildCloseReason,
    ) -> ChildCloseReceipt:
        """Close the parent's lease for the child.

        Refunds only registered child remaining state.
        """
        return self._parent.close_child(lease, reason=reason)

    def seal_parent(self) -> AccountSnapshot:
        """Seal the parent account."""
        return self._parent.seal()

    def snapshot(self) -> AccountSnapshot:
        """Get current parent account snapshot."""
        return self._parent.snapshot()

    def assert_conservation(self) -> None:
        """Assert parent per-axis resource conservation."""
        self._parent.assert_conservation()

    def child_snapshot(self, child_account: RequestAccount) -> AccountSnapshot:
        """Get child account snapshot."""
        return child_account.snapshot()

    def child_assert_conservation(self, child_account: RequestAccount) -> None:
        """Assert child per-axis resource conservation."""
        child_account.assert_conservation()

    @property
    def parent_account(self) -> RequestAccount:
        return self._parent

    @property
    def parent_capability(self) -> EnvelopeCapability:
        return self._parent_capability
