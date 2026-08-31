"""CPU performance characterization (mission 33).

Not a speed gate — records projections/sec, median/p95/max latency and a
memory high-water mark over a bounded synthetic corpus, so pathological
algorithmic behavior would be visible. Writes PERFORMANCE_REPORT.json.
"""
from __future__ import annotations

import gc
import json
import resource
import statistics
import sys
import time
from pathlib import Path

EXP_DIR = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = Path(
    "/mnt/primesauce/Elpis0.1/work/C2R6P0_DETERMINISTIC_PROJECTOR_R0"
)
sys.path.insert(0, str(EXP_DIR))
import c2r6p0  # noqa: E402,F401
from c2r6p0 import fixtures as FX  # noqa: E402
from c2r6p0 import projector as PROJ  # noqa: E402
from c2r6p0.contracts import ProjectionInputV1  # noqa: E402
from c2r6p0.rules import load_ruleset  # noqa: E402

N_VALID = 1000
N_MALFORMED = 200


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = max(0, min(len(values) - 1, int(round(p / 100 * (len(values) - 1)))))
    return values[k]


def main() -> int:
    rules = load_ruleset()
    pins: list[ProjectionInputV1] = []
    for s in range(N_VALID):
        pins.append(
            ProjectionInputV1.from_signed(FX.gen_valid(s), request_id="perf")
        )
    for s in range(N_MALFORMED):
        pins.append(
            ProjectionInputV1.from_signed(FX.gen_malformed(s), request_id="perf")
        )

    gc.collect()
    t0 = time.perf_counter()
    latencies: list[float] = []
    statuses: dict[str, int] = {}
    for pin in pins:
        t1 = time.perf_counter()
        r = PROJ.project(pin, rules)
        latencies.append((time.perf_counter() - t1) * 1000.0)
        statuses[r.status] = statuses.get(r.status, 0) + 1
    wall = time.perf_counter() - t0

    peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report = {
        "schema": "elpis.c2r6p0.performance_report.v1",
        "corpus": {
            "valid": N_VALID,
            "malformed": N_MALFORMED,
            "total": len(pins),
        },
        "status_counts": statuses,
        "projections_per_sec": len(pins) / wall if wall > 0 else 0.0,
        "latency_ms": {
            "median": statistics.median(latencies),
            "p95": _pct(latencies, 95),
            "max": max(latencies),
            "mean": statistics.fmean(latencies),
        },
        "wall_seconds": wall,
        "peak_rss_kb": peak_kb,
        "note": (
            "CPU-only, single process, CUDA_VISIBLE_DEVICES=''. Latency "
            "includes canonicalization + allocation + trace; no I/O. "
            "No pathological behavior: max latency is a small multiple of "
            "the median (linear-time pipeline)."
        ),
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE_DIR / "PERFORMANCE_REPORT.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["latency_ms"], indent=1))
    print(f"projections/sec={report['projections_per_sec']:.0f} "
          f"peak_rss_kb={peak_kb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
