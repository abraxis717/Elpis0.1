from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest

from elpis_reference.structural_guidance import (
    DECODING_AUTHORITY,
    VALIDATION_AUTHORITY,
    DecodedSourceArtifactV1,
    ValidationAuthorityError,
)
from elpis_reference.structural_guidance.validation_authority import (
    _new_validation_authority,
)


VALIDATOR_ID = "python.ast.v1"
VALIDATOR_VERSION = "v1"


def _artifact(
    *,
    source=(
        "def solution(arg_0):\n"
        '    """hello"""\n'
        "    return arg_0\n"
    ),
):
    source_sha = hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()

    unsigned = DecodedSourceArtifactV1(
        schema=(
            "elpis.structural-guidance."
            "decoded-source-artifact.v1"
        ),
        decoder_plan_digest="1" * 64,
        source_input_digest="2" * 64,
        source_emission_consumption_digest="3" * 64,
        planning_input_digest="4" * 64,
        materialization_digest="5" * 64,
        topology_digest="6" * 64,
        semantic_input_digest="7" * 64,
        request_id="request-1",
        source_emitter_id=(
            "elpis.structural-guidance."
            "deterministic-source-emitter"
        ),
        source_emitter_version="v1",
        language="python",
        source=source,
        source_sha256=source_sha,
        authority_applied=DECODING_AUTHORITY,
        authority_granted=0,
        planning_authorized=False,
        decoding_authorized=False,
        source_emission_authorized=False,
        execution_authorized=False,
        source_artifact_digest="",
    )

    artifact = replace(
        unsigned,
        source_artifact_digest=(
            unsigned.source_artifact_digest_computed()
        ),
    )

    artifact.validate()

    return artifact


def _precommit(
    authority,
):
    artifact = _artifact()

    intent = authority._precommit_from_owner(
        artifact,
        validator_id=VALIDATOR_ID,
        validator_version=VALIDATOR_VERSION,
    )

    return (
        artifact,
        intent,
    )


def test_precommit_exposes_no_capability():
    authority = (
        _new_validation_authority()
    )

    artifact, intent = _precommit(
        authority
    )

    assert (
        intent.source_artifact_digest
        == artifact.source_artifact_digest
    )

    assert (
        intent.source_sha256
        == artifact.source_sha256
    )

    assert not hasattr(
        intent,
        "capability_id",
    )

    assert not hasattr(
        intent,
        "authority",
    )

    intent.validate()


def test_reveal_grants_validation_only():
    authority = (
        _new_validation_authority()
    )

    _, intent = _precommit(
        authority
    )

    authorized = authority._reveal_from_owner(
        intent
    )

    receipt = authorized.receipt

    assert (
        receipt.authority
        == VALIDATION_AUTHORITY
    )

    assert receipt.planning_authorized is False
    assert receipt.decoding_authorized is False
    assert (
        receipt.source_emission_authorized
        is False
    )
    assert receipt.validation_authorized is True
    assert receipt.execution_authorized is False

    assert receipt.validator_id == VALIDATOR_ID
    assert (
        receipt.validator_version
        == VALIDATOR_VERSION
    )

    receipt.validate()


def test_reveal_is_one_shot():
    authority = (
        _new_validation_authority()
    )

    _, intent = _precommit(
        authority
    )

    authority._reveal_from_owner(
        intent
    )

    with pytest.raises(
        ValidationAuthorityError,
        match="precommitted",
    ):
        authority._reveal_from_owner(
            intent
        )


def test_consumption_is_one_shot():
    authority = (
        _new_validation_authority()
    )

    _, intent = _precommit(
        authority
    )

    authorized = authority._reveal_from_owner(
        intent
    )

    consumption = authority._consume_from_owner(
        authorized
    )

    assert (
        consumption.authority
        == VALIDATION_AUTHORITY
    )

    assert consumption.planning_authorized is False
    assert consumption.decoding_authorized is False
    assert (
        consumption.source_emission_authorized
        is False
    )
    assert consumption.validation_authorized is True
    assert consumption.execution_authorized is False

    consumption.validate()

    with pytest.raises(
        ValidationAuthorityError,
        match="not active",
    ):
        authority._consume_from_owner(
            authorized
        )


def test_cross_instance_consumption_rejected():
    issuer = (
        _new_validation_authority()
    )

    other = (
        _new_validation_authority()
    )

    _, intent = _precommit(
        issuer
    )

    authorized = issuer._reveal_from_owner(
        intent
    )

    with pytest.raises(
        ValidationAuthorityError,
        match="another",
    ):
        other._consume_from_owner(
            authorized
        )


def test_validator_identity_is_bound():
    authority = (
        _new_validation_authority()
    )

    _, intent = _precommit(
        authority
    )

    assert intent.validator_id == VALIDATOR_ID
    assert (
        intent.validator_version
        == VALIDATOR_VERSION
    )

    object.__setattr__(
        intent,
        "validator_version",
        "v2",
    )

    with pytest.raises(
        ValidationAuthorityError,
        match="digest mismatch",
    ):
        authority._reveal_from_owner(
            intent
        )


def test_tampered_source_artifact_is_rejected():
    artifact = _artifact()

    object.__setattr__(
        artifact,
        "source",
        artifact.source + "x = 1\n",
    )

    authority = (
        _new_validation_authority()
    )

    with pytest.raises(
        Exception,
    ):
        authority._precommit_from_owner(
            artifact,
            validator_id=VALIDATOR_ID,
            validator_version=VALIDATOR_VERSION,
        )


def test_authority_binds_full_source_lineage():
    artifact = _artifact()

    authority = (
        _new_validation_authority()
    )

    intent = authority._precommit_from_owner(
        artifact,
        validator_id=VALIDATOR_ID,
        validator_version=VALIDATOR_VERSION,
    )

    authorized = authority._reveal_from_owner(
        intent
    )

    consumption = authority._consume_from_owner(
        authorized
    )

    assert (
        consumption.source_artifact_digest
        == artifact.source_artifact_digest
    )
    assert (
        consumption.source_sha256
        == artifact.source_sha256
    )
    assert (
        consumption.decoder_plan_digest
        == artifact.decoder_plan_digest
    )
    assert (
        consumption.source_input_digest
        == artifact.source_input_digest
    )
    assert (
        consumption.planning_input_digest
        == artifact.planning_input_digest
    )
    assert (
        consumption.materialization_digest
        == artifact.materialization_digest
    )
    assert (
        consumption.topology_digest
        == artifact.topology_digest
    )
    assert (
        consumption.semantic_input_digest
        == artifact.semantic_input_digest
    )


def test_public_package_does_not_export_private_authority():
    import elpis_reference.structural_guidance as sg

    assert not hasattr(
        sg,
        "_ValidationAuthority",
    )

    assert not hasattr(
        sg,
        "_new_validation_authority",
    )
