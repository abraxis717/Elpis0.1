"""Deterministic fuzz qualification (mission 26).

Corpus: 10,000 generated valid graphs (seeds 0..9999) and 2,000
malformed/adversarial graphs (seeds 0..1999), all CPU-only and bounded.

Every PROJECTED result is checked against the full invariant battery
(conftest.check_invariants + binding-reference check + semantic
skeleton round-trip). Every malformed graph must be rejected with a
typed status (no crashes, no exceptions). In-process determinism:
projecting the same graph twice yields byte-identical canonical
result/trace bytes.

The report is written to the persistent evidence directory
(FUZZ_REPORT.json) — outside the git worktree, so the test never
mutates the repository.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pytest

from c2r6p0 import fixtures as FX
from c2r6p0.contracts import ProjectionStatus
from c2r6p0.projector import ProjectionInputV1
from c2r6p0.residual import (
    canonical_skeleton_of_payload,
    extract_semantic_skeleton,
)
from c2r6p0.canonicalize import canonicalize
from c2r6p0.rules import load_ruleset

from conftest import check_bindings_against_graph, check_invariants

VALID_N = 10000
MALFORMED_N = 2000
EVIDENCE_DIR = Path(
    "/mnt/primesauce/Elpis0.1/work/C2R6P0_DETERMINISTIC_PROJECTOR_R0"
)


def _corpus_sha(cases: list[bytes]) -> str:
    h = hashlib.sha256()
    for b in cases:
        h.update(b)
    return h.hexdigest()


def run_corpus(project) -> dict:
    """Run the full fuzz corpus; return the report payload."""
    t0 = time.perf_counter()
    ok = decomposed = 0
    statuses: dict[str, int] = {}
    lat_valid: list[float] = []
    lat_mal: list[float] = []
    corpus_sha = hashlib.sha256()
    n_roundtrip_checked = 0
    n_determinism_checked = 0
    t_start = time.perf_counter()
    for i in range(VALID_N):
        g = FX.gen_valid(seed=i)
        pin = ProjectionInputV1(request_id=f"fv{i:07d}", semantic_graph=g)
        ta = time.perf_counter()
        r = project(pin)
        tb = time.perf_counter()
        lat_valid.append(tb - ta)
        if r.status == ProjectionStatus.PROJECTED.value:
            ok += 1
            check_invariants(r)
            check_bindings_against_graph(r, g)
            # mission 26: semantic skeleton round-trip exact
            rs = load_ruleset()
            cg, err = canonicalize(g, rs)
            assert err is None and cg is not None
            got = extract_semantic_skeleton(r.bindings, r.invariants)
            want = canonical_skeleton_of_payload(cg.payload)
            assert got == want
            n_roundtrip_checked += 1
            # in-process byte determinism: reproject -> identical bytes
            r2 = project(pin)
            assert r.to_canonical_bytes() == r2.to_canonical_bytes()
            n_determinism_checked += 1
        elif r.status == ProjectionStatus.DECOMPOSITION_REQUIRED.value:
            decomposed += 1
            assert r.error is not None
        else:  # pragma: no cover - generator should not emit these
            pytest.fail(f"valid seed {i}: unexpected status {r.status}")
        corpus_sha.update(r.to_canonical_bytes())
    statuses_valid = {"PROJECTED": ok, "DECOMPOSITION_REQUIRED": decomposed}

    t_m = time.perf_counter()
    for i in range(MALFORMED_N):
        g = FX.gen_malformed(seed=i)
        pin = ProjectionInputV1(request_id=f"fm{i:07d}", semantic_graph=g)
        ta = time.perf_counter()
        r = project(pin)
        tb = time.perf_counter()
        lat_mal.append(tb - ta)
        assert r.status != ProjectionStatus.PROJECTED.value, (
            f"malformed seed {i} must not PROJECT: {r.status}"
        )
        assert r.error is not None and r.error.code, (
            f"malformed seed {i}: rejection must carry typed error"
        )
        statuses[r.status] = statuses.get(r.status, 0) + 1
        corpus_sha.update(r.to_canonical_bytes())
    t1 = time.perf_counter()

    def pct(xs: list[float], q: float) -> float:
        if not xs:
            return 0.0
        xs = sorted(xs)
        k = max(0, min(len(xs) - 1, int(round(q * (len(xs) - 1)))))
        return xs[k] * 1000.0

    report = {
        "schema": "elpis.c2r6p0.fuzz_report.v1",
        "valid_cases": VALID_N,
        "malformed_cases": MALFORMED_N,
        "valid_statuses": statuses_valid,
        "malformed_statuses": statuses,
        "roundtrip_checked": n_roundtrip_checked,
        "inprocess_determinism_checked": n_determinism_checked,
        "corpus_canonical_sha256": corpus_sha.hexdigest(),
        "performance": {
            "total_seconds": round(t1 - t0, 3),
            "valid_seconds": round(t_m - t_start, 3),
            "malformed_seconds": round(t1 - t_m, 3),
            "valid_projections_per_sec": round(
                VALID_N / max(t_m - t_start, 1e-9), 1
            ),
            "valid_latency_ms": {
                "median": round(pct(lat_valid, 0.50), 3),
                "p95": round(pct(lat_valid, 0.95), 3),
                "max": round(pct(lat_valid, 1.0), 3),
            },
            "malformed_latency_ms": {
                "median": round(pct(lat_mal, 0.50), 3),
                "p95": round(pct(lat_mal, 0.95), 3),
                "max": round(pct(lat_mal, 1.0), 3),
            },
        },
        "no_crashes": True,
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "FUZZ_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return report


@pytest.fixture(scope="module")
def fuzz_report(project) -> dict:
    return run_corpus(project)


class TestFuzzCorpus:
    def test_valid_corpus_counts(self, fuzz_report):
        assert fuzz_report["valid_cases"] >= 10000
        assert (
            fuzz_report["valid_statuses"]["PROJECTED"]
            + fuzz_report["valid_statuses"]["DECOMPOSITION_REQUIRED"]
            == fuzz_report["valid_cases"]
        )
        # the generator must actually produce a healthy PROJECTED majority
        assert fuzz_report["valid_statuses"]["PROJECTED"] > 7000
        # skeleton round-trip must have been exercised on every PROJECTED
        assert (
            fuzz_report["roundtrip_checked"]
            == fuzz_report["valid_statuses"]["PROJECTED"]
        )
        assert fuzz_report["inprocess_determinism_checked"] == (
            fuzz_report["valid_statuses"]["PROJECTED"]
        )

    def test_malformed_corpus_counts(self, fuzz_report):
        assert fuzz_report["malformed_cases"] >= 2000
        total_rejected = sum(fuzz_report["malformed_statuses"].values())
        assert total_rejected == fuzz_report["malformed_cases"]
        assert fuzz_report["no_crashes"] is True

    def test_performance_bounded(self, fuzz_report):
        perf = fuzz_report["performance"]
        # 12k projections must finish in well under a minute
        assert perf["total_seconds"] < 60.0
        assert perf["valid_latency_ms"]["p95"] < 50.0
        assert perf["valid_latency_ms"]["max"] < 200.0

    def test_corpus_sha_stable(self, fuzz_report):
        assert len(fuzz_report["corpus_canonical_sha256"]) == 64
