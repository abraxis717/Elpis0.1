"""G5.3C Ledger chain integrity tests."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_application_executor.ledger import ApplicationLedger
from elpis_grid81_application_executor.canonical import canonical_digest


class TestLedger:
    def test_empty_ledger(self):
        ledger = ApplicationLedger()
        assert ledger.is_empty
        assert not ledger.has_receipt("anything")

    def test_append_and_verify(self):
        ledger = ApplicationLedger()
        head = ledger.head
        entry = ledger.append(head, canonical_digest({"receipt": 1}))
        assert not ledger.is_empty
        assert ledger.head != head
        ok, status = ledger.verify_chain()
        assert ok
        assert status == "valid"

    def test_chain_corruption_detected(self):
        ledger = ApplicationLedger()
        head = ledger.head
        entry1 = ledger.append(head, canonical_digest({"receipt": 1}))
        # Tamper with entry
        ledger._entries[0]["entry_digest"] = "tampered"
        ok, status = ledger.verify_chain()
        assert not ok

    def test_stale_head_rejected(self):
        ledger = ApplicationLedger()
        head = ledger.head
        ledger.append(head, canonical_digest({"receipt": 1}))
        with pytest.raises(ValueError, match="Stale"):
            ledger.append(head, canonical_digest({"receipt": 2}))

    def test_multiple_entries(self):
        ledger = ApplicationLedger()
        for i in range(5):
            head = ledger.head
            ledger.append(head, canonical_digest({"receipt": i}))
        ok, status = ledger.verify_chain()
        assert ok
        assert status == "valid"

    def test_has_receipt(self):
        ledger = ApplicationLedger()
        assert not ledger.has_receipt("artifact123")
        ledger.append(ledger.head, canonical_digest({"r": 1}), artifact_digest="artifact123")
        assert ledger.has_receipt("artifact123")
