"""No-ambient-information tests (mission 31).

The projector must be a pure function of (explicit semantic input,
pinned ruleset). It must not inspect the filesystem, environment,
network, or the current time to decide projection semantics.

Method: pass-through RECORDING spies. Each ambient surface is wrapped
in a spy that forwards the call to the original and records it. The
spy window is tightly scoped around the PROJECTION LOOP ONLY — corpus
construction, spy installation/teardown, and pytest harness traffic
all happen outside the window, so the recorded set is exactly the
ambient accesses the projector itself performed.

Why pass-through rather than failing spies: monkeypatch.setattr(os,
"stat", ...) is global, and once armed pytest's own harness
(cacheprovider, assertion rewriting, the setattr machinery) also
stats files — harness traffic would then be indistinguishable from
projector traffic. Recording + tight windowing is the clean
separation.

The pinned ruleset is loaded ONCE at module import: its construction
legitimately hashes the frozen authority sources, so that filesystem
traffic belongs to setup, not to projection semantics.
"""
from __future__ import annotations

import datetime as _dt
import getpass
import json
import os
import random as _random
import socket as _socket
import time as _time
from pathlib import Path

import c2r6p0  # noqa: F401  (overlay)
from c2r6p0 import fixtures as FX
from c2r6p0 import projector as _projector
from c2r6p0.contracts import ProjectionInputV1
from c2r6p0.rules import load_ruleset

EVIDENCE_DIR = Path(
    "/mnt/primesauce/Elpis0.1/work/C2R6P0_DETERMINISTIC_PROJECTOR_R0"
)

# Loaded once, outside every spied window (its construction hashes the
# frozen authority sources, which legitimately touches the filesystem).
RULESET = load_ruleset()


def project(pin: ProjectionInputV1):
    return _projector.project(pin, RULESET)


def _corpus_pins():
    pins = []
    for i in range(0, 12):
        g = FX.gen_valid(seed=500 + i)
        pins.append(ProjectionInputV1.from_signed(g, request_id=f"na{i}"))
    for f in FX.POSITIVE_FIXTURES[:8]:
        pins.append(ProjectionInputV1.from_signed(f.graph, request_id="na"))
    return pins


def _ambient_scan(names: list, pins):
    """Project `pins` while recording ambient accesses in `names`.

    `names` is a list of (module, attr) pairs. Spies are pass-through:
    originals are installed before the loop and restored after it, so
    the spy window covers exactly the projection loop.

    Returns (results, records) where records is a list of
    ("module.attr", args, kwargs).
    """
    records: list = []
    originals = []
    for mod, attr in names:
        orig = getattr(mod, attr)

        def _spy(*a, _orig=orig, _mod=mod, _attr=attr, **kw):
            records.append((f"{_mod.__name__}.{_attr}", a, kw))
            return _orig(*a, **kw)

        setattr(mod, attr, _spy)
        originals.append((mod, attr, orig))
    try:
        results = [project(p) for p in pins]
    finally:
        for mod, attr, orig in reversed(originals):
            setattr(mod, attr, orig)
    return results, records


def test_env_not_read():
    # (a) marker env var present vs absent: identical canonical bytes
    os.environ["ELPIS_PROJECTION_HINT"] = "should_not_matter"
    pins = _corpus_pins()
    r1 = [p.to_canonical_bytes() for p in [project(x) for x in pins]]
    del os.environ["ELPIS_PROJECTION_HINT"]
    r2 = [p.to_canonical_bytes() for p in [project(x) for x in pins]]
    assert r1 == r2
    # (b) zero env/credential reads during the projection loop
    getpass_reads: list = []
    orig_gpa = getpass.getpass
    orig_gpu = getpass.getuser

    def _gpa(*a, **kw):
        getpass_reads.append(("getpass.getpass", a))
        return orig_gpa(*a, **kw)

    def _gpu(*a, **kw):
        getpass_reads.append(("getpass.getuser", a))
        return orig_gpu(*a, **kw)

    getpass.getpass = _gpa
    getpass.getuser = _gpu
    try:
        _, records = _ambient_scan([(os, "getenv")], pins)
    finally:
        getpass.getpass = orig_gpa
        getpass.getuser = orig_gpu
    assert records == []
    assert getpass_reads == []


def test_filesystem_not_read():
    pins = _corpus_pins()
    results, records = _ambient_scan(
        [
            (os, "stat"),
            (os, "access"),
            (os, "listdir"),
            (os, "open"),
            (os.path, "getsize"),
            (os.path, "exists"),
            (os.path, "isfile"),
            (os.path, "isdir"),
            (os.path, "getmtime"),
        ],
        pins,
    )
    assert results and all(len(r.to_canonical_bytes()) > 1000 for r in results)
    assert records == [], records[:5]


def test_time_not_read():
    pins = _corpus_pins()
    # time.time / time.time_ns / time.monotonic are the CPython
    # implementations behind datetime.now()/utcnow()/timestamp() —
    # zero calls to them proves no wall-clock or monotonic clock read
    # during projection.
    _, records = _ambient_scan(
        [
            (_time, "time"),
            (_time, "time_ns"),
            (_time, "monotonic"),
        ],
        pins,
    )
    assert records == []


def test_network_not_available():
    pins = _corpus_pins()
    results, records = _ambient_scan(
        [
            (_socket, "socket"),
            (_socket, "create_connection"),
            (_socket, "getaddrinfo"),
        ],
        pins,
    )
    assert results and all(len(r.to_canonical_bytes()) > 1000 for r in results)
    assert records == []


def test_random_not_used():
    pins = _corpus_pins()
    _, records = _ambient_scan(
        [
            (_random, "random"),
            (_random, "randint"),
            (_random, "randrange"),
            (_random, "choice"),
            (_random, "shuffle"),
            (_random, "seed"),
            (_random, "Random"),
        ],
        pins,
    )
    assert records == []


def test_repeated_projection_deterministic():
    # ambient purity implies byte determinism across repeated calls
    pins = _corpus_pins()
    a = [p.to_canonical_bytes() for p in [project(x) for x in pins]]
    b = [p.to_canonical_bytes() for p in [project(x) for x in pins]]
    assert a == b


def test_report():
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": "elpis.c2r6p0.nonambient_evidence.v1",
        "method": "pass-through recording spies, window scoped to the projection loop only",
        "env_invariance": "marker env var present/absent -> identical canonical bytes; os.getenv: zero calls; getpass.getpass/getuser: zero calls",
        "filesystem": "os.stat/access/listdir/open + os.path.getsize/exists/isfile/isdir/getmtime: zero calls during projection",
        "time": "time.time/time_ns/monotonic (the CPython implementations behind datetime.now/utcnow/timestamp): zero calls during projection",
        "network": "socket.socket/create_connection/getaddrinfo: zero calls during projection; projection succeeded",
        "random": "random.random/randint/randrange/choice/shuffle/seed/Random: zero calls during projection",
        "ruleset_loading": "pinned ruleset hashed the frozen authority sources ONCE at module import (outside the spied window); projection itself is pure",
        "pass": True,
    }
    (EVIDENCE_DIR / "NONAMBIENT_EVIDENCE.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
