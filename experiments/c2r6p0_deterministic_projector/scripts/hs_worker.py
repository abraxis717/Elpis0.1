"""Cross-process hash-seed worker (mission 25).

Projects a fixed corpus and emits:
  * stdout: ONE JSON line
      {"n": <count>, "corpus_sha256": ..., "fingerprints_sha256": ...}
  * (optional) argv[1]: a file path. If given, the raw concatenated
    canonical result bytes are written there, so cross-process
    comparison is over the actual serialized bytes (not just digests).

Run under different PYTHONHASHSEED values; digests AND byte files
must be identical across seeds. The corpus is fixed by construction
(named fixtures + seeds 0..99 of the valid generator), so every
process projects exactly the same graphs in the same order.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

EXP_DIR = Path(__file__).resolve().parent.parent
if str(EXP_DIR) not in sys.path:
    sys.path.insert(0, str(EXP_DIR))

import c2r6p0  # noqa: E402,F401  (installs authority overlay)
from c2r6p0 import fixtures as FX  # noqa: E402
from c2r6p0.projector import ProjectionInputV1  # noqa: E402
from c2r6p0.rules import load_ruleset  # noqa: E402


def main() -> None:
    rules = load_ruleset()
    h = hashlib.sha256()
    hf = hashlib.sha256()
    out: bytes | None = None
    out_path = sys.argv[1] if len(sys.argv) > 1 else None
    sink = open(out_path, "wb") if out_path else None
    n = 0
    for f in FX.POSITIVE_FIXTURES:
        pin = ProjectionInputV1.from_signed(f.graph, request_id="hs")
        r = c2r6p0.projector.project(pin, rules)
        b = r.to_canonical_bytes()
        h.update(b)
        if sink is not None:
            sink.write(b)
        hf.update(r.structural_input_fingerprint.encode("ascii"))
        n += 1
    for i in range(100):
        g = FX.gen_valid(seed=i)
        pin = ProjectionInputV1.from_signed(g, request_id=f"hs{i}")
        r = c2r6p0.projector.project(pin, rules)
        b = r.to_canonical_bytes()
        h.update(b)
        if sink is not None:
            sink.write(b)
        hf.update(r.structural_input_fingerprint.encode("ascii"))
        n += 1
    if sink is not None:
        sink.close()
    print(json.dumps({
        "n": n,
        "corpus_sha256": h.hexdigest(),
        "fingerprints_sha256": hf.hexdigest(),
    }))


if __name__ == "__main__":
    main()
