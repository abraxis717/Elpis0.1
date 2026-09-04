from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import inspect

import pytest

from elpis_reference.structural_guidance import (
    CANONICAL_STRUCTURAL_MATERIALIZER_ID,
    CANONICAL_STRUCTURAL_MATERIALIZER_VERSION,
    CanonicalResolvedTopologyMaterializerV1,
    DECODING_AUTHORITY,
    DETERMINISTIC_DECODER_ADAPTER_ID,
    DETERMINISTIC_DECODER_ADAPTER_VERSION,
    DETERMINISTIC_SOURCE_EMITTER_ID,
    DETERMINISTIC_SOURCE_EMITTER_VERSION,
    DETERMINISTIC_STRUCTURAL_PLANNER_ID,
    DETERMINISTIC_STRUCTURAL_PLANNER_VERSION,
    DecodedSourceArtifactV1,
    DeterministicDecoderAdapterV1,
    DeterministicSourceEmitterV1,
    DeterministicStructuralPlannerV1,
    DigestBoundResolvedTopologyObserverV1,
    ResolvedStructuralTopologyV1,
    SourceEmitterError,
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


def _sha(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


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
        structural_bindings_digest=_sha(
            b"{}"
        ),
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


def _emission_inputs(
    *,
    prompt=(
        '  implement   a typed function """ and tests  '
    ),
    body="x = 1\nreturn x",
):
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
        parameters=(
            "input value",
            "good_name",
        ),
        decoder_hints=(
            (
                "body",
                body,
            ),
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

    source_input = build_decoder_source_input(
        decoder_plan,
        planning_input,
        prompt=prompt,
    )

    sea = (
        _new_source_emission_authority()
    )

    sei = sea._precommit_from_owner(
        source_input,
        source_emitter_id=(
            DETERMINISTIC_SOURCE_EMITTER_ID
        ),
        source_emitter_version=(
            DETERMINISTIC_SOURCE_EMITTER_VERSION
        ),
    )

    sec = sea._consume_from_owner(
        sea._reveal_from_owner(
            sei
        )
    )

    return (
        decoder_plan,
        source_input,
        sec,
    )


def test_source_emitter_emits_authority_zero_artifact():
    (
        decoder_plan,
        source_input,
        consumption,
    ) = _emission_inputs()

    artifact = (
        DeterministicSourceEmitterV1()
        .emit(
            decoder_plan,
            source_input,
            consumption,
        )
    )

    assert isinstance(
        artifact,
        DecodedSourceArtifactV1,
    )

    assert (
        artifact.authority_applied
        == DECODING_AUTHORITY
    )

    assert artifact.authority_granted == 0
    assert artifact.planning_authorized is False
    assert artifact.decoding_authorized is False
    assert (
        artifact.source_emission_authorized
        is False
    )
    assert artifact.execution_authorized is False

    assert artifact.validate_digest()


def test_source_text_matches_deterministic_template():
    (
        decoder_plan,
        source_input,
        consumption,
    ) = _emission_inputs()

    artifact = (
        DeterministicSourceEmitterV1()
        .emit(
            decoder_plan,
            source_input,
            consumption,
        )
    )

    assert artifact.source == (
        "def solution(arg_0, good_name):\n"
        '    """implement a typed function '
        "''' and tests"
        '"""\n'
        "    x = 1\n"
        "    return x\n"
    )


def test_blank_body_lines_match_template_behavior():
    (
        decoder_plan,
        source_input,
        consumption,
    ) = _emission_inputs(
        prompt="hello",
        body="x = 1\n\nreturn x",
    )

    artifact = (
        DeterministicSourceEmitterV1()
        .emit(
            decoder_plan,
            source_input,
            consumption,
        )
    )

    assert artifact.source == (
        "def solution(arg_0, good_name):\n"
        '    """hello"""\n'
        "    x = 1\n"
        "\n"
        "    return x\n"
    )


def test_source_sha256_binds_exact_bytes():
    (
        decoder_plan,
        source_input,
        consumption,
    ) = _emission_inputs()

    artifact = (
        DeterministicSourceEmitterV1()
        .emit(
            decoder_plan,
            source_input,
            consumption,
        )
    )

    expected = hashlib.sha256(
        artifact.source.encode(
            "utf-8"
        )
    ).hexdigest()

    assert (
        artifact.source_sha256
        == expected
    )


def test_emitter_is_deterministic():
    (
        decoder_plan,
        source_input,
        consumption,
    ) = _emission_inputs()

    emitter = (
        DeterministicSourceEmitterV1()
    )

    first = emitter.emit(
        decoder_plan,
        source_input,
        consumption,
    )

    second = emitter.emit(
        decoder_plan,
        source_input,
        consumption,
    )

    assert first == second
    assert (
        first.source_artifact_digest
        == second.source_artifact_digest
    )


def test_foreign_source_input_is_rejected_at_plan_binding():
    (
        first_plan,
        first_input,
        first_consumption,
    ) = _emission_inputs(
        prompt="first"
    )

    (
        _,
        second_input,
        _,
    ) = _emission_inputs(
        prompt="second"
    )

    with pytest.raises(
        SourceEmitterError,
        match="source input decoder_plan_digest mismatch",
    ):
        (
            DeterministicSourceEmitterV1()
            .emit(
                first_plan,
                second_input,
                first_consumption,
            )
        )


def test_decoder_plan_cannot_be_retargeted():
    (
        first_plan,
        first_input,
        first_consumption,
    ) = _emission_inputs(
        body="return 1"
    )

    (
        second_plan,
        _,
        _,
    ) = _emission_inputs(
        body="return 2"
    )

    with pytest.raises(
        SourceEmitterError,
        match="decoder_plan_digest mismatch",
    ):
        (
            DeterministicSourceEmitterV1()
            .emit(
                second_plan,
                first_input,
                first_consumption,
            )
        )


def test_emitter_identity_is_bound():
    (
        decoder_plan,
        source_input,
        consumption,
    ) = _emission_inputs()

    other = (
        DeterministicSourceEmitterV1(
            source_emitter_id="other.emitter",
        )
    )

    with pytest.raises(
        SourceEmitterError,
        match="emitter identity mismatch",
    ):
        other.emit(
            decoder_plan,
            source_input,
            consumption,
        )


def test_source_artifact_tamper_is_detected():
    (
        decoder_plan,
        source_input,
        consumption,
    ) = _emission_inputs()

    artifact = (
        DeterministicSourceEmitterV1()
        .emit(
            decoder_plan,
            source_input,
            consumption,
        )
    )

    object.__setattr__(
        artifact,
        "source",
        artifact.source + "# tampered\n",
    )

    assert not artifact.validate_digest()


def test_emitter_public_surface_is_emit_only():
    methods = {
        name
        for name, value
        in inspect.getmembers(
            DeterministicSourceEmitterV1
        )
        if not name.startswith("_")
        and inspect.isfunction(value)
    }

    assert methods == {
        "emit",
    }


def test_source_artifact_has_no_execution_surface():
    methods = {
        name
        for name, value
        in inspect.getmembers(
            DecodedSourceArtifactV1
        )
        if not name.startswith("_")
        and inspect.isfunction(value)
    }

    assert methods == {
        "payload",
        "source_artifact_digest_computed",
        "validate",
        "validate_digest",
    }

    for forbidden in (
        "execute",
        "invoke",
        "run",
        "compile",
        "import_module",
    ):
        assert forbidden not in methods


@pytest.mark.parametrize(
    (
        "field",
        "value",
    ),
    (
        (
            "authority_granted",
            1,
        ),
        (
            "planning_authorized",
            True,
        ),
        (
            "decoding_authorized",
            True,
        ),
        (
            "source_emission_authorized",
            True,
        ),
        (
            "execution_authorized",
            True,
        ),
    ),
)
def test_output_authority_widening_is_detected(
    field,
    value,
):
    (
        decoder_plan,
        source_input,
        consumption,
    ) = _emission_inputs()

    artifact = (
        DeterministicSourceEmitterV1()
        .emit(
            decoder_plan,
            source_input,
            consumption,
        )
    )

    object.__setattr__(
        artifact,
        field,
        value,
    )

    assert not artifact.validate_digest()
