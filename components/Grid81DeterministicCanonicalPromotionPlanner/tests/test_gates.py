"""Tests for promotion gates."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from elpis_grid81_promotion_planner.source_binding import build_source_chain
from elpis_grid81_promotion_planner.gates import (
    evaluate_gates,
    GATE_DEFINITIONS,
    first_failure,
)
from elpis_grid81_promotion_planner.decision import make_decision, DECISION_READY

CONFIG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "source_config.json"
)
with open(CONFIG) as _f:
    config = json.load(_f)


def _load_config():
    with open(CONFIG) as f:
        return json.load(f)


def test_gate_count():
    chain = build_source_chain(_load_config())
    results = evaluate_gates(chain)
    assert len(results) == 20


def test_all_gates_pass_on_sealed_chain():
    chain = build_source_chain(_load_config())
    results = evaluate_gates(chain)
    for r in results:
        assert r.passed, f"Gate {r.gate_id} failed with {r.rejection_code}"


def test_gate_order_deterministic():
    chain = build_source_chain(_load_config())
    r1 = evaluate_gates(chain)
    r2 = evaluate_gates(chain)
    for i in range(len(r1)):
        assert r1[i].gate_id == r2[i].gate_id
        assert r1[i].gate_ordinal == r2[i].gate_ordinal


def test_gate_digests_deterministic():
    chain = build_source_chain(_load_config())
    r1 = evaluate_gates(chain)
    r2 = evaluate_gates(chain)
    for i in range(len(r1)):
        assert r1[i].digest == r2[i].digest


def test_decision_is_ready():
    chain = build_source_chain(_load_config())
    results = evaluate_gates(chain)
    decision = make_decision(results, chain)
    assert decision.decision == DECISION_READY


def test_first_failure_none_when_all_pass():
    chain = build_source_chain(_load_config())
    results = evaluate_gates(chain)
    assert first_failure(results) is None


def test_missing_phase_rejected():
    bad_config = dict(_load_config())
    bad_config["g53b1_directory"] = "/nonexistent/g53b1"
    try:
        build_source_chain(bad_config)
        assert False, "Should raise FileNotFoundError"
    except FileNotFoundError:
        pass


def test_gate_ids_unique():
    ids = [gid for gid, _, _ in GATE_DEFINITIONS]
    assert len(ids) == len(set(ids))


def test_gate_ordinal_ascending():
    ordinals = [ord_ for _, ord_, _ in GATE_DEFINITIONS]
    for i in range(len(ordinals) - 1):
        assert ordinals[i] < ordinals[i + 1]
