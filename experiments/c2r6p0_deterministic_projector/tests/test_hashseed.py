"""Cross-hash-seed byte determinism (mission 25).

For the same fixed corpus (named fixtures + valid seeds 0..99), fresh
Python processes under PYTHONHASHSEED in {0, 1, 7, 42, random} must
produce byte-identical serialized results and traces. We compare the
actual byte files (not just digests) and record DETERMINISM_REPORT.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

EXP_DIR = Path(__file__).resolve().parent.parent
WORKER = EXP_DIR / "scripts" / "hs_worker.py"
EVIDENCE_DIR = Path(
    "/mnt/primesauce/Elpis0.1/work/C2R6P0_DETERMINISTIC_PROJECTOR_R0"
)
SEEDS = ("0", "1", "7", "42", "random")


def _run(seed: str, out: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    env["CUDA_VISIBLE_DEVICES"] = ""
    proc = subprocess.run(
        [sys.executable, str(WORKER), str(out)],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, (seed, proc.stderr[-2000:])
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _report() -> dict:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        rows: list[dict] = []
        byte_sha: dict[str, str] = {}
        ref_bytes: bytes | None = None
        for seed in SEEDS:
            out = base / f"corpus_{seed}.bin"
            meta = _run(seed, out)
            blob = out.read_bytes()
            if ref_bytes is None:
                ref_bytes = blob
            byte_sha[seed] = meta["corpus_sha256"]
            rows.append({
                "seed": seed,
                "n": meta["n"],
                "corpus_sha256": meta["corpus_sha256"],
                "fingerprints_sha256": meta["fingerprints_sha256"],
                "byte_file_sha256": _sha(blob),
                "byte_file_len": len(blob),
                "bytes_identical_to_seed0": blob == ref_bytes,
            })
        all_same = len({r["corpus_sha256"] for r in rows}) == 1
        all_bytes_same = all(r["bytes_identical_to_seed0"] for r in rows)
        report = {
            "schema": "elpis.c2r6p0.determinism_report.v1",
            "seeds": list(SEEDS),
            "rows": rows,
            "corpus_sha256_identical_across_seeds": all_same,
            "serialized_bytes_identical_across_seeds": all_bytes_same,
            "byte_comparison": "raw concatenated ProjectionResultV1 canonical bytes",
            "pass": all_same and all_bytes_same,
        }
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        (EVIDENCE_DIR / "DETERMINISM_REPORT.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        return report


def _sha(b: bytes) -> str:
    import hashlib
    return hashlib.sha256(b).hexdigest()


class TestHashSeedDeterminism:
    def test_byte_identical_across_seeds(self):
        rep = _report()
        assert rep["corpus_sha256_identical_across_seeds"] is True
        assert rep["serialized_bytes_identical_across_seeds"] is True
        # every process projected the same number of cases
        ns = {r["n"] for r in rep["rows"]}
        assert len(ns) == 1
        assert rep["pass"] is True
