"""Upstream seal consumption — G5.0A, G5.0B, G5.1A verification."""

import json
import os
import hashlib
from .canonical import file_sha256
from .errors import (
    UpstreamG50ASealMismatch,
    UpstreamG50BSealMismatch,
    UpstreamG51ASealMismatch,
    CrossSealMismatch,
)


def verify_manifest(manifest_path, reports_dir):
    """Verify all files in a manifest against on-disk SHA-256.

    Returns (verified_count, total_count, mismatches, missing).
    """
    with open(manifest_path) as f:
        manifest = json.load(f)

    entries = manifest.get("evidence_files", [])
    verified = 0
    mismatches = []
    missing = []

    for entry in entries:
        filename = entry["filename"]
        expected_sha = entry["sha256"]
        expected_size = entry["byte_size"]
        fpath = os.path.join(reports_dir, filename)

        if not os.path.exists(fpath):
            missing.append(filename)
            continue

        actual_sha = file_sha256(fpath)
        actual_size = os.path.getsize(fpath)

        if actual_sha != expected_sha:
            mismatches.append({
                "filename": filename,
                "expected": expected_sha,
                "actual": actual_sha,
            })
        elif actual_size != expected_size:
            mismatches.append({
                "filename": filename,
                "expected_size": expected_size,
                "actual_size": actual_size,
            })
        else:
            verified += 1

    return verified, len(entries), mismatches, missing


def consume_upstream_seals(base):
    """Consume all three upstream seals. Returns consumption report."""
    g50a_reports = os.path.join(base, "reports", "G5_0A_StructuralGroupEvidenceContract")
    g50b_reports = os.path.join(base, "reports", "G5_0B_StructuralGroupProjectionCompiler")
    g51a_reports = os.path.join(base, "reports", "G5_1A_StructuralProposalAdjudicationContract")

    results = {}

    # G5.0A
    g50a_manifest = os.path.join(g50a_reports, "G50A_RAW_EVIDENCE_MANIFEST.json")
    g50a_verified, g50a_total, g50a_mismatches, g50a_missing = verify_manifest(g50a_manifest, g50a_reports)
    g50a_manifest_digest = file_sha256(g50a_manifest)

    if g50a_mismatches:
        raise UpstreamG50ASealMismatch(f"{len(g50a_mismatches)} digest mismatches in G5.0A")
    if g50a_missing:
        raise UpstreamG50ASealMismatch(f"{len(g50a_missing)} files missing in G5.0A")

    results["g50a"] = {
        "verified": g50a_verified,
        "total": g50a_total,
        "status": "UPSTREAM_G50A_SEAL_CONSUMED",
        "manifest_digest": g50a_manifest_digest,
        "mismatches": 0,
        "missing": 0,
    }

    # G5.0B
    g50b_manifest = os.path.join(g50b_reports, "G50B_RAW_EVIDENCE_MANIFEST.json")
    g50b_verified, g50b_total, g50b_mismatches, g50b_missing = verify_manifest(g50b_manifest, g50b_reports)
    g50b_manifest_digest = file_sha256(g50b_manifest)

    if g50b_mismatches:
        raise UpstreamG50BSealMismatch(f"{len(g50b_mismatches)} digest mismatches in G5.0B")
    if g50b_missing:
        raise UpstreamG50BSealMismatch(f"{len(g50b_missing)} files missing in G5.0B")

    results["g50b"] = {
        "verified": g50b_verified,
        "total": g50b_total,
        "status": "UPSTREAM_G50B_SEAL_CONSUMED",
        "manifest_digest": g50b_manifest_digest,
        "mismatches": 0,
        "missing": 0,
    }

    # G5.1A
    g51a_manifest = os.path.join(g51a_reports, "G51A_RAW_EVIDENCE_MANIFEST.json")
    g51a_verified, g51a_total, g51a_mismatches, g51a_missing = verify_manifest(g51a_manifest, g51a_reports)
    g51a_manifest_digest = file_sha256(g51a_manifest)

    if g51a_mismatches:
        raise UpstreamG51ASealMismatch(f"{len(g51a_mismatches)} digest mismatches in G5.1A")
    if g51a_missing:
        raise UpstreamG51ASealMismatch(f"{len(g51a_missing)} files missing in G5.1A")

    # Verify against expected digest
    expected_g51a_digest = "97eea6cfcbab02342e793efba793e2be749955c80e1d6520bbf79d77128f3392"
    if g51a_manifest_digest != expected_g51a_digest:
        raise UpstreamG51ASealMismatch(
            f"G5.1A manifest digest {g51a_manifest_digest} != expected {expected_g51a_digest}"
        )

    results["g51a"] = {
        "verified": g51a_verified,
        "total": g51a_total,
        "status": "UPSTREAM_G51A_SEAL_CONSUMED",
        "manifest_digest": g51a_manifest_digest,
        "expected_digest": expected_g51a_digest,
        "digest_match": True,
        "mismatches": 0,
        "missing": 0,
    }

    # Cross-seal consistency
    cross_seal = check_cross_seal_consistency(base, g50a_manifest_digest, g50b_manifest_digest, g51a_manifest_digest)

    return {
        "g50a": results["g50a"],
        "g50b": results["g50b"],
        "g51a": results["g51a"],
        "cross_seal": cross_seal,
        "status": "UPSTREAM_G50A_G50B_G51A_SEALS_CONSUMED",
    }


def check_cross_seal_consistency(base, g50a_digest, g50b_digest, g51a_digest):
    """Check cross-seal references between gates."""
    g50b_reports = os.path.join(base, "reports", "G5_0B_StructuralGroupProjectionCompiler")
    g51a_reports = os.path.join(base, "reports", "G5_1A_StructuralProposalAdjudicationContract")

    results = {"checks": [], "all_consistent": True}

    # G5.0B references G4 upstream (not G5.0A directly). G5.1A references both G5.0B and G5.0A.
    # Cross-seal chain: G5.0A -> G5.0B -> G5.1A
    # G5.1A validates G5.0B which validates G5.0A transitively
    g50b_seal = os.path.join(g50b_reports, "G50B_UPSTREAM_SEAL_CONSUMPTION.json")
    if os.path.exists(g50b_seal):
        with open(g50b_seal) as f:
            seal_data = json.load(f)
        # G5.0B may not directly reference G5.0A (it references G4)
        # Check if it has any G5.0A reference
        recorded_g50a = seal_data.get("g50b_recorded_g50a_digest", "")
        if not recorded_g50a:
            recorded_g50a = seal_data.get("g50a", {}).get("manifest_sha256", "")
        if not recorded_g50a:
            recorded_g50a = seal_data.get("g50a", {}).get("manifest_digest", "")
        # If G5.0B doesn't directly reference G5.0A, that's architecturally correct
        # (G5.0B consumes G4; G5.1A bridges G5.0A -> G5.0B -> G5.1A)
        if recorded_g50a:
            check = {
                "check": "G50B_records_G50A_manifest",
                "recorded": recorded_g50a,
                "actual": g50a_digest,
                "consistent": recorded_g50a == g50a_digest,
            }
            results["checks"].append(check)
            if not check["consistent"]:
                results["all_consistent"] = False
        else:
            results["checks"].append({
                "check": "G50B_records_G50A_manifest",
                "recorded": "(none - G5.0B references G4, not G5.0A directly)",
                "actual": g50a_digest,
                "consistent": True,
            })

    # G5.1A should reference G5.0B and G5.0A manifest digests
    g51a_seal = os.path.join(g51a_reports, "G51A_UPSTREAM_SEAL_CONSUMPTION.json")
    if os.path.exists(g51a_seal):
        with open(g51a_seal) as f:
            seal_data = json.load(f)
        # G5.1A seal stores digests as g50b_manifest_sha256, g50a_manifest_sha256
        recorded_g50b = seal_data.get("g50b_manifest_sha256", "")
        recorded_g50a = seal_data.get("g50a_manifest_sha256", "")

        check_b = {
            "check": "G51A_records_G50B_manifest",
            "recorded": recorded_g50b,
            "actual": g50b_digest,
            "consistent": recorded_g50b == g50b_digest,
        }
        results["checks"].append(check_b)
        if not check_b["consistent"]:
            results["all_consistent"] = False

        check_a = {
            "check": "G51A_records_G50A_manifest",
            "recorded": recorded_g50a,
            "actual": g50a_digest,
            "consistent": recorded_g50a == g50a_digest,
        }
        results["checks"].append(check_a)
        if not check_a["consistent"]:
            results["all_consistent"] = False

    return results


def compute_upstream_checksums(base):
    """Compute checksums of all upstream files (excluding __pycache__/*.pyc)."""
    checksums = {}

    upstream_dirs = [
        os.path.join(base, "reports", "G5_0A_StructuralGroupEvidenceContract"),
        os.path.join(base, "Grid81StructuralGroupProjectionCompiler"),
        os.path.join(base, "reports", "G5_0B_StructuralGroupProjectionCompiler"),
        os.path.join(base, "Grid81StructuralAdjudicationContract"),
        os.path.join(base, "reports", "G5_1A_StructuralProposalAdjudicationContract"),
    ]

    for d in upstream_dirs:
        if not os.path.exists(d):
            continue
        for root, dirs, files in os.walk(d):
            dirs[:] = [dd for dd in sorted(dirs) if dd not in ("__pycache__", ".pytest_cache", ".git")]
            for fname in sorted(files):
                if fname.endswith((".pyc", ".pyo")):
                    continue
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, base)
                checksums[rel] = file_sha256(fpath)

    return checksums
