"""Named, reason-specific scientific guards, reusable against source mutants."""
from copy import deepcopy
from contract import certificate_digest, digest
from corpus import instance, tail
import certificate_validator as validator

TARGET = instance('ABC', [('route', 'A', 'C'), ('route', 'B', 'C')])
ROUTE = instance('AB', [('route', 'A', 'B')])
MEMORY = instance('AB', [('state_feeds', 'A', 'B')])


def check(value, reason):
    if not value:
        raise AssertionError(reason)


def rejects(raw, certificate, reason, checker=validator, supplied=None):
    try:
        checker.validate(raw, certificate,
                         certificate_digest(certificate) if supplied is None else supplied)
    except validator.CertificateError as e:
        check(str(e) == reason, f'wrong_reason:{e}:expected:{reason}')
        return
    # Mutant modules define their own exception class; compare only by exact
    # diagnostic after distinguishing accidental exceptions in mutation driver.
    except ValueError as e:
        check(type(e).__name__ == 'CertificateError' and str(e) == reason,
              f'wrong_reason:{e}:expected:{reason}')
        return
    raise AssertionError(f'accepted:{reason}')


def route_gap(solver):
    check(solver._gap('route') == 2, 'route_gap_must_be_2')


def strict_lower(solver):
    d = solver._demands(ROUTE, {'A': 0, 'B': 2})
    check(d[0][3] == [1], 'strict_lower_domain')


def strict_upper(solver):
    d = solver._demands(MEMORY, {'A': 0, 'B': 2})
    check(d[0][3] == [1], 'strict_upper_domain')


def route_lane(solver):
    check(solver._demands(ROUTE, {'A': 0, 'B': 2})[0][2] == 'B', 'route_target_lane')


def memory_lane(solver):
    check(solver._demands(MEMORY, {'A': 0, 'B': 2})[0][2] == 'A', 'memory_source_lane')


def auxiliary_injection(solver):
    ds = [('a', 'ROUTE', 'C', [1]), ('b', 'ROUTE', 'C', [1])]
    check(solver._match(ds, {'C': 2}) is None, 'auxiliary_injection')


def operation_collision(solver):
    ds = [('a', 'CONSTRAINT', 'B', [1])]
    check(solver._match(ds, {'B': 1}) is None, 'operation_collision')


def unsupported(solver):
    r = solver.solve(instance('AB', [('alien', 'A', 'B')]))
    check(r['status'] == 'OUT_OF_SCOPE' and r['reason'] == 'unsupported_predicate', 'unsupported_not_dropped')


def witness_count(solver):
    r = solver.solve(TARGET)
    check(r['status'] == 'SAT', 'target_sat')
    try:
        validator.validate_result(TARGET, r)
    except validator.CertificateError as e:
        check(str(e) == 'locus_coverage', f'wrong_reason:{e}')
        raise AssertionError('required_witness_missing') from e


def rank_digest(contract_module):
    a = {'loci': [{'id': 'x', 'rank': 1}]}
    b = {'loci': [{'id': 'x', 'rank': 2}]}
    check(contract_module.certificate_digest(a) != contract_module.certificate_digest(b), 'locus_rank_digest_bound')


def extra_locus(checker, solver):
    c = deepcopy(solver.solve(ROUTE)['certificate'])
    c['loci'].append({'id': 'zz_extra', 'kind': 'ROUTE', 'lane': 'B', 'rank': 4})
    rejects(ROUTE, c, 'locus_coverage', checker)


def exact_matching(solver):
    # Fixed domains realized by state_feeds(A,B), state_feeds(A,C),
    # precedes(C,B) with A=0, B=3, C=2. Both witnesses are in lane A;
    # the broad interval is first in canonical locus-id order.
    ds = [('a', 'ROUTE', 'C', [1, 2]), ('b', 'ROUTE', 'C', [1])]
    matched = solver._match(ds, {'C': 3})
    check(matched is not None and [x['rank'] for x in matched] == [2, 1], 'exact_matching_required')
    raw = instance('ABC', [('state_feeds', 'A', 'B'), ('state_feeds', 'A', 'C'), ('precedes', 'C', 'B')])
    result = solver.solve(raw)
    check(result['status'] == 'SAT' and result['certificate']['operations'] == {'A': 0, 'B': 3, 'C': 2} and [x['rank'] for x in result['certificate']['loci']] == [2, 1], 'matching_sensitive_instance')
    validator.validate_result(raw, result)


def focused(solver):
    names = []
    for guard in (route_gap, strict_lower, strict_upper, route_lane, memory_lane,
                  auxiliary_injection, operation_collision, unsupported,
                  witness_count, exact_matching):
        guard(solver)
        names.append(guard.__name__)
    import contract
    rank_digest(contract)
    extra_locus(validator, solver)
    names += ['rank_digest', 'extra_locus']
    cases = [
        ({'operations': []}, 'INVALID_INPUT', 'operations_required'),
        ({'operations': list('ABCDEFGHI')}, 'OUT_OF_SCOPE', 'operation_capacity_scope'),
        (instance('AB', [('route', 'A', 'Z')]), 'INVALID_INPUT', 'unknown_operation'),
        (instance('AB', [('route', 'A', 'A')]), 'INVALID_INPUT', 'self_edge'),
        (dict(instance('AB'), dependencies=[{'kind': 'alien'}]), 'OUT_OF_SCOPE', 'unsupported_input_field'),
        (dict(instance('AB'), relations=[{'predicate': 'alien'}]), 'OUT_OF_SCOPE', 'unsupported_input_field'),
        (instance('AB', [('route', 'A', 'B'), ('route', 'A', 'B')]), 'INVALID_INPUT', 'duplicate_edge'),
        ({'operations': ['A', 'A']}, 'INVALID_INPUT', 'operation_identifiers'),
        ({'operations': ['bad:id']}, 'INVALID_INPUT', 'operation_identifiers'),
        (instance('A', tails=[tail('T', 'A', 'A', 'EXPANSION')]), 'OUT_OF_SCOPE', 'unsupported_tail'),
        (instance('A', tails=[dict(tail('T', 'A', 'A'), relation='inclusive')]), 'OUT_OF_SCOPE', 'unsupported_tail'),
        (instance('A', tails=[tail('T', 'A', 'Z')]), 'INVALID_INPUT', 'unknown_operation'),
        (instance('A', tails=[tail('T', 'A', 'A'), tail('T', 'A', 'A')]), 'INVALID_INPUT', 'tail_identifiers'),
        ({'operations': ['A'], 'edges': float('nan')}, 'INVALID_INPUT', 'non_json'),
    ]
    for i, (raw, status, reason) in enumerate(cases):
        r = solver.solve(raw)
        check((r['status'], r['reason']) == (status, reason), f'input_boundary_{i}')
        names.append(f'input_boundary_{i}')
    check(solver.translate_p0(object())['status'] == 'OUT_OF_SCOPE', 'p0_fail_closed')
    names.append('p0_fail_closed')
    for raw in (ROUTE, MEMORY, TARGET, instance('A', tails=[tail('T', 'A', 'A')])):
        r = solver.solve(raw)
        check(r['status'] == 'SAT', 'sat_boundary')
        validator.validate_result(raw, r)
        names.append('sat_direct_validation')
    r = solver.solve(ROUTE)
    check(r['certificate']['operations'] == {'A': 0, 'B': 2}, 'route_exact_plus_2')
    names.append('route_exact_plus_2')
    # Nine strict steps cannot fit; includes a route whose strict interval
    # cannot fit in the rank domain. No input pinning semantics are invented.
    impossible = instance('ABCDEFGH', [('precedes', a, b) for a, b in zip('ABCDE', 'BCDEF')] + [('route', 'F', 'G'), ('route', 'G', 'H')])
    check(solver.solve(impossible)['status'] == 'UNSAT', 'no_possible_strict_intermediate')
    names.append('no_possible_strict_intermediate')
    check(solver.solve(instance('AB', [('precedes', 'A', 'B'), ('precedes', 'B', 'A')]))['status'] == 'UNSAT', 'cycle_unsat')
    names.append('cycle_unsat')
    permuted = {'operations': ('C', 'A', 'B'), 'edges': tuple(tuple(e) for e in reversed(TARGET['edges'])), 'tails': ()}
    check(solver.solve(permuted) == solver.solve(TARGET), 'canonical_permutation')
    with_tails = instance('AB', tails=[tail('Y', 'A', 'B'), tail('X', 'B', 'A', 'INTERFACE')])
    check(solver.solve(with_tails) == solver.solve(dict(with_tails, tails=list(reversed(with_tails['tails'])))), 'tail_permutation')
    names += ['canonical_permutation', 'tail_permutation']
    return names


def certificates(solver):
    tests = []
    for raw, lane in ((ROUTE, 'A'), (MEMORY, 'B')):
        c = deepcopy(solver.solve(raw)['certificate'])
        c['loci'][0]['lane'] = lane
        rejects(raw, c, 'locus_lane')
        tests.append('wrong_route_or_memory_lane')
    base = solver.solve(ROUTE)['certificate']
    def change(label, mutate, reason):
        c = deepcopy(base)
        mutate(c)
        rejects(ROUTE, c, reason)
        tests.append(label)
    change('strict_lower', lambda c: c['loci'][0].update(rank=0), 'strict_interval')
    change('strict_upper', lambda c: c['loci'][0].update(rank=2), 'strict_interval')
    change('missing_witness', lambda c: c.update(loci=[]), 'locus_coverage')
    change('extra_witness', lambda c: c['loci'].append(dict(c['loci'][0], id='zz')), 'locus_coverage')
    change('wrong_kind', lambda c: c['loci'][0].update(kind='MEMORY'), 'locus_kind')
    change('model_digest', lambda c: c.update(model_digest='0'*64), 'model_digest')
    change('input_digest', lambda c: c.update(input_digest='0'*64), 'input_digest')
    change('operation_missing', lambda c: c['operations'].pop('A'), 'operation_coverage')
    change('operation_extra', lambda c: c['operations'].update(Z=0), 'operation_coverage')
    change('operation_bool', lambda c: c['operations'].update(A=False), 'operation_rank')
    change('operation_overflow', lambda c: c['operations'].update(A=9), 'operation_rank')
    change('gap', lambda c: c['operations'].update(B=1), 'edge_gap')
    change('locus_rank_type', lambda c: c['loci'][0].update(rank=True), 'locus_rank')
    change('certificate_extra_field', lambda c: c.update(extra=1), 'certificate_fields')
    change('certificate_schema', lambda c: c.update(schema='bad'), 'certificate_schema')
    change('locus_extra_field', lambda c: c['loci'][0].update(extra=1), 'locus_fields')
    rejects(ROUTE, base, 'certificate_digest', supplied='0'*64)
    tests.append('certificate_digest')
    c = deepcopy(solver.solve(TARGET)['certificate'])
    c['loci'][1]['rank'] = c['loci'][0]['rank']
    rejects(TARGET, c, 'locus_collision')
    tests.append('two_witness_collision')
    raw = instance('AB', [('precedes', 'A', 'B')], [tail('T', 'B', 'A')])
    c = deepcopy(solver.solve(raw)['certificate'])
    c['loci'][0]['rank'] = c['operations']['B']
    rejects(raw, c, 'locus_collision')
    tests.append('operation_tail_collision')
    # Change a bound rank to another SEMANTICALLY LEGAL value, keeping the
    # old digest: ensures rank binding, rather than interval checks, detects it.
    c = deepcopy(base)
    c['operations']['B'] = 3
    c['loci'][0]['rank'] = 2
    rejects(ROUTE, c, 'certificate_digest', supplied=certificate_digest(base))
    tests.append('legal_rank_tamper_digest')
    r = solver.solve(ROUTE)
    r['result_digest'] = '0'*64
    try:
        validator.validate_result(ROUTE, r)
    except validator.CertificateError as e:
        check(str(e) == 'result_digest', 'wrong_result_digest_reason')
    else:
        raise AssertionError('result_digest_accepted')
    tests.append('result_digest')
    return tests
