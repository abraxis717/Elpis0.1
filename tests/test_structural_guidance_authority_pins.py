from dataclasses import replace
import hashlib
import inspect
from pathlib import Path

import pytest

from elpis_reference.structural_guidance import authority
from elpis_reference.structural_guidance._authority.c2r6p0 import (
    allocator, canonicalize, contracts as projector_contracts, residual, rules,
)
from elpis_reference.structural_guidance._authority.c2r7c import structural_trm_features
from elpis_reference.structural_guidance._authority.elpis_p0 import (
    contracts, semantic_ir, structural_residual,
)


AUTHORITY_INPUTS = (
    (structural_residual, "FROZEN_STRUCTURAL_RESIDUAL_SHA256", "structural_residual_sha"),
    (structural_trm_features, "FROZEN_STRUCTURAL_TRM_FEATURES_SHA256", "features_sha"),
    (contracts, "FROZEN_P0_CONTRACTS_SHA256", "contracts_sha"),
    (semantic_ir, "FROZEN_P0_SEMANTIC_IR_SHA256", "semantic_ir_sha"),
)


def test_pins_match_exact_production_authorities():
    # Establish the import/use chain, including the P0 token contract rather
    # than the distinct c2r6p0 projector wrapper contract.
    assert residual.authority_residual is structural_residual.residual
    assert residual.FEATURES is structural_trm_features
    assert structural_residual.BasisToken is contracts.BasisToken
    assert allocator.BasisToken is contracts.BasisToken
    assert projector_contracts.BasisToken is contracts.BasisToken
    assert canonicalize.P0SemanticRequestV1 is semantic_ir.P0SemanticRequestV1
    assert projector_contracts.P0SemanticRequestV1 is semantic_ir.P0SemanticRequestV1

    loaded = rules.load_ruleset()
    for module, pin, field in AUTHORITY_INPUTS:
        actual = hashlib.sha256(Path(inspect.getsourcefile(module)).read_bytes()).hexdigest()
        assert getattr(loaded, field) == getattr(rules, pin) == getattr(authority, pin) == actual


def test_load_ruleset_verifies_all_imported_source_paths_on_every_load(tmp_path, monkeypatch):
    expected_paths = []
    for module, _, _ in AUTHORITY_INPUTS:
        copy = tmp_path / Path(module.__file__).name
        copy.write_bytes(Path(inspect.getsourcefile(module)).read_bytes())
        monkeypatch.setattr(module, "__file__", str(copy))
        expected_paths.append(str(copy))
    monkeypatch.chdir(tmp_path)
    checked_paths = []
    real_sha = rules._sha

    def record_sha(path):
        checked_paths.append(path)
        return real_sha(path)

    monkeypatch.setattr(rules, "_sha", record_sha)
    first = rules.load_ruleset()
    second = rules.load_ruleset()
    assert checked_paths == expected_paths * 2
    assert first.digest() == second.digest()


@pytest.mark.parametrize("module,pin,field", AUTHORITY_INPUTS, ids=lambda v: getattr(v, "__name__", v))
@pytest.mark.parametrize("missing", (False, True), ids=("changed-bytes", "missing-source"))
def test_authority_verification_fails_before_ruleset_construction(
    tmp_path, monkeypatch, module, pin, field, missing,
):
    copy = tmp_path / Path(module.__file__).name
    changed = Path(inspect.getsourcefile(module)).read_bytes() + b"\n# changed authority bytes\n"
    if not missing:
        copy.write_bytes(changed)
    monkeypatch.setattr(module, "__file__", str(copy))

    def must_not_construct(**kwargs):
        pytest.fail("an unverified ruleset was constructed")

    monkeypatch.setattr(rules, "BudgetedRulesetV2", must_not_construct)
    if missing:
        expected = f"frozen authority source unreadable: {module.__name__} ({copy})"
    else:
        expected = (
            f"frozen authority SHA-256 mismatch: {module.__name__} ({copy}); "
            f"expected={getattr(rules, pin)}; actual={hashlib.sha256(changed).hexdigest()}"
        )
    for _ in range(2):
        with pytest.raises(rules.FrozenAuthorityError) as exc:
            rules.load_ruleset()
        assert str(exc.value) == expected


def test_ruleset_digests_preserve_serialization_and_bind_corrected_identity():
    loaded = rules.load_ruleset()
    assert rules.Ruleset.digest(loaded) == "db883d2af6737655f7051155520a800303aa51f3c8c7736172eaca11d619634b"
    assert loaded.digest() == "01e83872fd25a71ad75a8d808ca6d17eb9d9ea3ff10f0e4194ad7ff530da33d5"
    assert rules.load_ruleset().digest() == loaded.digest()
    assert replace(loaded, node_budget=loaded.node_budget + 1).digest() != loaded.digest()

    # Restoring only the stale contract claim reproduces both baseline digests:
    # the necessary identity correction is the only digest behavior change.
    baseline = replace(
        loaded,
        contracts_sha="face8a09f0ad76a0e34cd4544a805302502ebb70ff8b7517934521d85ed8266a",
    )
    assert rules.Ruleset.digest(baseline) == "aa6b85653108b6b0d8b7d8aadda9be0f8c9c203403772c81c9f5473cba818177"
    assert baseline.digest() == "1aa8dd6010fb8711212507cdede0e06c0f89b5d483b396cb590e865dace53abb"
