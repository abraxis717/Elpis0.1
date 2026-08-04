"""Tests for capability limits."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_capability_authority.limits import create_capability_limit, validate_limit


def test_limit_creation():
    limit = create_capability_limit()
    assert validate_limit(limit)
    assert limit["max_consumptions"] == 1
    assert limit["single_use"] is True
    assert limit["valid_from_logical_tick"] == 0
    assert limit["valid_through_logical_tick"] == 0


def test_limit_custom_interval():
    limit = create_capability_limit(valid_from=0, valid_through=5)
    assert validate_limit(limit)
    assert limit["valid_from_logical_tick"] == 0
    assert limit["valid_through_logical_tick"] == 5


def test_limit_invalid_max_consumptions():
    limit = create_capability_limit()
    limit["max_consumptions"] = 2
    limit["limit_digest"] = ""  # broken digest
    assert not validate_limit(limit)


def test_limit_invalid_single_use():
    limit = create_capability_limit()
    limit["single_use"] = False
    assert not validate_limit(limit)


def test_limit_digest_valid():
    limit = create_capability_limit()
    assert len(limit["limit_digest"]) == 64


def test_limit_deterministic():
    l1 = create_capability_limit()
    l2 = create_capability_limit()
    assert l1["limit_digest"] == l2["limit_digest"]
