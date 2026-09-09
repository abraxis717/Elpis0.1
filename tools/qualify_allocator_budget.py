#!/usr/bin/env python3
"""Reproduce the predeclared corpus and deterministic node-entry measurement.

--baseline executes the exact Elpis2.1.9 allocator obtained from the local tag.
This is measurement, not an independent satisfiability oracle.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'components/FuryanLocusOracle/tests'))
import corpus
from elpis_reference.structural_guidance._authority.c2r6p0.allocator import _joint_assignment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    identity = json.loads((ROOT / 'tests/allocator_measurement_corpus.json').read_text())
    generator = ROOT / 'components/FuryanLocusOracle/tests/corpus.py'
    assert hashlib.sha256(generator.read_bytes()).hexdigest() == identity['generator_sha256']
    cases = []
    for n in (1, 2, 3):
        cases.extend({'group': 'canonical_core', 'instance': raw, 'orbit': orbit}
                     for raw, orbit in corpus.canonical_core(n))
    for group in ('single_tails', 'small_tail_minimality', 'stress'):
        cases.extend({'group': group, 'instance': raw} for raw in getattr(corpus, group)())
    data = ''.join(json.dumps(case, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n'
                   for case in cases).encode()
    assert hashlib.sha256(data).hexdigest() == identity['sha256']
    assert len(cases) == identity['cases']
    assert dict(Counter(case['group'] for case in cases)) == identity['groups']
    assignment = _joint_assignment
    if args.baseline:
        source = subprocess.check_output([
            'git', 'show', 'Elpis2.1.9:src/elpis_reference/structural_guidance/_authority/c2r6p0/allocator.py',
        ], cwd=ROOT)
        namespace = {'__name__': 'closure_baseline_allocator',
                     '__package__': 'elpis_reference.structural_guidance._authority.c2r6p0'}
        sys.modules[namespace['__name__']] = type(sys)(namespace['__name__'])
        sys.modules[namespace['__name__']].__dict__.update(namespace)
        namespace = sys.modules[namespace['__name__']].__dict__
        exec(compile(source, '<Elpis2.1.9 allocator>', 'exec'), namespace)
        assignment = namespace['_joint_assignment']
    maximum = 0
    exhausted = 0
    for case in cases:
        raw = case['instance']
        edges = [(a, b, 1 if k == 'precedes' else 2) for k, a, b in raw['edges']]
        demands = [(f'edge:{k}:{a}:{b}', b if k == 'route' else a, a, b)
                   for k, a, b in raw['edges'] if k != 'precedes']
        demands += [(f"tail:{t['id']}", t['lane'], t['after'], None) for t in raw['tails']]
        entries = 0
        def profile(frame, event, arg):
            nonlocal entries
            if event == 'call' and frame.f_code.co_name == 'search' and frame.f_code.co_filename == assignment.__code__.co_filename:
                entries += 1
        sys.setprofile(profile)
        try:
            result = assignment(raw['operations'], edges, demands)
        finally:
            sys.setprofile(None)
        if not args.baseline:
            assert entries == result.search_entries
            exhausted += result.status == 'SEARCH_BUDGET_EXHAUSTED'
        maximum = max(maximum, entries)
    print(json.dumps({'corpus_sha256': identity['sha256'], 'cases': len(cases),
                      'maximum_search_entries': maximum, 'multiplier': 4,
                      'selected_default': 4 * maximum,
                      'exhausted': exhausted if not args.baseline else 'NOT_BUDGETED'}, sort_keys=True))
    assert maximum == 21 and exhausted == 0


if __name__ == '__main__':
    main()
