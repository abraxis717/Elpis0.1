# elpis/contracts/budget.py — A1 budget algebra (§VI).
# B in (N ∪ {NOT_GRANTED})^7, product order on mutually granted axes.
# Laws (tested in test_a1_invariants.py):
#   spend:   B' = B - C, C ≻ 0 on ≥1 granted axis, else InvalidCharge
#   spawn:   B_after = B - C_spawn - Σ A_j,  C_spawn ≻ 0
#   refund:  remaining ≼ allocated;  B_final = B_after + Σ remaining
#   theorem (strict descent): B_final ≺ B_before because C_spawn is irrecoverable
#   NOT_GRANTED (None) is not infinity: any spend on that axis raises NotGranted.
from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Iterable

AXES = ("steps", "depth", "backend", "tokens", "energy", "wall_ms", "writes")


class BudgetError(RuntimeError): ...
class NotGranted(BudgetError): ...
class Exhausted(BudgetError): ...
class InvalidCharge(BudgetError): ...
class Incomparable(BudgetError): ...


@dataclass(frozen=True, slots=True)
class Charge:
    steps: int = 0; depth: int = 0; backend: int = 0; tokens: int = 0
    energy: int = 0; wall_ms: int = 0; writes: int = 0

    def __post_init__(self):
        for f in fields(self):
            v = getattr(self, f.name)
            if not isinstance(v, int) or v < 0:
                raise InvalidCharge(f"charge axis {f.name} must be int >= 0")

    @property
    def positive(self) -> bool:
        return any(getattr(self, a) > 0 for a in AXES)

    def __add__(self, o: "Charge") -> "Charge":
        return Charge(**{a: getattr(self, a) + getattr(o, a) for a in AXES})


@dataclass(frozen=True, slots=True)
class BudgetVector:
    steps: int | None; depth: int | None; backend: int | None
    tokens: int | None; energy: int | None; wall_ms: int | None
    writes: int | None

    def __post_init__(self):
        for a in AXES:
            v = getattr(self, a)
            if v is not None and (not isinstance(v, int) or v < 0):
                raise BudgetError(f"axis {a}: int>=0 or None (NOT_GRANTED)")

    # ---- order ---------------------------------------------------------
    def preceq(self, other: "BudgetVector") -> bool:
        for a in AXES:
            s, o = getattr(self, a), getattr(other, a)
            if (s is None) != (o is None):
                raise Incomparable(f"axis {a}: grant patterns differ")
            if s is not None and s > o:
                return False
        return True

    def strictly_less(self, other: "BudgetVector") -> bool:
        return self.preceq(other) and any(
            getattr(self, a) is not None and getattr(self, a) < getattr(other, a)
            for a in AXES)

    # ---- operations ----------------------------------------------------
    def spend(self, c: Charge) -> "BudgetVector":
        if not c.positive:
            raise InvalidCharge("every transition must charge C > 0")
        out = {}
        for a in AXES:
            have, need = getattr(self, a), getattr(c, a)
            if need == 0:
                out[a] = have
                continue
            if have is None:
                raise NotGranted(f"axis {a} was never granted")
            if have < need:
                raise Exhausted(f"axis {a}: have {have}, need {need}")
            out[a] = have - need
        return BudgetVector(**out)

    def allocate_children(self, allocations: Iterable[Charge], spawn_cost: Charge
                          ) -> tuple["BudgetVector", tuple["BudgetVector", ...]]:
        allocs = tuple(allocations)
        if not spawn_cost.positive:
            raise InvalidCharge("spawn cost must be > 0 (irrecoverable)")
        total = spawn_cost
        for a_j in allocs:
            if not a_j.positive:
                raise InvalidCharge("child allocation must be > 0")
            total = total + a_j
        parent_after = self.spend(total)
        # Child inherits NOT_GRANTED axes as NOT_GRANTED; spend(total) above
        # already guarantees a_j > 0 only on granted axes.
        children = tuple(
            BudgetVector(**{ax: (None if getattr(self, ax) is None
                                 else getattr(a_j, ax)) for ax in AXES})
            for a_j in allocs)
        return parent_after, children

    def refund_unused(self, allocated: Charge, remaining: "BudgetVector"
                      ) -> "BudgetVector":
        out = {}
        for a in AXES:
            rem = getattr(remaining, a)
            cap = getattr(allocated, a)
            if rem is None:
                out[a] = getattr(self, a)
                continue
            if rem > cap:
                raise InvalidCharge(f"refund axis {a}: remaining {rem} > allocated {cap}")
            have = getattr(self, a)
            out[a] = None if have is None else have + rem
        return BudgetVector(**out)

    def merge_child_accounting(self, spent: Iterable[Charge]) -> Charge:
        total = Charge()
        for c in spent:
            total = total + c
        return total

    # ---- status --------------------------------------------------------
    def exhausted_axes(self) -> tuple[str, ...]:
        return tuple(a for a in AXES if getattr(self, a) == 0)

    @property
    def any_exhausted(self) -> bool:
        return bool(self.exhausted_axes())


def from_legacy_scalar(steps: int) -> BudgetVector:
    """Legacy scalar budgets grant ONLY steps; every other axis is
    NOT_GRANTED — no invented defaults (A1 §VI)."""
    return BudgetVector(steps=steps, depth=None, backend=None, tokens=None,
                        energy=None, wall_ms=None, writes=None)
