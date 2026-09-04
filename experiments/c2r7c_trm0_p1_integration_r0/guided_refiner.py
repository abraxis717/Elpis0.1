from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import random
import sys
from typing import Callable

import torch

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent

for path in (
    EXPERIMENTS / "c2r6p0_deterministic_projector",
    EXPERIMENTS / "c2r6p1_projector_refiner_abi",
    EXPERIMENTS / "c2r7c_semantic_structural_probe",
):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from c2r6p1_bridge.contracts import CandidateMoveV1, RefinerInputV1
import c2r6p1_bridge.refiners as P1R
import guided_search_r0_2 as R02
import structural_trm_generalization as TRM

EXPECTED_CHECKPOINT_SHA256 = (
    "e58e44c9227d68971d0ab5f5e4f0eaf"
    "2e05d4faa97ec8232108aa73898273129"
)

FROZEN_COST_FN = R02.predecessor_search_functions()["cost"]


class GuidedRefinerError(RuntimeError):
    pass


@dataclass(frozen=True)
class GuidedSearchResult:
    final_input: RefinerInputV1
    chosen_path: tuple[CandidateMoveV1, ...]
    iterations: int
    best_cost: int
    stats: dict[str, int]
    authority_granted: int = 0


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class FrozenTRM0ProposalSource:
    """Proposal-only wrapper around the frozen structural TRM-0."""

    def __init__(
        self,
        *,
        model,
        checkpoint_sha256: str,
        checkpoint_epoch: int,
    ) -> None:
        self.model = model
        self.checkpoint_sha256 = str(checkpoint_sha256)
        self.checkpoint_epoch = int(checkpoint_epoch)

    @classmethod
    def from_checkpoint(
        cls,
        path: Path,
        *,
        expected_sha256: str = EXPECTED_CHECKPOINT_SHA256,
    ) -> "FrozenTRM0ProposalSource":
        path = Path(path)

        if not path.is_file():
            raise GuidedRefinerError(
                f"checkpoint missing: {path}"
            )

        actual = sha256_file(path)

        if actual != expected_sha256:
            raise GuidedRefinerError(
                "checkpoint identity mismatch: "
                f"{actual} != {expected_sha256}"
            )

        model, checkpoint = TRM.load_model(path)

        return cls(
            model=model,
            checkpoint_sha256=actual,
            checkpoint_epoch=int(
                checkpoint.get("epoch", -1)
            ),
        )

    def __call__(
        self,
        ri: RefinerInputV1,
    ) -> tuple[int, ...]:
        with torch.inference_mode():
            _, proposed_tensor, _ = self.model.propose(
                TRM.grid_tensor(ri.grid81),
                TRM.grid_tensor(ri.writable_mask),
                TRM.bits_tensor(ri.declared_features),
                TRM.bits_tensor(ri.active_residual),
                carry=None,
            )

        proposed = tuple(
            int(value)
            for value in proposed_tensor[0].tolist()
        )

        if len(proposed) != 81:
            raise GuidedRefinerError(
                f"TRM proposal width {len(proposed)} != 81"
            )

        return proposed


def structural_cost(ri: RefinerInputV1) -> int:
    """Delegate exactly to the frozen R0.2 predecessor objective."""
    return int(
        FROZEN_COST_FN(
            ri.grid81,
            ri.invariants,
        )
    )


def _evaluated_mutating_candidates(
    ri: RefinerInputV1,
):
    """Return only already-legal P1 candidates that actually mutate state."""
    candidates = []
    transitions = {}

    for candidate in P1R.legal_candidates(ri):
        transition = P1R.apply_candidate(
            ri,
            candidate,
        )

        if not transition.validation_ok:
            raise GuidedRefinerError(
                "P1 legal candidate failed authoritative "
                "transition validation"
            )

        if transition.grid_after == ri.grid81:
            continue

        candidates.append(candidate)
        transitions[candidate.move] = transition

    return candidates, transitions


def _transition_cost(
    transition,
    invariants,
) -> int:
    return int(
        FROZEN_COST_FN(
            transition.grid_after,
            invariants,
        )
    )


def choose_strict_improvement(
    *,
    current_cost: int,
    base_order,
    ordered,
    cost_by_move,
):
    """Frozen predecessor choice law.

    Only strict improvements are eligible. Ordering can therefore affect
    the result only when multiple improving candidates have the same
    minimum deterministic cost.
    """
    best = None
    best_cost = int(current_cost)

    for candidate in ordered:
        cost = int(cost_by_move[candidate.move])

        if cost < best_cost:
            best = candidate
            best_cost = cost

    if best is None:
        return None, best_cost, (), None

    tied = tuple(
        candidate
        for candidate in ordered
        if int(cost_by_move[candidate.move]) == best_cost
    )

    predecessor = next(
        candidate
        for candidate in base_order
        if int(cost_by_move[candidate.move]) == best_cost
    )

    return best, best_cost, tied, predecessor


def _proposal_order(
    *,
    ri: RefinerInputV1,
    candidates,
    transitions,
    proposal,
):
    moves = [
        candidate.move
        for candidate in candidates
    ]

    ordered_moves = R02.stable_guidance_order(
        ri.grid81,
        moves,
        proposal,
        apply_fn=lambda _current, move: (
            transitions[move].grid_after
        ),
    )

    by_move = {
        candidate.move: candidate
        for candidate in candidates
    }

    return [
        by_move[move]
        for move in ordered_moves
    ]


def replay_candidate_path(
    initial: RefinerInputV1,
    path: tuple[CandidateMoveV1, ...],
) -> RefinerInputV1:
    """Fail-closed replay through the frozen P1 authority."""
    current = initial

    for recorded in path:
        offered = {
            candidate.move: candidate
            for candidate in P1R.legal_candidates(current)
        }

        candidate = offered.get(recorded.move)

        if candidate is None:
            raise GuidedRefinerError(
                "recorded path contains a move no longer "
                "offered by P1 authority"
            )

        if candidate.enum_index != recorded.enum_index:
            raise GuidedRefinerError(
                "recorded candidate enum identity changed"
            )

        transition = P1R.apply_candidate(
            current,
            candidate,
        )

        if not transition.validation_ok:
            raise GuidedRefinerError(
                "recorded candidate failed P1 validation"
            )

        if transition.grid_after == current.grid81:
            raise GuidedRefinerError(
                "recorded path contains a non-mutating candidate"
            )

        current = P1R._next_input(
            current,
            transition,
        )

    return current


def run_guided_search(
    *,
    initial: RefinerInputV1,
    rng: random.Random,
    budget: int,
    proposal_source: Callable[[RefinerInputV1], tuple[int, ...]] | None,
    restarts: int = 8,
    plateau: int = 25,
) -> GuidedSearchResult:
    """P1-backed realization of the frozen R0.2 search law.

    P1 exclusively owns candidate legality and transition validation.
    The deterministic objective is the frozen C2R7-C cost.
    TRM guidance only stably reorders already-legal candidates before
    the strict-improvement scan. Plateau shakes are never guided.
    """
    if budget < 0:
        raise ValueError("budget cannot be negative")
    if restarts < 1:
        raise ValueError("restarts must be >= 1")
    if plateau < 0:
        raise ValueError("plateau cannot be negative")

    best_cost = structural_cost(initial)
    best_path: tuple[CandidateMoveV1, ...] = ()
    iterations = 0

    stats = {
        "guidance_queries": 0,
        "ordered_iterations": 0,
        "order_changed_iterations": 0,
        "equal_best_ties": 0,
        "guidance_tiebreak_changed_choice": 0,
        "plateau_shakes": 0,
        "restarts_started": 0,
        "authority_granted": 0,
    }

    for _restart in range(restarts):
        stats["restarts_started"] += 1

        current = initial
        current_path: list[CandidateMoveV1] = []
        cost = structural_cost(current)
        stuck = 0

        while iterations < budget:
            if cost == 0:
                replayed = replay_candidate_path(
                    initial,
                    tuple(current_path),
                )

                if (
                    replayed.refinement_state_fingerprint
                    != current.refinement_state_fingerprint
                ):
                    raise GuidedRefinerError(
                        "resolved path replay mismatch"
                    )

                return GuidedSearchResult(
                    final_input=current,
                    chosen_path=tuple(current_path),
                    iterations=iterations,
                    best_cost=0,
                    stats=stats,
                )

            iterations += 1

            candidates, transitions = (
                _evaluated_mutating_candidates(current)
            )

            if not candidates:
                break

            rng.shuffle(candidates)
            base_order = tuple(candidates)

            ordered = list(candidates)

            if proposal_source is not None:
                proposal = proposal_source(current)

                if len(proposal) != 81:
                    raise GuidedRefinerError(
                        "proposal source returned non-Grid81"
                    )

                ordered = _proposal_order(
                    ri=current,
                    candidates=candidates,
                    transitions=transitions,
                    proposal=proposal,
                )

                stats["guidance_queries"] += 1
                stats["ordered_iterations"] += 1

                if tuple(ordered) != base_order:
                    stats["order_changed_iterations"] += 1

            cost_by_move = {
                candidate.move: _transition_cost(
                    transitions[candidate.move],
                    current.invariants,
                )
                for candidate in candidates
            }

            (
                best_candidate,
                best_candidate_cost,
                tied,
                predecessor_choice,
            ) = choose_strict_improvement(
                current_cost=cost,
                base_order=base_order,
                ordered=ordered,
                cost_by_move=cost_by_move,
            )

            if (
                proposal_source is not None
                and best_candidate is not None
            ):
                if len(tied) > 1:
                    stats["equal_best_ties"] += 1

                if best_candidate != predecessor_choice:
                    stats[
                        "guidance_tiebreak_changed_choice"
                    ] += 1

            if best_candidate is not None:
                transition = transitions[
                    best_candidate.move
                ]

                current = P1R._next_input(
                    current,
                    transition,
                )
                current_path.append(best_candidate)
                cost = best_candidate_cost
                stuck = 0

            else:
                stuck += 1

                if stuck > plateau:
                    break

                for _ in range(rng.randint(1, 3)):
                    (
                        shake_candidates,
                        shake_transitions,
                    ) = _evaluated_mutating_candidates(
                        current
                    )

                    if not shake_candidates:
                        continue

                    shake = rng.choice(
                        shake_candidates
                    )
                    transition = shake_transitions[
                        shake.move
                    ]

                    current = P1R._next_input(
                        current,
                        transition,
                    )
                    current_path.append(shake)
                    stats["plateau_shakes"] += 1

                cost = structural_cost(current)

            if cost < best_cost:
                best_cost = cost
                best_path = tuple(current_path)

        if best_cost == 0:
            break

    final_input = replay_candidate_path(
        initial,
        best_path,
    )

    if structural_cost(final_input) != best_cost:
        raise GuidedRefinerError(
            "best path replay changed deterministic cost"
        )

    return GuidedSearchResult(
        final_input=final_input,
        chosen_path=best_path,
        iterations=iterations,
        best_cost=best_cost,
        stats=stats,
    )


class TRM0GuidedRefiner:
    """Convenience binding for one deterministic search invocation."""

    name = "TRM0GuidedRefiner"

    def __init__(
        self,
        *,
        proposal_source,
        seed: int,
        budget: int = 128,
        restarts: int = 8,
        plateau: int = 25,
    ) -> None:
        self.proposal_source = proposal_source
        self.seed = int(seed)
        self.budget = int(budget)
        self.restarts = int(restarts)
        self.plateau = int(plateau)

    def refine(
        self,
        ri: RefinerInputV1,
    ) -> GuidedSearchResult:
        return run_guided_search(
            initial=ri,
            rng=random.Random(self.seed),
            budget=self.budget,
            proposal_source=self.proposal_source,
            restarts=self.restarts,
            plateau=self.plateau,
        )
