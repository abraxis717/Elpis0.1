"""Test-only earliest-operation strategy, independent of candidate search."""
from reference import auxiliary


def earliest(instance):
    ranks = {o: 0 for o in instance['operations']}
    # Bellman-Ford relaxation computes least legal ranks if they exist.
    for iteration in range(len(ranks) + 1):
        changed = False
        for kind, a, b in instance['edges']:
            bound = ranks[a] + (1 if kind == 'precedes' else 2)
            if ranks[b] < bound:
                ranks[b] = bound
                changed = True
        if not changed:
            break
    if changed or max(ranks.values()) > 8:
        return {'status': 'FAIL', 'reason': 'operation_rank_capacity', 'operations': ranks}
    if not auxiliary(instance, ranks):
        return {'status': 'FAIL', 'reason': 'auxiliary_capacity', 'operations': ranks}
    return {'status': 'SAT', 'reason': '', 'operations': ranks}
