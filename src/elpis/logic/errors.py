"""L0 affine logic reference — exception hierarchy."""
from __future__ import annotations


class LogicError(RuntimeError):
    """Base class for Elpis L0 logic-layer violations."""


# --- Capability / envelope -------------------------------------------


class CapabilityError(LogicError):
    pass


class CapabilityConsumed(CapabilityError):
    pass


class CapabilityForgery(CapabilityError):
    pass


class EnvelopeConsumed(LogicError):
    pass


class UnknownEnvelope(LogicError):
    pass


class DuplicateEnvelopeId(LogicError):
    pass


# --- Resource / budget -----------------------------------------------


class ResourceError(LogicError):
    pass


class ResourceExhausted(ResourceError):
    pass


class InvalidAllocation(ResourceError):
    pass


class InvalidSpawnCost(ResourceError):
    pass


class BoolRejected(LogicError):
    """A boolean value was passed where an int was expected."""


# --- Account state ---------------------------------------------------


class OpenChildAccounts(LogicError):
    pass


class AccountSealed(LogicError):
    pass


class AccountWrongPid(LogicError):
    """Operation called from a process other than the creator."""


# --- Child lease -----------------------------------------------------


class LeaseConsumed(LogicError):
    pass


class LeaseForgery(CapabilityForgery):
    pass


class ChildNotSealed(LogicError, ValueError):
    """Child account must be sealed before its lease can be closed."""
    pass


# --- Obligation ------------------------------------------------------


class ObligationLedgerError(LogicError):
    pass


# --- Phase machine ---------------------------------------------------


class PhaseMachineError(LogicError):
    pass
