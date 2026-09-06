"""Transport and identity only; no placement or feasibility authority."""
import hashlib
import json
import re

MODEL_DIGEST = 'd66adcc26f3c7e99fe16db31074b61f71a84db9813ad222d0131d8fcb25073fd'
ID = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,63}\Z')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def certificate_digest(certificate):
    return digest(certificate)


def normalize(raw):
    """Return (normalized JSON object, status or None, stable reason)."""
    try:
        value = json.loads(canonical(raw))
    except (ValueError, TypeError, UnicodeError, OverflowError):
        return {'transport': 'non_json'}, 'INVALID_INPUT', 'non_json'
    if not isinstance(value, dict):
        return value, 'INVALID_INPUT', 'object_required'
    ops = value.get('operations')
    edges = value.get('edges', [])
    tails = value.get('tails', [])
    def invalid(reason):
        return value, 'INVALID_INPUT', reason
    def ident(s):
        return isinstance(s, str) and ID.fullmatch(s) is not None
    if not isinstance(ops, list) or not ops:
        return invalid('operations_required')
    if not all(ident(o) for o in ops) or len(set(ops)) != len(ops):
        return invalid('operation_identifiers')
    if not isinstance(edges, list) or not isinstance(tails, list):
        return invalid('arrays_required')
    seen = set()
    for e in edges:
        if not isinstance(e, list) or len(e) != 3 or not all(isinstance(x, str) for x in e):
            return invalid('edge_shape')
        kind, a, b = e
        if a not in ops or b not in ops:
            return invalid('unknown_operation')
        if a == b:
            return invalid('self_edge')
        if tuple(e) in seen:
            return invalid('duplicate_edge')
        seen.add(tuple(e))
    seen = set()
    for t in tails:
        if not isinstance(t, dict) or set(t) != {'id', 'lane', 'after', 'relation', 'kind'}:
            return invalid('tail_shape')
        if not ident(t['id']) or t['id'] in seen:
            return invalid('tail_identifiers')
        seen.add(t['id'])
        if not isinstance(t['lane'], str) or not isinstance(t['after'], str) or t['lane'] not in ops or t['after'] not in ops:
            return invalid('unknown_operation')
        if not isinstance(t['kind'], str) or not isinstance(t['relation'], str):
            return invalid('tail_shape')
    normalized = dict(value, operations=sorted(ops), edges=sorted(edges),
                      tails=sorted(tails, key=lambda t: t['id']))
    reason = ''
    if set(value) - {'operations', 'edges', 'tails'}:
        reason = 'unsupported_input_field'
    elif len(ops) > 8:
        reason = 'operation_capacity_scope'
    elif any(e[0] not in ('precedes', 'route', 'state_feeds') for e in edges):
        reason = 'unsupported_predicate'
    elif any(t['kind'] not in ('CONSTRAINT', 'INTERFACE') or t['relation'] != 'strict_after' for t in tails):
        reason = 'unsupported_tail'
    return normalized, ('OUT_OF_SCOPE' if reason else None), reason
