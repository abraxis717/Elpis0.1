"""Authority receipt verification: the HMAC must be under test, not stored.

WHY THIS FILE EXISTS
  An earlier repair verified receipts by comparing the supplied signature to
  a signature retained in memory. That established only "this receipt matches
  one I kept", never "this signature is valid under my key" -- if _sign_payload
  degenerated to a constant, stored-comparison would still accept genuine
  receipts and reject altered ones, and the cryptographic mechanism would be
  contributing nothing. test_verify_fails_under_wrong_key is the case that
  distinguishes the two designs.

SCOPE
  Process-local verification only. Receipts are NOT third-party verifiable;
  the key is a per-instance symmetric secret that is never exported.
"""
from __future__ import annotations

import dataclasses

import pytest

from elpis.logic.authority import CapabilityRegistry
from elpis.logic.errors import (
    CapabilityConsumed,
    CapabilityForgery,
    ReceiptRetentionExhausted,
)


def _consumed(scope: str = "grid81:read", request_id: str = "req1"):
    registry = CapabilityRegistry(issuer_id="test-issuer")
    capability = registry.issue(request_id=request_id, scope=scope)
    receipt = registry.consume(
        capability, request_id=request_id, required_scope=scope
    )
    return registry, receipt


# --- A1: scope binding ------------------------------------------------------

def test_unscoped_issue_is_rejected():
    registry = CapabilityRegistry(issuer_id="test-issuer")
    with pytest.raises((TypeError, ValueError)):
        registry.issue(request_id="req1")
    with pytest.raises(ValueError):
        registry.issue(request_id="req1", scope="")


def test_scope_widening_is_rejected_at_consume():
    registry = CapabilityRegistry(issuer_id="test-issuer")
    capability = registry.issue(request_id="req1", scope="grid81:read")
    with pytest.raises(CapabilityForgery):
        registry.consume(
            capability, request_id="req1", required_scope="canonical:write"
        )


def test_receipt_carries_the_bound_scope_not_the_requested_one():
    _, receipt = _consumed(scope="grid81:read")
    assert receipt.scope == "grid81:read"


def test_capability_is_single_use():
    registry = CapabilityRegistry(issuer_id="test-issuer")
    capability = registry.issue(request_id="req1", scope="s")
    registry.consume(capability, request_id="req1", required_scope="s")
    with pytest.raises(CapabilityConsumed):
        registry.consume(capability, request_id="req1", required_scope="s")


# --- A2: the signature is recomputed, not looked up -------------------------

def test_verify_accepts_a_genuine_receipt():
    registry, receipt = _consumed()
    assert registry.verify(receipt) is True


def test_verify_fails_under_wrong_key():
    """The decisive case. Stored fields and receipt are untouched; only the
    signing key changes. A stored-signature comparison would still accept."""
    registry, receipt = _consumed()
    original = registry._secret
    registry._secret = b"\x00" * 32
    try:
        assert registry.verify(receipt) is False
    finally:
        registry._secret = original
    assert registry.verify(receipt) is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("scope", "canonical:write"),
        ("request_id", "other-request"),
        ("nonce", "x" * 24),
        ("issuer_id", "other-issuer"),
        ("signature", "0" * 64),
        ("sequence", 99),
    ],
)
def test_verify_rejects_field_tamper(field, value):
    registry, receipt = _consumed()
    assert registry.verify(dataclasses.replace(receipt, **{field: value})) is False


def test_verify_rejects_a_receipt_from_another_registry():
    registry_a, receipt = _consumed()
    registry_b = CapabilityRegistry(issuer_id="test-issuer")
    assert registry_b.verify(receipt) is False


# --- retention is bounded and fail-closed -----------------------------------

def test_retention_raises_rather_than_silently_evicting():
    registry = CapabilityRegistry(issuer_id="test-issuer", retention_limit=2)
    for i in range(2):
        cap = registry.issue(request_id=f"r{i}", scope="s")
        registry.consume(cap, request_id=f"r{i}", required_scope="s")
    cap = registry.issue(request_id="r2", scope="s")
    with pytest.raises(ReceiptRetentionExhausted):
        registry.consume(cap, request_id="r2", required_scope="s")


def test_failed_consume_is_transactionally_inert():
    """Retention exhaustion must not advance _consume_sequence or otherwise
    mutate the registry. Raising after the sequence advanced would make a
    rejected operation a state change."""
    registry = CapabilityRegistry(issuer_id="test-issuer", retention_limit=1)
    first = registry.issue(request_id="r0", scope="s")
    registry.consume(first, request_id="r0", required_scope="s")

    pending = registry.issue(request_id="r1", scope="s")
    before = registry.state_digest()
    sequence_before = registry._consume_sequence

    with pytest.raises(ReceiptRetentionExhausted):
        registry.consume(pending, request_id="r1", required_scope="s")

    assert registry.state_digest() == before
    assert registry._consume_sequence == sequence_before
    assert pending.capability_id in registry._live


def test_rejected_scope_consume_is_transactionally_inert():
    registry = CapabilityRegistry(issuer_id="test-issuer")
    capability = registry.issue(request_id="req1", scope="grid81:read")
    before = registry.state_digest()

    with pytest.raises(CapabilityForgery):
        registry.consume(
            capability, request_id="req1", required_scope="canonical:write"
        )

    assert registry.state_digest() == before
    assert capability.capability_id in registry._live


def test_end_episode_closes_the_verification_window():
    registry = CapabilityRegistry(issuer_id="test-issuer", retention_limit=2)
    cap = registry.issue(request_id="r0", scope="s")
    receipt = registry.consume(cap, request_id="r0", required_scope="s")
    assert registry.verify(receipt) is True
    assert registry.end_episode() == 1
    # after the episode closes the receipt is no longer verifiable here; this
    # is stated, not silent.
    assert registry.verify(receipt) is False


@pytest.mark.parametrize("mutation", ["metadata", "scope"])
def test_missing_binding_is_inert(mutation):
    registry = CapabilityRegistry(issuer_id="test")
    cap = registry.issue(request_id="r", scope="s")
    if mutation == "metadata":
        del registry._capability_meta[cap.capability_id]
    else:
        del registry._capability_meta[cap.capability_id]["scope"]
    before = registry.state_digest()
    with pytest.raises(CapabilityForgery):
        registry.consume(cap, request_id="r", required_scope="s")
    assert registry.state_digest() == before


def test_retention_precedes_nonce_and_signing(monkeypatch):
    registry = CapabilityRegistry(issuer_id="test", retention_limit=1)
    cap = registry.issue(request_id="r", scope="s")
    registry.consume(cap, request_id="r", required_scope="s")
    pending = registry.issue(request_id="next", scope="s")
    def forbidden(*args, **kwargs):
        pytest.fail("retention precondition was too late")
    monkeypatch.setattr("elpis.logic.authority.secrets.token_urlsafe", forbidden)
    monkeypatch.setattr(registry, "_signing_payload", forbidden)
    monkeypatch.setattr(registry, "_sign_payload", forbidden)
    with pytest.raises(ReceiptRetentionExhausted):
        registry.consume(pending, request_id="next", required_scope="s")


def test_digest_covers_metadata_values_and_counter():
    registry = CapabilityRegistry(issuer_id="test")
    cap = registry.issue(request_id="r", scope="s")
    before = registry.state_digest()
    registry._capability_meta[cap.capability_id]["scope"] = "changed"
    assert registry.state_digest() != before
    before = registry.state_digest()
    registry._consume_sequence += 1
    assert registry.state_digest() != before
