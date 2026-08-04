"""Compilation pipeline — orchestrates adjudication across all rows."""

import json
import os
import hashlib
from .upstream import consume_upstream_seals, file_sha256
from .source_join import load_source_inventories, build_row_map, join_source_row, verify_source_join
from .input_envelope import build_input_envelope, verify_input_envelope
from .policy import adjudicate_row
from .dispositions import build_dispositions_for_row, verify_dispositions
from .abstention import build_abstention_record
from .review_request import build_review_request
from .adjudication import build_adjudication_record
from .semantic_identity import compute_semantic_identity


def compile_row(source_row_digest, rows, source_manifest_sha256):
    """Compile a single row through the full adjudication pipeline.

    Returns:
        dict with all output records for this row
    """
    row_data = join_source_row(source_row_digest, rows)

    # Build input envelope
    envelope = build_input_envelope(row_data, source_manifest_sha256)

    # Run policy
    policy_result = adjudicate_row(row_data, envelope)

    # Build dispositions
    dispositions = build_dispositions_for_row(row_data["proposals"], policy_result)

    # Build abstention
    abstention = build_abstention_record(policy_result)

    # Compute semantic identity
    semantic_digest = compute_semantic_identity(
        dispositions, row_data["conflicts"],
        policy_result["outcome"], policy_result["abstention"],
        policy_result["review_set"], policy_result["request_state"],
        policy_result["reason_codes"],
    )

    # Build adjudication record (placeholder digest for circular reference)
    # We need the record digest for the review request, but the review request
    # is referenced by the record. Break cycle: compute record without review request.
    adjudication = build_adjudication_record(
        envelope, dispositions, policy_result, abstention, semantic_digest
    )

    # Build review request
    review_request = build_review_request(
        envelope, policy_result, adjudication["adjudication_record_digest"]
    )

    return {
        "source_row_digest": source_row_digest,
        "envelope": envelope,
        "dispositions": dispositions,
        "abstention": abstention,
        "adjudication": adjudication,
        "review_request": review_request,
        "semantic_digest": semantic_digest,
    }


def compile_all(rows, source_manifest_sha256, output_dir, progress_callback=None):
    """Compile all rows through the adjudication pipeline.

    Returns:
        dict with all output inventories and audit data
    """
    envelopes = []
    all_dispositions = []
    abstentions = []
    adjudications = []
    review_requests = []
    row_index = []

    sorted_rows = sorted(rows.keys())
    total = len(sorted_rows)

    for i, src in enumerate(sorted_rows):
        if progress_callback and i % 1024 == 0:
            progress_callback(i, total)

        result = compile_row(src, rows, source_manifest_sha256)

        envelopes.append(result["envelope"])
        all_dispositions.extend(result["dispositions"])
        abstentions.append(result["abstention"])
        adjudications.append(result["adjudication"])
        review_requests.append(result["review_request"])

        # Build row adjudication index entry
        row_index.append({
            "source_row_digest": src,
            "source_split": rows[src]["row_index"]["source_split"],
            "input_digest": result["envelope"]["input_digest"],
            "proposal_set_digest": result["envelope"]["proposal_set_digest"],
            "disposition_digests": sorted([d["disposition_digest"] for d in result["dispositions"]]),
            "abstention_digest": result["abstention"]["abstention_digest"],
            "adjudication_record_digest": result["adjudication"]["adjudication_record_digest"],
            "adjudication_semantic_digest": result["semantic_digest"],
            "request_digest": result["review_request"]["request_digest"],
            "outcome": result["adjudication"]["outcome"],
            "request_state": result["review_request"]["request_state"],
            "review_set_proposal_digests": result["adjudication"]["review_set_proposal_digests"],
            "review_set_size": len(result["adjudication"]["review_set_proposal_digests"]),
            "reason_codes": result["adjudication"]["reason_codes"],
        })

    return {
        "envelopes": envelopes,
        "dispositions": all_dispositions,
        "abstentions": abstentions,
        "adjudications": adjudications,
        "review_requests": review_requests,
        "row_index": row_index,
    }


def write_jsonl(records, path):
    """Write records as canonical JSONL with final newline."""
    with open(path, "w") as f:
        for record in records:
            f.write(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")


def write_inventories(compilation, reports_dir):
    """Write all six canonical inventories to reports directory."""
    # Sort by source_row_digest
    compilation["envelopes"].sort(key=lambda e: e["source_row_digest"])
    compilation["dispositions"].sort(key=lambda d: (d.get("_sort_key", ""), d["group_id"], d["proposal_digest"]))
    compilation["abstentions"].sort(key=lambda a: a.get("_sort_key", ""))
    compilation["adjudications"].sort(key=lambda a: a.get("_sort_key", ""))
    compilation["review_requests"].sort(key=lambda r: r.get("_sort_key", ""))
    compilation["row_index"].sort(key=lambda r: r["source_row_digest"])

    # Clean sort keys before writing
    for record_list in [compilation["envelopes"], compilation["dispositions"],
                         compilation["abstentions"], compilation["adjudications"],
                         compilation["review_requests"]]:
        for r in record_list:
            r.pop("_sort_key", None)

    write_jsonl(compilation["envelopes"],
                os.path.join(reports_dir, "G51B_ADJUDICATION_INPUT_INVENTORY.jsonl"))
    write_jsonl(compilation["dispositions"],
                os.path.join(reports_dir, "G51B_PROPOSAL_DISPOSITION_INVENTORY.jsonl"))
    write_jsonl(compilation["abstentions"],
                os.path.join(reports_dir, "G51B_ABSTENTION_INVENTORY.jsonl"))
    write_jsonl(compilation["adjudications"],
                os.path.join(reports_dir, "G51B_ADJUDICATION_RECORD_INVENTORY.jsonl"))
    write_jsonl(compilation["review_requests"],
                os.path.join(reports_dir, "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl"))
    write_jsonl(compilation["row_index"],
                os.path.join(reports_dir, "G51B_ROW_ADJUDICATION_INDEX.jsonl"))


def compute_audit_counts(compilation):
    """Compute canonical counts for audit."""
    counts = {}

    # Disposition counts
    disp_counts = {}
    for d in compilation["dispositions"]:
        disp = d["disposition"]
        disp_counts[disp] = disp_counts.get(disp, 0) + 1
    counts["disposition_counts"] = disp_counts

    # Outcome counts
    outcome_counts = {}
    for a in compilation["adjudications"]:
        outcome = a["outcome"]
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
    counts["outcome_counts"] = outcome_counts

    # Request state counts
    request_counts = {}
    for r in compilation["review_requests"]:
        state = r["request_state"]
        request_counts[state] = request_counts.get(state, 0) + 1
    counts["request_state_counts"] = request_counts

    # Abstention kind counts
    abstention_counts = {}
    for a in compilation["abstentions"]:
        kind = a["abstention_kind"]
        abstention_counts[kind] = abstention_counts.get(kind, 0) + 1
    counts["abstention_kind_counts"] = abstention_counts

    # Review set size counts
    review_set_sizes = {}
    for a in compilation["adjudications"]:
        size = len(a["review_set_proposal_digests"])
        review_set_sizes[size] = review_set_sizes.get(size, 0) + 1
    counts["review_set_size_counts"] = review_set_sizes

    # Reason code counts
    reason_counts = {}
    for a in compilation["adjudications"]:
        for rc in a["reason_codes"]:
            reason_counts[rc] = reason_counts.get(rc, 0) + 1
    counts["reason_code_counts"] = reason_counts

    return counts
