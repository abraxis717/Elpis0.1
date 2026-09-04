from __future__ import annotations

import random

from c2r6p1_bridge.adapter import (
    adapt_projection_to_refiner_input,
)
from c2r6p1_bridge.contracts import CandidateMoveV1

from guided_refiner import (
    choose_strict_improvement,
    replay_candidate_path,
    run_guided_search,
    structural_cost,
)


def candidate(move, index):
    return CandidateMoveV1(
        move=move,
        enum_index=index,
    )


def test_choice_requires_strict_improvement():
    a = candidate(("set", 1, 4), 0)
    b = candidate(("set", 2, 4), 1)

    chosen, cost, tied, predecessor = (
        choose_strict_improvement(
            current_cost=2,
            base_order=(a, b),
            ordered=(b, a),
            cost_by_move={
                a.move: 2,
                b.move: 3,
            },
        )
    )

    assert chosen is None
    assert cost == 2
    assert tied == ()
    assert predecessor is None


def test_guidance_can_change_only_equal_best_choice():
    a = candidate(("set", 1, 4), 0)
    b = candidate(("set", 2, 4), 1)
    c = candidate(("set", 3, 4), 2)

    chosen, cost, tied, predecessor = (
        choose_strict_improvement(
            current_cost=4,
            base_order=(a, b, c),
            ordered=(b, a, c),
            cost_by_move={
                a.move: 2,
                b.move: 2,
                c.move: 3,
            },
        )
    )

    assert chosen == b
    assert predecessor == a
    assert cost == 2
    assert set(x.move for x in tied) == {
        a.move,
        b.move,
    }


def test_unique_best_is_order_invariant():
    a = candidate(("set", 1, 4), 0)
    b = candidate(("set", 2, 4), 1)
    c = candidate(("set", 3, 4), 2)

    first = choose_strict_improvement(
        current_cost=4,
        base_order=(a, b, c),
        ordered=(b, a, c),
        cost_by_move={
            a.move: 2,
            b.move: 1,
            c.move: 3,
        },
    )

    second = choose_strict_improvement(
        current_cost=4,
        base_order=(a, b, c),
        ordered=(c, a, b),
        cost_by_move={
            a.move: 2,
            b.move: 1,
            c.move: 3,
        },
    )

    assert first[0] == b
    assert second[0] == b
    assert first[1] == second[1] == 1


def test_zero_agreement_guidance_is_predecessor_equivalent(
    one_projected,
):
    ri = adapt_projection_to_refiner_input(
        one_projected
    )

    plain = run_guided_search(
        initial=ri,
        rng=random.Random(9127),
        budget=8,
        proposal_source=None,
        restarts=2,
        plateau=1,
    )

    guided = run_guided_search(
        initial=ri,
        rng=random.Random(9127),
        budget=8,
        proposal_source=lambda state: state.grid81,
        restarts=2,
        plateau=1,
    )

    assert (
        guided.final_input.refinement_state_fingerprint
        == plain.final_input.refinement_state_fingerprint
    )
    assert guided.chosen_path == plain.chosen_path
    assert guided.best_cost == plain.best_cost
    assert guided.authority_granted == 0


def test_guided_path_replays_through_frozen_p1(
    one_projected,
):
    ri = adapt_projection_to_refiner_input(
        one_projected
    )

    proposal = tuple(
        9 if ri.writable_mask[i] else ri.grid81[i]
        for i in range(81)
    )

    result = run_guided_search(
        initial=ri,
        rng=random.Random(311),
        budget=10,
        proposal_source=lambda _state: proposal,
        restarts=2,
        plateau=2,
    )

    replayed = replay_candidate_path(
        ri,
        result.chosen_path,
    )

    assert (
        replayed.refinement_state_fingerprint
        == result.final_input.refinement_state_fingerprint
    )
    assert replayed.frozen_mask == ri.frozen_mask
    assert replayed.writable_mask == ri.writable_mask
    assert replayed.invariants == ri.invariants
    assert structural_cost(replayed) == result.best_cost
    assert result.stats["authority_granted"] == 0
    assert result.authority_granted == 0


def test_structural_cost_matches_frozen_r0_2_objective(
    one_projected,
):
    import guided_search_r0_2 as R02

    ri = adapt_projection_to_refiner_input(
        one_projected
    )

    frozen_cost = (
        R02.predecessor_search_functions()["cost"](
            ri.grid81,
            ri.invariants,
        )
    )

    assert structural_cost(ri) == frozen_cost
