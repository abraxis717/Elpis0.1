"""Complete finite Furyan R0 oracle. See FURYAN_R0_SPEC.md for authority."""
import json
import sys
from contract import MODEL_DIGEST, canonical, digest, certificate_digest, normalize


def _gap(kind):
    return 1 if kind == 'precedes' else 2


def _demands(instance, ranks):
    demands = []
    for kind, a, b in instance['edges']:
        if kind == 'precedes':
            continue
        lane = b if kind == 'route' else a
        token = 'ROUTE' if kind == 'route' else 'MEMORY'
        allowed = list(range(ranks[a] + 1, ranks[b]))
        demands.append((f'edge:{kind}:{a}:{b}', token, lane, allowed))
    for t in instance['tails']:
        demands.append((f"tail:{t['id']}", t['kind'], t['lane'],
                        list(range(ranks[t['after']] + 1, 9))))
    return sorted(demands)


def _match(demands, ranks):
    """Exact injection by complete DFS; first solution is lexicographic."""
    used = {o: {r} for o, r in ranks.items()}
    result = []
    def visit(i):
        if i == len(demands):
            return list(result)
        name, kind, lane, allowed = demands[i]
        for rank in allowed:
            if rank in used[lane]:
                continue
            used[lane].add(rank)
            result.append({'id': name, 'kind': kind, 'lane': lane, 'rank': rank})
            found = visit(i + 1)
            if found is not None:
                return found
            result.pop()
            used[lane].remove(rank)
        return None
    return visit(0)


def _propagate(ops, edges, fixed):
    low = {o: fixed.get(o, 0) for o in ops}
    high = {o: fixed.get(o, 8) for o in ops}
    changed = True
    while changed:
        changed = False
        for kind, a, b in edges:
            gap = _gap(kind)
            l, h = max(low[b], low[a] + gap), min(high[a], high[b] - gap)
            changed |= l != low[b] or h != high[a]
            low[b], high[a] = l, h
            if low[b] > high[b] or low[a] > high[a]:
                return None
    return low, high


def _search(instance):
    ops, edges = instance['operations'], instance['edges']
    counts = {o: 0 for o in ops}
    for kind, a, b in edges:
        if kind != 'precedes':
            counts[b if kind == 'route' else a] += 1
    for t in instance['tails']:
        counts[t['lane']] += 1
    if any(c > 8 for c in counts.values()):
        return None
    fixed = {}
    def visit(i):
        bounds = _propagate(ops, edges, fixed)
        if bounds is None:
            return None
        if i == len(ops):
            loci = _match(_demands(instance, fixed), fixed)
            return (dict(fixed), loci) if loci is not None else None
        low, high = bounds
        op = ops[i]
        for rank in range(low[op], high[op] + 1):
            fixed[op] = rank
            found = visit(i + 1)
            if found is not None:
                return found
        fixed.pop(op, None)
        return None
    return visit(0)


def solve(raw):
    instance, status, reason = normalize(raw)
    cert = None
    if status is None:
        found = _search(instance)
        status = 'SAT' if found is not None else 'UNSAT'
        reason = '' if found is not None else 'finite_search_exhausted'
        if found is not None:
            ranks, loci = found
            cert = {'schema': 'furyan.certificate.r0', 'model_digest': MODEL_DIGEST,
                    'input_digest': digest(instance), 'operations': ranks, 'loci': loci}
    result = {'schema': 'furyan.result.r0', 'normalized_input': instance,
              'input_digest': digest(instance), 'model_digest': MODEL_DIGEST,
              'status': status, 'reason': reason, 'certificate': cert,
              'certificate_digest': certificate_digest(cert) if cert is not None else None}
    result['result_digest'] = digest(result)
    return result


def translate_p0(_request):
    """R0 intentionally exposes no automatic P0 semantic derivation."""
    return {'status': 'OUT_OF_SCOPE', 'reason': 'automatic_p0_translation_unavailable'}


if __name__ == '__main__':
    sys.stdout.buffer.write(canonical(solve(json.load(sys.stdin))) + b'\n')
