"""Tests for upstream seal verification."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_capability_authority.upstream import verify_manifest, EXPECTED_DIGESTS

BASE = os.path.join(os.path.dirname(__file__), "..", "..")


@pytest.mark.skip(reason="Upstream seal verification requires full evidence report trees (excluded from promotion)")
def test_g50a_manifest_verified():
    path = os.path.join(BASE, "reports", "G5_0A_StructuralGroupEvidenceContract", "G50A_RAW_EVIDENCE_MANIFEST.json")
    result = verify_manifest(path, "G5.0A", EXPECTED_DIGESTS["G5.0A"], 16)
    assert result["status"] == "VERIFIED"
    assert result["verified"] == 16
    assert result["missing"] == 0
    assert result["digest_mismatches"] == 0


@pytest.mark.skip(reason="Upstream seal verification requires full evidence report trees (excluded from promotion)")
def test_g50b_manifest_verified():
    path = os.path.join(BASE, "reports", "G5_0B_StructuralGroupProjectionCompiler", "G50B_RAW_EVIDENCE_MANIFEST.json")
    result = verify_manifest(path, "G5.0B", EXPECTED_DIGESTS["G5.0B"], 26)
    assert result["status"] == "VERIFIED"
    assert result["verified"] == 26
    assert result["missing"] == 0
    assert result["digest_mismatches"] == 0


@pytest.mark.skip(reason="Upstream seal verification requires full evidence report trees (excluded from promotion)")
def test_g51a_manifest_verified():
    path = os.path.join(BASE, "reports", "G5_1A_StructuralProposalAdjudicationContract", "G51A_RAW_EVIDENCE_MANIFEST.json")
    result = verify_manifest(path, "G5.1A", EXPECTED_DIGESTS["G5.1A"], 21)
    assert result["status"] == "VERIFIED"
    assert result["verified"] == 21
    assert result["missing"] == 0


@pytest.mark.skip(reason="Upstream seal verification requires full evidence report trees (excluded from promotion)")
def test_g51b_manifest_verified():
    path = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator", "G51B_RAW_EVIDENCE_MANIFEST.json")
    result = verify_manifest(path, "G5.1B", EXPECTED_DIGESTS["G5.1B"], 32)
    assert result["status"] == "VERIFIED"
    assert result["verified"] == 32
    assert result["missing"] == 0


@pytest.mark.skip(reason="Upstream seal verification requires full evidence report trees (excluded from promotion)")
def test_g52a_manifest_verified():
    path = os.path.join(BASE, "reports", "G5_2A_StructuralInfluenceCapabilityAuthorityContract", "G52A_RAW_EVIDENCE_MANIFEST.json")
    result = verify_manifest(path, "G5.2A", EXPECTED_DIGESTS["G5.2A"], 24)
    assert result["status"] == "VERIFIED"
    assert result["verified"] == 24
    assert result["missing"] == 0


def test_expected_digests_complete():
    assert len(EXPECTED_DIGESTS) == 5
    for phase in ["G5.0A", "G5.0B", "G5.1A", "G5.1B", "G5.2A"]:
        assert phase in EXPECTED_DIGESTS
        assert len(EXPECTED_DIGESTS[phase]) == 64
