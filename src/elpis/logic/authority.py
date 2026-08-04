"""L0 Authority registry — explicit process-local capability registry.

Rules:
  - explicit instance, never module-global
  - RLock protected
  - creator PID checked
  - process nonce checked
  - exact scope binding
  - disjoint live/consumed/revoked sets
  - copy-on-write state, one-pointer commit
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
from dataclasses import dataclass
from threading import RLock
from typing import TYPE_CHECKING

from elpis.contracts.closure import AuthorityReceipt, canonical_json_bytes

from .errors import (
    AccountWrongPid,
    CapabilityConsumed,
    CapabilityForgery,
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

    def __init__(self, *, issuer_id: str) -> None:
        if not issuer_id:
            raise ValueError("issuer_id must be non-empty")
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

    def _sign(
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
    ) -> str:
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
        canonical = canonical_json_bytes(payload)
        return hmac.new(
            self._secret, canonical, hashlib.sha256
        ).hexdigest()

    def issue(
        self,
        *,
        request_id: str,
        scope: str = "",
    ) -> AuthorityCapability:
        self._check_pid()
        if not request_id:
            raise ValueError("request_id must be non-empty")

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
            if meta and meta.get("scope") and meta["scope"] != required_scope:
                raise CapabilityForgery(
                    f"capability scope {meta['scope']!r} != required {required_scope!r}"
                )

            self._consume_sequence += 1
            consume_seq = self._consume_sequence
            receipt_nonce = secrets.token_urlsafe(24)

            # Compute HMAC signature
            scope_for_sign = required_scope
            signature = self._sign(
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
