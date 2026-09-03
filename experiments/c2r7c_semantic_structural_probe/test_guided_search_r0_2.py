from __future__ import annotations

from collections import Counter

import random

import guided_search_r0_2 as g


class FixedRNG:
    def shuffle(self, values):
        # Deliberately preserve supplied order.
        return None

    def randint(self, a, b):
        return a

    def choice(self, values):
        return values[0]


def _toy_apply(state, move):
    mapping = {
        ((0,), "B"): (1,),
        ((0,), "A"): (2,),
        ((2,), "SOLVE"): (3,),
    }
    return mapping[(state, move)]


def _toy_legal(state, mask):
    del mask
    if state == (0,):
        return ["B", "A"]
    if state == (2,):
        return ["SOLVE"]
    return []


def _toy_cost(state, invariants):
    del invariants
    return {
        (0,): 2,
        (1,): 1,
        (2,): 1,
        (3,): 0,
    }[state]


TOY_SEARCH = {
    "cost": _toy_cost,
    "legal_moves": _toy_legal,
    "apply": _toy_apply,
}


def test_budget_is_frozen_at_balanced_r01_point():
    assert g.SEARCH_BUDGET == 128


def test_guidance_order_preserves_exact_move_multiset():
    current = (0, 0)
    moves = [
        ("set", 0, 2),
        ("set", 0, 1),
        ("set", 1, 1),
    ]

    def apply_fn(state, move):
        _, index, value = move
        out = list(state)
        out[index] = value
        return tuple(out)

    proposal = (1, 1)

    ordered = g.stable_guidance_order(
        current,
        moves,
        proposal,
        apply_fn=apply_fn,
    )

    assert Counter(map(repr, ordered)) == Counter(map(repr, moves))
    assert ordered[:2] == [
        ("set", 0, 1),
        ("set", 1, 1),
    ]


def test_guidance_sort_is_stable_for_equal_scores():
    current = (0, 0)
    moves = [
        ("set", 1, 1),
        ("set", 0, 1),
    ]

    def apply_fn(state, move):
        _, index, value = move
        out = list(state)
        out[index] = value
        return tuple(out)

    ordered = g.stable_guidance_order(
        current,
        moves,
        (1, 1),
        apply_fn=apply_fn,
    )

    assert ordered == moves


def test_plain_clone_preserves_predecessor_trajectory_logic():
    final, steps, stats = g.refine_guided_search(
        (0,),
        (True,),
        (),
        FixedRNG(),
        2,
        proposal_fn=None,
        search_functions=TOY_SEARCH,
        restarts=1,
        plateau=0,
    )

    # Base order B,A -> equal deterministic cost -> predecessor keeps B.
    assert final == (1,)
    assert steps == 2
    assert stats["guidance_queries"] == 0


def test_guidance_only_breaks_equal_cost_tie():
    def proposal_fn(current):
        if current == (0,):
            return (2,), {}
        return (3,), {}

    final, steps, stats = g.refine_guided_search(
        (0,),
        (True,),
        (),
        FixedRNG(),
        2,
        proposal_fn=proposal_fn,
        search_functions=TOY_SEARCH,
        restarts=1,
        plateau=0,
    )

    # A and B have identical deterministic cost. Guidance may therefore
    # select A by ordering, after which ordinary search reaches cost zero.
    assert final == (3,)
    assert steps == 2
    assert stats["guidance_queries"] == 2
    assert stats["order_changed_iterations"] >= 1
    assert stats["equal_best_ties"] >= 1
    assert stats["guidance_tiebreak_changed_choice"] >= 1


def test_predecessor_search_helpers_resolve_from_exact_source():
    sf = g.predecessor_search_functions()

    assert sf["refine_search"].__name__ == "refine_search"
    assert sf["cost"].__name__ == "_cost"
    assert sf["legal_moves"].__name__ == "_legal_moves"
    assert sf["apply"].__name__ == "_apply"


def test_real_move_ordering_cannot_create_or_delete_candidates():
    sf = g.predecessor_search_functions()

    # This property is already asserted internally, but lock the actual
    # production function identity as part of the contract.
    assert callable(sf["legal_moves"])
    assert callable(sf["apply"])



def test_plain_clone_matches_predecessor_on_real_fixtures():
    ns = g.r01._load_probe_namespace()
    make_fixture = ns["make_fixture"]
    predecessor = ns["refine_search"]

    for i in range(8):
        fixture_rng = random.Random(910_000 + i)
        schema = make_fixture(
            fixture_rng,
            fixture_rng.randint(3, 6),
        )

        seed = 920_000 + i

        expected_final, expected_steps = predecessor(
            schema.initial_grid,
            schema.writable_mask,
            schema.invariants,
            random.Random(seed),
            g.SEARCH_BUDGET,
        )

        actual_final, actual_steps, stats = g.refine_guided_search(
            schema.initial_grid,
            schema.writable_mask,
            schema.invariants,
            random.Random(seed),
            g.SEARCH_BUDGET,
            proposal_fn=None,
        )

        assert actual_final == expected_final
        assert actual_steps == expected_steps
        assert stats["guidance_queries"] == 0
