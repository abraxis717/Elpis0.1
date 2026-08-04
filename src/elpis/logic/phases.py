"""L0 Phase machine — internally owned counters, reuses A1 phase contracts.

Rules:
  - repair_budget exact int >= 0, bool rejected
  - gap_reentries_used starts at 0
  - transition_count starts at 0
  - PhaseContext constructed from internal counters
  - validate_phase_transition() called
  - VALIDATION->MATERIALIZATION decrements repair budget
  - AUDIT->CONTEXT_ASSEMBLY increments gap reentries
  - terminal phases have no outgoing transition
  - all transitions RLock protected
  - failed transition leaves state unchanged
  - snapshots frozen
  - no caller-supplied counters
  - no import of account or obligations
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from elpis.contracts.phases import (
    Phase,
    PHASE_TRANSITIONS,
    PhaseContext,
    validate_phase_transition,
)

from .errors import (
    BoolRejected,
    PhaseMachineError,
)


@dataclass(frozen=True, slots=True)
class PhaseSnapshot:
    current_phase: Phase
    repair_budget_remaining: int
    gap_reentries_used: int
    transition_count: int


@dataclass(frozen=True, slots=True)
class PhaseTransitionReceipt:
    source_phase: Phase
    target_phase: Phase
    repair_budget_remaining: int
    gap_reentries_used: int
    transition_count: int
    reason_ref: str | None
    evidence_ref: str | None


class PhaseMachine:
    """Internally owned phase state machine."""

    def __init__(
        self,
        *,
        request_id: str,
        initial_phase: Phase,
        repair_budget: int = 0,
    ) -> None:
        if not request_id:
            raise ValueError("request_id must be non-empty")

        # Bool guard on repair_budget
        if type(repair_budget) is bool:
            raise BoolRejected("repair_budget: bool is not accepted as int")
        if not isinstance(repair_budget, int) or repair_budget < 0:
            raise ValueError(
                f"repair_budget must be int >= 0, got {type(repair_budget).__name__}"
            )

        self._request_id = request_id
        self._current_phase = initial_phase
        self._repair_budget = repair_budget
        self._gap_reentries_used = 0
        self._transition_count = 0
        self._lock = RLock()

    def snapshot(self) -> PhaseSnapshot:
        with self._lock:
            return PhaseSnapshot(
                current_phase=self._current_phase,
                repair_budget_remaining=self._repair_budget,
                gap_reentries_used=self._gap_reentries_used,
                transition_count=self._transition_count,
            )

    def request_transition(
        self,
        target: Phase,
        *,
        reason_ref: str | None = None,
        evidence_ref: str | None = None,
    ) -> PhaseTransitionReceipt:
        with self._lock:
            source = self._current_phase

            # Check terminal
            if not PHASE_TRANSITIONS.get(source):
                raise PhaseMachineError(
                    f"{source.value} is a terminal phase with no outgoing transitions"
                )

            # Pre-check repair budget before A1 validator
            if source is Phase.VALIDATION and target is Phase.MATERIALIZATION:
                if self._repair_budget <= 0:
                    raise PhaseMachineError("repair budget exhausted")

            # Validate transition via A1
            ctx = PhaseContext(
                gap_reentries_used=self._gap_reentries_used,
                repair_budget_remaining=self._repair_budget,
            )
            try:
                validate_phase_transition(source, target, ctx)
            except Exception as e:
                raise PhaseMachineError(
                    f"illegal phase transition {source.value} -> {target.value}: {e}"
                ) from e

            # Compute new internal state
            new_repair = self._repair_budget
            new_gap = self._gap_reentries_used
            new_count = self._transition_count + 1

            # VALIDATION -> MATERIALIZATION decrements repair budget
            if source is Phase.VALIDATION and target is Phase.MATERIALIZATION:
                new_repair = self._repair_budget - 1

            # AUDIT -> CONTEXT_ASSEMBLY increments gap reentries
            if source is Phase.AUDIT and target is Phase.CONTEXT_ASSEMBLY:
                new_gap = self._gap_reentries_used + 1

            # Commit
            self._current_phase = target
            self._repair_budget = new_repair
            self._gap_reentries_used = new_gap
            self._transition_count = new_count

            return PhaseTransitionReceipt(
                source_phase=source,
                target_phase=target,
                repair_budget_remaining=new_repair,
                gap_reentries_used=new_gap,
                transition_count=new_count,
                reason_ref=reason_ref,
                evidence_ref=evidence_ref,
            )
