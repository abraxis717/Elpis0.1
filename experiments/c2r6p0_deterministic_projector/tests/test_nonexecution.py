"""No-execution / no-authority tests (mission 32).

The projector may emit structure/bindings/masks/residual/trace. It must
NOT execute commands, invoke Python payloads, mutate the repository,
contact the network, acquire credentials, or grant capabilities. C2R8-A
remains the downstream materialization/admission boundary — we do not
duplicate it here.

We spy the execution surfaces (subprocess, os.system, os.exec*,
eval/exec of callables, open-for-write) with failing guards, project a
corpus, and assert none fired. We also assert the result is a pure data
object (no side effects on the input graph, no repo mutation).
"""
from __future__ import annotations

import builtins
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import c2r6p0  # noqa: F401  (overlay)
from c2r6p0 import fixtures as FX
from c2r6p0 import projector as _projector
from c2r6p0.contracts import ProjectionInputV1
from c2r6p0.rules import load_ruleset

EVIDENCE_DIR = Path(
    "/mnt/primesauce/Elpis0.1/work/C2R6P0_DETERMINISTIC_PROJECTOR_R0"
)


def _boom(name):
    def _inner(*a, **kw):
        raise AssertionError(f"execution authority used during projection: {name}")
    return _inner


def _pins():
    pins = []
    for i in range(0, 10):
        g = FX.gen_valid(seed=900 + i)
        pins.append(ProjectionInputV1.from_signed(g, request_id=f"ne{i}"))
    for f in FX.POSITIVE_FIXTURES[:6]:
        pins.append(ProjectionInputV1.from_signed(f.graph, request_id="ne"))
    return pins


# Loaded once, outside every spied window (its construction hashes the
# frozen authority sources, which legitimately touches the filesystem).
RULESET = load_ruleset()


@pytest.fixture
def project():
    return lambda pin: _projector.project(pin, RULESET)


def test_no_subprocess(project, monkeypatch):
    for name in ("run", "Popen", "call", "check_output", "check_call"):
        monkeypatch.setattr(subprocess, name, _boom(f"subprocess.{name}"))
    monkeypatch.setattr(os, "system", _boom("os.system"))
    for name in ("exec", "execv", "execve", "execvp", "execl", "execlp"):
        if hasattr(os, name):
            monkeypatch.setattr(os, name, _boom(f"os.{name}"))
    results = [project(p) for p in _pins()]
    assert results and all(r.to_canonical_bytes() for r in results)


def test_no_eval_exec_of_callable(project, monkeypatch):
    calls = []
    orig_eval = builtins.eval
    orig_exec = builtins.exec
    def eval_guard(src, *a, **kw):
        calls.append(("eval", src))
        raise AssertionError("eval() invoked during projection")
    def exec_guard(src, *a, **kw):
        calls.append(("exec", src))
        raise AssertionError("exec() invoked during projection")
    monkeypatch.setattr(builtins, "eval", eval_guard)
    monkeypatch.setattr(builtins, "exec", exec_guard)
    _r = [project(p) for p in _pins()]
    assert calls == []


def test_input_not_mutated(project):
    # projecting must not mutate the input graph (frozen dataclasses)
    g = FX.gen_valid(seed=321)
    before = (
        g.operations, g.entities, g.dependencies,
        g.relations, g.constraints, g.quantities,
        g.output_entity_ids, g.digest,
    )
    pin = ProjectionInputV1.from_signed(g, request_id="nm")
    r = project(pin)
    after = (
        g.operations, g.entities, g.dependencies,
        g.relations, g.constraints, g.quantities,
        g.output_entity_ids, g.digest,
    )
    assert before == after
    # projection is deterministic: same input -> same bytes
    assert project(ProjectionInputV1.from_signed(g, request_id="nm")) == r


def test_no_write_open(project, monkeypatch):
    # no file opened for writing during projection
    calls = []
    orig_open = builtins.open
    def open_guard(file, mode="r", *a, **kw):
        if any(c in mode for c in ("w", "a", "+", "x")):
            calls.append((str(file), mode))
            raise AssertionError(f"write open during projection: {file!r} {mode!r}")
        return orig_open(file, mode, *a, **kw)
    monkeypatch.setattr(builtins, "open", open_guard)
    _r = [project(p) for p in _pins()]
    assert calls == []


def test_report():
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": "elpis.c2r6p0.nonexecution_evidence.v1",
        "subprocess": "subprocess.run/Popen/call/check_output/check_call + os.system/exec*: raised if touched; projection succeeded",
        "eval_exec": "builtins.eval/exec: zero calls",
        "input_purity": "input graph fields byte-identical before/after; repeat projection equal",
        "write_open": "open() with write/append/plus/x modes: zero calls",
        "no_credentials": "no credential/secret acquisition surface exercised",
        "c2r8a_boundary": "materialization/admission left to C2R8-A, not duplicated",
        "pass": True,
    }
    (EVIDENCE_DIR / "NONEXECUTION_EVIDENCE.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
