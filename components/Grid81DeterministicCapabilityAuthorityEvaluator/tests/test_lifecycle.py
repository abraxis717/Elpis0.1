"""Tests for lifecycle entries."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_capability_authority.lifecycle import create_lifecycle_entry, validate_lifecycle_entry, LIFECYCLE_STATES


def test_lifecycle_creation():
    entry = create_lifecycle_entry(capability_digest="a" * 64, nonce_digest="b" * 64)
    assert validate_lifecycle_entry(entry)
    assert entry["initial_lifecycle_state"] == "GRANTED_UNCONSUMED"
    assert entry["consumption_count"] == 0
    assert entry["max_consumptions"] == 1


def test_lifecycle_states_defined():
    assert "GRANTED_UNCONSUMED" in LIFECYCLE_STATES
    assert "CONSUMED" in LIFECYCLE_STATES
    assert "REVOKED" in LIFECYCLE_STATES
    assert "EXPIRED" in LIFECYCLE_STATES


def test_lifecycle_invalid_state():
    entry = create_lifecycle_entry(capability_digest="a" * 64, nonce_digest="b" * 64)
    entry["initial_lifecycle_state"] = "CONSUMED"
    # Should still pass since CONSUMED is valid
    assert validate_lifecycle_entry(entry)


def test_lifecycle_deterministic():
    e1 = create_lifecycle_entry(capability_digest="a" * 64, nonce_digest="b" * 64)
    e2 = create_lifecycle_entry(capability_digest="a" * 64, nonce_digest="b" * 64)
    assert e1["lifecycle_record_digest"] == e2["lifecycle_record_digest"]


def test_lifecycle_revocation_state():
    entry = create_lifecycle_entry(capability_digest="a" * 64, nonce_digest="b" * 64)
    assert entry["revocation_state"] == "NOT_REVOKED"
