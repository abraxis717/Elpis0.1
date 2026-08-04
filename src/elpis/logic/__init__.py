"""Elpis L0 — affine logic reference package.

Pure, process-local, non-authoritative, non-persistent, framework-independent.
"""
from .account import (
    AccountSnapshot,
    AdvanceReceipt,
    ChildAllocation,
    ChildCloseReceipt,
    ChildCloseReason,
    ChildLease,
    EnvelopeCapability,
    OpenChildSnapshot,
    RequestAccount,
)
from .authority import (
    AuthorityCapability,
    CapabilityRegistry,
    CapabilityRegistrySnapshot,
)
from .budget_adapter import (
    add_charges,
    add_refund,
    budget_from_allocation,
    canonical_axes,
    charge_from_difference,
    subtract_checked,
    validate_budget,
    validate_charge,
    zero_budget_like,
)
from .errors import (
    AccountSealed,
    AccountWrongPid,
    BoolRejected,
    CapabilityConsumed,
    CapabilityError,
    CapabilityForgery,
    ChildNotSealed,
    DuplicateEnvelopeId,
    EnvelopeConsumed,
    InvalidAllocation,
    InvalidSpawnCost,
    LeaseConsumed,
    LeaseForgery,
    LogicError,
    ObligationLedgerError,
    OpenChildAccounts,
    PhaseMachineError,
    ResourceError,
    ResourceExhausted,
    UnknownEnvelope,
)
from .obligations import ObligationLedger
from .phases import (
    PhaseMachine,
    PhaseSnapshot,
    PhaseTransitionReceipt,
)

__all__ = [
    # Records
    "AccountSnapshot",
    "AdvanceReceipt",
    "ChildAllocation",
    "ChildCloseReceipt",
    "ChildCloseReason",
    "ChildLease",
    "EnvelopeCapability",
    "OpenChildSnapshot",
    # Account
    "RequestAccount",
    # Authority
    "AuthorityCapability",
    "CapabilityRegistry",
    "CapabilityRegistrySnapshot",
    # Budget adapter
    "add_charges",
    "add_refund",
    "budget_from_allocation",
    "canonical_axes",
    "charge_from_difference",
    "subtract_checked",
    "validate_budget",
    "validate_charge",
    "zero_budget_like",
    # Errors
    "AccountSealed",
    "AccountWrongPid",
    "BoolRejected",
    "CapabilityConsumed",
    "CapabilityError",
    "CapabilityForgery",
    "DuplicateEnvelopeId",
    "EnvelopeConsumed",
    "InvalidAllocation",
    "InvalidSpawnCost",
    "LeaseConsumed",
    "LeaseForgery",
    "LogicError",
    "ObligationLedgerError",
    "OpenChildAccounts",
    "PhaseMachineError",
    "ResourceError",
    "ResourceExhausted",
    "UnknownEnvelope",
    # Obligations
    "ObligationLedger",
    # Phases
    "PhaseMachine",
    "PhaseSnapshot",
    "PhaseTransitionReceipt",
]
