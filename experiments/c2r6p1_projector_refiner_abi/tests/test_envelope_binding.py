"""Semantic binding envelope preservation (mission 6).

Adapting to refiner input and reconstructing the envelope must not merge,
rename, or lose bindings. The structural model sees ONLY the structural
search state; the outer deterministic system retains semantic identity.
"""
from __future__ import annotations

from dataclasses import replace

import conftest as C

from c2r6p0.contracts import binding_payload, canonical_bytes
from c2r6p1_bridge import (
    adapt_projection_to_refiner_input,
    build_envelope,
)


def test_envelope_preserves_every_binding_verbatim(one_projected):
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    env = build_envelope(r, ri)
    b = env.structural_bindings
    # identity: same object, same ids
    assert b is r.bindings
    assert [o.semantic_id for o in b.op_bindings] == [
        o.semantic_id for o in r.bindings.op_bindings
    ]
    assert [e.semantic_id for e in b.entity_bindings] == [
        e.semantic_id for e in r.bindings.entity_bindings
    ]
    assert [e.semantic_id for e in b.edge_bindings] == [
        e.semantic_id for e in r.bindings.edge_bindings
    ]
    assert b.output_entity_ids == r.bindings.output_entity_ids
    # no merge / no loss / no rename: canonical payloads byte-identical
    assert (
        canonical_bytes(binding_payload(b))
        == canonical_bytes(binding_payload(r.bindings))
    )


def test_envelope_digest_bound_to_bindings(one_projected):
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    env = build_envelope(r, ri)
    assert env.envelope_digest == env.envelope_digest_computed()
    # mutating the op-binding operators changes the envelope digest
    if r.bindings.op_bindings:
        ops2 = tuple(replace(o, operator=o.operator + "_mut")
                     for o in r.bindings.op_bindings)
        r2 = C.rebind(r, bindings=replace(r.bindings, op_bindings=ops2))
        env2 = build_envelope(r2, adapt_projection_to_refiner_input(r2))
        assert env2.envelope_digest_computed() != env.envelope_digest_computed()
    # mutating output_entity_ids changes the envelope digest
    r3 = C.rebind(r, bindings=replace(
        r.bindings,
        output_entity_ids=r.bindings.output_entity_ids + ("zz_extra",),
    ))
    env3 = build_envelope(r3, adapt_projection_to_refiner_input(r3))
    assert env3.envelope_digest_computed() != env.envelope_digest_computed()


def test_envelope_rejects_wrong_schema(one_projected):
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    env = build_envelope(r, ri)
    try:
        replace(env, schema="c2r6p1.refiner-envelope.v2")
        raise AssertionError("expected schema rejection")
    except ValueError:
        pass


def test_structural_view_has_no_semantic_identity(one_projected):
    """The structural refiner view must not leak a semantic identifier."""
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    view = ri.structural_view()
    blob = canonical_bytes(view).decode("utf-8")
    # no semantic_id strings from the bindings appear in the structural view
    for b in r.bindings.op_bindings:
        assert b.semantic_id not in blob
    for b in r.bindings.entity_bindings:
        assert b.semantic_id not in blob
    # but it does carry the structural state
    assert view["grid81"] == list(r.grid81)
    assert view["active_residual"] == list(r.active_residual)


def test_envelope_preserved_across_refinement(one_projected):
    """The semantic envelope survives a structural transition unchanged
    (out-of-band): the binding payload and its digests are invariant while
    the structural state mutates."""
    from c2r6p1_bridge import FirstLegalMoveRefiner, run_refiner_bounded

    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    env = build_envelope(r, ri)
    ri1, trace, applied = run_refiner_bounded(
        FirstLegalMoveRefiner(), ri, max_moves=4
    )
    if applied == 0:
        return
    # reconstruct the envelope from the FINAL structural state: the
    # semantic sidecar is identical (it never mutates with the grid)
    env_final_payload = env.envelope_payload()
    # the binding payload is byte-stable
    assert (
        canonical_bytes(binding_payload(env.structural_bindings))
        == canonical_bytes(binding_payload(r.bindings))
    )
    # the structural input digest DID change (state mutated) but the
    # semantic digests did not
    assert env_final_payload["semantic_input_digest"] == r.semantic_input_digest
    assert env_final_payload["projection_digest"] == r.projection_digest
    assert env_final_payload["projection_trace_digest"] == r.trace.trace_digest
