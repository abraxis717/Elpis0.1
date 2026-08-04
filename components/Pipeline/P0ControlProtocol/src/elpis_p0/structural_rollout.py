"""Minimal structural rollout controller for RECURSIVE_ROLLOUT_QUALIFICATION.

Responsibilities:
- Accept one qualified initial StructuralRefinementInputV1
- Invoke the qualified StructuralOracle adapter (evaluate_one_step)
- Select the already-authoritative canonical transition
- Append a hash-chained receipt
- Test terminal conditions
- Repeat within the fixed budget
- Return an immutable rollout receipt chain

May NOT:
- Retrieve context or change projection semantics
- Alter writable masks or clamps
- Select a noncanonical oracle candidate
- Mutate StructuralOracle
- Invoke learned T00, ECRF, spine models, Darwinian selection
- Write persistent memory

StructuralOracle is the sole structural-transition authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Canonical helpers
# ---------------------------------------------------------------------------

def _canonical_bytes(obj: Any) -> bytes:
    """Minimal canonical JSON bytes."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    """Lowercase SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def _digest(payload: dict) -> str:
    """Compute digest of a payload dict."""
    return _sha256_hex(_canonical_bytes(payload))


# ---------------------------------------------------------------------------
# Termination dispositions (sealed precedence order)
# ---------------------------------------------------------------------------

class RolloutDisposition(str, Enum):
    """Terminal disposition for a structural rollout.

    Precedence (highest first):
    CONTRACT_VIOLATION > ADAPTER_FAILURE > ORACLE_FAILURE
      > INVALID_TRANSITION > RESOLVED > QUIESCENT
      > CYCLE_DETECTED > NO_VALID_TRANSITION > STEP_BUDGET_EXHAUSTED
    """
    RESOLVED = "RESOLVED"
    QUIESCENT = "QUIESCENT"
    NO_VALID_TRANSITION = "NO_VALID_TRANSITION"
    CYCLE_DETECTED = "CYCLE_DETECTED"
    STEP_BUDGET_EXHAUSTED = "STEP_BUDGET_EXHAUSTED"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    ADAPTER_FAILURE = "ADAPTER_FAILURE"
    ORACLE_FAILURE = "ORACLE_FAILURE"
    CONTRACT_VIOLATION = "CONTRACT_VIOLATION"


# ---------------------------------------------------------------------------
# Rollout state contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class StructuralRolloutInputV1:
    """Immutable input passed to the rollout controller.

    Binds all identity required for a deterministic structural rollout.
    No hidden semantic state.
    """
    schema_version: str = "structural.rollout.input.v1"
    grid81: Tuple[int, ...] = ()
    writable_mask81: Tuple[int, ...] = ()
    grid_digest: str = ""
    mask_digest: str = ""
    combined_digest: str = ""
    scope_identity: str = ""
    initial_state_digest: str = ""
    oracle_identity: str = "structural_oracle.v1"
    adapter_identity: str = "structural_oracle_adapter.v1"
    budget: int = 20
    history_digest: str = ""

    def __post_init__(self) -> None:
        # Compute grid digest
        gd = _digest({"grid81": list(self.grid81)})
        object.__setattr__(self, "grid_digest", gd)

        # Compute mask digest
        md = _digest({"writable_mask81": list(self.writable_mask81)})
        object.__setattr__(self, "mask_digest", md)

        # Compute combined digest
        cd = _digest({
            "schema_version": self.schema_version,
            "grid_digest": gd,
            "mask_digest": md,
        })
        object.__setattr__(self, "combined_digest", cd)

        # Scope identity = mask digest
        object.__setattr__(self, "scope_identity", md)

        # Initial state digest = grid digest
        object.__setattr__(self, "initial_state_digest", gd)

        # History digest = empty for initial state
        if not self.history_digest:
            object.__setattr__(self, "history_digest", _sha256_hex(b""))


@dataclass(frozen=True, slots=True)
class StructuralRolloutStepV1:
    """Immutable result of a single structural rollout step.

    Binds:
        step index
        input-state digest
        candidate-set digest
        selected-transition digest
        output-state digest
        violation codes
        quiescence status
        termination status (if terminal)
    """
    schema_version: str = "structural.rollout.step.v1"
    step_index: int = 0
    input_state_digest: str = ""
    candidate_set_digest: str = ""
    selected_transition_digest: str = ""
    output_state_digest: str = ""
    violation_codes: Tuple[str, ...] = ()
    quiescence: bool = False
    termination_disposition: Optional[str] = None
    candidate_count: int = 0
    rationale_codes: Tuple[str, ...] = ()
    step_digest: str = ""

    def __post_init__(self) -> None:
        payload = {
            "schema_version": self.schema_version,
            "step_index": self.step_index,
            "input_state_digest": self.input_state_digest,
            "candidate_set_digest": self.candidate_set_digest,
            "selected_transition_digest": self.selected_transition_digest,
            "output_state_digest": self.output_state_digest,
            "violation_codes": list(self.violation_codes),
            "quiescence": self.quiescence,
            "termination_disposition": self.termination_disposition,
            "candidate_count": self.candidate_count,
            "rationale_codes": list(self.rationale_codes),
        }
        object.__setattr__(self, "step_digest", _digest(payload))


@dataclass(frozen=True, slots=True)
class StructuralRolloutReceiptV1:
    """Hash-chained append-only receipt for a rollout step.

    Each receipt binds the previous receipt's digest, creating
    an immutable, append-only trace.
    """
    schema_version: str = "structural.rollout.receipt.v1"
    step_index: int = 0
    input_state_digest: str = ""
    candidate_set_digest: str = ""
    selected_transition_digest: str = ""
    output_state_digest: str = ""
    violation_codes: Tuple[str, ...] = ()
    quiescence: bool = False
    termination_disposition: Optional[str] = None
    previous_receipt_digest: str = ""
    receipt_digest: str = ""

    def __post_init__(self) -> None:
        payload = {
            "schema_version": self.schema_version,
            "step_index": self.step_index,
            "input_state_digest": self.input_state_digest,
            "candidate_set_digest": self.candidate_set_digest,
            "selected_transition_digest": self.selected_transition_digest,
            "output_state_digest": self.output_state_digest,
            "violation_codes": list(self.violation_codes),
            "quiescence": self.quiescence,
            "termination_disposition": self.termination_disposition,
            "previous_receipt_digest": self.previous_receipt_digest,
        }
        object.__setattr__(self, "receipt_digest", _digest(payload))


@dataclass(frozen=True, slots=True)
class StructuralRolloutResultV1:
    """Immutable result of a complete structural rollout.

    Contains:
        initial input identity
        all step results
        all receipts (hash chain)
        terminal disposition
        final state digest
        receipt chain digest
        candidate counts per step
    """
    schema_version: str = "structural.rollout.result.v1"
    initial_input_digest: str = ""
    initial_grid81: Tuple[int, ...] = ()
    initial_mask81: Tuple[int, ...] = ()
    steps: Tuple[StructuralRolloutStepV1, ...] = ()
    receipts: Tuple[StructuralRolloutReceiptV1, ...] = ()
    terminal_disposition: str = ""
    final_state_digest: str = ""
    receipt_chain_digest: str = ""
    total_steps: int = 0
    step_budget: int = 0
    cycle_detected: bool = False
    cycle_state_digest: str = ""
    result_digest: str = ""

    def __post_init__(self) -> None:
        # Receipt chain digest = SHA-256 of all receipt digests joined
        receipt_digests = "|".join(r.receipt_digest for r in self.receipts)
        object.__setattr__(
            self, "receipt_chain_digest", _sha256_hex(receipt_digests.encode())
        )

        # Overall result digest
        payload = {
            "schema_version": self.schema_version,
            "initial_input_digest": self.initial_input_digest,
            "terminal_disposition": self.terminal_disposition,
            "final_state_digest": self.final_state_digest,
            "receipt_chain_digest": self.receipt_chain_digest,
            "total_steps": self.total_steps,
            "cycle_detected": self.cycle_detected,
        }
        object.__setattr__(self, "result_digest", _digest(payload))


# ---------------------------------------------------------------------------
# Rollout controller
# ---------------------------------------------------------------------------

class StructuralRolloutController:
    """Minimal deterministic structural rollout controller.

    Invokes StructuralOracle via the qualified one-step adapter,
    applies the canonical transition, and repeats until terminal
    conditions are met within the fixed budget.

    StructuralOracle is the sole structural-transition authority.
    """

    def __init__(
        self,
        *,
        max_steps: int = 20,
        adapter_fn: Optional[Any] = None,
    ) -> None:
        """
        Args:
            max_steps: Fixed step budget for qualification.
            adapter_fn: One-step adapter function. Defaults to
                elpis_p0.structural_oracle_adapter.evaluate_one_step.
        """
        self._max_steps = max_steps
        if adapter_fn is not None:
            self._adapter = adapter_fn
        else:
            from .structural_oracle_adapter import evaluate_one_step
            self._adapter = evaluate_one_step

    def execute(
        self,
        initial_input: StructuralRolloutInputV1,
    ) -> StructuralRolloutResultV1:
        """Execute a deterministic structural rollout.

        Pipeline:
            StructuralRolloutInputV1
              -> evaluate_one_step() -> next grid
              -> repeat until terminal or budget exhausted

        Args:
            initial_input: Validated rollout input.

        Returns:
            StructuralRolloutResultV1 with complete receipt chain.
        """
        # Import adapter types
        from .structural_oracle_adapter import OneStepAdapterResult
        from elpis_fractal_spine.structural_refinement import (
            STRUCTURAL_OPCODE_DOMAIN,
            StructuralRefinementInputV1,
        )

        current_grid = initial_input.grid81
        mask = initial_input.writable_mask81
        current_digest = initial_input.grid_digest

        steps: List[StructuralRolloutStepV1] = []
        receipts: List[StructuralRolloutReceiptV1] = []
        seen_digests: List[str] = [current_digest]
        previous_receipt_digest = _sha256_hex(b"")

        budget = min(initial_input.budget, self._max_steps) if initial_input.budget > 0 else self._max_steps
        step_index = 0

        while step_index < budget:
            # Build refinement input for this step
            input_v1 = StructuralRefinementInputV1(
                grid81=current_grid,
                writable_mask81=mask,
            )

            # Evaluate one step
            try:
                result: OneStepAdapterResult = self._adapter(input_v1)
            except Exception as e:
                # Adapter failure -> fail closed
                step = StructuralRolloutStepV1(
                    step_index=step_index,
                    input_state_digest=current_digest,
                    termination_disposition=RolloutDisposition.ADAPTER_FAILURE,
                    candidate_count=0,
                )
                receipt = StructuralRolloutReceiptV1(
                    step_index=step_index,
                    input_state_digest=current_digest,
                    previous_receipt_digest=previous_receipt_digest,
                    termination_disposition=RolloutDisposition.ADAPTER_FAILURE,
                )
                steps.append(step)
                receipts.append(receipt)
                return StructuralRolloutResultV1(
                    initial_input_digest=initial_input.combined_digest,
                    initial_grid81=initial_input.grid81,
                    initial_mask81=mask,
                    steps=tuple(steps),
                    receipts=tuple(receipts),
                    terminal_disposition=RolloutDisposition.ADAPTER_FAILURE,
                    final_state_digest=current_digest,
                    total_steps=len(steps),
                    step_budget=budget,
                )

            # Check for contract violations FIRST — before accessing proposal
            violation_codes = result.violation_codes

            # Candidate set digest = oracle transition digest
            candidate_set_digest = result.oracle_transition_digest

            # Selected transition digest = oracle transition digest
            # (canonical selection is already done by the oracle)
            selected_transition_digest = result.oracle_transition_digest

            # Check for contract violations — fail closed before touching proposal
            if any("ILLEGAL_WRITE" in v for v in violation_codes):
                # Contract violation -> fail closed
                step = StructuralRolloutStepV1(
                    step_index=step_index,
                    input_state_digest=current_digest,
                    candidate_set_digest=candidate_set_digest,
                    selected_transition_digest=selected_transition_digest,
                    output_state_digest=current_digest,
                    violation_codes=violation_codes,
                    quiescence=result.quiescence,
                    termination_disposition=RolloutDisposition.CONTRACT_VIOLATION,
                    candidate_count=result.candidate_count,
                    rationale_codes=result.rationale_codes,
                )
                receipt = StructuralRolloutReceiptV1(
                    step_index=step_index,
                    input_state_digest=current_digest,
                    candidate_set_digest=candidate_set_digest,
                    selected_transition_digest=selected_transition_digest,
                    output_state_digest=current_digest,
                    violation_codes=violation_codes,
                    previous_receipt_digest=previous_receipt_digest,
                    termination_disposition=RolloutDisposition.CONTRACT_VIOLATION,
                )
                steps.append(step)
                receipts.append(receipt)
                return StructuralRolloutResultV1(
                    initial_input_digest=initial_input.combined_digest,
                    initial_grid81=initial_input.grid81,
                    initial_mask81=mask,
                    steps=tuple(steps),
                    receipts=tuple(receipts),
                    terminal_disposition=RolloutDisposition.CONTRACT_VIOLATION,
                    final_state_digest=current_digest,
                    total_steps=len(steps),
                    step_budget=budget,
                )

            # Extract canonical next state grid (safe: no violation codes)
            proposed = result.proposal.proposed_grid81
            next_digest = _digest({"grid81": list(proposed)})

            # Check quiescence
            if result.quiescence:
                step = StructuralRolloutStepV1(
                    step_index=step_index,
                    input_state_digest=current_digest,
                    candidate_set_digest=candidate_set_digest,
                    selected_transition_digest=selected_transition_digest,
                    output_state_digest=next_digest,
                    violation_codes=violation_codes,
                    quiescence=True,
                    termination_disposition=RolloutDisposition.QUIESCENT,
                    candidate_count=result.candidate_count,
                    rationale_codes=result.rationale_codes,
                )
                receipt = StructuralRolloutReceiptV1(
                    step_index=step_index,
                    input_state_digest=current_digest,
                    candidate_set_digest=candidate_set_digest,
                    selected_transition_digest=selected_transition_digest,
                    output_state_digest=next_digest,
                    violation_codes=violation_codes,
                    previous_receipt_digest=previous_receipt_digest,
                    quiescence=True,
                    termination_disposition=RolloutDisposition.QUIESCENT,
                )
                steps.append(step)
                receipts.append(receipt)
                return StructuralRolloutResultV1(
                    initial_input_digest=initial_input.combined_digest,
                    initial_grid81=initial_input.grid81,
                    initial_mask81=mask,
                    steps=tuple(steps),
                    receipts=tuple(receipts),
                    terminal_disposition=RolloutDisposition.QUIESCENT,
                    final_state_digest=next_digest,
                    total_steps=len(steps),
                    step_budget=budget,
                )

            # Check for NO_VALID_TRANSITION
            if result.violation_codes and "NO_VALID_TRANSITION" in result.violation_codes:
                step = StructuralRolloutStepV1(
                    step_index=step_index,
                    input_state_digest=current_digest,
                    candidate_set_digest=candidate_set_digest,
                    selected_transition_digest=selected_transition_digest,
                    output_state_digest=next_digest,
                    violation_codes=violation_codes,
                    quiescence=result.quiescence,
                    termination_disposition=RolloutDisposition.NO_VALID_TRANSITION,
                    candidate_count=result.candidate_count,
                    rationale_codes=result.rationale_codes,
                )
                receipt = StructuralRolloutReceiptV1(
                    step_index=step_index,
                    input_state_digest=current_digest,
                    candidate_set_digest=candidate_set_digest,
                    selected_transition_digest=selected_transition_digest,
                    output_state_digest=next_digest,
                    violation_codes=violation_codes,
                    previous_receipt_digest=previous_receipt_digest,
                    termination_disposition=RolloutDisposition.NO_VALID_TRANSITION,
                )
                steps.append(step)
                receipts.append(receipt)
                return StructuralRolloutResultV1(
                    initial_input_digest=initial_input.combined_digest,
                    initial_grid81=initial_input.grid81,
                    initial_mask81=mask,
                    steps=tuple(steps),
                    receipts=tuple(receipts),
                    terminal_disposition=RolloutDisposition.NO_VALID_TRANSITION,
                    final_state_digest=next_digest,
                    total_steps=len(steps),
                    step_budget=budget,
                )

            # Check identity transition FIRST — before cycle detection
            # If next_digest == current_digest, the grid didn't change: RESOLVED
            if next_digest == current_digest:
                step = StructuralRolloutStepV1(
                    step_index=step_index,
                    input_state_digest=current_digest,
                    candidate_set_digest=candidate_set_digest,
                    selected_transition_digest=selected_transition_digest,
                    output_state_digest=next_digest,
                    violation_codes=violation_codes,
                    quiescence=False,
                    termination_disposition=RolloutDisposition.RESOLVED,
                    candidate_count=result.candidate_count,
                    rationale_codes=result.rationale_codes,
                )
                receipt = StructuralRolloutReceiptV1(
                    step_index=step_index,
                    input_state_digest=current_digest,
                    candidate_set_digest=candidate_set_digest,
                    selected_transition_digest=selected_transition_digest,
                    output_state_digest=next_digest,
                    violation_codes=violation_codes,
                    previous_receipt_digest=previous_receipt_digest,
                    termination_disposition=RolloutDisposition.RESOLVED,
                )
                steps.append(step)
                receipts.append(receipt)
                return StructuralRolloutResultV1(
                    initial_input_digest=initial_input.combined_digest,
                    initial_grid81=initial_input.grid81,
                    initial_mask81=mask,
                    steps=tuple(steps),
                    receipts=tuple(receipts),
                    terminal_disposition=RolloutDisposition.RESOLVED,
                    final_state_digest=next_digest,
                    total_steps=len(steps),
                    step_budget=budget,
                )

            # Check for cycle (state digest seen before, and NOT identity)
            if next_digest in seen_digests:
                step = StructuralRolloutStepV1(
                    step_index=step_index,
                    input_state_digest=current_digest,
                    candidate_set_digest=candidate_set_digest,
                    selected_transition_digest=selected_transition_digest,
                    output_state_digest=next_digest,
                    violation_codes=violation_codes,
                    quiescence=result.quiescence,
                    termination_disposition=RolloutDisposition.CYCLE_DETECTED,
                    candidate_count=result.candidate_count,
                    rationale_codes=result.rationale_codes,
                )
                receipt = StructuralRolloutReceiptV1(
                    step_index=step_index,
                    input_state_digest=current_digest,
                    candidate_set_digest=candidate_set_digest,
                    selected_transition_digest=selected_transition_digest,
                    output_state_digest=next_digest,
                    violation_codes=violation_codes,
                    previous_receipt_digest=previous_receipt_digest,
                    termination_disposition=RolloutDisposition.CYCLE_DETECTED,
                )
                steps.append(step)
                receipts.append(receipt)
                return StructuralRolloutResultV1(
                    initial_input_digest=initial_input.combined_digest,
                    initial_grid81=initial_input.grid81,
                    initial_mask81=mask,
                    steps=tuple(steps),
                    receipts=tuple(receipts),
                    terminal_disposition=RolloutDisposition.CYCLE_DETECTED,
                    final_state_digest=next_digest,
                    total_steps=len(steps),
                    step_budget=budget,
                    cycle_detected=True,
                    cycle_state_digest=next_digest,
                )

            # Check: grid actually changed (non-identity transition)
            if next_digest == current_digest:
                # Identity transition — state is resolved
                step = StructuralRolloutStepV1(
                    step_index=step_index,
                    input_state_digest=current_digest,
                    candidate_set_digest=candidate_set_digest,
                    selected_transition_digest=selected_transition_digest,
                    output_state_digest=next_digest,
                    violation_codes=violation_codes,
                    quiescence=False,
                    termination_disposition=RolloutDisposition.RESOLVED,
                    candidate_count=result.candidate_count,
                    rationale_codes=result.rationale_codes,
                )
                receipt = StructuralRolloutReceiptV1(
                    step_index=step_index,
                    input_state_digest=current_digest,
                    candidate_set_digest=candidate_set_digest,
                    selected_transition_digest=selected_transition_digest,
                    output_state_digest=next_digest,
                    violation_codes=violation_codes,
                    previous_receipt_digest=previous_receipt_digest,
                    termination_disposition=RolloutDisposition.RESOLVED,
                )
                steps.append(step)
                receipts.append(receipt)
                return StructuralRolloutResultV1(
                    initial_input_digest=initial_input.combined_digest,
                    initial_grid81=initial_input.grid81,
                    initial_mask81=mask,
                    steps=tuple(steps),
                    receipts=tuple(receipts),
                    terminal_disposition=RolloutDisposition.RESOLVED,
                    final_state_digest=next_digest,
                    total_steps=len(steps),
                    step_budget=budget,
                )

            # Valid transition — continue
            step = StructuralRolloutStepV1(
                step_index=step_index,
                input_state_digest=current_digest,
                candidate_set_digest=candidate_set_digest,
                selected_transition_digest=selected_transition_digest,
                output_state_digest=next_digest,
                violation_codes=violation_codes,
                quiescence=result.quiescence,
                termination_disposition=None,
                candidate_count=result.candidate_count,
                rationale_codes=result.rationale_codes,
            )
            receipt = StructuralRolloutReceiptV1(
                step_index=step_index,
                input_state_digest=current_digest,
                candidate_set_digest=candidate_set_digest,
                selected_transition_digest=selected_transition_digest,
                output_state_digest=next_digest,
                violation_codes=violation_codes,
                previous_receipt_digest=previous_receipt_digest,
            )
            steps.append(step)
            receipts.append(receipt)

            # Advance state
            seen_digests.append(next_digest)
            previous_receipt_digest = receipt.receipt_digest
            current_grid = proposed
            current_digest = next_digest
            step_index += 1

        # Budget exhausted
        final_disposition = RolloutDisposition.STEP_BUDGET_EXHAUSTED
        return StructuralRolloutResultV1(
            initial_input_digest=initial_input.combined_digest,
            initial_grid81=initial_input.grid81,
            initial_mask81=mask,
            steps=tuple(steps),
            receipts=tuple(receipts),
            terminal_disposition=final_disposition,
            final_state_digest=current_digest,
            total_steps=len(steps),
            step_budget=budget,
        )
