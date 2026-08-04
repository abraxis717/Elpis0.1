"""Test authority boundary conditions."""

import os
import sys

BASE = os.environ.get("ELPIS_BASE", "$ELPIS_CANON_ROOT/Elpis_Canon")
sys.path.insert(0, os.path.join(BASE, "Grid81DeterministicStructuralAdjudicator", "src"))

from elpis_grid81_adjudication.source_join import load_jsonl


FORBIDDEN_IMPORTS = [
    "torch", "transformers", "subprocess", "CUDA", "llama.cpp",
    "scheduler", "router", "capability_issuer", "capability_consumer",
]

FORBIDDEN_FIELDS = [
    "capability_token", "authority_token", "model_path", "adapter_path",
    "device", "port", "command", "runtime", "selected", "activation",
    "score", "confidence", "threshold", "priority", "lifecycle_eligible",
]


class TestForbiddenImports:
    def test_no_forbidden_imports_in_source(self):
        src_dir = os.path.join(BASE, "Grid81DeterministicStructuralAdjudicator", "src")
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fname in files:
                if fname.endswith(".py"):
                    fpath = os.path.join(root, fname)
                    with open(fpath) as f:
                        content = f.read()
                    for imp in FORBIDDEN_IMPORTS:
                        assert f"import {imp}" not in content, f"Forbidden import '{imp}' in {fpath}"


class TestForbiddenPaths:
    FORBIDDEN_PATHS = ["activation", "runtime", "router", "scheduler",
                       "model_loader", "adapter_loader", "capability_issuer", "capability_consumer"]

    def test_no_forbidden_directories(self):
        package = os.path.join(BASE, "Grid81DeterministicStructuralAdjudicator")
        for forbidden in self.FORBIDDEN_PATHS:
            path = os.path.join(package, forbidden)
            assert not os.path.exists(path), f"Forbidden directory exists: {path}"


class TestRequestNotCapability:
    def test_review_requests_no_capability_fields(self):
        reports = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator")
        rr_path = os.path.join(reports, "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl")
        if not os.path.exists(rr_path):
            return
        records = load_jsonl(rr_path)
        for r in records:
            for field in FORBIDDEN_FIELDS:
                assert field not in r, f"Forbidden field '{field}' in review request"
            assert r["required_capability_class"] == "STRUCTURAL_INFLUENCE_CAPABILITY_V1"
            assert len(r["claims_not_made"]) > 0


class TestAdjudicationAuthority:
    def test_adjudication_records_claims_not_made(self):
        reports = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator")
        adj_path = os.path.join(reports, "G51B_ADJUDICATION_RECORD_INVENTORY.jsonl")
        if not os.path.exists(adj_path):
            return
        records = load_jsonl(adj_path)
        for r in records:
            claims = r.get("claims_not_made", [])
            assert len(claims) > 0
            for field in FORBIDDEN_FIELDS:
                assert field not in r, f"Forbidden field '{field}' in adjudication record"
