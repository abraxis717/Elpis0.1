"""C2R7C TRM-0 guided-search R0.2.

The frozen TRM has no execution authority.

The predecessor legal move set and deterministic residual cost remain
authoritative.  TRM output may only stably reorder the already-legal move
list so that, when multiple moves attain the same best deterministic cost,
the predecessor search trajectory may prefer a move locally agreeing with
the TRM proposal.
"""

from __future__ import annotations

from collections import Counter

import torch

import structural_trm_generalization as r01


SEARCH_BUDGET = 128

ARM_PLAIN = "plain_search"
ARM_MATCHED = "search_trm_matched"
ARM_ZERO = "search_trm_zero_residual"
ARM_MISMATCH = "search_trm_mismatched_residual"


class GuidanceUnevaluable(RuntimeError):
    pass


def _changed_indices(current, candidate):
    return tuple(
        i for i, (a, b) in enumerate(zip(current, candidate))
        if a != b
    )


def move_proposal_agreement(
    current,
    move,
    proposal,
    *,
    apply_fn,
):
    """Fraction of cells changed by `move` agreeing with TRM proposal.

    The score cannot make an illegal move legal and cannot inspect any
    semantic sidecar.  It sees only current grid, one already-legal move,
    and the model's proposed native grid.
    """
    candidate = apply_fn(current, move)
    changed = _changed_indices(current, candidate)

    if not changed:
        return 0.0

    matches = sum(
        int(candidate[i] == proposal[i])
        for i in changed
    )
    return matches / len(changed)


def stable_guidance_order(
    current,
    moves,
    proposal,
    *,
    apply_fn,
):
    """Stable reorder only; exact move multiset is preserved."""
    before = list(moves)

    ordered = sorted(
        before,
        key=lambda move: -move_proposal_agreement(
            current,
            move,
            proposal,
            apply_fn=apply_fn,
        ),
    )

    assert Counter(map(repr, ordered)) == Counter(map(repr, before))
    return ordered


def predecessor_search_functions():
    """Recover exact predecessor search helpers from refine_search globals."""
    ns = r01._load_probe_namespace()
    refine_search = ns["refine_search"]
    g = refine_search.__globals__

    return {
        "refine_search": refine_search,
        "cost": g["_cost"],
        "legal_moves": g["_legal_moves"],
        "apply": g["_apply"],
    }


def build_trm_proposal_fn(
    *,
    model,
    schema,
    residual_fn,
    mode,
):
    """Return a state-local proposal oracle with R0.1 residual semantics."""
    if mode not in {"matched", "zero", "mismatched"}:
        raise ValueError(mode)

    initial_residual = residual_fn(
        schema.initial_grid,
        schema.invariants,
    )
    declared, _ = r01.encode_constraint_state(
        schema.invariants,
        initial_residual,
    )

    mask_t = r01.grid_tensor(schema.writable_mask)

    def proposal_fn(current):
        current_residual = residual_fn(
            current,
            schema.invariants,
        )

        _, matched_active = r01.encode_constraint_state(
            schema.invariants,
            current_residual,
        )

        active, mismatch = r01.select_arm_residual(
            mode,
            declared,
            matched_active,
        )

        metadata = {
            "mismatch_distinct": None,
            "mismatch_reason": "",
        }

        if mode == "mismatched":
            metadata["mismatch_distinct"] = bool(mismatch.distinct)
            metadata["mismatch_reason"] = mismatch.reason

            if not mismatch.distinct:
                raise GuidanceUnevaluable(mismatch.reason)

            violations = r01.validate_mismatch_contract(
                declared,
                matched_active,
                active,
            )
            if violations:
                raise GuidanceUnevaluable(
                    "mismatch_contract_violation:"
                    + ";".join(violations)
                )

        grid_t = r01.grid_tensor(current)

        with torch.inference_mode():
            _, proposed_tensor, _ = model.propose(
                grid_t,
                mask_t,
                r01.bits_tensor(declared),
                r01.bits_tensor(active),
                carry=None,
            )

        proposal = tuple(
            int(v)
            for v in proposed_tensor[0].tolist()
        )

        return proposal, metadata

    return proposal_fn


def refine_guided_search(
    grid,
    mask,
    invariants,
    rng,
    budget,
    *,
    proposal_fn=None,
    search_functions=None,
    restarts=8,
    plateau=25,
):
    """Exact predecessor search plus optional stable proposal tie-ordering."""
    sf = (
        predecessor_search_functions()
        if search_functions is None
        else search_functions
    )

    cost_fn = sf["cost"]
    legal_moves_fn = sf["legal_moves"]
    apply_fn = sf["apply"]

    best = grid
    best_cost = cost_fn(grid, invariants)
    iterations = 0

    stats = {
        "guidance_queries": 0,
        "ordered_iterations": 0,
        "order_changed_iterations": 0,
        "mismatch_distinct_steps": 0,
        "mismatch_unevaluable": False,
        "mismatch_reason": "",
        "equal_best_ties": 0,
        "guidance_tiebreak_changed_choice": 0,
    }

    for _ in range(restarts):
        current = grid
        cost = cost_fn(current, invariants)
        stuck = 0

        while iterations < budget:
            if cost == 0:
                return current, iterations, stats

            iterations += 1

            moves = legal_moves_fn(current, mask)
            if not moves:
                break

            # Exact predecessor stochastic base ordering.
            rng.shuffle(moves)
            base_order = tuple(moves)

            if proposal_fn is not None:
                try:
                    proposal, metadata = proposal_fn(current)
                except GuidanceUnevaluable as exc:
                    stats["mismatch_unevaluable"] = True
                    stats["mismatch_reason"] = str(exc)
                    return best, iterations, stats

                stats["guidance_queries"] += 1

                if metadata.get("mismatch_distinct") is True:
                    stats["mismatch_distinct_steps"] += 1

                before = tuple(moves)

                moves = stable_guidance_order(
                    current,
                    moves,
                    proposal,
                    apply_fn=apply_fn,
                )

                stats["ordered_iterations"] += 1
                if tuple(moves) != before:
                    stats["order_changed_iterations"] += 1

            # Exact predecessor deterministic objective.
            best_move = None
            best_move_cost = cost
            move_costs = {}

            for move in moves:
                candidate_cost = cost_fn(
                    apply_fn(current, move),
                    invariants,
                )
                move_costs[move] = candidate_cost

                if candidate_cost < best_move_cost:
                    best_move = move
                    best_move_cost = candidate_cost

            if proposal_fn is not None and best_move is not None:
                tied_best = [
                    move
                    for move in moves
                    if move_costs[move] == best_move_cost
                ]
                if len(tied_best) > 1:
                    stats["equal_best_ties"] += 1

                predecessor_choice = next(
                    move
                    for move in base_order
                    if move_costs[move] == best_move_cost
                )

                if best_move != predecessor_choice:
                    stats["guidance_tiebreak_changed_choice"] += 1

            if best_move is not None:
                current = apply_fn(current, best_move)
                cost = best_move_cost
                stuck = 0
            else:
                stuck += 1

                if stuck > plateau:
                    break

                # Exact predecessor plateau escape. TRM does not reorder this.
                for _ in range(rng.randint(1, 3)):
                    shake_moves = legal_moves_fn(current, mask)
                    if shake_moves:
                        current = apply_fn(
                            current,
                            rng.choice(shake_moves),
                        )

                cost = cost_fn(current, invariants)

            if cost < best_cost:
                best = current
                best_cost = cost

        if best_cost == 0:
            break

    return best, iterations, stats


def run_guided_search_arm(
    *,
    arm_name,
    guidance_mode,
    model,
    schema,
    rng,
    budget,
    residual_fn,
    is_resolved_fn,
    validate_transition_fn,
    materialisable_fn,
    quiescent_fn,
):
    """Run one bounded search arm with unchanged external authority."""
    if arm_name == ARM_PLAIN:
        proposal_fn = None
    else:
        proposal_fn = build_trm_proposal_fn(
            model=model,
            schema=schema,
            residual_fn=residual_fn,
            mode=guidance_mode,
        )

    initial = schema.initial_grid
    initial_residual = residual_fn(
        initial,
        schema.invariants,
    )

    res = r01._empty_result(
        arm_name,
        len(initial_residual),
    )

    final, steps, stats = refine_guided_search(
        initial,
        schema.writable_mask,
        schema.invariants,
        rng,
        budget,
        proposal_fn=proposal_fn,
    )

    try:
        validate_transition_fn(initial, final, schema)
        res["valid_transitions"] = 1
    except Exception as exc:
        res["invalid_transitions"] = 1
        res["error"] = f"{type(exc).__name__}: {exc}"
        final = initial
        steps = 0

    if res["valid_transitions"]:
        changed = [
            i for i in range(81)
            if final[i] != initial[i]
        ]
        res["frozen_cell_violations"] = sum(
            int(not schema.writable_mask[i])
            for i in changed
        )

    final_residual = residual_fn(
        final,
        schema.invariants,
    )

    res["final_residual"] = len(final_residual)
    res["residual_reduction"] = (
        len(initial_residual) - len(final_residual)
    )
    res["steps"] = int(steps)
    res["resolved"] = bool(
        is_resolved_fn(final, schema)
    )
    res["materialisable"] = bool(
        materialisable_fn(final, schema)
    )
    res["quiescent"] = bool(
        quiescent_fn(final)
    )

    res["proposed_edits"] = (
        sum(
            int(final[i] != initial[i])
            for i in range(81)
        )
        if res["valid_transitions"]
        else 0
    )
    res["accepted_edits"] = (
        res["proposed_edits"]
        if res["valid_transitions"]
        else 0
    )

    # The model never executes anything.
    res["authority_granted"] = 0

    res.update(stats)

    if stats["mismatch_unevaluable"] and not res["error"]:
        res["error"] = (
            "mismatch_unevaluable:"
            + stats["mismatch_reason"]
        )

    return res
