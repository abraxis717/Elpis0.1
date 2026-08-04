"""Test source inventory join."""

import os
import sys

BASE = os.environ.get("ELPIS_BASE", "/mnt/primesauce/Elpis_Canon")
sys.path.insert(0, os.path.join(BASE, "Grid81DeterministicStructuralAdjudicator", "src"))

from elpis_grid81_adjudication.source_join import load_source_inventories, build_row_map, join_source_row, verify_source_join
from elpis_grid81_adjudication.errors import SourceJoinMissingRow


class TestSourceJoin:
    def test_load_inventories(self):
        inv = load_source_inventories(BASE)
        assert len(inv["proposals"]) == 40960
        assert len(inv["evidence"]) == 40960
        assert len(inv["orderings"]) == 8192
        assert len(inv["conflicts"]) == 23500
        assert len(inv["row_index"]) == 8192

    def test_build_row_map(self):
        inv = load_source_inventories(BASE)
        rows = build_row_map(inv)
        assert len(rows) == 8192

    def test_five_proposals_per_row(self):
        inv = load_source_inventories(BASE)
        rows = build_row_map(inv)
        for src, row in rows.items():
            assert len(row["proposals"]) == 5, f"Row {src} has {len(row['proposals'])} proposals"

    def test_all_proposals_admissible(self):
        inv = load_source_inventories(BASE)
        rows = build_row_map(inv)
        for src, row in rows.items():
            for p in row["proposals"]:
                assert p["admissible_for_adjudication"] is True

    def test_join_missing_row(self):
        inv = load_source_inventories(BASE)
        rows = build_row_map(inv)
        try:
            join_source_row("nonexistent_digest", rows)
            assert False, "Should have raised SourceJoinMissingRow"
        except SourceJoinMissingRow:
            pass

    def test_verify_source_join(self):
        inv = load_source_inventories(BASE)
        rows = build_row_map(inv)
        audit = verify_source_join(rows, inv)
        assert audit["status"] == "ADJUDICATION_SOURCE_JOIN_VERIFIED"
        assert audit["all_pass"] is True
        assert audit["row_count"] == 8192
        assert audit["proposal_count"] == 40960
