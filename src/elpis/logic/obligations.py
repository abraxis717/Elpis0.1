"""L0 Obligation runtime ledger — thin mutable wrapper over C1.

Delegates certification to C1 certify_obligations().
"""
from __future__ import annotations

from threading import RLock

from elpis.contracts.closure import (
    ObligationCertificate,
    ObligationEvidence,
    ObligationManifest,
    ObligationRequirement,
    certify_obligations,
)

from .errors import ObligationLedgerError


class ObligationLedger:
    """Process-local obligation ledger.

    Mutable until successful certification, then frozen.
    """

    def __init__(self, *, manifest: ObligationManifest) -> None:
        self._manifest = manifest
        self._lock = RLock()
        self._evidence: dict[str, ObligationEvidence] = {}
        self._certified = False
        self._certificate: ObligationCertificate | None = None
        self._declared_ids = {
            req.obligation_id for req in manifest.requirements
        }
        self._required_ids = {
            req.obligation_id
            for req in manifest.requirements
            if req.required
        }

    def record(self, evidence: ObligationEvidence) -> None:
        with self._lock:
            if self._certified:
                raise ObligationLedgerError("ledger is certified and frozen")

            if evidence.obligation_id not in self._declared_ids:
                raise ObligationLedgerError(
                    f"undeclared obligation ID: {evidence.obligation_id!r}"
                )

            if evidence.obligation_id in self._evidence:
                raise ObligationLedgerError(
                    f"duplicate evidence for: {evidence.obligation_id!r}"
                )

            self._evidence[evidence.obligation_id] = evidence

    def certify(self) -> ObligationCertificate:
        with self._lock:
            if self._certified:
                raise ObligationLedgerError("ledger already certified")

            evidence_tuple = tuple(self._evidence.values())
            try:
                certificate = certify_obligations(
                    self._manifest, evidence_tuple
                )
            except Exception:
                raise

            self._certified = True
            self._certificate = certificate
            return certificate

    @property
    def certified(self) -> bool:
        return self._certified

    @property
    def certificate(self) -> ObligationCertificate | None:
        return self._certificate

    @property
    def manifest(self) -> ObligationManifest:
        return self._manifest

    @property
    def evidence_count(self) -> int:
        return len(self._evidence)
