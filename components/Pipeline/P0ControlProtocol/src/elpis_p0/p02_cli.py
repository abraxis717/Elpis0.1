"""P0.2 CLI - command-line interface for one-child affine expansion."""
from __future__ import annotations

import json
import sys

from elpis.contracts.budget import BudgetVector, Charge

from .p02_runner import (
    DeterministicProposalTRM,
    run_p02_expansion,
)
from .expansion import EXPANSION_TOKEN, VOID_TOKEN


def _golden_parent_grid() -> tuple[int, ...]:
    """Create a parent grid with one EXPANSION cell at position 40."""
    grid = [VOID_TOKEN] * 81
    grid[0] = 1   # INPUT
    grid[1] = 2   # TRANSFORM
    grid[2] = 3   # OUTPUT
    grid[40] = EXPANSION_TOKEN  # Central cell proposes expansion
    grid[80] = 9  # RESOLUTION
    return tuple(grid)


def run_golden() -> None:
    """Run the golden P0.2 expansion request and print JSON result."""
    parent_grid = _golden_parent_grid()

    # Parent TRM: proposes expansion at cell 40
    parent_trm = DeterministicProposalTRM(
        proposed_grid81=parent_grid,
        expansion_cells=(40,),
    )

    # Child TRM: resolves expansion cell to OUTPUT (3)
    child_grid = list(parent_grid)
    child_grid[40] = 3  # Resolved to OUTPUT
    child_trm = DeterministicProposalTRM(
        proposed_grid81=tuple(child_grid),
        expansion_cells=(),
    )

    # Budget: grant steps=10, depth=1
    initial_budget = BudgetVector(
        steps=10,
        depth=1,
        backend=None,
        tokens=None,
        energy=None,
        wall_ms=None,
        writes=None,
    )

    spawn_cost = Charge(steps=1, depth=0)
    child_allocation = Charge(steps=5, depth=0)
    child_refinement_charge = Charge(steps=2, depth=0)

    result = run_p02_expansion(
        request_id="p02-golden-001",
        parent_seed_grid81=parent_grid,
        parent_trm=parent_trm,
        child_trm=child_trm,
        initial_budget=initial_budget,
        spawn_cost=spawn_cost,
        child_allocation=child_allocation,
        child_refinement_charge=child_refinement_charge,
        current_depth=0,
    )

    # Output summary
    output = {
        "request_id": result.request_id,
        "admission_decision": result.admission.decision,
        "chosen_cell": result.admission.chosen_cell,
        "child_allocated": result.child_allocated,
        "child_inference_invoked": result.child_inference_invoked,
        "child_closed": result.child_closed,
        "structural_result_digest": result.structural_result_digest,
        "expert_activated": result.expert_activated,
        "artifact_executed": result.artifact_executed,
        "memory_written": result.memory_written,
        "governance_invoked": result.governance_invoked,
        "stop_authorized": result.stop_authorized,
    }

    if result.fold_record:
        output["folded_token"] = result.fold_record.folded_token
        output["unresolved_expansion"] = result.fold_record.unresolved_expansion
        output["fold_after_digest"] = result.fold_record.parent_after_digest

    if result.child_seed:
        output["child_seed_digest"] = result.child_seed.child_seed_digest

    print(json.dumps(output, indent=2))


def main() -> None:
    if len(sys.argv) < 2:
        run_golden()
        return

    command = sys.argv[1]
    if command == "golden":
        run_golden()
    elif command == "help":
        print("Usage: elpis-p02 [golden|help]")
        print("  golden  - Run the golden P0.2 expansion request")
        print("  help    - Show this help message")
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
