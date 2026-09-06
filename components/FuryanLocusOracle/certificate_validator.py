"""Independent direct SAT-certificate checker; never invokes the oracle."""
from contract import MODEL_DIGEST, digest, certificate_digest, normalize


class CertificateError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise CertificateError(reason)


def validate(raw, certificate, supplied_digest):
    instance, status, _ = normalize(raw)
    require(status is None, 'input_not_supported')
    c = certificate
    require(isinstance(c, dict) and set(c) == {'schema', 'model_digest', 'input_digest', 'operations', 'loci'}, 'certificate_fields')
    require(c['schema'] == 'furyan.certificate.r0', 'certificate_schema')
    require(c['model_digest'] == MODEL_DIGEST, 'model_digest')
    require(c['input_digest'] == digest(instance), 'input_digest')
    r = c['operations']
    require(isinstance(r, dict) and set(r) == set(instance['operations']), 'operation_coverage')
    require(all(type(v) is int and 0 <= v <= 8 for v in r.values()), 'operation_rank')
    expected = {}
    for kind, a, b in instance['edges']:
        gap = 1 if kind == 'precedes' else 2
        require(r[b] >= r[a] + gap, 'edge_gap')
        if kind != 'precedes':
            expected[f'edge:{kind}:{a}:{b}'] = (
                'ROUTE' if kind == 'route' else 'MEMORY',
                b if kind == 'route' else a, r[a], r[b])
    for t in instance['tails']:
        expected[f"tail:{t['id']}"] = (t['kind'], t['lane'], r[t['after']], 9)
    loci = c['loci']
    require(isinstance(loci, list), 'loci_type')
    require(all(isinstance(x, dict) and set(x) == {'id', 'kind', 'lane', 'rank'} and isinstance(x['id'], str) for x in loci), 'locus_fields')
    ids = [x['id'] for x in loci]
    require(len(ids) == len(set(ids)) and set(ids) == set(expected), 'locus_coverage')
    require(ids == sorted(ids), 'locus_order')
    occupied = {(o, v) for o, v in r.items()}
    for x in loci:
        if x['id'] not in expected:
            continue  # unreachable with exact coverage; mutation target M11
        kind, lane, low, high = expected[x['id']]
        require(x['kind'] == kind, 'locus_kind')
        require(x['lane'] == lane, 'locus_lane')
        v = x['rank']
        require(type(v) is int and 0 <= v <= 8, 'locus_rank')
        require(low < v < high, 'strict_interval')
        require((lane, v) not in occupied, 'locus_collision')
        occupied.add((lane, v))
    require(supplied_digest == certificate_digest(c), 'certificate_digest')
    return True


def validate_result(raw, result):
    require(isinstance(result, dict) and set(result) == {'schema', 'normalized_input', 'input_digest', 'model_digest', 'status', 'reason', 'certificate', 'certificate_digest', 'result_digest'}, 'result_fields')
    require(result['schema'] == 'furyan.result.r0' and result['status'] == 'SAT' and result['reason'] == '', 'result_status')
    normalized, status, _ = normalize(raw)
    require(status is None and result['normalized_input'] == normalized, 'normalized_input')
    require(result['model_digest'] == MODEL_DIGEST, 'model_digest')
    require(result['input_digest'] == digest(normalized), 'input_digest')
    validate(raw, result['certificate'], result['certificate_digest'])
    require(result['result_digest'] == digest({k: v for k, v in result.items() if k != 'result_digest'}), 'result_digest')
    return True
