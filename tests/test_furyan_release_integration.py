"""Release-integration gate for frozen Furyan R0 scientific authority.

The historical production differential remains frozen inside the Furyan
component as evidence of the allocator defect qualified by Elpis2.1.5.

Current-production allocator behavior is intentionally qualified separately:
once that defect is repaired, successor releases must not require production
to continue returning the historical failure.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "components/FuryanLocusOracle"
FURYAN_TESTS = COMPONENT / "tests"
SOLVER_PATH = COMPONENT / "FuryanLocusOracle.py"

sys.path.insert(0, str(FURYAN_TESTS))
sys.path.insert(0, str(COMPONENT))

import contract
import certificate_validator
import guards
import corpus
import reference
import baseline
import mutations

EXPECTED_FILES = {'components/FuryanLocusOracle/FURYAN_R0_SPEC.md': 'd66adcc26f3c7e99fe16db31074b61f71a84db9813ad222d0131d8fcb25073fd',
 'components/FuryanLocusOracle/FuryanLocusOracle.py': '3aea7f9fb7ee6bf3c1c38b95a12023fd5277670919fba70d06d69c139701825c',
 'components/FuryanLocusOracle/certificate_validator.py': '3cb1c2ad120ef216f888dca0a2d6673b7858d4e72605ed419d14e03d049d7a0c',
 'components/FuryanLocusOracle/contract.py': 'c50d4cbc81da717e68196619c71c0419909bd28a7a51b34c71ada5ee443e5618',
 'components/FuryanLocusOracle/tests/baseline.py': 'd1e08558cb910c7ef8b24c2f4bb9970093d984a109b0d60b03333a22c490ec93',
 'components/FuryanLocusOracle/tests/corpus.py': '8b637d18f16dcadcc0c61e0a1f78029c30d4d93dc63da330746ad449b04f1afe',
 'components/FuryanLocusOracle/tests/guards.py': '05d45351b3e3bfb2ad642c71c4597c6c1dcd538051355c5a97f3ae4331a5cb8a',
 'components/FuryanLocusOracle/tests/mutations.py': 'bbf21a9c190e6fedaf1eb985d2ae1ae20120f385def905d2fb7e189fd71aa14a',
 'components/FuryanLocusOracle/tests/production_differential.py': '47f49dbc1f44ee472e01d58cfc898b54e62368463264d3214e65edbb5f16d7f9',
 'components/FuryanLocusOracle/tests/reference.py': 'c554e0ddac751a51fdb953757b63c613cb8b294fc44257990dc524135e99ff1b',
 'components/FuryanLocusOracle/tests/run_science.py': 'b4e8c44348b0594fb8659485975802379a8530d61822a3099cef532728d7eccc'}

EXPECTED_COUNTS = {
    "1": {"canonical": 1, "labeled": 1, "SAT": 1, "UNSAT": 0},
    "2": {"canonical": 36, "labeled": 64, "SAT": 8, "UNSAT": 28},
    "3": {"canonical": 43968, "labeled": 262144, "SAT": 456, "UNSAT": 43512},
}

EXPECTED_INVENTORY_SHA256 = (
    "29645430e5cc6500f74e99091a233562ce116e6853df3bc0205f5cf12ef3488f"
)

EXPECTED_MINIMAL = [
    {
        "operations": ["A", "B", "C"],
        "edges": [["route", "A", "B"], ["route", "C", "B"]],
        "tails": [],
    },
    {
        "operations": ["A", "B", "C"],
        "edges": [
            ["state_feeds", "A", "B"],
            ["state_feeds", "A", "C"],
        ],
        "tails": [],
    },
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_solver():
    spec = importlib.util.spec_from_file_location(
        "furyan_release_under_test",
        SOLVER_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_scientific_inventory_and_hashes():
    actual = sorted(
        str(p.relative_to(ROOT))
        for p in COMPONENT.rglob("*")
        if p.is_file() and p.suffix in {".py", ".md"}
    )

    assert actual == sorted(EXPECTED_FILES)

    for rel, expected in EXPECTED_FILES.items():
        assert sha(ROOT / rel) == expected, rel

    assert sha(SOLVER_PATH) == (
        "3aea7f9fb7ee6bf3c1c38b95a12023fd5277670919fba70d06d69c139701825c"
    )


def test_focused_certificates_and_mutations():
    solver = load_solver()

    assert guards.focused(solver)
    assert guards.certificates(solver)

    target = solver.solve(guards.TARGET)
    assert target["status"] == "SAT"
    assert target["certificate"]["operations"] == {
        "A": 0,
        "B": 0,
        "C": 3,
    }
    assert [x["rank"] for x in target["certificate"]["loci"]] == [1, 2]

    certificate_validator.validate_result(
        guards.TARGET,
        target,
    )

    assert baseline.earliest(guards.TARGET) == {
        "status": "FAIL",
        "reason": "auxiliary_capacity",
        "operations": {"A": 0, "B": 0, "C": 2},
    }

    records = mutations.run(solver, SOLVER_PATH)

    assert len(records) == 12
    assert [x["mutant"] for x in records] == [
        f"M{i}" for i in range(1, 13)
    ]
    assert all(x["result"] == "KILLED" for x in records)


def test_historical_production_differential_remains_frozen_evidence():
    """The old production-defect witness remains byte-identical evidence."""
    rel = "components/FuryanLocusOracle/tests/production_differential.py"

    assert sha(ROOT / rel) == EXPECTED_FILES[rel]



def test_exhaustive_44005_case_reference_equivalence_and_minimality():
    solver = load_solver()

    counts = {}
    stream = hashlib.sha256()

    minimal_key = None
    minimal = []

    for n in (1, 2, 3):
        cases = corpus.canonical_core(n)

        count = {
            "canonical": len(cases),
            "labeled": sum(size for _, size in cases),
            "SAT": 0,
            "UNSAT": 0,
        }

        for raw, orbit_size in cases:
            result = solver.solve(raw)
            expected_status = (
                "SAT" if reference.brute(raw) else "UNSAT"
            )

            assert result["status"] == expected_status, corpus.serial(raw)

            if expected_status == "SAT":
                certificate_validator.validate_result(raw, result)

            count[expected_status] += 1

            stream.update(
                contract.canonical(
                    {
                        "input": raw,
                        "status": result["status"],
                        "orbit_size": orbit_size,
                    }
                )
                + b"\n"
            )

            if (
                result["status"] == "SAT"
                and baseline.earliest(raw)["status"] == "FAIL"
            ):
                key = (n, len(raw["edges"]))

                if minimal_key is None:
                    minimal_key = key

                if key == minimal_key:
                    minimal.append(raw)

        counts[str(n)] = count

    assert sum(v["canonical"] for v in counts.values()) == 44005
    assert counts == EXPECTED_COUNTS
    assert stream.hexdigest() == EXPECTED_INVENTORY_SHA256

    assert minimal_key == (3, 2)
    assert minimal == EXPECTED_MINIMAL


def test_fresh_process_sat_and_unsat_byte_identity():
    cases = {
        "SAT": guards.TARGET,
        "UNSAT": corpus.instance(
            "AB",
            [
                ("precedes", "A", "B"),
                ("precedes", "B", "A"),
            ],
        ),
    }

    for status, raw in cases.items():
        outputs = []

        for seed, cwd in (
            ("1", ROOT),
            ("999", Path("/tmp")),
            ("42", ROOT),
        ):
            env = dict(
                os.environ,
                PYTHONHASHSEED=seed,
                PYTHONDONTWRITEBYTECODE="1",
            )

            outputs.append(
                subprocess.check_output(
                    [sys.executable, str(SOLVER_PATH)],
                    input=contract.canonical(raw),
                    cwd=cwd,
                    env=env,
                )
            )

        assert outputs[0] == outputs[1] == outputs[2]
