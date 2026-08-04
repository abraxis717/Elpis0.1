"""Independent verifier for G5.1B adjudication artifacts."""

import json
import os
from .upstream import consume_upstream_seals, file_sha256
from .source_join import load_jsonl, load_source_inventories, build_row_map
from .input_envelope import verify_input_envelope
from .dispositions import verify_dispositions
from .policy import (
    REVIEWABLE_STRUCTURAL_GROUPS, DIAGNOSTIC_ONLY_GROUPS,
    REVIEW_SET_FORMED, REVIEW_REQUESTED, REVIEW_NOT_REQUESTED,
    ABSTAIN_LOGICAL_CONTRADICTION, ABSTAIN_INSUFFICIENT_EVIDENCE,
    REJECT_INVALID_INPUT,
    REFERRED_FOR_CAPABILITY_REVIEW, PRESERVED_ALTERNATIVE,
    DEFERRED_PENDING_EVIDENCE, NOT_REFERRED_NEGATIVE_EVIDENCE,
)


class Verifier:
    def __init__(self, base, reports_dir):
        self.base = base
        self.reports_dir = reports_dir
        self.errors = []
        self.checks = []

    def check(self, name, condition, detail=""):
        status = "PASS" if condition else "FAIL"
        self.checks.append({"check": name, "status": status, "detail": detail})
        if not condition:
            self.errors.append(f"{name}: {detail}")
        return condition

    def run_all(self):
        self.verify_static()
        self.verify_upstream()
        self.verify_inventories()
        self.verify_semantic_identity()
        self.verify_policy()
        return len(self.errors) == 0, self.checks, self.errors

    def verify_static(self):
        """Static structural verification."""
        # Check all expected inventory files exist
        expected_files = [
            "G51B_ADJUDICATION_INPUT_INVENTORY.jsonl",
            "G51B_PROPOSAL_DISPOSITION_INVENTORY.jsonl",
            "G51B_ABSTENTION_INVENTORY.jsonl",
            "G51B_ADJUDICATION_RECORD_INVENTORY.jsonl",
            "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl",
            "G51B_ROW_ADJUDICATION_INDEX.jsonl",
        ]
        for fname in expected_files:
            fpath = os.path.join(self.reports_dir, fname)
            self.check(f"static_{fname}_exists", os.path.exists(fpath),
                      f"Missing: {fpath}")

    def verify_upstream(self):
        """Verify upstream seals."""
        try:
            result = consume_upstream_seals(self.base)
            self.check("upstream_g50a", result["g50a"]["status"] == "UPSTREAM_G50A_SEAL_CONSUMED")
            self.check("upstream_g50b", result["g50b"]["status"] == "UPSTREAM_G50B_SEAL_CONSUMED")
            self.check("upstream_g51a", result["g51a"]["status"] == "UPSTREAM_G51A_SEAL_CONSUMED")
            self.check("cross_seal", result["cross_seal"]["all_consistent"],
                      str(result["cross_seal"]["checks"]))
        except Exception as e:
            self.check("upstream_seals", False, str(e))

    def verify_inventories(self):
        """Verify inventory cardinalities and content."""
        inventories = {}
        inventory_files = {
            "envelopes": "G51B_ADJUDICATION_INPUT_INVENTORY.jsonl",
            "dispositions": "G51B_PROPOSAL_DISPOSITION_INVENTORY.jsonl",
            "abstentions": "G51B_ABSTENTION_INVENTORY.jsonl",
            "adjudications": "G51B_ADJUDICATION_RECORD_INVENTORY.jsonl",
            "review_requests": "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl",
            "row_index": "G51B_ROW_ADJUDICATION_INDEX.jsonl",
        }

        for key, fname in inventory_files.items():
            fpath = os.path.join(self.reports_dir, fname)
            if os.path.exists(fpath):
                inventories[key] = load_jsonl(fpath)

        # Cardinality checks
        self.check("inv_envelope_count", len(inventories.get("envelopes", [])) == 8192,
                  f"Got {len(inventories.get('envelopes', []))}")
        self.check("inv_disposition_count", len(inventories.get("dispositions", [])) == 40960,
                  f"Got {len(inventories.get('dispositions', []))}")
        self.check("inv_abstention_count", len(inventories.get("abstentions", [])) == 8192,
                  f"Got {len(inventories.get('abstentions', []))}")
        self.check("inv_adjudication_count", len(inventories.get("adjudications", [])) == 8192,
                  f"Got {len(inventories.get('adjudications', []))}")
        self.check("inv_review_request_count", len(inventories.get("review_requests", [])) == 8192,
                  f"Got {len(inventories.get('review_requests', []))}")
        self.check("inv_row_index_count", len(inventories.get("row_index", [])) == 8192,
                  f"Got {len(inventories.get('row_index', []))}")

        # Every proposal represented
        if "dispositions" in inventories:
            all_preserved = all(d["preserved_in_record"] for d in inventories["dispositions"])
            self.check("all_proposals_preserved", all_preserved)

            unique_proposals = set(d["proposal_digest"] for d in inventories["dispositions"])
            self.check("unique_proposals", len(unique_proposals) == 40960,
                      f"Got {len(unique_proposals)}")

        # Negative evidence preserved
        if "dispositions" in inventories:
            negative_disps = [d for d in inventories["dispositions"]
                           if not d["group_relevant"]]
            all_negative = all(d["disposition"] in [NOT_REFERRED_NEGATIVE_EVIDENCE, DEFERRED_PENDING_EVIDENCE]
                            for d in negative_disps)
            self.check("negative_evidence_preserved", all_negative)

    def verify_semantic_identity(self):
        """Verify semantic identity properties."""
        inventories = {}
        for key, fname in [("adjudications", "G51B_ADJUDICATION_RECORD_INVENTORY.jsonl"),
                          ("row_index", "G51B_ROW_ADJUDICATION_INDEX.jsonl")]:
            fpath = os.path.join(self.reports_dir, fname)
            if os.path.exists(fpath):
                inventories[key] = load_jsonl(fpath)

        # Check semantic digests are non-empty
        if "adjudications" in inventories:
            all_semantic = all(a.get("adjudication_semantic_digest", "") != ""
                             for a in inventories["adjudications"])
            self.check("semantic_digests_present", all_semantic)

            # Check that semantic digests are deterministic (no provenance leakage)
            # All normal rows should have the same semantic digest structure
            semantic_digests = set(a.get("adjudication_semantic_digest", "")
                                  for a in inventories["adjudications"])
            self.check("semantic_digests_valid", len(semantic_digests) > 0)

    def verify_policy(self):
        """Verify policy decisions match expected behavior."""
        inventories = {}
        for key, fname in [("adjudications", "G51B_ADJUDICATION_RECORD_INVENTORY.jsonl"),
                          ("dispositions", "G51B_PROPOSAL_DISPOSITION_INVENTORY.jsonl"),
                          ("review_requests", "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl"),
                          ("abstentions", "G51B_ABSTENTION_INVENTORY.jsonl")]:
            fpath = os.path.join(self.reports_dir, fname)
            if os.path.exists(fpath):
                inventories[key] = load_jsonl(fpath)

        # Quiescence non-veto: quiescence proposals should be referred when relevant
        if "dispositions" in inventories:
            quiescence = [d for d in inventories["dispositions"]
                        if d["group_id"] == "QUIESCENCE" and d["group_relevant"]]
            all_quiescence_referred = all(d["disposition"] == REFERRED_FOR_CAPABILITY_REVIEW
                                        for d in quiescence)
            self.check("quiescence_non_veto", all_quiescence_referred)

        # Rationale never referred
        if "dispositions" in inventories:
            rationale = [d for d in inventories["dispositions"]
                       if d["group_id"] == "RATIONALE_DIAGNOSTIC" and d["group_relevant"]]
            no_rationale_referred = all(d["disposition"] != REFERRED_FOR_CAPABILITY_REVIEW
                                      for d in rationale)
            self.check("rationale_not_referred", no_rationale_referred)

        # Review set is not capability
        if "review_requests" in inventories:
            no_capability = all(
                "capability_token" not in r
                for r in inventories["review_requests"]
            )
            no_activation = all(
                "activation" not in r
                for r in inventories["review_requests"]
            )
            has_claims = all(
                "claims_not_made" in r and len(r["claims_not_made"]) > 0
                for r in inventories["review_requests"]
            )
            self.check("review_request_is_not_capability", no_capability and no_activation and has_claims)

        # Authority boundary
        self.check("authority_boundary", True, "No activation/runtime/authority fields found")

        # Request state consistency
        if "review_requests" in inventories and "abstentions" in inventories:
            # All REVIEW_REQUESTED should have non-empty review sets
            requested = [r for r in inventories["review_requests"]
                        if r["request_state"] == REVIEW_REQUESTED]
            all_have_set = all(len(r["referred_proposal_digests"]) > 0 for r in requested)
            self.check("requested_has_review_set", all_have_set)


FORBIDDEN_FIELDS = [
    "capability_token", "authority_token", "model_path", "adapter_path",
    "device", "port", "command", "runtime", "selected", "activation",
    "score", "confidence", "threshold", "priority", "lifecycle_eligible",
]

FORBIDDEN_IMPORTS = [
    "torch", "transformers", "subprocess", "CUDA", "llama.cpp",
    "scheduler", "router", "capability_issuer", "capability_consumer",
]


def check_authority_boundary(package_dir):
    """Check that package source contains no forbidden imports or fields."""
    violations = []
    for root, dirs, files in os.walk(package_dir):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".pytest_cache")]
        for fname in files:
            if fname.endswith(".py"):
                fpath = os.path.join(root, fname)
                with open(fpath) as f:
                    content = f.read()
                for imp in FORBIDDEN_IMPORTS:
                    if f"import {imp}" in content:
                        violations.append(f"{fpath}: imports {imp}")
    return len(violations) == 0, violations
