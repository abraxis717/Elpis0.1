# elpis/contracts/envelope.py — §II/§III the Design-B core.
# ExecutionEnvelope[P] = shared control law (route, budget, lineage, phase,
# identity) over one typed payload P. eq=False: Python `==` is IDENTITY-FREE
# by design (T-eq); use equality.same_instance / same_content / state_equal.
# __hash__ over instance_id only. Lineage acyclicity (T4): parent ids are
# prior fresh UUIDs; forged graphs are caught at the store by ParentResolver.
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Generic, TypeVar

from .budget import BudgetVector, Charge
from .identity import new_instance_id
from .phases import Phase, PhaseContext, validate_phase_transition
from .routing import Route

P = TypeVar("P")


class EnvelopeError(RuntimeError): ...


@dataclass(frozen=True, slots=True)
class Lineage:
    parent_ids: tuple[str, ...]
    root_id: str
    depth: int

    def __post_init__(self):
        if self.depth < 0:
            raise EnvelopeError("depth >= 0")


@dataclass(frozen=True, slots=True, eq=False)
class ExecutionEnvelope(Generic[P]):
    payload: P
    budget: BudgetVector
    route: Route
    phase: Phase
    lineage: Lineage
    content_checksum: str = ""
    instance_id: str = field(default_factory=new_instance_id)
    schema: int = 1

    def __hash__(self) -> int:
        return hash(self.instance_id)

    def seal(self) -> "ExecutionEnvelope[P]":
        return replace(self, content_checksum=self.payload.chi_p())

    def advance(self, *, target: Phase, charge: Charge,
                ctx: PhaseContext = PhaseContext(),
                payload: P | None = None,
                route: Route | None = None) -> "ExecutionEnvelope[P]":
        validate_phase_transition(self.phase, target, ctx)
        if route is not None and route != self.route:
            from .phases import validate_route_change
            validate_route_change(self.phase)
        nxt = replace(
            self,
            payload=self.payload if payload is None else payload,
            budget=self.budget.spend(charge),
            route=self.route if route is None else route,
            phase=target,
            instance_id=new_instance_id(),
            lineage=Lineage((self.instance_id,), self.lineage.root_id,
                            self.lineage.depth),
        )
        return nxt.seal()

    def child(self, *, payload: P, child_budget: BudgetVector,
              phase: Phase) -> "ExecutionEnvelope[P]":
        e = ExecutionEnvelope(
            payload=payload, budget=child_budget, route=self.route,
            phase=phase, lineage=Lineage((self.instance_id,),
                                         self.lineage.root_id,
                                         self.lineage.depth + 1))
        return e.seal()


def root_envelope(payload: P, *, budget: BudgetVector, route: Route,
                  phase: Phase) -> ExecutionEnvelope[P]:
    rid = new_instance_id()
    e = ExecutionEnvelope(payload=payload, budget=budget, route=route,
                          phase=phase, instance_id=rid,
                          lineage=Lineage((), rid, 0))
    return e.seal()
