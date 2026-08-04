"""Source chain binding — read-only census and evidence extraction."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .canonical import PhaseEvidence, SourceChain


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def _extract_evidence_files(manifest: dict) -> tuple:
    """Extract sorted evidence file tuples from a manifest."""
    files_raw = manifest.get("evidence_files", {})
    entries = []
    for fname, meta in sorted(files_raw.items()):
        entries.append((fname, meta["sha256"], meta["size"]))
    return tuple(entries)


def _find_disposition(directory: str) -> str:
    """Extract disposition from final report markdown."""
    report = os.path.join(directory, "G53B1_FINAL_REPORT.md")
    if not os.path.exists(report):
        report = os.path.join(directory, "G53B_FINAL_REPORT.md")
    if not os.path.exists(report):
        report = os.path.join(directory, "G53C_FINAL_REPORT.md")
    if not os.path.exists(report):
        report = os.path.join(directory, "G53D_FINAL_REPORT.md")
    if not os.path.exists(report):
        return ""
    with open(report) as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("G53") and "_" in stripped and not stripped.startswith("#"):
                return stripped
    return ""


def census_phase(phase_id: str, source_dir: str, manifest_name: str) -> PhaseEvidence:
    """Census a single phase directory and extract evidence binding."""
    manifest_path = os.path.join(source_dir, manifest_name)
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    manifest = _read_json(manifest_path)
    manifest_digest = _file_sha256(manifest_path)
    evidence_files = _extract_evidence_files(manifest)
    disposition = _find_disposition(source_dir)

    return PhaseEvidence(
        phase_id=phase_id,
        source_directory=source_dir,
        manifest_path=manifest_path,
        manifest_digest=manifest_digest,
        disposition=disposition,
        evidence_files=evidence_files,
    )


def census_g53c(source_dir: str, receipts_path: str, determinism_path: str,
                 authority_path: str, nonmutation_path: str,
                 post_qual_path: str) -> PhaseEvidence:
    """Enrich G5.3C census with receipt, state, and ledger digests."""
    pe = census_phase("G5.3C", source_dir, "RAW_EVIDENCE_MANIFEST.json")

    # Extract receipt digests
    receipts = []
    with open(receipts_path) as f:
        for line in f:
            line = line.strip()
            if line:
                receipt = json.loads(line)
                receipts.append(receipt)

    if receipts:
        last = receipts[-1]
        # Collect all artifact/capability digests
        artifact_digests = tuple(r["artifact_digest"] for r in receipts)
        capability_digests = tuple(r["capability_digest"] for r in receipts)
        shadow_receipt_digest = _receipt_chain_digest(receipts)
        resulting_state_digest = last["resulting_state_digest"]
        resulting_ledger_head = last["resulting_ledger_head"]
    else:
        artifact_digests = ()
        capability_digests = ()
        shadow_receipt_digest = ""
        resulting_state_digest = ""
        resulting_ledger_head = ""

    # Determinism evidence
    det = _read_json(determinism_path)
    determinism_digest = det.get("results", {}).get("0", {}).get("receipt_digest", "")

    # Authority evidence
    auth = _read_json(authority_path)

    # Lifecycle state from post-qualification
    pq = _read_json(post_qual_path)
    lifecycle = pq.get("canonical_lifecycle", "")

    return PhaseEvidence(
        phase_id="G5.3C",
        source_directory=source_dir,
        manifest_path=pe.manifest_path,
        manifest_digest=pe.manifest_digest,
        disposition=pe.disposition,
        evidence_files=pe.evidence_files,
        artifact_digest=":".join(sorted(artifact_digests)),
        capability_digest=":".join(sorted(capability_digests)),
        lifecycle_state=lifecycle,
        shadow_receipt_digest=shadow_receipt_digest,
        resulting_state_digest=resulting_state_digest,
        resulting_ledger_head=resulting_ledger_head,
        bundle_digest=determinism_digest,
    )


def census_g53d(source_dir: str) -> PhaseEvidence:
    """Enrich G5.3D census with bundle digest and binding info."""
    pe = census_phase("G5.3D", source_dir, "RAW_EVIDENCE_MANIFEST.json")

    post_qual = os.path.join(source_dir, "G53D_POST_QUALIFICATION_VERIFICATION.json")
    if os.path.exists(post_qual):
        pq = _read_json(post_qual)
        bundle_digest = pq.get("bundle_digest", "")
    else:
        bundle_digest = ""

    return PhaseEvidence(
        phase_id="G5.3D",
        source_directory=source_dir,
        manifest_path=pe.manifest_path,
        manifest_digest=pe.manifest_digest,
        disposition=pe.disposition,
        evidence_files=pe.evidence_files,
        bundle_digest=bundle_digest,
    )


def census_g53b1(source_dir: str) -> PhaseEvidence:
    """Census G5.3B.1 phase."""
    pe = census_phase("G5.3B.1", source_dir, "G53B_RAW_EVIDENCE_MANIFEST.json")
    return pe


def _receipt_chain_digest(receipts: list) -> str:
    """Compute deterministic digest of a receipt chain."""
    chain = json.dumps(receipts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(chain.encode("utf-8")).hexdigest()


def build_source_chain(config: dict) -> SourceChain:
    """Build a complete source chain from a configuration dict."""
    g53b1_dir = config["g53b1_directory"]
    g53c_dir = config["g53c_directory"]
    g53d_dir = config["g53d_directory"]

    g53b1 = census_g53b1(g53b1_dir)

    g53c_receipts = os.path.join(g53c_dir, "G53C_APPLICATION_RECEIPTS.jsonl")
    g53c_determinism = os.path.join(g53c_dir, "G53C_THREE_SEED_DETERMINISM.json")
    g53c_authority = os.path.join(g53c_dir, "G53C_AUTHORITY_AUDIT.json")
    g53c_nonmutation = os.path.join(g53c_dir, "G53C_CANONICAL_NONMUTATION_AUDIT.json")
    g53c_post_qual = os.path.join(g53c_dir, "G53C_POST_QUALIFICATION_VERIFICATION.json")

    g53c = census_g53c(g53c_dir, g53c_receipts, g53c_determinism,
                       g53c_authority, g53c_nonmutation, g53c_post_qual)

    g53d = census_g53d(g53d_dir)

    return SourceChain(g53b1=g53b1, g53c=g53c, g53d=g53d)
