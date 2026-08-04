"""G5.3C Application ledger with chain integrity.

Each application receipt chains to the previous ledger head.
Tampering with any receipt breaks the chain.
"""
from dataclasses import dataclass
import copy

from .canonical import canonical_digest


@dataclass(frozen=True)
class LedgerEntry:
    """Immutable ledger entry linking to previous head."""
    sequence: int
    previous_head: str
    receipt_digest: str
    entry_digest: str


class ApplicationLedger:
    """Append-only application ledger with chain verification."""

    def __init__(self):
        self._entries: list[dict] = []
        self._applied_artifacts: set[str] = set()  # artifact digests
        self._applied_receipts: set[str] = set()   # receipt digests

    @property
    def head(self) -> str:
        """Current ledger head digest."""
        if not self._entries:
            return canonical_digest({"sequence": 0, "previous_head": "", "receipt_digests": []})
        return self._entries[-1]["entry_digest"]

    @property
    def is_empty(self) -> bool:
        return len(self._entries) == 0

    def has_receipt(self, artifact_digest: str) -> bool:
        """Check if an application receipt already exists for this artifact."""
        return artifact_digest in self._applied_artifacts

    def append(self, previous_head: str, receipt_digest: str,
               artifact_digest: str = "") -> LedgerEntry:
        """Append a new entry and return it.

        Verifies previous_head matches current head (optimistic CAS).
        """
        if previous_head != self.head:
            raise ValueError(
                f"Stale ledger head: expected {self.head[:16]}..., got {previous_head[:16]}..."
            )

        sequence = len(self._entries) + 1
        entry = {
            "sequence": sequence,
            "previous_head": previous_head,
            "receipt_digest": receipt_digest,
        }
        entry["entry_digest"] = canonical_digest(entry)

        self._entries.append(entry)
        self._applied_receipts.add(receipt_digest)
        if artifact_digest:
            self._applied_artifacts.add(artifact_digest)

        return LedgerEntry(
            sequence=sequence,
            previous_head=previous_head,
            receipt_digest=receipt_digest,
            entry_digest=entry["entry_digest"],
        )

    def verify_chain(self) -> tuple[bool, str]:
        """Verify the entire ledger chain integrity."""
        if not self._entries:
            return True, "empty"

        for i, entry in enumerate(self._entries):
            # Verify digest
            expected = canonical_digest({
                "sequence": entry["sequence"],
                "previous_head": entry["previous_head"],
                "receipt_digest": entry["receipt_digest"],
            })
            if expected != entry["entry_digest"]:
                return False, f"digest_mismatch_at_sequence:{entry['sequence']}"

            # Verify chain linkage
            if i > 0:
                if entry["previous_head"] != self._entries[i - 1]["entry_digest"]:
                    return False, f"chain_break_at_sequence:{entry['sequence']}"

        return True, "valid"

    def to_dict(self) -> dict:
        """Serialize ledger for evidence."""
        return {
            "entries": copy.deepcopy(self._entries),
            "head": self.head,
            "count": len(self._entries),
        }


def ledger_head_digest(entries: list[dict]) -> str:
    """Compute ledger head from a list of entry dicts."""
    if not entries:
        return canonical_digest({"sequence": 0, "previous_head": "", "receipt_digests": []})
    return entries[-1]["entry_digest"]
