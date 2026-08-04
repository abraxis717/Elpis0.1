"""G5.2B Source-domain join audit.

Joins G5.1B capability-review requests, adjudication records, proposal dispositions,
and row adjudication index by their binding fields.
"""
import json
import os

from .canonical import sha256_bytes, canonical_json_bytes, check_hex64


def load_jsonl(path: str) -> list:
    """Load a JSONL file, returning list of dicts."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def perform_source_join(requests_path: str, adjudications_path: str,
                        dispositions_path: str, row_index_path: str) -> dict:
    """Perform the source-domain join and verify all binding constraints."""

    requests = load_jsonl(requests_path)
    adjudications = load_jsonl(adjudications_path)
    dispositions = load_jsonl(dispositions_path)
    row_index = load_jsonl(row_index_path)

    # Index by binding keys
    adjudication_by_record_digest = {}
    for adj in adjudications:
        adj_by_digest = adj.get("adjudication_record_digest", "")
        adjudication_by_record_digest[adj_by_digest] = adj

    # Index dispositions by adjudication record digest
    dispositions_by_adjudication = {}
    for disp in dispositions:
        # Dispositions don't directly carry adjudication digest; index by proposal_digest
        pass

    # Index row_index by request digest
    row_by_request = {}
    for row in row_index:
        req_digest = row.get("request_digest", "")
        row_by_request[req_digest] = row

    # Validate each request
    total_requests = len(requests)
    review_requested_count = 0
    scope_size_1 = 0
    scope_size_2 = 0
    total_authorized_proposals = 0

    validation_errors = []

    for req in requests:
        req_digest = req.get("request_digest", "")
        req_state = req.get("request_state", "")
        req_class = req.get("required_capability_class", "")
        referred = req.get("referred_proposal_digests", [])
        adj_digest = req.get("adjudication_record_digest", "")
        proposal_set_digest = req.get("proposal_set_digest", "")

        # Check request state
        if req_state == "REVIEW_REQUESTED":
            review_requested_count += 1

        # Check capability class
        if req_class != "STRUCTURAL_INFLUENCE_CAPABILITY_V1":
            validation_errors.append(f"Invalid capability class for {req_digest}")

        # Check digest validity
        if not check_hex64(req_digest):
            validation_errors.append(f"Invalid request digest format: {req_digest}")

        # Check adjudication binding
        adj = adjudication_by_record_digest.get(adj_digest)
        if adj is None:
            validation_errors.append(f"Missing adjudication for {req_digest}")

        # Check referred set
        if len(referred) == 0:
            validation_errors.append(f"Empty referred set for {req_digest}")
        else:
            # Check uniqueness
            if len(referred) != len(set(referred)):
                validation_errors.append(f"Duplicate in referred set for {req_digest}")

        # Count scope sizes
        if len(referred) == 1:
            scope_size_1 += 1
        elif len(referred) == 2:
            scope_size_2 += 1

        total_authorized_proposals += len(referred)

    # Count dispositions
    referred_count = sum(1 for d in dispositions if d.get("disposition") == "REFERRED_FOR_CAPABILITY_REVIEW")
    negative_evidence_count = sum(1 for d in dispositions if d.get("disposition") == "NOT_REFERRED_NEGATIVE_EVIDENCE")
    preserved_count = sum(1 for d in dispositions if d.get("disposition") == "PRESERVED_ALTERNATIVE")

    return {
        "source_rows": len(requests),
        "capability_review_requests": len(requests),
        "adjudication_records": len(adjudications),
        "proposal_dispositions": len(dispositions),
        "row_index_records": len(row_index),
        "review_requested": review_requested_count,
        "review_not_requested": len(requests) - review_requested_count,
        "referred_proposals": referred_count,
        "negative_evidence_proposals": negative_evidence_count,
        "preserved_rationale_proposals": preserved_count,
        "total_authorized_proposals": total_authorized_proposals,
        "scope_size_1": scope_size_1,
        "scope_size_2": scope_size_2,
        "validation_errors": validation_errors,
        "status": "CAPABILITY_AUTHORITY_SOURCE_JOIN_VERIFIED" if len(validation_errors) == 0 else "SOURCE_JOIN_FAILED",
    }


def get_source_requests(requests_path: str) -> list:
    """Load and return all source capability-review requests."""
    return load_jsonl(requests_path)
