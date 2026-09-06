"""Deterministic exhaustive isomorphism quotient and bounded larger corpus."""
from itertools import permutations, combinations, combinations_with_replacement
import json


def serial(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)


def instance(ops, edges=(), tails=()):
    return {'operations': sorted(ops), 'edges': sorted(map(list, edges)),
            'tails': sorted(tails, key=lambda t: t['id'])}


def tail(name, lane, after, kind='CONSTRAINT'):
    return {'id': name, 'lane': lane, 'after': after, 'kind': kind,
            'relation': 'strict_after'}


def canonical_core(n):
    """Visit each subset orbit once, then select its least JSON representative.

    All permutation actions map a bitset bijectively to another subset;
    removing the entire orbit partitions the complete labeled universe.
    No DAG restriction or semantic redundancy elimination is performed.
    """
    ops = tuple('ABCDEFGH'[:n])
    vocabulary = tuple((k, a, b) for k in ('precedes', 'route', 'state_feeds')
                       for a in ops for b in ops if a != b)
    maps = []
    for perm in permutations(ops):
        rename = dict(zip(ops, perm))
        maps.append(tuple(vocabulary.index((k, rename[a], rename[b]))
                          for k, a, b in vocabulary))
    seen = bytearray(1 << len(vocabulary))
    results = []
    for mask in range(len(seen)):
        if seen[mask]:
            continue
        present = [i for i in range(len(vocabulary)) if mask & (1 << i)]
        orbit = {sum(1 << action[i] for i in present) for action in maps}
        choices = []
        for other in orbit:
            seen[other] = 1
            edges = [e for i, e in enumerate(vocabulary) if other & (1 << i)]
            choices.append(instance(ops, edges))
        best = min(choices, key=serial)
        results.append((best, len(orbit)))
    results.sort(key=lambda pair: (len(pair[0]['edges']), serial(pair[0])))
    return results


def single_tails():
    for total in range(10):
        for constraints in range(total + 1):
            yield instance('A', tails=[tail(f'T{i}', 'A', 'A',
                            'CONSTRAINT' if i < constraints else 'INTERFACE')
                            for i in range(total)])


def small_tail_minimality():
    """Finite all n<=2 cases with <=2 obligations (edges + tails).

    Tail ids are assigned after sorting requirements; repeated identical
    requirements remain distinct obligations. Renamings are canonicalized.
    """
    for n in (1, 2):
        ops = tuple('AB'[:n])
        edge_options = [(k, a, b) for k in ('precedes', 'route', 'state_feeds')
                        for a in ops for b in ops if a != b]
        tail_options = [(lane, after, kind) for lane in ops for after in ops
                        for kind in ('CONSTRAINT', 'INTERFACE')]
        seen = {}
        for total in range(3):
            for ec in range(total + 1):
                for es in combinations(edge_options, ec):
                    for ts in combinations_with_replacement(tail_options, total - ec):
                        choices = []
                        for perm in permutations(ops):
                            ren = dict(zip(ops, perm))
                            tdefs = sorted((ren[l], ren[a], k) for l, a, k in ts)
                            choices.append(instance(ops,
                                [(k, ren[a], ren[b]) for k, a, b in es],
                                [tail(f'T{i}', l, a, k) for i, (l, a, k) in enumerate(tdefs)]))
                        best = min(choices, key=serial)
                        seen[serial(best)] = best
        yield from sorted(seen.values(), key=lambda x: (len(x['edges']) + len(x['tails']), serial(x)))


def stress():
    for n in range(4, 9):
        ops = 'ABCDEFGH'[:n]
        yield instance(ops)
        for kind in ('precedes', 'route', 'state_feeds'):
            yield instance(ops, [(kind, ops[i], ops[i+1]) for i in range(n-1)])
            yield instance(ops, [(kind, ops[i], ops[(i+1) % n]) for i in range(n)])
        yield instance(ops, [('route', a, ops[-1]) for a in ops[:-1]])
        yield instance(ops, [('state_feeds', ops[0], b) for b in ops[1:4]])
        yield instance(ops, [('route', a, b) for a, b in combinations(ops, 2)])
        for count in (1, 7, 8, 9):
            # Bound and lane the same; capacity UNSAT can be established
            # independently before enumerating isolated operation choices.
            yield instance(ops, tails=[tail(f'T{i}', 'A', 'A') for i in range(count)])
        yield instance(ops, [('precedes', 'A', 'B')],
                       [tail('a', 'B', 'A'), tail('b', 'B', 'B')])
