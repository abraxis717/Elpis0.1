"""Executable independent source mutants; exact designated diagnostics only."""
from pathlib import Path
from types import ModuleType
import sys
import hashlib
import contract
import certificate_validator
import guards


def module_from(source, name):
    module = ModuleType(name)
    exec(compile(source, f'<{name}>', 'exec'), module.__dict__)
    return module


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError('mutation_anchor_not_unique')
    return source.replace(old, new)


def run(solver, solver_path):
    base = Path(solver_path).read_text()
    root = Path(solver_path).parent
    contracts = (root / 'contract.py').read_text()
    checker = (root / 'certificate_validator.py').read_text()
    specs = [
        ('M1', 'solver', "return 1 if kind == 'precedes' else 2", "return 1 if kind == 'precedes' else 1", guards.route_gap, 'route_gap_must_be_2', 'rule_unit_redundant_constraint'),
        ('M2', 'solver', 'range(ranks[a] + 1, ranks[b])', 'range(ranks[a], ranks[b])', guards.strict_lower, 'strict_lower_domain', 'domain_rule'),
        ('M3', 'solver', 'range(ranks[a] + 1, ranks[b])', 'range(ranks[a] + 1, ranks[b] + 1)', guards.strict_upper, 'strict_upper_domain', 'domain_rule'),
        ('M4', 'solver', "lane = b if kind == 'route' else a", "lane = a if kind == 'route' else a", guards.route_lane, 'route_target_lane', 'lane_rule'),
        ('M5', 'solver', "lane = b if kind == 'route' else a", "lane = b if kind == 'route' else b", guards.memory_lane, 'memory_source_lane', 'lane_rule'),
        ('M6', 'solver', 'if rank in used[lane]:', 'if False:', guards.auxiliary_injection, 'auxiliary_injection', 'matching_feasibility'),
        ('M7', 'solver', 'used = {o: {r} for o, r in ranks.items()}', 'used = {o: set() for o, r in ranks.items()}', guards.operation_collision, 'operation_collision', 'matching_feasibility'),
        ('M8', 'contract', "reason = 'unsupported_predicate'", "normalized['edges'] = [e for e in edges if e[0] in ('precedes', 'route', 'state_feeds')]", guards.unsupported, 'unsupported_not_dropped', 'public_status'),
        ('M9', 'solver', 'return sorted(demands)', 'return sorted(demands)[1:]', guards.witness_count, 'required_witness_missing', 'independent_certificate'),
        ('M10', 'digest', 'return digest(certificate)', "return digest(dict(certificate, loci=[{k:v for k,v in x.items() if k != 'rank'} for x in certificate['loci']]))", guards.rank_digest, 'locus_rank_digest_bound', 'identity_rule'),
        ('M11', 'validator', "len(ids) == len(set(ids)) and set(ids) == set(expected)", "len(ids) == len(set(ids)) and set(expected) <= set(ids)", guards.extra_locus, 'accepted:locus_coverage', 'independent_certificate'),
        ('M12', 'solver', "            result.pop()\n            used[lane].remove(rank)", "            return None  # commit to first fit even if continuation fails", guards.exact_matching, 'exact_matching_required', 'matching_feasibility'),
    ]
    records = []
    for ident, kind, old, new, guard, reason, level in specs:
        original = base if kind == 'solver' else checker if kind == 'validator' else contracts
        changed = replace_once(original, old, new)
        mutant = module_from(changed, ident)
        try:
            if kind == 'contract':
                sys.modules['contract'] = mutant
                target = module_from(base, ident + '_solver')
            else:
                target = mutant
        finally:
            sys.modules['contract'] = contract
        try:
            if kind == 'validator':
                guard(target, solver)
            else:
                guard(target)
        except AssertionError as e:
            if str(e) != reason:
                raise AssertionError(f'{ident}:wrong_reason:{e}:expected:{reason}') from e
            records.append({'mutant': ident, 'expected_detecting_test': guard.__name__,
                            'actual_detecting_test': guard.__name__, 'diagnostic': str(e),
                            'result': 'KILLED', 'detection_level': level,
                            'mutant_source_sha256': hashlib.sha256(changed.encode()).hexdigest()})
        else:
            raise AssertionError(f'{ident}:SURVIVED:{guard.__name__}')
    return records
