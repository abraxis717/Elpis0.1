"""L0 budget adapter — pure stateless wrapper over A1 BudgetVector/Charge.

Laws enforced at L0 boundary (not in A1):
  - bool explicitly rejected (type(v) is bool)
  - float explicitly rejected
  - negative values rejected
  - None preserved exactly (NOT_GRANTED)
  - Charge never contains None
  - grant pattern preserved
  - addition into NOT_GRANTED forbidden
  - subtraction from NOT_GRANTED forbidden
  - deterministic AXES order
  - no mutation, no hidden state
"""
from __future__ import annotations

from elpis.contracts.budget import (
    AXES,
    BudgetVector,
    Charge,
    BudgetError,
    InvalidCharge,
    NotGranted,
    Exhausted,
    Incomparable,
)
from .errors import BoolRejected


# ---------------------------------------------------------------------------
# Internal guards
# ---------------------------------------------------------------------------

def _guard_axis_budget(name: str, value: object) -> None:
    if type(value) is bool:
        raise BoolRejected(f"{name}: bool is not accepted as int")
    if value is not None:
        if not isinstance(value, int):
            raise BudgetError(
                f"{name}: expected int or None, got {type(value).__name__}"
            )
        if value < 0:
            raise BudgetError(f"{name}: negative value {value}")


def _guard_axis_charge(name: str, value: object) -> None:
    if type(value) is bool:
        raise BoolRejected(f"{name}: bool is not accepted as int")
    if not isinstance(value, int):
        raise InvalidCharge(
            f"{name}: expected int, got {type(value).__name__}"
        )
    if value < 0:
        raise InvalidCharge(f"{name}: negative value {value}")


# ---------------------------------------------------------------------------
# Public validators
# ---------------------------------------------------------------------------

def validate_budget(value: BudgetVector) -> None:
    """Validate a BudgetVector at the L0 boundary."""
    for a in AXES:
        _guard_axis_budget(f"BudgetVector.{a}", getattr(value, a))


def validate_charge(value: Charge, *, require_positive: bool = False) -> None:
    """Validate a Charge at the L0 boundary.

    When require_positive=True the charge must be > 0 on at least one axis.
    """
    for a in AXES:
        _guard_axis_charge(f"Charge.{a}", getattr(value, a))
    if require_positive and not value.positive:
        raise InvalidCharge(
            "charge must be strictly positive on at least one axis"
        )


# ---------------------------------------------------------------------------
# Canonical / structural helpers
# ---------------------------------------------------------------------------

def canonical_axes(value: BudgetVector) -> tuple[tuple[str, int | None], ...]:
    """Return axes in deterministic AXES order."""
    return tuple((a, getattr(value, a)) for a in AXES)


def zero_budget_like(value: BudgetVector) -> BudgetVector:
    """BudgetVector with same grant pattern but 0 on every granted axis."""
    return BudgetVector(
        **{a: (0 if getattr(value, a) is not None else None) for a in AXES}
    )


# ---------------------------------------------------------------------------
# Allocation / arithmetic
# ---------------------------------------------------------------------------

def budget_from_allocation(parent: BudgetVector, allocation: Charge) -> BudgetVector:
    """Derive child budget from parent grant pattern and allocation Charge."""
    validate_budget(parent)
    validate_charge(allocation)
    return BudgetVector(
        **{
            a: (None if getattr(parent, a) is None else getattr(allocation, a))
            for a in AXES
        }
    )


def subtract_checked(value: BudgetVector, charge: Charge) -> BudgetVector:
    """Spend a charge, NOT_GRANTED axes stay NOT_GRANTED."""
    validate_budget(value)
    validate_charge(charge)
    out: dict[str, int | None] = {}
    for a in AXES:
        have = getattr(value, a)
        need = getattr(charge, a)
        if need == 0:
            out[a] = have
            continue
        if have is None:
            raise NotGranted(f"axis {a}: NOT_GRANTED, cannot subtract")
        if have < need:
            raise Exhausted(f"axis {a}: have {have}, need {need}")
        out[a] = have - need
    return BudgetVector(**out)


def add_refund(value: BudgetVector, refund: BudgetVector) -> BudgetVector:
    """Add refund budget, NOT_GRANTED preserved. Adding into NOT_GRANTED forbidden."""
    validate_budget(value)
    validate_budget(refund)
    out: dict[str, int | None] = {}
    for a in AXES:
        base = getattr(value, a)
        add = getattr(refund, a)
        if base is None:
            if add is not None:
                raise BudgetError(f"axis {a}: cannot add into NOT_GRANTED")
            out[a] = None
            continue
        if add is None:
            out[a] = base
            continue
        out[a] = base + add
    return BudgetVector(**out)


def charge_from_difference(before: BudgetVector, after: BudgetVector) -> Charge:
    """Compute the Charge consumed between before and after BudgetVectors."""
    validate_budget(before)
    validate_budget(after)
    fields: dict[str, int] = {}
    for a in AXES:
        b = getattr(before, a)
        a_val = getattr(after, a)
        if b is None:
            fields[a] = 0
            continue
        if a_val is None:
            raise Incomparable(f"axis {a}: before granted, after NOT_GRANTED")
        diff = b - a_val
        if diff < 0:
            raise BudgetError(f"axis {a}: after ({a_val}) > before ({b})")
        fields[a] = diff
    return Charge(**fields)


def add_charges(left: Charge, right: Charge) -> Charge:
    """Add two Charges axis-wise."""
    validate_charge(left)
    validate_charge(right)
    return Charge(
        **{a: getattr(left, a) + getattr(right, a) for a in AXES}
    )
