"""L0 Authority registry — explicit process-local capability registry.

Rules:
  - explicit instance, never module-global
  - RLock protected
  - creator PID checked
  - process nonce checked
  - exact scope binding
  - disjoint live/consumed/revoked sets
  - rejected scope/retention consumes leave state unchanged
  - copying a handle does not copy authority
  - pickling raises TypeError
  - receipt is evidence only
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from dataclasses import asdict, dataclass
from threading import RLock
from typing import TYPE_CHECKING

from elpis.contracts.closure import AuthorityReceipt, canonical_json_bytes

from .errors import (
    AccountWrongPid,
    CapabilityConsumed,
    CapabilityForgery,
    ReceiptRetentionExhausted,
)


@dataclass(frozen=True, slots=True)
class AuthorityCapability:
    issuer_id: str
    capability_id: str
    request_id: str
    process_nonce: str
    creator_pid: int
    issue_sequence: int

    def __reduce__(self) -> object:
        raise TypeError("AuthorityCapability cannot be pickled")

    def __copy__(self) -> "AuthorityCapability":
        # Frozen dataclass with slots: copy returns self (immutable)
        return self

    def __deepcopy__(self, memo: dict | None = None) -> "AuthorityCapability":
        raise TypeError("AuthorityCapability cannot be deep-copied")

    def __reduce_ex__(self, protocol: int) -> object:
        raise TypeError("AuthorityCapability cannot be pickled")


@dataclass(frozen=True, slots=True)
class CapabilityRegistrySnapshot:
    issuer_id: str
    live_capabilities: tuple[str, ...]
    consumed_capabilities: tuple[str, ...]
    revoked_capabilities: tuple[str, ...]
    consume_sequence: int
    creator_pid: int


class CapabilityRegistry:
    """Explicit process-local authority capability registry."""

    def __init__(self, *, issuer_id: str, retention_limit: int = 4096) -> None:
        if not issuer_id:
            raise ValueError("issuer_id must be non-empty")
        if type(retention_limit) is not int or retention_limit < 1:
            raise ValueError("retention_limit must be a positive integer")
        self._retention_limit = retention_limit
        self._verification_payloads: dict[int, bytes] = {}
        self.issuer_id = issuer_id
        self._secret = secrets.token_bytes(32)
        self._process_nonce = secrets.token_urlsafe(32)
        self._creator_pid = os.getpid()
        self._consume_sequence = 0
        self._live: set[str] = set()
        self._consumed: set[str] = set()
        self._revoked: set[str] = set()
        self._capability_meta: dict[str, dict] = {}
        self._lock = RLock()

    def _check_pid(self) -> None:
        if os.getpid() != self._creator_pid:
            raise AccountWrongPid(
                f"registry created in PID {self._creator_pid}, "
                f"called from PID {os.getpid()}"
            )

    def _signing_payload(
        self,
        *,
        issuer_id: str,
        request_id: str,
        scope: str,
        capability_id: str,
        capability: AuthorityCapability,
        process_nonce: str,
        creator_pid: int,
        issue_sequence: int,
        consume_sequence: int,
        receipt_nonce: str,
    ) -> bytes:
        payload = {
            "issuer_id": issuer_id,
            "request_id": request_id,
            "scope": scope,
            "capability_id": capability_id,
            "capability_issuer_id": capability.issuer_id,
            "capability_request_id": capability.request_id,
            "capability_process_nonce": capability.process_nonce,
            "capability_creator_pid": capability.creator_pid,
            "capability_issue_sequence": capability.issue_sequence,
            "consume_sequence": consume_sequence,
            "receipt_nonce": receipt_nonce,
            "process_nonce": process_nonce,
            "creator_pid": creator_pid,
            "issue_sequence": issue_sequence,
        }
        return canonical_json_bytes(payload)

    def _sign_payload(self, payload: bytes) -> str:
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def verify(self, receipt: AuthorityReceipt) -> bool:
        """Verify within this process and retained episode only.

        No third-party, cross-process, or asymmetric verification is provided.
        """
        self._check_pid()
        if type(receipt) is not AuthorityReceipt:
            return False
        with self._lock:
            payload = self._verification_payloads.get(receipt.sequence)
            if payload is None:
                return False
            import json
            signed = json.loads(payload)
            if (receipt.issuer_id, receipt.request_id, receipt.scope,
                    receipt.nonce, receipt.sequence) != (
                    signed["issuer_id"], signed["request_id"], signed["scope"],
                    signed["receipt_nonce"], signed["consume_sequence"]):
                return False
            return isinstance(receipt.signature, str) and hmac.compare_digest(
                self._sign_payload(payload), receipt.signature
            )

    def end_episode(self) -> int:
        """Close the verification window; capability lifecycle remains intact."""
        self._check_pid()
        with self._lock:
            count = len(self._verification_payloads)
            self._verification_payloads.clear()
            return count

    def state_digest(self) -> str:
        """Digest registry data, including metadata, counters, and key identity.

        Synchronization machinery (the lock) is excluded.
        """
        self._check_pid()
        with self._lock:
            state = {
                "issuer_id": self.issuer_id,
                "secret_digest": hashlib.sha256(self._secret).hexdigest(),
                "process_nonce": self._process_nonce,
                "creator_pid": self._creator_pid,
                "consume_sequence": self._consume_sequence,
                "retention_limit": self._retention_limit,
                "live": sorted(self._live),
                "consumed": sorted(self._consumed),
                "revoked": sorted(self._revoked),
                "metadata": {
                    key: {name: asdict(value) if isinstance(value, AuthorityCapability)
                          else value for name, value in meta.items()}
                    for key, meta in self._capability_meta.items()
                },
                "verification_payloads": {
                    str(key): value.hex()
                    for key, value in self._verification_payloads.items()
                },
            }
            return hashlib.sha256(canonical_json_bytes(state)).hexdigest()

    def issue(
        self,
        *,
        request_id: str,
        scope: str,
    ) -> AuthorityCapability:
        self._check_pid()
        if not request_id:
            raise ValueError("request_id must be non-empty")

        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("scope must be explicit and non-empty")

        with self._lock:
            capability_id = f"cap_{uuid.uuid4().hex}"
            cap = AuthorityCapability(
                issuer_id=self.issuer_id,
                capability_id=capability_id,
                request_id=request_id,
                process_nonce=self._process_nonce,
                creator_pid=self._creator_pid,
                issue_sequence=len(self._live) + len(self._consumed) + len(self._revoked),
            )
            self._live.add(capability_id)
            self._capability_meta[capability_id] = {
                "request_id": request_id,
                "scope": scope,
                "capability": cap,
            }
            return cap

    def consume(
        self,
        capability: AuthorityCapability,
        *,
        request_id: str,
        required_scope: str,
    ) -> AuthorityReceipt:
        self._check_pid()
        if not request_id:
            raise ValueError("request_id must be non-empty")
        if not required_scope:
            raise ValueError("required_scope must be non-empty")

        if type(capability) is not AuthorityCapability:
            raise CapabilityForgery("expected AuthorityCapability")

        cap_id = capability.capability_id

        with self._lock:
            if capability.issuer_id != self.issuer_id:
                raise CapabilityForgery("unknown authority issuer")
            if capability.process_nonce != self._process_nonce:
                raise CapabilityForgery("process nonce mismatch")
            if capability.creator_pid != self._creator_pid:
                raise CapabilityForgery("creator PID mismatch")
            if capability.request_id != request_id:
                raise CapabilityForgery(
                    f"capability request_id {capability.request_id} != {request_id}"
                )
            # Lifecycle check
            if cap_id not in self._live:
                if cap_id in self._consumed:
                    raise CapabilityConsumed("capability already consumed")
                if cap_id in self._revoked:
                    raise CapabilityConsumed("capability was revoked")
                raise CapabilityForgery("unknown capability")
            # Scope binding check
            meta = self._capability_meta.get(cap_id)
            if not meta or not meta.get("scope"):
                raise CapabilityForgery("missing capability metadata or bound scope")
            if meta.get("capability") != capability:
                raise CapabilityForgery("capability metadata mismatch")
            if meta["scope"] != required_scope:
                raise CapabilityForgery(
                    f"capability scope {meta['scope']!r} != required {required_scope!r}"
                )

            if len(self._verification_payloads) >= self._retention_limit:
                raise ReceiptRetentionExhausted("receipt verification window is full")

            consume_seq = self._consume_sequence + 1
            receipt_nonce = secrets.token_urlsafe(24)

            # Compute HMAC signature
            scope_for_sign = meta["scope"]
            payload = self._signing_payload(
                issuer_id=self.issuer_id,
                request_id=request_id,
                scope=scope_for_sign,
                capability_id=cap_id,
                capability=capability,
                process_nonce=self._process_nonce,
                creator_pid=self._creator_pid,
                issue_sequence=capability.issue_sequence,
                consume_sequence=consume_seq,
                receipt_nonce=receipt_nonce,
            )

            signature = self._sign_payload(payload)

            # Commit only after validation and signing succeed.
            self._consume_sequence = consume_seq
            self._verification_payloads[consume_seq] = payload
            # Move from live to consumed
            self._live.discard(cap_id)
            self._consumed.add(cap_id)

            return AuthorityReceipt(
                issuer_id=self.issuer_id,
                request_id=request_id,
                scope=scope_for_sign,
                nonce=receipt_nonce,
                sequence=consume_seq,
                signature=signature,
            )

    def revoke(
        self,
        capability: AuthorityCapability,
        *,
        reason: str,
    ) -> None:
        self._check_pid()
        if type(capability) is not AuthorityCapability:
            raise CapabilityForgery("expected AuthorityCapability")

        cap_id = capability.capability_id
        with self._lock:
            if capability.issuer_id != self.issuer_id:
                raise CapabilityForgery("unknown authority issuer")
            if cap_id not in self._live:
                raise CapabilityConsumed("capability not live")
            self._live.discard(cap_id)
            self._revoked.add(cap_id)

    def snapshot(self) -> CapabilityRegistrySnapshot:
        with self._lock:
            return CapabilityRegistrySnapshot(
                issuer_id=self.issuer_id,
                live_capabilities=tuple(sorted(self._live)),
                consumed_capabilities=tuple(sorted(self._consumed)),
                revoked_capabilities=tuple(sorted(self._revoked)),
                consume_sequence=self._consume_sequence,
                creator_pid=self._creator_pid,
            )
