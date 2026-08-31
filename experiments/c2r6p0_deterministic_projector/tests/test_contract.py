"""Input/output contract tests (missions 5, 6, 30)."""
from __future__ import annotations

import pytest

from elpis_p0.semantic_ir import (
    P0SemanticRequestV1,
    SemanticDependencyV1,
    SemanticEntityV1,
    SemanticOperationV1,
)

from conftest import simple_graph, wrap
from c2r6p0.contracts import (
    ProjectionError,
    ProjectionInputV1,
    ProjectionStatus,
    ProjectionResultV1,
)


class TestInputWrapper:
    def test_minimal(self, project):
        r = project(wrap(simple_graph()))
        assert r.status == "PROJECTED"
        assert r.error is None

    def test_schema_mismatch(self):
        with pytest.raises(ValueError):
            ProjectionInputV1(
                schema="bogus.v9",
                semantic_graph=simple_graph(),
            )

    def test_wrong_graph_type(self):
        with pytest.raises(ValueError):
            ProjectionInputV1(semantic_graph="not-a-graph")  # type: ignore[arg-type]

    def test_debug_tag_bounds(self):
        with pytest.raises(ValueError):
            ProjectionInputV1(
                semantic_graph=simple_graph(), debug_tag="x" * 129,
            )
        with pytest.raises(ValueError):
            ProjectionInputV1(
                semantic_graph=simple_graph(), debug_tag="a\x00b",
            )

    def test_wrapper_is_frozen(self):
        pin = wrap(simple_graph())
        with pytest.raises(Exception):
            pin.request_id = "other"  # type: ignore[misc]


class TestResultContract:
    def test_projected_fields(self, project):
        r = project(wrap(simple_graph()))
        assert isinstance(r, ProjectionResultV1)
        assert r.status == "PROJECTED"
        assert r.grid81 and len(r.grid81) == 81
        assert r.frozen_mask and r.writable_mask
        assert r.bindings is not None
        assert r.trace is not None and r.trace.events
        assert r.declared_features and len(r.declared_features) == 529
        assert r.active_residual and len(r.active_residual) == 529
        assert r.structural_input_fingerprint
        assert r.projection_digest

    def test_rejection_fields_typed(self, project):
        # illegal cycle -> typed rejection, not an exception
        g = P0SemanticRequestV1(
            request_id="rc",
            entities=(SemanticEntityV1("e0", "input", "v", "str"),),
            operations=(
                SemanticOperationV1("a", "s"),
                SemanticOperationV1("b", "s"),
            ),
            dependencies=(
                SemanticDependencyV1("d1", "a", "b"),
                SemanticDependencyV1("d2", "b", "a"),
            ),
            digest="",
        )
        r = project(wrap(g))
        assert r.status == ProjectionStatus.INVALID_SEMANTIC_IR.value
        assert isinstance(r.error, ProjectionError)
        assert r.error.code
        assert r.error.rule
        assert isinstance(r.error.detail, dict)
        # no opaque traceback leaked into the result
        d = r.to_dict()
        assert "Traceback" not in str(d)

    def test_status_vocabulary(self):
        expected = {
            "PROJECTED",
            "INVALID_SEMANTIC_IR",
            "UNSUPPORTED_SEMANTIC_SHAPE",
            "DECOMPOSITION_REQUIRED",
            "AMBIGUOUS_BINDING",
            "STRUCTURAL_CONTRADICTION",
        }
        actual = {s.value for s in ProjectionStatus}
        assert expected <= actual

    def test_canonical_serialization_roundtrip(self, project):
        r = project(wrap(simple_graph()))
        b = r.to_canonical_bytes()
        r2 = project(wrap(simple_graph()))
        assert r2.to_canonical_bytes() == b
        assert r.projection_digest == r2.projection_digest

    def test_rejection_serializes(self, project):
        # unsupported entity kind: a validly-digested graph (via the
        # builder, so the authority digest check does not shadow the kind
        # check) that the canonicalizer must reject by rule.
        from elpis_p0.semantic_ir import build_semantic_request_v1
        g = build_semantic_request_v1(
            request_id="rc2",
            entities=(SemanticEntityV1("w", "widget", "v", "str"),),
            operations=(SemanticOperationV1("a", "s"),),
        )
        r = project(wrap(g))
        assert r.status == "UNSUPPORTED_SEMANTIC_SHAPE"
        assert r.error.code == "ERR.UNSUPPORTED_SEMANTIC_SHAPE"
        d = r.to_dict()
        assert d["error"]["rule"] == "R4.UNSUPPORTED_KIND"
