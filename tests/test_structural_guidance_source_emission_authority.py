from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib

import pytest

from elpis_reference.structural_guidance import (
    CANONICAL_STRUCTURAL_MATERIALIZER_ID,
    CANONICAL_STRUCTURAL_MATERIALIZER_VERSION,
    CanonicalResolvedTopologyMaterializerV1,
    DECODING_AUTHORITY,
    DETERMINISTIC_DECODER_ADAPTER_ID,
    DETERMINISTIC_DECODER_ADAPTER_VERSION,
    DETERMINISTIC_STRUCTURAL_PLANNER_ID,
    DETERMINISTIC_STRUCTURAL_PLANNER_VERSION,
    DeterministicDecoderAdapterV1,
    DeterministicStructuralPlannerV1,
    DigestBoundResolvedTopologyObserverV1,
    ResolvedStructuralTopologyV1,
    SourceEmissionAuthorityError,
    build_decoder_source_input,
    build_planning_input,
)
from elpis_reference.structural_guidance.decoding_authority import (
    _new_decoding_authority,
)
from elpis_reference.structural_guidance.materialization_authority import (
    _new_resolved_topology_materialization_authority,
)
from elpis_reference.structural_guidance.planning_authority import (
    _new_planning_authority,
)
from elpis_reference.structural_guidance.source_emission_authority import (
    _new_source_emission_authority,
)


EMITTER_ID = (
    "elpis.structural-guidance."
    "deterministic-source-emitter"
)
EMITTER_VERSION = "v1"


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class _Schema:
    schema_digest: str


def _topology():
    unsigned = ResolvedStructuralTopologyV1(
        schema=(
            "elpis.structural-guidance."
            "resolved-topology.v1"
        ),
        grid81=(0,) * 81,
        frozen_mask=(0,) * 81,
        writable_mask=(1,) * 81,
        invariants=(),
        lane_bindings=(),
        structural_schema=_Schema(
            schema_digest="1" * 64,
        ),
        declared_features=(0,) * 529,
        active_residual=(0,) * 529,
        residual_ids=(),
        structural_bindings_json="{}",
        structural_bindings_digest=_sha(b"{}"),
        semantic_input_digest="2" * 64,
        rule_set_digest="3" * 64,
        projection_structural_schema_digest="4" * 64,
        refiner_structural_schema_digest="5" * 64,
        projection_digest="6" * 64,
        projection_trace_digest="7" * 64,
        projection_fingerprint="8" * 64,
        refinement_state_fingerprint="9" * 64,
        refiner_input_digest="a" * 64,
        envelope_digest="b" * 64,
        receipt_digest="c" * 64,
        checkpoint_sha256="d" * 64,
        best_cost=0,
        iterations=0,
        applied_moves=0,
        authority_granted=0,
        topology_digest="",
    )

    signed = replace(
        unsigned,
        topology_digest=(
            unsigned.topology_digest_computed()
        ),
    )

    signed.validate()
    return signed


def _source_input():
    prompt = "implement a typed function"

    topology = _topology()

    observation = (
        DigestBoundResolvedTopologyObserverV1()
        .observe(topology)
    )

    ma = (
        _new_resolved_topology_materialization_authority()
    )

    mi = ma._precommit_from_owner(
        topology,
        observation,
        materializer_id=(
            CANONICAL_STRUCTURAL_MATERIALIZER_ID
        ),
        materializer_version=(
            CANONICAL_STRUCTURAL_MATERIALIZER_VERSION
        ),
    )

    mc = ma._consume_from_owner(
        ma._reveal_from_owner(mi)
    )

    materialization = (
        CanonicalResolvedTopologyMaterializerV1()
        .materialize(
            topology,
            mc,
        )
    )

    planning_input = build_planning_input(
        materialization,
        request_id="request-1",
        prompt=prompt,
        domain="python",
        entrypoint="solve problem",
        parameters=("input value",),
        decoder_hints=(
            ("body", "return None"),
        ),
        allowed_experts=(
            "python.ast",
            "python.codegen",
        ),
        selected_experts=(
            "python.ast",
            "python.codegen",
        ),
        max_tokens=512,
    )

    pa = _new_planning_authority()

    pi = pa._precommit_from_owner(
        planning_input,
        planner_id=(
            DETERMINISTIC_STRUCTURAL_PLANNER_ID
        ),
        planner_version=(
            DETERMINISTIC_STRUCTURAL_PLANNER_VERSION
        ),
    )

    pc = pa._consume_from_owner(
        pa._reveal_from_owner(pi)
    )

    planning_artifact = (
        DeterministicStructuralPlannerV1()
        .plan(
            planning_input,
            pc,
        )
    )

    da = _new_decoding_authority()

    di = da._precommit_from_owner(
        planning_artifact,
        decoder_adapter_id=(
            DETERMINISTIC_DECODER_ADAPTER_ID
        ),
        decoder_adapter_version=(
            DETERMINISTIC_DECODER_ADAPTER_VERSION
        ),
    )

    dc = da._consume_from_owner(
        da._reveal_from_owner(di)
    )

    decoder_plan = (
        DeterministicDecoderAdapterV1()
        .adapt(
            planning_artifact,
            dc,
        )
    )

    return build_decoder_source_input(
        decoder_plan,
        planning_input,
        prompt=prompt,
    )


def _precommit(authority):
    source_input = _source_input()

    intent = authority._precommit_from_owner(
        source_input,
        source_emitter_id=EMITTER_ID,
        source_emitter_version=EMITTER_VERSION,
    )

    return source_input, intent


def test_precommit_grants_no_capability():
    authority = (
        _new_source_emission_authority()
    )

    source_input, intent = _precommit(
        authority
    )

    assert (
        intent.source_input_digest
        == source_input.source_input_digest
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


def test_reveal_grants_source_emission_without_execution():
    authority = (
        _new_source_emission_authority()
    )

    _, intent = _precommit(
        authority
    )

    authorized = authority._reveal_from_owner(
        intent
    )

    receipt = authorized.receipt

    assert receipt.authority == DECODING_AUTHORITY
    assert receipt.planning_authorized is False
    assert receipt.decoding_authorized is True
    assert (
        receipt.source_emission_authorized
        is True
    )
    assert receipt.execution_authorized is False

    assert receipt.source_emitter_id == EMITTER_ID
    assert (
        receipt.source_emitter_version
        == EMITTER_VERSION
    )

    receipt.validate()


def test_reveal_is_one_shot():
    authority = (
        _new_source_emission_authority()
    )

    _, intent = _precommit(
        authority
    )

    authority._reveal_from_owner(
        intent
    )

    with pytest.raises(
        SourceEmissionAuthorityError,
        match="precommitted",
    ):
        authority._reveal_from_owner(
            intent
        )


def test_consumption_is_one_shot():
    authority = (
        _new_source_emission_authority()
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

    assert consumption.authority == DECODING_AUTHORITY
    assert consumption.planning_authorized is False
    assert consumption.decoding_authorized is True
    assert (
        consumption.source_emission_authorized
        is True
    )
    assert consumption.execution_authorized is False

    consumption.validate()

    with pytest.raises(
        SourceEmissionAuthorityError,
        match="not active",
    ):
        authority._consume_from_owner(
            authorized
        )


def test_cross_instance_consumption_rejected():
    issuer = (
        _new_source_emission_authority()
    )
    other = (
        _new_source_emission_authority()
    )

    _, intent = _precommit(
        issuer
    )

    authorized = issuer._reveal_from_owner(
        intent
    )

    with pytest.raises(
        SourceEmissionAuthorityError,
        match="another",
    ):
        other._consume_from_owner(
            authorized
        )


def test_emitter_identity_is_bound():
    authority = (
        _new_source_emission_authority()
    )

    _, intent = _precommit(
        authority
    )

    assert intent.source_emitter_id == EMITTER_ID

    object.__setattr__(
        intent,
        "source_emitter_version",
        "v2",
    )

    with pytest.raises(
        SourceEmissionAuthorityError,
        match="digest mismatch",
    ):
        authority._reveal_from_owner(
            intent
        )


def test_tampered_source_input_rejected():
    source_input = _source_input()

    object.__setattr__(
        source_input,
        "docstring_summary",
        "retargeted",
    )

    authority = (
        _new_source_emission_authority()
    )

    with pytest.raises(
        Exception,
    ):
        authority._precommit_from_owner(
            source_input,
            source_emitter_id=EMITTER_ID,
            source_emitter_version=EMITTER_VERSION,
        )


def test_public_package_does_not_export_private_authority():
    import elpis_reference.structural_guidance as sg

    assert not hasattr(
        sg,
        "_SourceEmissionAuthority",
    )

    assert not hasattr(
        sg,
        "_new_source_emission_authority",
    )
