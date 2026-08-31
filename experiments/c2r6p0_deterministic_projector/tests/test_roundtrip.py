"""Semantic skeleton round-trip tests (mission 22).

Required property, supported subset:
    canonical semantic skeleton -> project -> extract_semantic_skeleton
        == canonical semantic skeleton
"""
from __future__ import annotations

from elpis_p0.semantic_ir import semantic_request_payload

from conftest import wrap
from c2r6p0 import fixtures as FX
from c2r6p0.canonicalize import canonicalize
from c2r6p0.residual import (
    canonical_skeleton_of_payload,
    extract_semantic_skeleton,
)
from c2r6p0.rules import load_ruleset


def _roundtrip(graph, project) -> None:
    r = project(wrap(graph))
    if r.status != "PROJECTED":
        return
    got = extract_semantic_skeleton(r.bindings, r.invariants)
    want = canonical_skeleton_of_payload(
        _payload(graph)
    )
    assert got == want


def _payload(graph) -> dict:
    rs = load_ruleset()
    g, err = canonicalize(graph, rs)
    assert err is None and g is not None
    return g.payload


class TestRoundTrip:
    def test_named_projected_fixtures(self, project):
        for f in FX.POSITIVE_FIXTURES:
            if f.expect == "PROJECTED":
                _roundtrip(f.graph, project)

    def test_generated_corpus(self, project):
        for seed in range(50, 120):
            _roundtrip(FX.gen_valid(seed), project)

    def test_skeleton_non_generative(self, project):
        # no prose / no invented ids: every skeleton identity exists in
        # the original graph payload
        g = FX.gen_valid(77)
        r = project(wrap(g))
        if r.status != "PROJECTED":
            import pytest
            pytest.skip("decomposed")
        skel = extract_semantic_skeleton(r.bindings, r.invariants)
        payload = _payload(g)
        ent_ids = {e["entity_id"] for e in payload["entities"]}
        op_ids = {o["operation_id"] for o in payload["operations"]}
        for e in skel["entities"]:
            assert e["entity_id"] in ent_ids
        for o in skel["operations"]:
            assert o["operation_id"] in op_ids
        for d in skel["dependencies"]:
            assert d["predecessor_operation_id"] in op_ids
            assert d["successor_operation_id"] in op_ids
        for rel in skel["relations"]:
            assert rel["source_id"] in ent_ids | op_ids
            assert rel["target_id"] in ent_ids | op_ids

    def test_skeleton_digests_deterministic(self, project):
        from c2r6p0.contracts import canonical_bytes, sha256_hex
        g = FX.gen_valid(88)
        r = project(wrap(g))
        if r.status != "PROJECTED":
            import pytest
            pytest.skip("decomposed")
        s1 = sha256_hex(canonical_bytes(
            extract_semantic_skeleton(r.bindings, r.invariants)
        ))
        r2 = project(wrap(g))
        s2 = sha256_hex(canonical_bytes(
            extract_semantic_skeleton(r2.bindings, r2.invariants)
        ))
        assert s1 == s2
