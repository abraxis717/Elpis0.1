"""Trusted structural-guidance runtime through static source validation.

This is the terminal production composition surface for structural guidance.

It composes the already-qualified stages:

Semantic IR
-> Projector
-> bounded structural-guidance admission
-> resolved topology
-> zero-authority observation
-> one-shot structural materialization
-> planning input
-> one-shot planning
-> deterministic structural planning
-> one-shot decoding adapter
-> authority-zero decoder-specific plan
-> prompt/source-input binding
-> one-shot source emission
-> deterministic source emission
-> one-shot validation
-> canonical Python AST policy
-> authority-zero terminal validation result

Generated source is never compiled, imported, invoked, or executed here.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from ._authority.elpis_p0.semantic_ir import (
    P0SemanticRequestV1,
)
from .admission import (
    StructuralGuidanceAdmissionConfig,
)
from .decoder_adapter import (
    DETERMINISTIC_DECODER_ADAPTER_ID,
    DETERMINISTIC_DECODER_ADAPTER_VERSION,
    DeterministicDecoderAdapterV1,
)
from .decoding_authority import (
    _new_decoding_authority,
)
from .hook import (
    project_semantic_request_and_admit,
)
from .materialization_authority import (
    _new_resolved_topology_materialization_authority,
)
from .materializer import (
    CANONICAL_STRUCTURAL_MATERIALIZER_ID,
    CANONICAL_STRUCTURAL_MATERIALIZER_VERSION,
    CanonicalResolvedTopologyMaterializerV1,
)
from .observer import (
    DigestBoundResolvedTopologyObserverV1,
)
from .planner import (
    DETERMINISTIC_STRUCTURAL_PLANNER_ID,
    DETERMINISTIC_STRUCTURAL_PLANNER_VERSION,
    DeterministicStructuralPlannerV1,
)
from .planning_authority import (
    _new_planning_authority,
)
from .planning_input import (
    build_planning_input,
)
from .resolved import (
    build_resolved_structural_topology,
)
from .source_emission_authority import (
    _new_source_emission_authority,
)
from .source_emitter import (
    DETERMINISTIC_SOURCE_EMITTER_ID,
    DETERMINISTIC_SOURCE_EMITTER_VERSION,
    DeterministicSourceEmitterV1,
)
from .source_input import (
    build_decoder_source_input,
)
from .structural_validator import (
    STRUCTURAL_PYTHON_AST_VALIDATOR_ID,
    STRUCTURAL_PYTHON_AST_VALIDATOR_VERSION,
    StructuralPythonASTValidatorV1,
)
from .validation_authority import (
    _new_validation_authority,
)


STRUCTURAL_GUIDANCE_RUNTIME_RESULT_SCHEMA = (
    "elpis.structural-guidance."
    "runtime-result.v1"
)

RUNTIME_STATUS_VALIDATED_SOURCE = (
    "VALIDATED_SOURCE"
)

RUNTIME_STATUS_VALIDATION_REJECTED = (
    "VALIDATION_REJECTED"
)

_RUNTIME_RESULT_DOMAIN = (
    "elpis.structural-guidance."
    "runtime-result.v1"
)

AUTHORITY_ZERO = 0


class StructuralGuidanceRuntimeError(
    ValueError
):
    """Fail-closed runtime composition error."""


def _canonical_json_bytes(
    payload: object,
) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _domain_digest(
    domain: str,
    payload: object,
) -> str:
    return hashlib.sha256(
        domain.encode("ascii")
        + b"\x00"
        + _canonical_json_bytes(payload)
    ).hexdigest()


def _is_digest(
    value: object,
) -> bool:
    if (
        not isinstance(value, str)
        or len(value) != 64
    ):
        return False

    try:
        int(value, 16)
    except ValueError:
        return False

    return True


@dataclass(frozen=True, slots=True)
class StructuralGuidanceRuntimeResultV1:
    """Terminal authority-zero result of one structural-guidance request."""

    schema: str
    status: str

    request_id: str
    semantic_input_digest: str

    topology_digest: str
    checkpoint_sha256: str

    materialization_digest: str

    planning_input_digest: str
    planning_artifact_digest: str

    decoder_plan_digest: str
    source_input_digest: str

    source_artifact_digest: str
    source_sha256: str

    validation_evidence_digest: str
    validation_code: str
    validation_passed: bool

    source: str

    authority_granted: int
    validation_authorized: bool
    execution_authorized: bool

    runtime_result_digest: str

    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "status": self.status,
            "request_id": self.request_id,
            "semantic_input_digest": (
                self.semantic_input_digest
            ),
            "topology_digest": (
                self.topology_digest
            ),
            "checkpoint_sha256": (
                self.checkpoint_sha256
            ),
            "materialization_digest": (
                self.materialization_digest
            ),
            "planning_input_digest": (
                self.planning_input_digest
            ),
            "planning_artifact_digest": (
                self.planning_artifact_digest
            ),
            "decoder_plan_digest": (
                self.decoder_plan_digest
            ),
            "source_input_digest": (
                self.source_input_digest
            ),
            "source_artifact_digest": (
                self.source_artifact_digest
            ),
            "source_sha256": (
                self.source_sha256
            ),
            "validation_evidence_digest": (
                self.validation_evidence_digest
            ),
            "validation_code": (
                self.validation_code
            ),
            "validation_passed": (
                self.validation_passed
            ),
            "source": self.source,
            "authority_granted": (
                self.authority_granted
            ),
            "validation_authorized": (
                self.validation_authorized
            ),
            "execution_authorized": (
                self.execution_authorized
            ),
        }

    def runtime_result_digest_computed(
        self,
    ) -> str:
        return _domain_digest(
            _RUNTIME_RESULT_DOMAIN,
            self.payload(),
        )

    def validate(
        self,
    ) -> None:
        if (
            self.schema
            != STRUCTURAL_GUIDANCE_RUNTIME_RESULT_SCHEMA
        ):
            raise StructuralGuidanceRuntimeError(
                "unsupported runtime result schema"
            )

        expected_status = (
            RUNTIME_STATUS_VALIDATED_SOURCE
            if self.validation_passed
            else RUNTIME_STATUS_VALIDATION_REJECTED
        )

        if self.status != expected_status:
            raise StructuralGuidanceRuntimeError(
                "runtime status/validation decision mismatch"
            )

        if (
            not isinstance(
                self.request_id,
                str,
            )
            or not self.request_id
        ):
            raise StructuralGuidanceRuntimeError(
                "request_id cannot be empty"
            )

        for name in (
            "semantic_input_digest",
            "topology_digest",
            "checkpoint_sha256",
            "materialization_digest",
            "planning_input_digest",
            "planning_artifact_digest",
            "decoder_plan_digest",
            "source_input_digest",
            "source_artifact_digest",
            "source_sha256",
            "validation_evidence_digest",
            "runtime_result_digest",
        ):
            if not _is_digest(
                getattr(self, name)
            ):
                raise StructuralGuidanceRuntimeError(
                    f"{name} must be SHA-256 hex"
                )

        if not isinstance(
            self.validation_passed,
            bool,
        ):
            raise StructuralGuidanceRuntimeError(
                "validation_passed must be bool"
            )

        if (
            not isinstance(
                self.validation_code,
                str,
            )
            or not self.validation_code
        ):
            raise StructuralGuidanceRuntimeError(
                "validation_code cannot be empty"
            )

        if not isinstance(
            self.source,
            str,
        ):
            raise StructuralGuidanceRuntimeError(
                "source must be str"
            )

        actual_source_sha = (
            hashlib.sha256(
                self.source.encode("utf-8")
            ).hexdigest()
        )

        if (
            actual_source_sha
            != self.source_sha256
        ):
            raise StructuralGuidanceRuntimeError(
                "terminal source SHA-256 mismatch"
            )

        if self.authority_granted != AUTHORITY_ZERO:
            raise StructuralGuidanceRuntimeError(
                "terminal result may not grant authority"
            )

        if self.validation_authorized is not False:
            raise StructuralGuidanceRuntimeError(
                "terminal result may not propagate validation authority"
            )

        if self.execution_authorized is not False:
            raise StructuralGuidanceRuntimeError(
                "terminal result may not authorize execution"
            )

        if (
            self.runtime_result_digest
            != self.runtime_result_digest_computed()
        ):
            raise StructuralGuidanceRuntimeError(
                "runtime result digest mismatch"
            )

    def validate_digest(
        self,
    ) -> bool:
        try:
            self.validate()
        except StructuralGuidanceRuntimeError:
            return False

        return True


def _terminal_result(
    *,
    request_id: str,
    topology,
    materialization,
    planning_input,
    planning_artifact,
    decoder_plan,
    source_input,
    source_artifact,
    evidence,
) -> StructuralGuidanceRuntimeResultV1:
    status = (
        RUNTIME_STATUS_VALIDATED_SOURCE
        if evidence.passed
        else RUNTIME_STATUS_VALIDATION_REJECTED
    )

    base = {
        "schema": (
            STRUCTURAL_GUIDANCE_RUNTIME_RESULT_SCHEMA
        ),
        "status": status,
        "request_id": request_id,
        "semantic_input_digest": (
            topology.semantic_input_digest
        ),
        "topology_digest": (
            topology.topology_digest
        ),
        "checkpoint_sha256": (
            topology.checkpoint_sha256
        ),
        "materialization_digest": (
            materialization.materialization_digest
        ),
        "planning_input_digest": (
            planning_input.planning_input_digest
        ),
        "planning_artifact_digest": (
            planning_artifact.planning_artifact_digest
        ),
        "decoder_plan_digest": (
            decoder_plan.decoder_plan_digest
        ),
        "source_input_digest": (
            source_input.source_input_digest
        ),
        "source_artifact_digest": (
            source_artifact.source_artifact_digest
        ),
        "source_sha256": (
            source_artifact.source_sha256
        ),
        "validation_evidence_digest": (
            evidence.evidence_digest
        ),
        "validation_code": (
            evidence.code
        ),
        "validation_passed": (
            evidence.passed
        ),
        "source": (
            source_artifact.source
        ),
        "authority_granted": 0,
        "validation_authorized": False,
        "execution_authorized": False,
    }

    unsigned = (
        StructuralGuidanceRuntimeResultV1(
            **base,
            runtime_result_digest="",
        )
    )

    signed = (
        StructuralGuidanceRuntimeResultV1(
            **base,
            runtime_result_digest=(
                unsigned
                .runtime_result_digest_computed()
            ),
        )
    )

    signed.validate()

    return signed


def run_structural_guidance_runtime(
    semantic_request: P0SemanticRequestV1,
    guidance_config: StructuralGuidanceAdmissionConfig,
    *,
    request_id: str,
    prompt: str,
    domain: str = "python",
    entrypoint: str = "solution",
    parameters: tuple[str, ...] = (),
    decoder_hints: tuple[
        tuple[str, str],
        ...,
    ] = (),
    allowed_experts: tuple[str, ...] = (
        "python.codegen",
        "python.ast",
        "python.tests",
        "python.typing",
    ),
    selected_experts: tuple[str, ...] = (
        "python.codegen",
        "python.ast",
        "python.tests",
        "python.typing",
    ),
    max_tokens: int = 512,
    debug_tag: str = "",
) -> StructuralGuidanceRuntimeResultV1:
    """Run one opted-in request through terminal static validation.

    The learned-guidance gate remains explicit and default-OFF.
    This function refuses a disabled guidance config because resolved topology
    materialization requires a real ADMITTED guidance result.

    Validation rejection is returned as a terminal authority-zero result.
    No generated source execution occurs in either terminal state.
    """

    if not isinstance(
        semantic_request,
        P0SemanticRequestV1,
    ):
        raise TypeError(
            "semantic_request must be P0SemanticRequestV1"
        )

    if not isinstance(
        guidance_config,
        StructuralGuidanceAdmissionConfig,
    ):
        raise TypeError(
            "guidance_config must be StructuralGuidanceAdmissionConfig"
        )

    if not guidance_config.enabled:
        raise StructuralGuidanceRuntimeError(
            "validated-source runtime requires explicit "
            "structural-guidance opt-in"
        )

    if (
        not isinstance(
            request_id,
            str,
        )
        or not request_id
    ):
        raise StructuralGuidanceRuntimeError(
            "request_id cannot be empty"
        )

    if not isinstance(
        prompt,
        str,
    ):
        raise TypeError(
            "prompt must be str"
        )

    projected = (
        project_semantic_request_and_admit(
            semantic_request,
            guidance_config,
            request_id=request_id,
            debug_tag=debug_tag,
        )
    )

    if projected.fallback_required:
        raise StructuralGuidanceRuntimeError(
            "structural-guidance admission required fallback"
        )

    if not projected.admitted:
        raise StructuralGuidanceRuntimeError(
            "structural-guidance request was not admitted"
        )

    topology = (
        build_resolved_structural_topology(
            projected
        )
    )

    observation = (
        DigestBoundResolvedTopologyObserverV1()
        .observe(
            topology
        )
    )

    materialization_authority = (
        _new_resolved_topology_materialization_authority()
    )

    materialization_intent = (
        materialization_authority
        ._precommit_from_owner(
            topology,
            observation,
            materializer_id=(
                CANONICAL_STRUCTURAL_MATERIALIZER_ID
            ),
            materializer_version=(
                CANONICAL_STRUCTURAL_MATERIALIZER_VERSION
            ),
        )
    )

    materialization_consumption = (
        materialization_authority
        ._consume_from_owner(
            materialization_authority
            ._reveal_from_owner(
                materialization_intent
            )
        )
    )

    materialization = (
        CanonicalResolvedTopologyMaterializerV1()
        .materialize(
            topology,
            materialization_consumption,
        )
    )

    planning_input = build_planning_input(
        materialization,
        request_id=request_id,
        prompt=prompt,
        domain=domain,
        entrypoint=entrypoint,
        parameters=parameters,
        decoder_hints=decoder_hints,
        allowed_experts=allowed_experts,
        selected_experts=selected_experts,
        max_tokens=max_tokens,
    )

    planning_authority = (
        _new_planning_authority()
    )

    planning_intent = (
        planning_authority
        ._precommit_from_owner(
            planning_input,
            planner_id=(
                DETERMINISTIC_STRUCTURAL_PLANNER_ID
            ),
            planner_version=(
                DETERMINISTIC_STRUCTURAL_PLANNER_VERSION
            ),
        )
    )

    planning_consumption = (
        planning_authority
        ._consume_from_owner(
            planning_authority
            ._reveal_from_owner(
                planning_intent
            )
        )
    )

    planning_artifact = (
        DeterministicStructuralPlannerV1()
        .plan(
            planning_input,
            planning_consumption,
        )
    )

    decoding_authority = (
        _new_decoding_authority()
    )

    decoding_intent = (
        decoding_authority
        ._precommit_from_owner(
            planning_artifact,
            decoder_adapter_id=(
                DETERMINISTIC_DECODER_ADAPTER_ID
            ),
            decoder_adapter_version=(
                DETERMINISTIC_DECODER_ADAPTER_VERSION
            ),
        )
    )

    decoding_consumption = (
        decoding_authority
        ._consume_from_owner(
            decoding_authority
            ._reveal_from_owner(
                decoding_intent
            )
        )
    )

    decoder_plan = (
        DeterministicDecoderAdapterV1()
        .adapt(
            planning_artifact,
            decoding_consumption,
        )
    )

    source_input = (
        build_decoder_source_input(
            decoder_plan,
            planning_input,
            prompt=prompt,
        )
    )

    source_emission_authority = (
        _new_source_emission_authority()
    )

    source_emission_intent = (
        source_emission_authority
        ._precommit_from_owner(
            source_input,
            source_emitter_id=(
                DETERMINISTIC_SOURCE_EMITTER_ID
            ),
            source_emitter_version=(
                DETERMINISTIC_SOURCE_EMITTER_VERSION
            ),
        )
    )

    source_emission_consumption = (
        source_emission_authority
        ._consume_from_owner(
            source_emission_authority
            ._reveal_from_owner(
                source_emission_intent
            )
        )
    )

    source_artifact = (
        DeterministicSourceEmitterV1()
        .emit(
            decoder_plan,
            source_input,
            source_emission_consumption,
        )
    )

    validation_authority = (
        _new_validation_authority()
    )

    validation_intent = (
        validation_authority
        ._precommit_from_owner(
            source_artifact,
            validator_id=(
                STRUCTURAL_PYTHON_AST_VALIDATOR_ID
            ),
            validator_version=(
                STRUCTURAL_PYTHON_AST_VALIDATOR_VERSION
            ),
        )
    )

    validation_consumption = (
        validation_authority
        ._consume_from_owner(
            validation_authority
            ._reveal_from_owner(
                validation_intent
            )
        )
    )

    evidence = (
        StructuralPythonASTValidatorV1()
        .validate(
            decoder_plan,
            source_artifact,
            validation_consumption,
        )
    )

    return _terminal_result(
        request_id=request_id,
        topology=topology,
        materialization=materialization,
        planning_input=planning_input,
        planning_artifact=planning_artifact,
        decoder_plan=decoder_plan,
        source_input=source_input,
        source_artifact=source_artifact,
        evidence=evidence,
    )
