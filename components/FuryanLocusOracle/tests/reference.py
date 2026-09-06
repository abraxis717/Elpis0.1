"""Test-only exhaustive reference. No candidate, contract or validator imports."""
from itertools import product
from functools import lru_cache


@lru_cache(None)
def rank_table(n):
    """All vectors, independently annotated with satisfied directed triples."""
    vocabulary = tuple((k, a, b) for k in ('precedes', 'route', 'state_feeds')
                       for a in range(n) for b in range(n) if a != b)
    rows = []
    for vector in product(range(9), repeat=n):
        mask = 0
        for i, (kind, a, b) in enumerate(vocabulary):
            if vector[b] - vector[a] >= (1 if kind == 'precedes' else 2):
                mask |= 1 << i
        rows.append((vector, mask))
    return vocabulary, rows


def auxiliary(instance, ranks):
    """Enumerate the Cartesian product of all legal witness ranks."""
    lanes, domains = [], []
    for kind, a, b in instance['edges']:
        if kind == 'precedes':
            continue
        lanes.append(b if kind == 'route' else a)
        domains.append(tuple(v for v in range(9) if ranks[a] < v < ranks[b]))
    for t in instance['tails']:
        lanes.append(t['lane'])
        domains.append(tuple(v for v in range(9) if v > ranks[t['after']]))
    # Pigeonhole bound is direct, independent of candidate matching.
    if any(lanes.count(lane) > 8 for lane in ranks):
        return False
    for vector in product(*domains):
        cells = list(zip(lanes, vector)) + list(ranks.items())
        if len(cells) == len(set(cells)):
            return True
    return False


def brute(instance):
    ops = sorted(instance['operations'])
    demands = [b if k == 'route' else a for k, a, b in instance['edges'] if k != 'precedes'] + [t['lane'] for t in instance['tails']]
    if any(demands.count(o) > 8 for o in ops):
        return False
    # Isolated operations can always be set to zero independently.
    used = {x for _, a, b in instance['edges'] for x in (a, b)} | {x for t in instance['tails'] for x in (t['lane'], t['after'])}
    if used and len(used) < len(ops):
        return brute(dict(instance, operations=sorted(used)))
    if len(ops) <= 3:
        vocabulary, rows = rank_table(len(ops))
        index = {o: i for i, o in enumerate(ops)}
        mask = sum(1 << vocabulary.index((k, index[a], index[b]))
                   for k, a, b in instance['edges'])
        for vector, truth in rows:
            if truth & mask == mask and auxiliary(instance, dict(zip(ops, vector))):
                return True
        return False
    # Larger corpus: enumerate product prefixes, rejecting a prefix only when
    # a fully assigned edge already fails. No bounds propagation or matching.
    assigned = {}
    def visit(i):
        if i == len(ops):
            return auxiliary(instance, assigned)
        op = ops[i]
        for v in range(9):
            assigned[op] = v
            if all(a not in assigned or b not in assigned or
                   assigned[b] - assigned[a] >= (1 if k == 'precedes' else 2)
                   for k, a, b in instance['edges']):
                if visit(i + 1):
                    return True
        assigned.pop(op)
        return False
    return visit(0)
