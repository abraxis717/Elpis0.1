"""G5.3C Authority boundary tests."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_application_executor.authority import (
    verify_authority_boundary, verify_no_canonical_write, FORBIDDEN_FIELDS,
    check_forbidden_fields,
)
from elpis_grid81_application_executor.canonical import canonical_digest
from elpis_grid81_application_executor.fixture import (
    create_shadow_fixture, create_shadow_artifact, mutate_and_rehash,
)


class TestAuthorityBoundary:
    def test_valid_artifact_passes(self):
        fixture = create_shadow_fixture(0, scope_size=1)
        artifact = create_shadow_artifact(fixture, 0)
        ok, violations = verify_authority_boundary(artifact)
        assert ok
        assert len(violations) == 0

    def test_forbidden_field_detected(self):
        fixture = create_shadow_fixture(0, scope_size=1)
        artifact = create_shadow_artifact(fixture, 0)
        mut = mutate_and_rehash(artifact, "winner", "forbidden")
        ok, violations = verify_authority_boundary(mut)
        assert not ok
        assert any("winner" in v for v in violations)

    def test_canonical_write_detected(self):
        fixture = create_shadow_fixture(0, scope_size=1)
        artifact = create_shadow_artifact(fixture, 0)
        mut = mutate_and_rehash(artifact, "canonical_path", "/bad")
        ok, issues = verify_no_canonical_write(mut)
        assert not ok
        assert any("canonical_path" in i for i in issues)

    def test_nested_forbidden_field_detected(self):
        obj = {"proposal_bindings": [{"winner": "bad"}]}
        violations = check_forbidden_fields(obj)
        assert len(violations) > 0

    def test_no_forbidden_in_clean_artifact(self):
        fixture = create_shadow_fixture(0, scope_size=1)
        artifact = create_shadow_artifact(fixture, 0)
        violations = check_forbidden_fields(artifact)
        assert len(violations) == 0

    def test_forbidden_fields_list_non_empty(self):
        assert len(FORBIDDEN_FIELDS) > 0

    def test_authority_violation_count(self):
        """Check that we have a reasonable number of forbidden fields."""
        assert len(FORBIDDEN_FIELDS) >= 20
