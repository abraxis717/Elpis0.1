"""Test configuration for the C2R6-P1 bridge suite.

Wires the C2R6-P0 authority overlay (elpis_p0 -> frozen C2R7-C
structural_residual + canonical elpis_p0; C2R7-C probe dir on sys.path for
structural_trm_features), then the experiment dir (so ``c2r6p1_bridge`` is
importable). All shared builders + common invariants live here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

EXP_DIR = Path(__file__).resolve().parent.parent
if str(EXP_DIR) not in sys.path:
    sys.path.insert(0, str(EXP_DIR))

# The frozen C2R6-P0 projector package lives in its own experiment dir;
# add it so `import c2r6p0` resolves (its __init__ installs the overlay).
C2R6P0_EXP_DIR = EXP_DIR.parent / "c2r6p0_deterministic_projector"
if str(C2R6P0_EXP_DIR) not in sys.path:
    sys.path.insert(0, str(C2R6P0_EXP_DIR))

# Install the C2R6-P0 authority overlay (idempotent; pinned paths).
import c2r6p0  # noqa: F401,E402
from c2r6p0 import fixtures as C2R6P0_FIX  # noqa: E402
from c2r6p0 import projector as C2R6P0_PROJECTOR  # noqa: E402
from c2r6p0.contracts import ProjectionInputV1, ProjectionStatus  # noqa: E402
from c2r6p0.rules import load_ruleset  # noqa: E402
from c2r6p0.residual import build_fingerprint as _proj_fp  # noqa: E402


def rebind(r, **fields):
    """Apply ``replace(r, **fields)`` then recompute the projector's
    structural input fingerprint so the resulting projection stays
    self-consistent (the bridge recomputes this fingerprint and rejects
    a stale one). Use for binding-only mutations where the structural
    grid/masks/invariants are unchanged, so the refinement fingerprint
    stays identical and only the semantic fingerprint/envelope digests
    move."""
    from dataclasses import replace as _rep

    m = _rep(r, **fields)
    return _rep(
        m,
        structural_input_fingerprint=_proj_fp(
            m.grid81,
            m.frozen_mask,
            m.writable_mask,
            m.invariants,
            m.lane_bindings,
            m.declared_features,
            m.active_residual,
            m.bindings,
        ),
    )

from c2r6p1_bridge import (  # noqa: E402
    BridgeRejectionCode,
    BridgeRejectionError,
    FirstLegalMoveRefiner,
    NullRefiner,
    adapt_projection_to_refiner_input,
    apply_candidate,
    build_envelope,
    legal_candidates,
    replay_transition_chain,
    run_refiner_bounded,
)

from elpis_p0.structural_residual import (  # noqa: E402
    GRID_SIZE,
    residual as authority_residual,
    validate_transition,
)


@pytest.fixture(scope="session")
def ruleset():
    return load_ruleset()


@pytest.fixture(scope="session")
def project():
    rs = load_ruleset()
    return lambda pin: C2R6P0_PROJECTOR.project(pin, rs)


def wrap(graph, **kw) -> ProjectionInputV1:
    return ProjectionInputV1.from_signed(graph, **kw)


def projected_cases(n: int, seed_base: int = 20260831):
    """Deterministic PROJECTED projections from the frozen C2R6-P0 fixtures.

    Uses the frozen C2R6-P0 generator (gen_valid) — no duplicated fixture
    semantics. Yields (name, projection_result) for PROJECTED results only.
    """
    rs = load_ruleset()
    out = []
    s = seed_base
    while len(out) < n:
        g = C2R6P0_FIX.gen_valid(s)
        r = C2R6P0_PROJECTOR.project(wrap(g, request_id=f"c2r6p1_{s}"), rs)
        if r.status == ProjectionStatus.PROJECTED.value:
            out.append((f"proj_{s:07d}", r))
        s += 1
    return out


@pytest.fixture(scope="session")
def one_projected(project):
    """A single, fixed, representative PROJECTED projection (seed 0)."""
    g = C2R6P0_FIX.gen_valid(0)
    r = project(wrap(g, request_id="c2r6p1_fixed_0"))
    assert r.status == ProjectionStatus.PROJECTED.value
    return r


def expect_rejection(fn, code, **kw):
    """Assert fn raises BridgeRejectionError with a code in the allowed set.

    ``code`` may be a single BridgeRejectionCode (exact) or an iterable of
    acceptable codes (where the first check to fire is deterministic but
    order-dependent). Negative-test hygiene: the assertion is made on the
    typed rejection object, not on a bare except (which would swallow our
    own assertion errors).
    """
    allowed = (
        {code} if isinstance(code, BridgeRejectionCode) else set(code)
    )
    try:
        fn()
    except BridgeRejectionError as e:
        assert e.rejection.code in allowed, (
            f"expected one of "
            f"{[c.value for c in sorted(allowed, key=lambda c: c.value)]}, "
            f"got {e.rejection.code.value} detail={e.rejection.detail}"
        )
        return e.rejection
    except AssertionError:
        raise
    except Exception as e:  # noqa: BLE001
        raise AssertionError(
            f"expected BridgeRejectionError in "
            f"{[c.value for c in allowed]}, got {type(e).__name__}: {e}"
        )
    raise AssertionError(
        f"expected BridgeRejectionError in {[c.value for c in allowed]}, "
        "got none"
    )
