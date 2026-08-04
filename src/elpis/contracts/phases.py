# elpis/contracts/phases.py — §VIII closed phase machine with owners.
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class Phase(str, Enum):
    CONTEXT_ASSEMBLY = "context_assembly"
    STRUCTURAL_PROJECTION = "structural_projection"
    PROPOSAL = "proposal"
    REFINEMENT = "refinement"
    MATERIALIZATION = "materialization"
    VALIDATION = "validation"
    AUDIT = "audit"
    GOVERNANCE = "governance"
    EXPANSION = "expansion"
    RETRACTION = "retraction"
    EMISSION = "emission"
    MEMORY_CANDIDATE = "memory_candidate"
    MEMORY_COMMIT = "memory_commit"
    ABORT = "abort"


_P = Phase
PHASE_TRANSITIONS: dict[Phase, frozenset[Phase]] = {
    _P.CONTEXT_ASSEMBLY: frozenset({_P.STRUCTURAL_PROJECTION, _P.ABORT}),
    _P.STRUCTURAL_PROJECTION: frozenset({_P.PROPOSAL, _P.ABORT}),
    _P.PROPOSAL: frozenset({_P.REFINEMENT, _P.ABORT}),
    _P.REFINEMENT: frozenset({_P.MATERIALIZATION, _P.AUDIT, _P.ABORT}),
    _P.MATERIALIZATION: frozenset({_P.VALIDATION, _P.ABORT}),
    _P.VALIDATION: frozenset({_P.AUDIT, _P.MATERIALIZATION, _P.ABORT}),  # repair edge, budgeted
    _P.AUDIT: frozenset({_P.GOVERNANCE, _P.RETRACTION, _P.CONTEXT_ASSEMBLY, _P.ABORT}),  # gap edge, once
    _P.GOVERNANCE: frozenset({_P.EMISSION, _P.EXPANSION, _P.REFINEMENT, _P.ABORT}),
    _P.EXPANSION: frozenset({_P.PROPOSAL, _P.ABORT}),
    _P.RETRACTION: frozenset({_P.REFINEMENT, _P.ABORT}),
    _P.EMISSION: frozenset({_P.MEMORY_CANDIDATE}),
    _P.MEMORY_CANDIDATE: frozenset({_P.MEMORY_COMMIT}),
    _P.MEMORY_COMMIT: frozenset(),
    _P.ABORT: frozenset(),
}

# OWNER maps each Phase to its verified owner module path (A0/live source).
# None = ownership not yet resolved; do NOT fabricate module strings.
OWNER: dict[Phase, str | None] = {
    _P.CONTEXT_ASSEMBLY: "elpis.context",
    _P.STRUCTURAL_PROJECTION: "Transformers.Elpis_R1",
    _P.PROPOSAL: "elpis.spine",
    _P.REFINEMENT: "elpis.spine",
    _P.MATERIALIZATION: None,
    _P.VALIDATION: None,
    _P.AUDIT: None,
    _P.GOVERNANCE: None,
    _P.EXPANSION: None,
    _P.RETRACTION: None,
    _P.EMISSION: "elpis.runtime",
    _P.MEMORY_CANDIDATE: None,
    _P.MEMORY_COMMIT: None,
    _P.ABORT: None,
}


class IllegalPhaseTransition(RuntimeError): ...


@dataclass(frozen=True, slots=True)
class PhaseContext:
    gap_reentries_used: int = 0
    repair_budget_remaining: int = 0


def validate_phase_transition(current: Phase, target: Phase,
                              ctx: PhaseContext = PhaseContext()) -> None:
    if target not in PHASE_TRANSITIONS[current]:
        raise IllegalPhaseTransition(f"{current.value} -> {target.value}")
    if current is _P.AUDIT and target is _P.CONTEXT_ASSEMBLY \
            and ctx.gap_reentries_used >= 1:
        raise IllegalPhaseTransition("gap re-entry allowed at most once")
    if current is _P.VALIDATION and target is _P.MATERIALIZATION \
            and ctx.repair_budget_remaining <= 0:
        raise IllegalPhaseTransition("repair budget exhausted")


ROUTE_CHANGE_PHASES = frozenset({_P.PROPOSAL, _P.GOVERNANCE})


def validate_route_change(phase: Phase) -> None:
    if phase not in ROUTE_CHANGE_PHASES:
        raise IllegalPhaseTransition(f"route change illegal in {phase.value}")
