from __future__ import annotations

import ast
import dataclasses
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

import elpis_reference.p0_validator_ingress as p0_ingress
from elpis_reference.p0_validator_ingress import (
    P0ProjectionTraceV1,
    build_p0_projection_trace,
)


REPO = Path(__file__).resolve().parents[1]


def _default_getattr_sites():
    out = set()
    for path in sorted((REPO / "src").rglob("*.py")):
        rel = str(path.relative_to(REPO))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 3
            ):
                continue
            attr = (
                node.args[1].value
                if isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
                else None
            )
            out.add((rel, attr, ast.unparse(node.args[2])))
    return out


def test_only_semantically_optional_getattr_defaults_remain():
    assert _default_getattr_sites() == {
        (
            "src/elpis/contracts/identity.py",
            "TYPE_TAG",
            "type(v).__qualname__",
        ),
        (
            "src/elpis_reference/vendor/fprm/models/"
            "fixed_point_reasoning/model_utils.py",
            "loop_window",
            "0",
        ),
        (
            "src/elpis_reference/vendor/fprm/models/"
            "fixed_point_reasoning/model_utils.py",
            "loop_recency_init",
            "8.0",
        ),
    }


def test_semantic_request_digest_is_structurally_required():
    field = next(
        f
        for f in dataclasses.fields(P0ProjectionTraceV1)
        if f.name == "semantic_request_digest"
    )
    assert field.default is dataclasses.MISSING
    assert field.default_factory is dataclasses.MISSING

    parameter = inspect.signature(
        build_p0_projection_trace
    ).parameters["semantic_request_digest"]
    assert parameter.default is inspect.Parameter.empty


def test_missing_lineage_semantic_request_digest_fails_closed():
    lineage = SimpleNamespace(
        artifact_digest="a" * 64,
        decoder_plan_digest="b" * 64,
        p0_result_digest="c" * 64,
        projection_digest="d" * 64,
        request_id="request",
        structural_proposal_digest="e" * 64,
        validator_code="V",
        validator_evidence_digest="f" * 64,
        validator_id="validator",
        validator_index=0,
    )
    with pytest.raises(AttributeError):
        p0_ingress._lineage_payload(lineage)
