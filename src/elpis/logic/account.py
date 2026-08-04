"""L0 RequestAccount — process-local affine resource account.

Closes A1 ownership defects:
  - consume-once envelope advancement
  - registered child allocations
  - consume-once child leases
  - caller-independent child refunds
  - per-axis resource conservation
  - internally owned sequence counters
  - copy-on-write failure atomicity
"""
from __future__ import annotations

import os
import secrets
import uuid
from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import TYPE_CHECKING

from elpis.contracts.budget import (
    AXES,
    BudgetVector,
    Charge,
    InvalidCharge,
    NotGranted,
    Exhausted,
)

from .budget_adapter import (
    add_charges,
    budget_from_allocation,
    subtract_checked,
    add_refund,
    validate_budget,
    validate_charge,
)
from .errors import (
    BoolRejected,
    AccountSealed,
    AccountWrongPid,
    CapabilityConsumed,
    CapabilityForgery,
    ChildNotSealed,
    DuplicateEnvelopeId,
    EnvelopeConsumed,
    InvalidAllocation,
    InvalidSpawnCost,
    LeaseConsumed,
    LeaseForgery,
    OpenChildAccounts,
    ResourceExhausted,
    UnknownEnvelope,
)

if TYPE_CHECKING:
    from .budget_adapter import BudgetVector as _BV


# ===================================================================
# Frozen records
# ===================================================================


@dataclass(frozen=True, slots=True)
class EnvelopeCapability:
    account_id: str
    request_id: str
    envelope_id: str
    capability_id: str
    account_nonce: str
    issue_sequence: int

    def __reduce__(self) -> object:
        raise TypeError("EnvelopeCapability cannot be pickled")

    def __copy__(self) -> "EnvelopeCapability":
        return self

    def __deepcopy__(self, memo: dict | None = None) -> "EnvelopeCapability":
        raise TypeError("EnvelopeCapability cannot be deep-copied")

    def __reduce_ex__(self, protocol: int) -> object:
        raise TypeError("EnvelopeCapability cannot be pickled")


@dataclass(frozen=True, slots=True)
class AdvanceReceipt:
    account_id: str
    request_id: str
    predecessor_envelope_id: str
    successor_envelope_id: str
    consumed_capability_id: str
    successor_capability_id: str
    charge: Charge
    budget_before: BudgetVector
    budget_after: BudgetVector
    sequence: int


class ChildCloseReason(str, Enum):
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    ABORTED = "aborted"


@dataclass(frozen=True, slots=True)
class ChildLease:
    parent_account_id: str
    parent_request_id: str
    child_account_id: str
    child_request_id: str
    allocation_id: str
    lease_id: str
    child_root_envelope_id: str
    account_nonce: str
    issue_sequence: int

    def __reduce__(self) -> object:
        raise TypeError("ChildLease cannot be pickled")

    def __reduce_ex__(self, protocol: int) -> object:
        if protocol == -1:
            return (type(self), (
                self.parent_account_id,
                self.parent_request_id,
                self.child_account_id,
                self.child_request_id,
                self.allocation_id,
                self.lease_id,
                self.child_root_envelope_id,
                self.account_nonce,
                self.issue_sequence,
            ))
        raise TypeError("ChildLease cannot be pickled")


@dataclass(frozen=True, slots=True)
class ChildAllocation:
    parent_receipt: AdvanceReceipt
    parent_successor: EnvelopeCapability
    lease: ChildLease
    child_account: "RequestAccount"
    child_root: EnvelopeCapability


@dataclass(frozen=True, slots=True)
class ChildCloseReceipt:
    parent_account_id: str
    parent_request_id: str
    child_account_id: str
    child_request_id: str
    allocation_id: str
    lease_id: str
    reason: ChildCloseReason
    refunded: BudgetVector
    child_spent: Charge
    sequence: int


@dataclass(frozen=True, slots=True)
class OpenChildSnapshot:
    child_account_id: str
    child_request_id: str
    allocation_id: str
    lease_id: str
    allocated_budget: BudgetVector
    child_sealed: bool


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    account_id: str
    request_id: str
    initial_budget: BudgetVector
    remaining_budget: BudgetVector
    spent: Charge
    open_children: tuple[OpenChildSnapshot, ...]
    live_envelope_capability_ids: tuple[str, ...]
    consumed_envelope_capability_ids: tuple[str, ...]
    revoked_envelope_capability_ids: tuple[str, ...]
    seen_envelope_ids: tuple[str, ...]
    closed_allocation_ids: tuple[str, ...]
    sealed: bool
    sequence: int
    creator_pid: int


# ===================================================================
# Private internal state
# ===================================================================

class _ChildRecord:
    __slots__ = (
        "lease",
        "child_account",
        "child_root",
        "allocated_budget",
        "closed",
    )

    def __init__(
        self,
        lease: ChildLease,
        child_account: "RequestAccount",
        child_root: EnvelopeCapability,
        allocated_budget: BudgetVector,
    ) -> None:
        self.lease = lease
        self.child_account = child_account
        self.child_root = child_root
        self.allocated_budget = allocated_budget
        self.closed = False


class _AccountState:
    """Private copy-on-write state container."""
    __slots__ = (
        "account_id",
        "request_id",
        "creator_pid",
        "account_nonce",
        "initial_budget",
        "remaining_budget",
        "spent",
        "sequence",
        "live_capabilities",
        "consumed_capabilities",
        "revoked_capabilities",
        "seen_envelope_ids",
        "children",
        "closed_allocation_ids",
        "sealed",
        "child_request_ids",
    )

    def __init__(
        self,
        *,
        account_id: str,
        request_id: str,
        creator_pid: int,
        account_nonce: str,
        initial_budget: BudgetVector,
    ) -> None:
        self.account_id = account_id
        self.request_id = request_id
        self.creator_pid = creator_pid
        self.account_nonce = account_nonce
        self.initial_budget = initial_budget
        self.remaining_budget = initial_budget
        self.spent = Charge()
        self.sequence = 0
        self.live_capabilities: set[str] = set()
        self.consumed_capabilities: set[str] = set()
        self.revoked_capabilities: set[str] = set()
        self.seen_envelope_ids: set[str] = set()
        self.children: dict[str, _ChildRecord] = {}
        self.closed_allocation_ids: set[str] = set()
        self.sealed = False
        self.child_request_ids: set[str] = set()

    def copy(self) -> _AccountState:
        import copy
        s = _AccountState.__new__(_AccountState)
        s.account_id = self.account_id
        s.request_id = self.request_id
        s.creator_pid = self.creator_pid
        s.account_nonce = self.account_nonce
        s.initial_budget = self.initial_budget
        s.remaining_budget = self.remaining_budget
        s.spent = self.spent
        s.sequence = self.sequence
        s.live_capabilities = self.live_capabilities.copy()
        s.consumed_capabilities = self.consumed_capabilities.copy()
        s.revoked_capabilities = self.revoked_capabilities.copy()
        s.seen_envelope_ids = self.seen_envelope_ids.copy()
        s.children = self.children.copy()
        s.closed_allocation_ids = self.closed_allocation_ids.copy()
        s.sealed = self.sealed
        s.child_request_ids = self.child_request_ids.copy()
        return s


# ===================================================================
# RequestAccount
# ===================================================================


class RequestAccount:
    """Process-local affine resource account.

    Non-authoritative, non-persistent, framework-independent.
    """

    def __init__(self) -> None:
        raise NotImplementedError("Use RequestAccount.open()")

    # ---------------------------------------------------------------
    # Open
    # ---------------------------------------------------------------

    @classmethod
    def open(
        cls,
        *,
        request_id: str,
        initial_budget: BudgetVector,
        root_envelope_id: str,
    ) -> tuple["RequestAccount", EnvelopeCapability]:
        if not request_id:
            raise ValueError("request_id must be non-empty")
        if not root_envelope_id:
            raise ValueError("root_envelope_id must be non-empty")
        validate_budget(initial_budget)

        account_id = f"acc_{uuid.uuid4().hex}"
        account_nonce = secrets.token_urlsafe(32)
        creator_pid = os.getpid()

        state = _AccountState(
            account_id=account_id,
            request_id=request_id,
            creator_pid=creator_pid,
            account_nonce=account_nonce,
            initial_budget=initial_budget,
        )
        state.live_capabilities.add(root_envelope_id)
        state.seen_envelope_ids.add(root_envelope_id)
        state.sequence = 0

        cap = EnvelopeCapability(
            account_id=account_id,
            request_id=request_id,
            envelope_id=root_envelope_id,
            capability_id=root_envelope_id,
            account_nonce=account_nonce,
            issue_sequence=0,
        )

        account = cls.__new__(cls)
        account._state = state
        account._lock = RLock()
        return account, cap

    # ---------------------------------------------------------------
    # Snapshot
    # ---------------------------------------------------------------

    def snapshot(self) -> AccountSnapshot:
        with self._lock:
            st = self._state
            open_children: tuple[OpenChildSnapshot, ...] = tuple(
                OpenChildSnapshot(
                    child_account_id=rec.child_account._state.account_id,
                    child_request_id=rec.lease.child_request_id,
                    allocation_id=rec.lease.allocation_id,
                    lease_id=rec.lease.lease_id,
                    allocated_budget=rec.allocated_budget,
                    child_sealed=rec.child_account._state.sealed,
                )
                for rec in st.children.values()
                if not rec.closed
            )
            return AccountSnapshot(
                account_id=st.account_id,
                request_id=st.request_id,
                initial_budget=st.initial_budget,
                remaining_budget=st.remaining_budget,
                spent=st.spent,
                open_children=open_children,
                live_envelope_capability_ids=tuple(sorted(st.live_capabilities)),
                consumed_envelope_capability_ids=tuple(sorted(st.consumed_capabilities)),
                revoked_envelope_capability_ids=tuple(sorted(st.revoked_capabilities)),
                seen_envelope_ids=tuple(sorted(st.seen_envelope_ids)),
                closed_allocation_ids=tuple(sorted(st.closed_allocation_ids)),
                sealed=st.sealed,
                sequence=st.sequence,
                creator_pid=st.creator_pid,
            )

    # ---------------------------------------------------------------
    # Conservation
    # ---------------------------------------------------------------

    def assert_conservation(self) -> None:
        """Verify per-axis conservation invariant.

        For granted axes:
          remaining + spent + sum(open child allocations) == initial
        For NOT_GRANTED axes:
          remaining is None, spent axis is 0.
        """
        with self._lock:
            st = self._state
            for a in AXES:
                initial_val = getattr(st.initial_budget, a)
                if initial_val is None:
                    assert getattr(st.remaining_budget, a) is None, (
                        f"conservation: axis {a} initial NOT_GRANTED but remaining is not None"
                    )
                    assert getattr(st.spent, a) == 0, (
                        f"conservation: axis {a} NOT_GRANTED but spent > 0"
                    )
                    for rec in st.children.values():
                        if not rec.closed:
                            child_alloc_val = getattr(rec.allocated_budget, a)
                            assert child_alloc_val is None, (
                                f"conservation: axis {a} NOT_GRANTED but child allocation granted"
                            )
                else:
                    remaining_val = getattr(st.remaining_budget, a)
                    spent_val = getattr(st.spent, a)
                    child_sum = sum(
                        getattr(rec.allocated_budget, a)
                        for rec in st.children.values()
                        if not rec.closed
                        and getattr(rec.allocated_budget, a) is not None
                    )
                    total = remaining_val + spent_val + child_sum
                    assert total == initial_val, (
                        f"conservation: axis {a}: "
                        f"remaining({remaining_val}) + spent({spent_val}) + "
                        f"children({child_sum}) = {total} != initial({initial_val})"
                    )

    # ---------------------------------------------------------------
    # Internal checks
    # ---------------------------------------------------------------

    def _check_creator_pid(self) -> None:
        if os.getpid() != self._state.creator_pid:
            raise AccountWrongPid(
                f"account {self._state.account_id} created in PID "
                f"{self._state.creator_pid}, called from PID {os.getpid()}"
            )

    def _check_not_sealed(self) -> None:
        if self._state.sealed:
            raise AccountSealed(
                f"account {self._state.account_id} is sealed"
            )

    def _consume_envelope(self, state: _AccountState, capability: EnvelopeCapability) -> str:
        cap_id = capability.capability_id
        # Verify binding FIRST — forged capability detection
        if capability.account_id != state.account_id:
            raise CapabilityForgery(
                f"capability belongs to account {capability.account_id}, "
                f"not {state.account_id}"
            )
        if capability.request_id != state.request_id:
            raise CapabilityForgery(
                f"capability request_id {capability.request_id} != "
                f"{state.request_id}"
            )
        if capability.account_nonce != state.account_nonce:
            raise CapabilityForgery(
                "capability account_nonce mismatch"
            )
        # Then check lifecycle state
        if cap_id in state.consumed_capabilities:
            raise EnvelopeConsumed(
                f"envelope capability {cap_id} already consumed"
            )
        if cap_id not in state.live_capabilities:
            raise UnknownEnvelope(
                f"envelope capability {cap_id} is not live"
            )
        state.live_capabilities.discard(cap_id)
        state.consumed_capabilities.add(cap_id)
        return cap_id

    def _issue_capability(
        self, state: _AccountState, envelope_id: str
    ) -> EnvelopeCapability:
        state.sequence += 1
        state.live_capabilities.add(envelope_id)
        state.seen_envelope_ids.add(envelope_id)
        return EnvelopeCapability(
            account_id=state.account_id,
            request_id=state.request_id,
            envelope_id=envelope_id,
            capability_id=envelope_id,
            account_nonce=state.account_nonce,
            issue_sequence=state.sequence,
        )

    # ---------------------------------------------------------------
    # Advance
    # ---------------------------------------------------------------

    def advance(
        self,
        capability: EnvelopeCapability,
        *,
        successor_envelope_id: str,
        charge: Charge,
    ) -> tuple[AdvanceReceipt, EnvelopeCapability]:
        with self._lock:
            self._check_creator_pid()
            self._check_not_sealed()

            if type(capability) is not EnvelopeCapability:
                raise CapabilityForgery("expected EnvelopeCapability")
            if not successor_envelope_id:
                raise ValueError("successor_envelope_id must be non-empty")
            if successor_envelope_id in self._state.seen_envelope_ids:
                raise DuplicateEnvelopeId(
                    f"envelope ID {successor_envelope_id} already seen"
                )

            validate_charge(charge, require_positive=True)

            state = self._state.copy()
            consumed_cap_id = self._consume_envelope(state, capability)

            budget_before = state.remaining_budget
            budget_after = subtract_checked(budget_before, charge)
            state.remaining_budget = budget_after
            state.spent = add_charges(state.spent, charge)

            successor_cap = self._issue_capability(state, successor_envelope_id)

            state.sequence += 1
            seq = state.sequence

            self._state = state

            receipt = AdvanceReceipt(
                account_id=state.account_id,
                request_id=state.request_id,
                predecessor_envelope_id=consumed_cap_id,
                successor_envelope_id=successor_envelope_id,
                consumed_capability_id=consumed_cap_id,
                successor_capability_id=successor_cap.capability_id,
                charge=charge,
                budget_before=budget_before,
                budget_after=budget_after,
                sequence=seq,
            )
            return receipt, successor_cap

    # ---------------------------------------------------------------
    # Allocate child
    # ---------------------------------------------------------------

    def allocate_child(
        self,
        capability: EnvelopeCapability,
        *,
        successor_envelope_id: str,
        child_request_id: str,
        child_root_envelope_id: str,
        allocation: Charge,
        spawn_cost: Charge,
    ) -> ChildAllocation:
        with self._lock:
            self._check_creator_pid()
            self._check_not_sealed()

            if type(capability) is not EnvelopeCapability:
                raise CapabilityForgery("expected EnvelopeCapability")
            if not successor_envelope_id:
                raise ValueError("successor_envelope_id must be non-empty")
            if not child_request_id:
                raise ValueError("child_request_id must be non-empty")
            if not child_root_envelope_id:
                raise ValueError("child_root_envelope_id must be non-empty")

            # Unique checks
            if child_request_id in self._state.child_request_ids:
                raise DuplicateEnvelopeId(
                    f"child_request_id {child_request_id} already used in this parent"
                )
            if successor_envelope_id in self._state.seen_envelope_ids:
                raise DuplicateEnvelopeId(
                    f"envelope ID {successor_envelope_id} already seen"
                )
            if child_root_envelope_id in self._state.seen_envelope_ids:
                raise DuplicateEnvelopeId(
                    f"envelope ID {child_root_envelope_id} already seen"
                )

            # Validate allocation and spawn cost (L0-specific exceptions)
            validate_charge(allocation)
            if not allocation.positive:
                raise InvalidAllocation("child allocation must be positive on at least one axis")
            validate_charge(spawn_cost)
            if not spawn_cost.positive:
                raise InvalidSpawnCost("spawn cost must be positive on at least one axis")

            state = self._state.copy()

            # Consume predecessor
            consumed_cap_id = self._consume_envelope(state, capability)

            # Deduct allocation + spawn cost
            total_cost = add_charges(allocation, spawn_cost)
            budget_before = state.remaining_budget
            budget_after = subtract_checked(budget_before, total_cost)
            state.remaining_budget = budget_after

            # Spawn cost goes to spent
            state.spent = add_charges(state.spent, spawn_cost)

            # Create child budget from parent grant pattern + allocation
            child_budget = budget_from_allocation(state.initial_budget, allocation)

            # Create child account
            child_account, child_root_cap = RequestAccount.open(
                request_id=child_request_id,
                initial_budget=child_budget,
                root_envelope_id=child_root_envelope_id,
            )

            # Register child request ID
            state.child_request_ids.add(child_request_id)

            # Create allocation ID and lease
            allocation_id = f"alloc_{uuid.uuid4().hex}"
            lease_id = f"lease_{uuid.uuid4().hex}"

            state.sequence += 1
            issue_seq = state.sequence

            lease = ChildLease(
                parent_account_id=state.account_id,
                parent_request_id=state.request_id,
                child_account_id=child_account._state.account_id,
                child_request_id=child_request_id,
                allocation_id=allocation_id,
                lease_id=lease_id,
                child_root_envelope_id=child_root_envelope_id,
                account_nonce=state.account_nonce,
                issue_sequence=issue_seq,
            )

            child_record = _ChildRecord(
                lease=lease,
                child_account=child_account,
                child_root=child_root_cap,
                allocated_budget=child_budget,
            )
            state.children[allocation_id] = child_record

            # Issue successor capability
            successor_cap = self._issue_capability(state, successor_envelope_id)

            self._state = state

            # Build parent receipt
            parent_receipt = AdvanceReceipt(
                account_id=state.account_id,
                request_id=state.request_id,
                predecessor_envelope_id=consumed_cap_id,
                successor_envelope_id=successor_envelope_id,
                consumed_capability_id=consumed_cap_id,
                successor_capability_id=successor_cap.capability_id,
                charge=total_cost,
                budget_before=budget_before,
                budget_after=budget_after,
                sequence=issue_seq,
            )

            return ChildAllocation(
                parent_receipt=parent_receipt,
                parent_successor=successor_cap,
                lease=lease,
                child_account=child_account,
                child_root=child_root_cap,
            )

    # ---------------------------------------------------------------
    # Close child
    # ---------------------------------------------------------------

    def close_child(
        self,
        lease: ChildLease,
        *,
        reason: ChildCloseReason,
    ) -> ChildCloseReceipt:
        with self._lock:
            self._check_creator_pid()
            self._check_not_sealed()

            if type(lease) is not ChildLease:
                raise LeaseForgery("expected ChildLease")
            if lease.parent_account_id != self._state.account_id:
                raise LeaseForgery(
                    f"lease belongs to account {lease.parent_account_id}, "
                    f"not {self._state.account_id}"
                )
            if lease.parent_request_id != self._state.request_id:
                raise LeaseForgery(
                    f"lease request_id {lease.parent_request_id} != "
                    f"{self._state.request_id}"
                )
            if lease.account_nonce != self._state.account_nonce:
                raise LeaseForgery("lease nonce mismatch")

            alloc_id = lease.allocation_id
            record = self._state.children.get(alloc_id)
            if record is None or record.lease != lease:
                raise LeaseForgery("unknown or forged lease")
            if record.closed:
                raise LeaseConsumed("child lease already consumed")

            child = record.child_account
            child_state = child._state

            # Require child sealed and no open children
            if not child_state.sealed:
                raise ChildNotSealed("child must be sealed before close")
            if any(not r.closed for r in child_state.children.values()):
                raise OpenChildAccounts("child has open grandchild accounts")

            # Read child state
            child_remaining = child_state.remaining_budget
            child_spent = child_state.spent

            state = self._state.copy()

            # Remove from open children
            rec = state.children[alloc_id]
            rec.closed = True

            # Refund remaining to parent
            state.remaining_budget = add_refund(state.remaining_budget, child_remaining)

            # Add child spent to parent spent
            state.spent = add_charges(state.spent, child_spent)

            # Consume lease
            state.closed_allocation_ids.add(alloc_id)

            state.sequence += 1
            seq = state.sequence

            self._state = state

            return ChildCloseReceipt(
                parent_account_id=state.account_id,
                parent_request_id=state.request_id,
                child_account_id=child_state.account_id,
                child_request_id=lease.child_request_id,
                allocation_id=alloc_id,
                lease_id=lease.lease_id,
                reason=reason,
                refunded=child_remaining,
                child_spent=child_spent,
                sequence=seq,
            )

    # ---------------------------------------------------------------
    # Seal
    # ---------------------------------------------------------------

    def seal(self) -> AccountSnapshot:
        with self._lock:
            if self._state.sealed:
                raise AccountSealed("account already sealed")

            open_children = [
                alloc_id
                for alloc_id, rec in self._state.children.items()
                if not rec.closed
            ]
            if open_children:
                raise OpenChildAccounts(
                    f"cannot seal: {len(open_children)} open child(ren): "
                    f"{open_children}"
                )

            state = self._state.copy()

            # Revoke all live capabilities
            for cap_id in state.live_capabilities:
                state.revoked_capabilities.add(cap_id)
            state.live_capabilities.clear()

            state.sealed = True

            self._state = state

            return self.snapshot()
