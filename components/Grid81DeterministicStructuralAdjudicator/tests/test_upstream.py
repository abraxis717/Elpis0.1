"""Test upstream seal consumption."""

import os
import sys
import json

BASE = os.environ.get("ELPIS_BASE", "$ELPIS_CANON_ROOT/Elpis_Canon")
sys.path.insert(0, os.path.join(BASE, "Grid81DeterministicStructuralAdjudicator", "src"))

from elpis_grid81_adjudication.upstream import consume_upstream_seals, file_sha256


class TestUpstreamSeals:
    def test_g50a_seal(self):
        result = consume_upstream_seals(BASE)
        assert result["g50a"]["status"] == "UPSTREAM_G50A_SEAL_CONSUMED"
        assert result["g50a"]["verified"] == 16
        assert result["g50a"]["total"] == 16
        assert result["g50a"]["mismatches"] == 0
        assert result["g50a"]["missing"] == 0

    def test_g50b_seal(self):
        result = consume_upstream_seals(BASE)
        assert result["g50b"]["status"] == "UPSTREAM_G50B_SEAL_CONSUMED"
        assert result["g50b"]["verified"] == 26
        assert result["g50b"]["total"] == 26
        assert result["g50b"]["mismatches"] == 0
        assert result["g50b"]["missing"] == 0

    def test_g51a_seal(self):
        result = consume_upstream_seals(BASE)
        assert result["g51a"]["status"] == "UPSTREAM_G51A_SEAL_CONSUMED"
        assert result["g51a"]["verified"] == 21
        assert result["g51a"]["total"] == 21
        assert result["g51a"]["mismatches"] == 0
        assert result["g51a"]["missing"] == 0

    def test_g51a_expected_digest(self):
        result = consume_upstream_seals(BASE)
        expected = "97eea6cfcbab02342e793efba793e2be749955c80e1d6520bbf79d77128f3392"
        assert result["g51a"]["manifest_digest"] == expected

    def test_cross_seal_consistency(self):
        result = consume_upstream_seals(BASE)
        assert result["cross_seal"]["all_consistent"] is True

    def test_overall_status(self):
        result = consume_upstream_seals(BASE)
        assert result["status"] == "UPSTREAM_G50A_G50B_G51A_SEALS_CONSUMED"

    def test_manifest_file_digests(self):
        g50a_path = os.path.join(BASE, "reports", "G5_0A_StructuralGroupEvidenceContract", "G50A_RAW_EVIDENCE_MANIFEST.json")
        g50b_path = os.path.join(BASE, "reports", "G5_0B_StructuralGroupProjectionCompiler", "G50B_RAW_EVIDENCE_MANIFEST.json")
        g51a_path = os.path.join(BASE, "reports", "G5_1A_StructuralProposalAdjudicationContract", "G51A_RAW_EVIDENCE_MANIFEST.json")

        assert os.path.exists(g50a_path)
        assert os.path.exists(g50b_path)
        assert os.path.exists(g51a_path)

        assert len(file_sha256(g50a_path)) == 64
        assert len(file_sha256(g50b_path)) == 64
        assert len(file_sha256(g51a_path)) == 64
