from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib

import pytest

from elpis_reference.structural_guidance import (
    CANONICAL_STRUCTURAL_MATERIALIZER_ID,
    CANONICAL_STRUCTURAL_MATERIALIZER_VERSION,
    CanonicalResolvedTopologyMaterializerV1,
    DETERMINISTIC_DECODER_ADAPTER_ID,
    DETERMINISTIC_DECODER_ADAPTER_VERSION,
    DETERMINISTIC_STRUCTURAL_PLANNER_ID,
    DETERMINISTIC_STRUCTURAL_PLANNER_VERSION,
    DecoderSourceInputError,
    DeterministicDecoderAdapterV1,
    DeterministicStructuralPlannerV1,
    DigestBoundResolvedTopologyObserverV1,
    ResolvedStructuralTopologyV1,
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


def _chain(
    *,
    prompt='  hello   world  """ unsafe ',
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

    return (
        planning_input,
        decoder_plan,
    )


def test_source_input_rebinds_exact_prompt():
    prompt = (
        '  hello   world  """ unsafe '
    )

    planning_input, decoder_plan = (
        _chain(prompt=prompt)
    )

    source_input = build_decoder_source_input(
        decoder_plan,
        planning_input,
        prompt=prompt,
    )

    assert (
        source_input.decoder_plan_digest
        == decoder_plan.decoder_plan_digest
    )

    assert (
        source_input.prompt_digest
        == planning_input.prompt_digest
    )

    assert (
        source_input.docstring_summary
        == "hello world ''' unsafe"
    )

    assert source_input.validate_digest()


def test_raw_prompt_field_is_not_retained_but_summary_is():
    prompt = "  secret   prompt text  "

    planning_input, decoder_plan = (
        _chain(prompt=prompt)
    )

    source_input = build_decoder_source_input(
        decoder_plan,
        planning_input,
        prompt=prompt,
    )

    assert not hasattr(
        source_input,
        "prompt",
    )

    assert (
        source_input.docstring_summary
        == "secret prompt text"
    )

    assert (
        source_input.prompt_digest
        == planning_input.prompt_digest
    )


def test_wrong_prompt_is_rejected():
    planning_input, decoder_plan = (
        _chain(prompt="original")
    )

    with pytest.raises(
        DecoderSourceInputError,
        match="does not match",
    ):
        build_decoder_source_input(
            decoder_plan,
            planning_input,
            prompt="retargeted",
        )


def test_summary_matches_legacy_normalization_and_limit():
    prompt = (
        "   "
        + ("word   " * 100)
    )

    planning_input, decoder_plan = (
        _chain(prompt=prompt)
    )

    source_input = build_decoder_source_input(
        decoder_plan,
        planning_input,
        prompt=prompt,
    )

    expected = " ".join(
        prompt.strip().split()
    )[:240].replace(
        '"""',
        "'''",
    )

    assert (
        source_input.docstring_summary
        == expected
    )

    assert len(
        source_input.docstring_summary
    ) <= 240


def test_source_input_remains_authority_zero():
    prompt = "hello"

    planning_input, decoder_plan = (
        _chain(prompt=prompt)
    )

    source_input = build_decoder_source_input(
        decoder_plan,
        planning_input,
        prompt=prompt,
    )

    assert source_input.authority_granted == 0
    assert source_input.planning_authorized is False
    assert source_input.decoding_authorized is False
    assert (
        source_input.source_emission_authorized
        is False
    )
    assert source_input.execution_authorized is False


def test_mismatched_planning_input_is_rejected():
    first_input, first_plan = _chain(
        prompt="first"
    )

    second_input, _ = _chain(
        prompt="second"
    )

    assert (
        first_input.planning_input_digest
        != second_input.planning_input_digest
    )

    with pytest.raises(
        DecoderSourceInputError,
        match="planning_input_digest mismatch",
    ):
        build_decoder_source_input(
            first_plan,
            second_input,
            prompt="second",
        )


def test_source_input_tamper_is_detected():
    planning_input, decoder_plan = (
        _chain(prompt="hello")
    )

    source_input = build_decoder_source_input(
        decoder_plan,
        planning_input,
        prompt="hello",
    )

    object.__setattr__(
        source_input,
        "docstring_summary",
        "retargeted",
    )

    assert not source_input.validate_digest()


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
def test_authority_widening_is_rejected(
    field,
    value,
):
    planning_input, decoder_plan = (
        _chain(prompt="hello")
    )

    source_input = build_decoder_source_input(
        decoder_plan,
        planning_input,
        prompt="hello",
    )

    object.__setattr__(
        source_input,
        field,
        value,
    )

    assert not source_input.validate_digest()
