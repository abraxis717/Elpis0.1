"""Mission 22 — nonambient / nonexecution gate.

Proves the bridge and both deterministic test refiners perform NO network,
subprocess, filesystem mutation, wall-clock, environment, credential, or
model/CUDA access during adaptation, candidate enumeration, transitions,
replay, and packer round-trips.

The guard (``ambient_guard``) patches every standard-library surface the
bridge must not touch and fails closed on the first violation. We run the
full data path under the guard and assert ZERO hits.

Also asserts the run is CPU-only (no CUDA touched during the path).
"""
from __future__ import annotations

import time

import conftest as C
from c2r6p1_bridge import (
    NullRefiner,
    FirstLegalMoveRefiner,
    adapt_projection_to_refiner_input,
    build_envelope,
    legal_candidates,
    run_refiner_bounded,
    replay_transition_chain,
    roundtrip_529,
    one_hot,
    ambient_guard,
    AmbientViolation,
)


def _full_bridge_path(r) -> None:
    """Exercise the entire bridge data path for one projected result."""
    ri = adapt_projection_to_refiner_input(r)
    env = build_envelope(r, ri)
    cands = legal_candidates(ri)
    ri_n, tr_n, _ = run_refiner_bounded(NullRefiner(), ri, 1)
    ri1, tr1, _ = run_refiner_bounded(FirstLegalMoveRefiner(), ri, 4)
    final = replay_transition_chain(r, tr1)
    # packer round-trip on the real vectors + one-hot boundary bits
    roundtrip_529(ri.declared_features, ri.active_residual)
    for bit in (0, 511, 512, 528):
        roundtrip_529(*one_hot(bit))
    # force the env/replay paths to actually run (no short-circuit)
    assert env.envelope_digest
    assert final.refinement_state_fingerprint
    assert ri_n.refinement_state_fingerprint
    assert cands is not None


def test_full_bridge_path_nonambient() -> None:
    """The whole bridge path runs with ZERO ambient touches (5 seeds)."""
    cases = C.projected_cases(5, seed_base=0)
    hits = []
    for _name, r in cases:
        with ambient_guard() as h:
            _full_bridge_path(r)
        hits.extend(h)
    assert hits == [], "ambient guard tripped: %r" % hits


def test_full_bridge_path_nonexecution() -> None:
    """No subprocess / command execution during the bridge path.

    ``subprocess`` is in the fail-on set, so any Popen/run/call would have
    raised AmbientViolation; reaching here with no hits proves
    nonexecution.
    """
    cases = C.projected_cases(2, seed_base=0)
    for _name, r in cases:
        with ambient_guard(fail_on=("subprocess",)):
            _full_bridge_path(r)


def test_guard_detects_violation_when_touched(one_projected) -> None:
    """The guard actually fails closed: a deliberate wall-clock touch
    (time.time) during the guarded region must raise AmbientViolation.
    This proves the guard is a real instrument, not a no-op."""
    r = one_projected
    try:
        with ambient_guard(fail_on=("wall_clock",)):
            ri = adapt_projection_to_refiner_input(r)
            time.time()  # deliberate violation
            assert ri.refiner_input_digest
    except AmbientViolation as e:
        assert any(h.startswith("wall_clock") for h in e.hits)
    else:
        raise AssertionError("guard did not fail closed on a wall-clock touch")


def test_full_bridge_path_no_cuda_touched() -> None:
    """CUDA device calls (is_available/set_device) are patched; running the
    bridge path under fail_on=('cuda',) proves the path never calls them."""
    cases = C.projected_cases(2, seed_base=0)
    for _name, r in cases:
        with ambient_guard(fail_on=("cuda",)):
            _full_bridge_path(r)


def test_non_cuda_device_selected() -> None:
    """Document the run environment: if torch is present and CUDA is
    available, the bridge still never selects a CUDA device (no
    set_device call under the guard)."""
    try:
        import torch  # noqa: F401
    except Exception:
        return  # torch absent -> trivially non-CUDA
    r = C.projected_cases(1, seed_base=0)[0][1]
    with ambient_guard(fail_on=("cuda",)):
        _full_bridge_path(r)
