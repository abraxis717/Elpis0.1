"""ProposalDispositionV1 — disposition record construction."""

from .canonical import canonical_digest
from .policy import (
    REFERRED_FOR_CAPABILITY_REVIEW,
    PRESERVED_ALTERNATIVE,
    DEFERRED_PENDING_EVIDENCE,
    NOT_REFERRED_NEGATIVE_EVIDENCE,
    REJECTED_CONTRACT_INVALID,
)


def build_disposition_record(p, policy_disposition):
    """Build a ProposalDispositionV1 record for a single proposal.

    Args:
        p: proposal record from source inventory
        policy_disposition: disposition dict from policy adjudication

    Returns:
        ProposalDispositionV1 dict
    """
    record = {
        "schema_version": "proposal-disposition.v1",
        "proposal_digest": p["proposal_digest"],
        "group_id": policy_disposition["group_id"],
        "group_relevant": policy_disposition["group_relevant"],
        "disposition": policy_disposition["disposition"],
        "reason_codes": policy_disposition["reason_codes"],
        "preserved_in_record": True,
    }

    # Compute digest from record without digest field
    disposition_digest = canonical_digest(record)
    record["disposition_digest"] = disposition_digest

    return record


def build_dispositions_for_row(proposals, policy_result):
    """Build all disposition records for a row.

    Returns list of ProposalDispositionV1 dicts, ordered by group_id, proposal_digest.
    """
    # Map policy dispositions by proposal_digest
    policy_map = {d["proposal_digest"]: d for d in policy_result["dispositions"]}

    dispositions = []
    for p in proposals:
        pd = policy_map.get(p["proposal_digest"])
        if pd is None:
            raise ValueError(f"Missing policy disposition for proposal {p['proposal_digest']}")
        dispositions.append(build_disposition_record(p, pd))

    # Sort canonically: group_id, proposal_digest
    dispositions.sort(key=lambda d: (d["group_id"], d["proposal_digest"]))

    return dispositions


def verify_dispositions(dispositions, proposals):
    """Verify disposition ledger completeness and correctness."""
    errors = []

    # Check count matches proposal count
    if len(dispositions) != len(proposals):
        errors.append(f"Disposition count {len(dispositions)} != proposal count {len(proposals)}")

    # Check every proposal has exactly one disposition
    proposal_digests_in = set(p["proposal_digest"] for p in proposals)
    proposal_digests_out = set(d["proposal_digest"] for d in dispositions)

    if proposal_digests_in != proposal_digests_out:
        missing = proposal_digests_in - proposal_digests_out
        extra = proposal_digests_out - proposal_digests_in
        if missing:
            errors.append(f"Missing dispositions for: {missing}")
        if extra:
            errors.append(f"Extra dispositions for: {extra}")

    # Check for duplicates
    if len(dispositions) != len(proposal_digests_out):
        errors.append("Duplicate proposal digests in dispositions")

    # Check preserved_in_record is always True
    for d in dispositions:
        if d["preserved_in_record"] is not True:
            errors.append(f"preserved_in_record not True for {d['proposal_digest']}")

    # Check disposition digest
    for d in dispositions:
        d_copy = {k: v for k, v in d.items() if k != "disposition_digest"}
        expected = canonical_digest(d_copy)
        if d["disposition_digest"] != expected:
            errors.append(f"disposition_digest mismatch for {d['proposal_digest']}")

    return len(errors) == 0, errors
