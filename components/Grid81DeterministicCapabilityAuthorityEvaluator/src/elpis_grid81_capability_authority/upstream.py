"""G5.2B Upstream seal verification and cross-seal consumption.

Verifies G5.0A, G5.0B, G5.1A, G5.1B, G5.2A manifests and cross-seal bindings.
"""
import json
import os

from .canonical import sha256_file, sha256_bytes


EXPECTED_DIGESTS = {
    "G5.0A": "2d530cdeb20be915baf86709a5dde5c7b24259b9736d7cb5d69be493464418b3",
    "G5.0B": "e730b35f7a325a0b0ff8610755ad2179c655456351d5f3d5e3c434684dcfc04b",
    "G5.1A": "97eea6cfcbab02342e793efba793e2be749955c80e1d6520bbf79d77128f3392",
    "G5.1B": "e24b6c097507b6b99053c1c0bc76a43101e99f850bd36ac67859de37231186b7",
    "G5.2A": "b681ea6479c112c06ba16c3ff7834db9c75bca69d76a9e8875572bee31b5a842",
}


def verify_manifest(manifest_path: str, phase_label: str, expected_digest: str, expected_count: int) -> dict:
    """Verify a raw evidence manifest: file count, digests, completeness."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Support multiple manifest shapes
    entries = manifest.get("entries", manifest.get("files", manifest.get("evidence_files", [])))
    manifest_dir = os.path.dirname(manifest_path)
    verified = 0
    missing = 0
    mismatches = 0

    for entry in entries:
        filename = entry.get("filename", entry.get("filepath", entry.get("path", "")))
        expected_sha = entry.get("sha256", entry.get("digest", ""))

        if os.path.isabs(filename):
            filepath = filename
        else:
            filepath = os.path.join(manifest_dir, filename)

        if not os.path.isfile(filepath):
            missing += 1
            continue

        actual_sha = sha256_file(filepath)
        if actual_sha != expected_sha:
            mismatches += 1
        else:
            verified += 1

    manifest_bytes = open(manifest_path, "rb").read()
    manifest_digest = sha256_bytes(manifest_bytes)

    return {
        "phase": phase_label,
        "expected_digest": expected_digest,
        "computed_manifest_digest": manifest_digest,
        "digest_matches": manifest_digest == expected_digest,
        "expected_count": expected_count,
        "verified": verified,
        "missing": missing,
        "digest_mismatches": mismatches,
        "status": "VERIFIED" if (verified == expected_count and missing == 0 and mismatches == 0 and manifest_digest == expected_digest) else "FAILED",
    }


def find_upstream_digest(findings: dict, upstream_label: str) -> str:
    """Find the upstream digest in a findings report."""
    key = f"consumed_{upstream_label.lower().replace('.', '')}_manifest_digest"
    if key in findings:
        return findings[key]
    # Try alternate patterns
    for k in findings:
        kl = k.lower()
        if upstream_label.lower().replace('.', '') in kl and 'digest' in kl and 'manifest' in kl:
            return findings[k]
    return ""


def verify_cross_seals(base_dir: str, reports_dir: str) -> dict:
    """Verify cross-seal consistency for all upstream phases."""
    findings_paths = {
        "G5.0A": os.path.join(base_dir, "reports", "G5_0A_StructuralGroupEvidenceContract", "G50A_FINDINGS.json"),
        "G5.0B": os.path.join(base_dir, "reports", "G5_0B_StructuralGroupProjectionCompiler", "G50B_FINDINGS.json"),
        "G5.1A": os.path.join(base_dir, "reports", "G5_1A_StructuralProposalAdjudicationContract", "G51A_FINDINGS.json"),
        "G5.1B": os.path.join(base_dir, "reports", "G5_1B_DeterministicStructuralAdjudicator", "G51B_FINDINGS.json"),
        "G5.2A": os.path.join(base_dir, "reports", "G5_2A_StructuralInfluenceCapabilityAuthorityContract", "G52A_FINDINGS.json"),
    }

    manifest_paths = {
        "G5.0A": os.path.join(base_dir, "reports", "G5_0A_StructuralGroupEvidenceContract", "G50A_RAW_EVIDENCE_MANIFEST.json"),
        "G5.0B": os.path.join(base_dir, "reports", "G5_0B_StructuralGroupProjectionCompiler", "G50B_RAW_EVIDENCE_MANIFEST.json"),
        "G5.1A": os.path.join(base_dir, "reports", "G5_1A_StructuralProposalAdjudicationContract", "G51A_RAW_EVIDENCE_MANIFEST.json"),
        "G5.1B": os.path.join(base_dir, "reports", "G5_1B_DeterministicStructuralAdjudicator", "G51B_RAW_EVIDENCE_MANIFEST.json"),
        "G5.2A": os.path.join(base_dir, "reports", "G5_2A_StructuralInfluenceCapabilityAuthorityContract", "G52A_RAW_EVIDENCE_MANIFEST.json"),
    }

    # Compute independent digests
    independent_digests = {}
    for phase, path in manifest_paths.items():
        independent_digests[phase] = sha256_file(path)

    # Read findings and extract recorded upstream digests
    findings_data = {}
    for phase, path in findings_paths.items():
        if os.path.isfile(path):
            with open(path, "r") as f:
                findings_data[phase] = json.load(f)

    # Expected cross-seal bindings: dependent -> upstream
    expected_bindings = [
        ("G5.0B", "G5.0A"),
        ("G5.1A", "G5.0A"),
        ("G5.1A", "G5.0B"),
        ("G5.1B", "G5.0A"),
        ("G5.1B", "G5.0B"),
        ("G5.1B", "G5.1A"),
        ("G5.2A", "G5.0A"),
        ("G5.2A", "G5.0B"),
        ("G5.2A", "G5.1A"),
        ("G5.2A", "G5.1B"),
    ]

    cross_seal_checks = []
    all_match = True

    for dependent, upstream in expected_bindings:
        dep_findings = findings_data.get(dependent, {})
        recorded = find_upstream_digest(dep_findings, upstream)
        expected = independent_digests.get(upstream, "")
        match = recorded == expected
        if not match:
            all_match = False
        cross_seal_checks.append({
            "dependent": dependent,
            "upstream": upstream,
            "recorded_digest": recorded,
            "independent_digest": expected,
            "match": match,
        })

    # Also verify that each phase's own manifest digest matches expected
    for phase in ["G5.0A", "G5.0B", "G5.1A", "G5.1B", "G5.2A"]:
        computed = independent_digests.get(phase, "")
        if computed != EXPECTED_DIGESTS[phase]:
            all_match = False

    status = "UPSTREAM_G50A_G50B_G51A_G51B_G52A_SEALS_CONSUMED" if all_match else "CROSS_SEAL_CONSUMPTION_MISMATCH"

    return {
        "cross_seal_checks": cross_seal_checks,
        "independent_digests": independent_digests,
        "all_match": all_match,
        "status": status,
    }
