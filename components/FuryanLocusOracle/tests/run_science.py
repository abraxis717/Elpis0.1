"""Freeze, qualify, and requalify exactly the same bytes after promotion."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

COMPONENT = Path(__file__).resolve().parents[1]
ROOT = COMPONENT.parents[1]
sys.path.insert(0, str(COMPONENT))
from contract import MODEL_DIGEST, canonical, digest
from certificate_validator import validate_result
from guards import TARGET, check, focused, certificates
from corpus import canonical_core, single_tails, small_tail_minimality, stress, serial, instance
from reference import brute
from baseline import earliest
import mutations
import production_differential

BASE = 'dcbc011d7f55707e4fdf998de744f7794675a656'
TREE = 'd4d11452a84598c0bf36029d32e1a1fbc6cfbb9d'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def write(evidence, name, value):
    (evidence / name).write_bytes(canonical(value) + b'\n')


def source_files():
    return sorted(p for p in COMPONENT.rglob('*') if p.suffix in ('.py', '.md'))


def freeze(evidence):
    check(not (COMPONENT / 'FuryanLocusOracle.py').exists(), 'premature_final_filename')
    check(git('rev-parse', 'HEAD') == BASE, 'base_commit')
    check(git('rev-parse', 'HEAD^{tree}') == TREE, 'base_tree')
    check(git('rev-parse', 'Elpis2.1.4^{commit}') == BASE, 'base_tag')
    check(git('branch', '--show-current') == 'science/FuryanLocusOracle-r0', 'science_branch')
    authority = {'schema': 'furyan.frozen-authority.r0', 'base_commit': BASE,
                 'base_tree': TREE, 'main_ref': git('rev-parse', 'refs/heads/main'),
                 'files': {str(p.relative_to(ROOT)): sha(p) for p in source_files()},
                 'production_parity_sha256': sha(evidence / 'PRODUCTION_SEMANTIC_PARITY.md'),
                 'model_digest': MODEL_DIGEST}
    check(sha(COMPONENT / 'FURYAN_R0_SPEC.md') == MODEL_DIGEST, 'spec_digest')
    write(evidence, 'FROZEN_AUTHORITY.json', authority)
    print('FROZEN_AUTHORITY', digest(authority), flush=True)


def verify_freeze(evidence, promoted):
    authority = json.loads((evidence / 'FROZEN_AUTHORITY.json').read_text())
    actual_paths = set()
    for name, expected in authority['files'].items():
        actual = name.replace('/furyan_candidate.py', '/FuryanLocusOracle.py') if promoted else name
        path = ROOT / actual
        check(sha(path) == expected, 'frozen_source_changed:' + actual)
        actual_paths.add(path)
    check(actual_paths == set(source_files()), 'source_inventory_changed')
    check(sha(evidence / 'PRODUCTION_SEMANTIC_PARITY.md') == authority['production_parity_sha256'], 'parity_changed')
    check(sha(COMPONENT / 'FURYAN_R0_SPEC.md') == MODEL_DIGEST, 'spec_digest')
    check(git('rev-parse', 'HEAD') == BASE and git('rev-parse', 'HEAD^{tree}') == TREE, 'base_changed')
    check(git('rev-parse', 'Elpis2.1.4^{commit}') == BASE, 'tag_changed')
    check(git('rev-parse', 'refs/heads/main') == authority['main_ref'], 'main_changed')
    check(git('branch', '--show-current') == 'science/FuryanLocusOracle-r0', 'branch_changed')
    changed = git('diff', '--name-only', BASE).splitlines()
    check(all(p.startswith('components/FuryanLocusOracle/') for p in changed), 'existing_source_modified')
    check(not (COMPONENT / ('furyan_candidate.py' if promoted else 'FuryanLocusOracle.py')).exists(), 'filename_gate')
    return authority


def load_solver(path):
    spec = importlib.util.spec_from_file_location('furyan_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def independence_audit(solver_path):
    allowed = {'json', 'sys', 'hashlib', 're', 'contract'}
    files = [solver_path, COMPONENT / 'contract.py', COMPONENT / 'certificate_validator.py']
    imports = {}
    for path in files:
        tree = ast.parse(path.read_text())
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.append(node.module)
        check(set(modules) <= allowed, 'unauthorized_identity_or_production_import')
        imports[path.name] = sorted(modules)
    checker = (COMPONENT / 'certificate_validator.py').read_text()
    check(all(s not in checker for s in ('_search', '_match', '_propagate', 'furyan_candidate', 'FuryanLocusOracle')), 'checker_search_dependency')
    reference = (COMPONENT / 'tests/reference.py').read_text()
    check('import contract' not in reference and 'import furyan' not in reference and 'certificate_validator' not in reference, 'reference_dependency')
    return imports


def determinism(solver_path):
    cases = {'SAT': TARGET, 'UNSAT': instance('AB', [('precedes', 'A', 'B'), ('precedes', 'B', 'A')])}
    records = {}
    for status, raw in cases.items():
        outputs = []
        for seed, directory in (('1', ROOT), ('999', Path('/tmp')), ('42', ROOT)):
            env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE='1')
            output = subprocess.check_output([sys.executable, str(solver_path)],
                input=canonical(raw), cwd=directory, env=env)
            outputs.append(output)
        check(outputs[0] == outputs[1] == outputs[2], f'fresh_process_{status}')
        r = json.loads(outputs[0])
        check(r['status'] == status, 'fresh_process_status')
        records[status] = {'processes': 3, 'hash_seeds': ['1', '999', '42'],
                           'byte_identity': True, 'stdout_sha256': hashlib.sha256(outputs[0]).hexdigest(),
                           'input_digest': r['input_digest'], 'certificate_digest': r['certificate_digest'],
                           'result_digest': r['result_digest'], 'result_utf8': outputs[0].decode()}
    return records


def cross_check(solver, raw):
    result = solver.solve(raw)
    expected = 'SAT' if brute(raw) else 'UNSAT'
    check(result['status'] == expected, 'solver_reference_disagreement:' + serial(raw))
    if expected == 'SAT':
        validate_result(raw, result)
    return result


def qualification(evidence, solver_path, promoted):
    authority = verify_freeze(evidence, promoted)
    solver = load_solver(solver_path)
    report = {'status': 'RUNNING', 'promoted': promoted, 'solver_sha256': sha(solver_path),
              'frozen_authority_digest': digest(authority), 'model_digest': MODEL_DIGEST}
    stage = 'promoted' if promoted else 'provisional'
    report['independence_audit'] = independence_audit(solver_path)
    report['focused_tests'] = focused(solver)
    report['certificate_tests'] = certificates(solver)
    print('focused and independent certificate tests PASS', flush=True)
    target = solver.solve(TARGET)
    check(target['certificate']['operations'] == {'A': 0, 'B': 0, 'C': 3}, 'canonical_target_ranks')
    check([x['rank'] for x in target['certificate']['loci']] == [1, 2], 'canonical_target_witnesses')
    validate_result(TARGET, target)
    baseline = earliest(TARGET)
    check(baseline == {'status': 'FAIL', 'reason': 'auxiliary_capacity', 'operations': {'A': 0, 'B': 0, 'C': 2}}, 'baseline_target_capacity')
    report['theorem'] = {'input': TARGET, 'oracle': target, 'baseline': baseline,
        'validator': 'PASS', 'claim': 'Earliest-operation scheduling followed by auxiliary-locus placement is incomplete for the Furyan R0 placement model.'}
    write(evidence, stage + '_THEOREM.json', report['theorem'])
    report['mutations'] = mutations.run(solver, solver_path)
    print('all mandatory source mutations killed for intended reasons', flush=True)
    report['determinism'] = determinism(solver_path)
    print('six fresh processes: SAT and UNSAT byte identity PASS', flush=True)
    report['production_differential'] = production_differential.run(solver)
    write(evidence, stage + '_PRODUCTION_DIFFERENTIAL.json', report['production_differential'])
    print('actual production differential confirmed with exact diagnostic', flush=True)
    counts, minimal, searched, minimal_key = {}, [], 0, None
    stream = hashlib.sha256()
    for n in (1, 2, 3):
        corpus = canonical_core(n)
        count = {'canonical': len(corpus), 'labeled': sum(size for _, size in corpus), 'SAT': 0, 'UNSAT': 0}
        check(count['labeled'] == 2 ** (3*n*(n-1)), 'orbit_partition_count')
        for index, (raw, orbit_size) in enumerate(corpus):
            result = cross_check(solver, raw)
            count[result['status']] += 1
            stream.update(canonical({'input': raw, 'status': result['status'], 'orbit_size': orbit_size}) + b'\n')
            key = (n, len(raw['edges']))
            if minimal_key is None or key <= minimal_key:
                searched += 1
                if result['status'] == 'SAT' and earliest(raw)['status'] == 'FAIL':
                    if minimal_key is None:
                        minimal_key = key
                    minimal.append(raw)
            if index and index % 10000 == 0:
                print(f'exhaustive n={n}: {index}/{len(corpus)} checked', flush=True)
        counts[str(n)] = count
        print(f'exhaustive n={n}: {count}', flush=True)
    report['exhaustive_core'] = counts
    report['exhaustive_inventory_sha256'] = stream.hexdigest()
    check(bool(minimal), 'minimality_no_counterexample_found')
    report['minimality'] = {'scope': 'core without tails', 'key': list(minimal_key),
                           'first': minimal[0], 'all_tied': minimal, 'corpus_searched': searched}
    tail_min = []
    tail_count = 0
    for raw in small_tail_minimality():
        result = cross_check(solver, raw)
        tail_count += 1
        if result['status'] == 'SAT' and earliest(raw)['status'] == 'FAIL':
            tail_min.append(raw)
    report['bounded_tail_minimality'] = {'scope': 'all n<=2, <=2 edges+tails modulo operation/tail-id renaming',
                                       'corpus_searched': tail_count, 'counterexamples': tail_min}
    one = list(single_tails())
    for raw in one:
        cross_check(solver, raw)
    report['one_operation_tail_cases'] = len(one)
    larger = list(stress())
    larger_counts = {'SAT': 0, 'UNSAT': 0}
    for i, raw in enumerate(larger):
        result = cross_check(solver, raw)
        larger_counts[result['status']] += 1
        if (i+1) % 15 == 0:
            print(f'bounded larger reference corpus: {i+1}/{len(larger)} checked', flush=True)
    report['larger_corpus'] = {'total': len(larger), **larger_counts}
    verify_freeze(evidence, promoted)
    subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
    # Also inspect untracked source whitespace, which git diff omits.
    for path in source_files():
        for line in path.read_text().splitlines():
            check(line == line.rstrip(), 'source_trailing_whitespace')
    report['git_diff_check'] = 'PASS'
    report['existing_elpis_files_modified'] = 0
    report['status'] = 'SCIENTIFIC_PASS'
    write(evidence, stage + '_SCIENTIFIC_PASS.json', report)
    print('SCIENTIFIC_PASS', stage, 'sha256=' + sha(solver_path), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--promoted', action='store_true')
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    if args.freeze:
        freeze(args.evidence)
        return
    solver_path = COMPONENT / ('FuryanLocusOracle.py' if args.promoted else 'furyan_candidate.py')
    try:
        qualification(args.evidence, solver_path, args.promoted)
    except AssertionError as exc:
        write(args.evidence, ('promoted' if args.promoted else 'provisional') + '_SCIENTIFIC_NONPASS.json',
              {'status': 'SCIENTIFIC_NONPASS', 'reason': str(exc), 'traceback': traceback.format_exc()})
        print('SCIENTIFIC_NONPASS', str(exc), flush=True)
        raise
    except Exception as exc:
        write(args.evidence, 'MECHANICAL_BLOCKER.json',
              {'status': 'MECHANICAL_BLOCKER', 'reason': str(exc), 'traceback': traceback.format_exc()})
        print('MECHANICAL_BLOCKER', str(exc), flush=True)
        raise


if __name__ == '__main__':
    main()
