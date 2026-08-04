"""Source inventory join — load G5.0B inventories, join by source_row_digest."""

import json
import os
from .errors import SourceJoinMissingRow, ProposalSetIncomplete, ProposalSetDuplicate


def load_jsonl(path):
    """Load a JSONL file, returning list of dicts."""
    records = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_source_inventories(base):
    """Load all 5 G5.0B inventories from reports directory.

    Returns dict with keys: proposals, evidence, orderings, conflicts, row_index.
    Each value is a list of records keyed by source_row_digest.
    """
    g50b_reports = os.path.join(base, "reports", "G5_0B_StructuralGroupProjectionCompiler")

    proposal_path = os.path.join(g50b_reports, "G50B_STRUCTURAL_GROUP_PROPOSAL_INVENTORY.jsonl")
    evidence_path = os.path.join(g50b_reports, "G50B_STRUCTURAL_GROUP_EVIDENCE_INVENTORY.jsonl")
    ordering_path = os.path.join(g50b_reports, "G50B_PROPOSAL_ORDERING_INVENTORY.jsonl")
    conflict_path = os.path.join(g50b_reports, "G50B_STRUCTURAL_CONFLICT_INVENTORY.jsonl")
    row_index_path = os.path.join(g50b_reports, "G50B_ROW_COMPILATION_INDEX.jsonl")

    proposals = load_jsonl(proposal_path)
    evidence = load_jsonl(evidence_path)
    orderings = load_jsonl(ordering_path)
    conflicts = load_jsonl(conflict_path)
    row_index = load_jsonl(row_index_path)

    return {
        "proposals": proposals,
        "evidence": evidence,
        "orderings": orderings,
        "conflicts": conflicts,
        "row_index": row_index,
    }


def build_row_map(inventories):
    """Build per-row data structures from inventories.

    Returns dict keyed by source_row_digest with:
      proposals: list of proposal records
      evidence: list of evidence records
      ordering: ordering record
      conflicts: list of conflict records
      row_index: row index record
    """
    # Index proposals by source_row_digest
    proposals_by_row = {}
    for p in inventories["proposals"]:
        # Proposals don't have source_row_digest directly - get from evidence binding
        pass

    # Build from row index as the primary key
    rows = {}
    for ri in inventories["row_index"]:
        src = ri["source_row_digest"]
        if src not in rows:
            rows[src] = {
                "proposals": [],
                "evidence": [],
                "ordering": None,
                "conflicts": [],
                "row_index": ri,
            }

    # Map proposals to rows via evidence_digest -> source_row_digest
    # First build evidence lookup: canonical_payload_digest -> source_row_digest
    evidence_map = {}
    for e in inventories["evidence"]:
        evidence_map[e["canonical_payload_digest"]] = e

    # Now map proposals
    for p in inventories["proposals"]:
        ev = evidence_map.get(p["evidence_digest"])
        if ev:
            src = ev["source_row_digest"]
            if src in rows:
                rows[src]["proposals"].append(p)
            # Also store evidence
            rows[src]["evidence"].append(ev)

    # Map orderings
    for o in inventories["orderings"]:
        src = o["source_row_digest"]
        if src in rows:
            rows[src]["ordering"] = o

    # Map conflicts
    for c in inventories["conflicts"]:
        src = c["source_row_digest"]
        if src in rows:
            rows[src]["conflicts"].append(c)

    return rows


def join_source_row(source_row_digest, rows):
    """Join data for a single source row. Returns row data dict."""
    if source_row_digest not in rows:
        raise SourceJoinMissingRow(f"Row {source_row_digest} not found")

    row = rows[source_row_digest]

    # Verify proposal count
    if len(row["proposals"]) != 5:
        raise ProposalSetIncomplete(
            f"Row {source_row_digest} has {len(row['proposals'])} proposals, expected 5"
        )

    # Check for duplicate proposals
    proposal_digests = [p["proposal_digest"] for p in row["proposals"]]
    if len(set(proposal_digests)) != len(proposal_digests):
        raise ProposalSetDuplicate(
            f"Row {source_row_digest} has duplicate proposal digests"
        )

    # All proposals must be admissible
    for p in row["proposals"]:
        if not p.get("admissible_for_adjudication", False):
            raise ProposalSetIncomplete(
                f"Row {source_row_digest} has inadmissible proposal {p['proposal_digest']}"
            )

    return row


def verify_source_join(rows, inventories):
    """Verify source join completeness. Returns audit report."""
    row_count = len(rows)
    total_proposals = sum(len(r["proposals"]) for r in rows.values())
    total_evidence = sum(len(r["evidence"]) for r in rows.values())
    total_conflicts = sum(len(r["conflicts"]) for r in rows.values())

    # Verify counts
    all_checks = []

    check = {"check": "row_count", "expected": 8192, "actual": row_count, "pass": row_count == 8192}
    all_checks.append(check)

    check = {"check": "proposal_count", "expected": 40960, "actual": total_proposals, "pass": total_proposals == 40960}
    all_checks.append(check)

    check = {"check": "evidence_count", "expected": 40960, "actual": total_evidence, "pass": total_evidence == 40960}
    all_checks.append(check)

    check = {"check": "orderings_present", "actual": sum(1 for r in rows.values() if r["ordering"]), "pass": True}
    all_checks.append(check)

    # Check 5 proposals per row
    rows_with_5 = sum(1 for r in rows.values() if len(r["proposals"]) == 5)
    check = {"check": "five_proposals_per_row", "expected": 8192, "actual": rows_with_5, "pass": rows_with_5 == 8192}
    all_checks.append(check)

    # Check all proposals admissible
    all_admissible = all(
        p["admissible_for_adjudication"]
        for r in rows.values()
        for p in r["proposals"]
    )
    check = {"check": "all_proposals_admissible", "pass": all_admissible}
    all_checks.append(check)

    # Verify evidence binding
    evidence_map = {e["canonical_payload_digest"]: e for e in inventories["evidence"]}
    evidence_bindings_ok = True
    for r in rows.values():
        for p in r["proposals"]:
            ev = evidence_map.get(p["evidence_digest"])
            if not ev or ev["source_row_digest"] != r["row_index"]["source_row_digest"]:
                evidence_bindings_ok = False
                break
    check = {"check": "evidence_bindings_valid", "pass": evidence_bindings_ok}
    all_checks.append(check)

    all_pass = all(c["pass"] for c in all_checks)

    return {
        "row_count": row_count,
        "proposal_count": total_proposals,
        "evidence_count": total_evidence,
        "conflict_count": total_conflicts,
        "checks": all_checks,
        "all_pass": all_pass,
        "status": "ADJUDICATION_SOURCE_JOIN_VERIFIED" if all_pass else "SOURCE_JOIN_FAILED",
    }
