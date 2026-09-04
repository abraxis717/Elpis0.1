"""Native structural-guidance validation over the canonical Python AST policy.

This module does not reimplement AST policy and does not manufacture legacy
P0 request/artifact/result objects.

Validation requires:
* the exact authority-zero DecoderSpecificPlanV1;
* the exact authority-zero DecodedSourceArtifactV1 bound to that plan; and
* one consumed VALIDATION capability bound to that source artifact and this
  validator identity.

The resulting evidence carries no reusable validation or execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from elpis.python_ast_policy import (
    PythonASTPolicyDecisionV1,
    evaluate_python_ast_policy,
)

from .decoder_adapter import (
    DecoderSpecificPlanV1,
)
from .source_emitter import (
    DecodedSourceArtifactV1,
)
from .validation_authority import (
    VALIDATION_AUTHORITY,
    ValidationConsumptionV1,
)


STRUCTURAL_VALIDATION_EVIDENCE_SCHEMA = (
    "elpis.structural-guidance."
    "validation-evidence.v1"
)

STRUCTURAL_PYTHON_AST_VALIDATOR_ID = (
    "python.ast.v1"
)

STRUCTURAL_PYTHON_AST_VALIDATOR_VERSION = (
    "v1"
)

_EVIDENCE_DOMAIN = (
    "elpis.structural-guidance."
    "validation-evidence.v1"
)

_ID = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
)


class StructuralValidationError(ValueError):
    """Fail-closed structural validation rejection."""


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


def _require_digest(
    name: str,
    value: str,
) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
    ):
        raise StructuralValidationError(
            f"{name} must be SHA-256 hex"
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise StructuralValidationError(
            f"{name} must be SHA-256 hex"
        ) from exc


def _policy_evidence(
    decision: PythonASTPolicyDecisionV1,
    *,
    entrypoint: str,
) -> tuple[
    bool,
    str,
    str,
    tuple[tuple[str, object], ...],
]:
    code = decision.code

    if code == "LANGUAGE_MISMATCH":
        return (
            False,
            code,
            (
                "PythonASTValidator received "
                "a non-Python artifact"
            ),
            (),
        )

    if code == "SYNTAX_ERROR":
        return (
            False,
            code,
            decision.syntax_message,
            (
                (
                    "lineno",
                    decision.lineno,
                ),
                (
                    "offset",
                    decision.offset,
                ),
            ),
        )

    if code == "ENTRYPOINT_MISSING":
        return (
            False,
            code,
            (
                "expected function "
                f"{entrypoint!r} "
                "was not defined"
            ),
            (
                (
                    "functions",
                    decision.functions,
                ),
            ),
        )

    if code == "IMPORT_FORBIDDEN":
        return (
            False,
            code,
            (
                "P0 template artifacts "
                "may not import modules"
            ),
            (
                (
                    "lineno",
                    decision.lineno,
                ),
            ),
        )

    if code == "SCOPE_MUTATION_FORBIDDEN":
        return (
            False,
            code,
            (
                "global/nonlocal mutation "
                "is forbidden in P0"
            ),
            (
                (
                    "lineno",
                    decision.lineno,
                ),
            ),
        )

    if code == "BANNED_CALL":
        return (
            False,
            code,
            (
                f"call to {decision.call_name!r} "
                "is forbidden in P0"
            ),
            (
                (
                    "lineno",
                    decision.lineno,
                ),
            ),
        )

    if (
        code == "AST_VALID"
        and decision.passed
    ):
        return (
            True,
            code,
            (
                "artifact parsed and passed "
                "P0 static policy"
            ),
            (
                (
                    "entrypoint",
                    entrypoint,
                ),
                (
                    "node_count",
                    decision.node_count,
                ),
            ),
        )

    raise StructuralValidationError(
        "canonical Python AST policy returned "
        "an unsupported decision"
    )


@dataclass(frozen=True, slots=True)
class StructuralValidationEvidenceV1:
    schema: str

    source_artifact_digest: str
    source_sha256: str

    decoder_plan_digest: str
    validation_consumption_digest: str

    planning_input_digest: str
    materialization_digest: str
    topology_digest: str
    semantic_input_digest: str

    request_id: str

    validator_id: str
    validator_version: str

    passed: bool
    code: str
    message: str
    details: tuple[
        tuple[str, object],
        ...,
    ]

    authority_applied: str
    authority_granted: int

    planning_authorized: bool
    decoding_authorized: bool
    source_emission_authorized: bool
    validation_authorized: bool
    execution_authorized: bool

    evidence_digest: str

    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_artifact_digest": (
                self.source_artifact_digest
            ),
            "source_sha256": (
                self.source_sha256
            ),
            "decoder_plan_digest": (
                self.decoder_plan_digest
            ),
            "validation_consumption_digest": (
                self.validation_consumption_digest
            ),
            "planning_input_digest": (
                self.planning_input_digest
            ),
            "materialization_digest": (
                self.materialization_digest
            ),
            "topology_digest": (
                self.topology_digest
            ),
            "semantic_input_digest": (
                self.semantic_input_digest
            ),
            "request_id": (
                self.request_id
            ),
            "validator_id": (
                self.validator_id
            ),
            "validator_version": (
                self.validator_version
            ),
            "passed": (
                self.passed
            ),
            "code": (
                self.code
            ),
            "message": (
                self.message
            ),
            "details": [
                [
                    key,
                    value,
                ]
                for key, value
                in self.details
            ],
            "authority_applied": (
                self.authority_applied
            ),
            "authority_granted": (
                self.authority_granted
            ),
            "planning_authorized": (
                self.planning_authorized
            ),
            "decoding_authorized": (
                self.decoding_authorized
            ),
            "source_emission_authorized": (
                self.source_emission_authorized
            ),
            "validation_authorized": (
                self.validation_authorized
            ),
            "execution_authorized": (
                self.execution_authorized
            ),
        }

    def evidence_digest_computed(
        self,
    ) -> str:
        return _domain_digest(
            _EVIDENCE_DOMAIN,
            self.payload(),
        )

    def validate(
        self,
    ) -> None:
        if (
            self.schema
            != STRUCTURAL_VALIDATION_EVIDENCE_SCHEMA
        ):
            raise StructuralValidationError(
                "unsupported structural validation evidence schema"
            )

        for name, value in (
            (
                "source_artifact_digest",
                self.source_artifact_digest,
            ),
            (
                "source_sha256",
                self.source_sha256,
            ),
            (
                "decoder_plan_digest",
                self.decoder_plan_digest,
            ),
            (
                "validation_consumption_digest",
                self.validation_consumption_digest,
            ),
            (
                "planning_input_digest",
                self.planning_input_digest,
            ),
            (
                "materialization_digest",
                self.materialization_digest,
            ),
            (
                "topology_digest",
                self.topology_digest,
            ),
            (
                "semantic_input_digest",
                self.semantic_input_digest,
            ),
            (
                "evidence_digest",
                self.evidence_digest,
            ),
        ):
            _require_digest(
                name,
                value,
            )

        if (
            not isinstance(self.request_id, str)
            or not self.request_id
        ):
            raise StructuralValidationError(
                "request_id cannot be empty"
            )

        if (
            not isinstance(self.validator_id, str)
            or not _ID.fullmatch(
                self.validator_id
            )
        ):
            raise StructuralValidationError(
                "invalid validator_id"
            )

        if (
            not isinstance(
                self.validator_version,
                str,
            )
            or not _ID.fullmatch(
                self.validator_version
            )
        ):
            raise StructuralValidationError(
                "invalid validator_version"
            )

        if not isinstance(
            self.passed,
            bool,
        ):
            raise StructuralValidationError(
                "passed must be bool"
            )

        if (
            not isinstance(self.code, str)
            or not self.code
        ):
            raise StructuralValidationError(
                "code cannot be empty"
            )

        if not isinstance(
            self.message,
            str,
        ):
            raise StructuralValidationError(
                "message must be string"
            )

        if not isinstance(
            self.details,
            tuple,
        ):
            raise StructuralValidationError(
                "details must be tuple"
            )

        canonical_details = []

        for index, item in enumerate(
            self.details
        ):
            if (
                not isinstance(
                    item,
                    tuple,
                )
                or len(item) != 2
            ):
                raise StructuralValidationError(
                    f"details[{index}] must be key/value tuple"
                )

            key, value = item

            if (
                not isinstance(key, str)
                or not key
            ):
                raise StructuralValidationError(
                    f"details[{index}] key invalid"
                )

            canonical_details.append(
                [
                    key,
                    value,
                ]
            )

        try:
            _canonical_json_bytes(
                canonical_details
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise StructuralValidationError(
                "details are not canonical JSON data"
            ) from exc

        if (
            self.authority_applied
            != VALIDATION_AUTHORITY
        ):
            raise StructuralValidationError(
                "wrong applied authority"
            )

        if self.authority_granted != 0:
            raise StructuralValidationError(
                "validation evidence may not grant authority"
            )

        if self.planning_authorized is not False:
            raise StructuralValidationError(
                "validation evidence may not authorize planning"
            )

        if self.decoding_authorized is not False:
            raise StructuralValidationError(
                "validation evidence may not authorize decoding"
            )

        if (
            self.source_emission_authorized
            is not False
        ):
            raise StructuralValidationError(
                "validation evidence may not authorize source emission"
            )

        if self.validation_authorized is not False:
            raise StructuralValidationError(
                "validation evidence may not propagate validation authority"
            )

        if self.execution_authorized is not False:
            raise StructuralValidationError(
                "validation evidence may not authorize execution"
            )

        if (
            self.evidence_digest
            != self.evidence_digest_computed()
        ):
            raise StructuralValidationError(
                "validation evidence digest mismatch"
            )

    def validate_digest(
        self,
    ) -> bool:
        try:
            self.validate()
        except StructuralValidationError:
            return False

        return True


@dataclass(frozen=True, slots=True)
class StructuralPythonASTValidatorV1:
    validator_id: str = (
        STRUCTURAL_PYTHON_AST_VALIDATOR_ID
    )

    validator_version: str = (
        STRUCTURAL_PYTHON_AST_VALIDATOR_VERSION
    )

    def __post_init__(
        self,
    ) -> None:
        if (
            not _ID.fullmatch(
                self.validator_id
            )
        ):
            raise StructuralValidationError(
                "invalid validator_id"
            )

        if (
            not _ID.fullmatch(
                self.validator_version
            )
        ):
            raise StructuralValidationError(
                "invalid validator_version"
            )

    def validate(
        self,
        decoder_plan: DecoderSpecificPlanV1,
        artifact: DecodedSourceArtifactV1,
        consumption: ValidationConsumptionV1,
    ) -> StructuralValidationEvidenceV1:
        if not isinstance(
            decoder_plan,
            DecoderSpecificPlanV1,
        ):
            raise TypeError(
                "decoder_plan must be DecoderSpecificPlanV1"
            )

        decoder_plan.validate()

        if not decoder_plan.validate_digest():
            raise StructuralValidationError(
                "decoder plan digest invalid"
            )

        if not isinstance(
            artifact,
            DecodedSourceArtifactV1,
        ):
            raise TypeError(
                "artifact must be DecodedSourceArtifactV1"
            )

        artifact.validate()

        if not artifact.validate_digest():
            raise StructuralValidationError(
                "source artifact digest invalid"
            )

        if not isinstance(
            consumption,
            ValidationConsumptionV1,
        ):
            raise TypeError(
                "consumption must be ValidationConsumptionV1"
            )

        consumption.validate()

        artifact_plan_bindings = (
            (
                "decoder_plan_digest",
                artifact.decoder_plan_digest,
                decoder_plan.decoder_plan_digest,
            ),
            (
                "planning_input_digest",
                artifact.planning_input_digest,
                decoder_plan.planning_input_digest,
            ),
            (
                "materialization_digest",
                artifact.materialization_digest,
                decoder_plan.materialization_digest,
            ),
            (
                "topology_digest",
                artifact.topology_digest,
                decoder_plan.topology_digest,
            ),
            (
                "semantic_input_digest",
                artifact.semantic_input_digest,
                decoder_plan.semantic_input_digest,
            ),
            (
                "request_id",
                artifact.request_id,
                decoder_plan.request_id,
            ),
        )

        for (
            name,
            actual,
            expected,
        ) in artifact_plan_bindings:
            if actual != expected:
                raise StructuralValidationError(
                    f"artifact {name} mismatch"
                )

        consumption_bindings = (
            (
                "source_artifact_digest",
                consumption.source_artifact_digest,
                artifact.source_artifact_digest,
            ),
            (
                "source_sha256",
                consumption.source_sha256,
                artifact.source_sha256,
            ),
            (
                "decoder_plan_digest",
                consumption.decoder_plan_digest,
                decoder_plan.decoder_plan_digest,
            ),
            (
                "source_input_digest",
                consumption.source_input_digest,
                artifact.source_input_digest,
            ),
            (
                "planning_input_digest",
                consumption.planning_input_digest,
                artifact.planning_input_digest,
            ),
            (
                "materialization_digest",
                consumption.materialization_digest,
                artifact.materialization_digest,
            ),
            (
                "topology_digest",
                consumption.topology_digest,
                artifact.topology_digest,
            ),
            (
                "semantic_input_digest",
                consumption.semantic_input_digest,
                artifact.semantic_input_digest,
            ),
            (
                "request_id",
                consumption.request_id,
                artifact.request_id,
            ),
        )

        for (
            name,
            actual,
            expected,
        ) in consumption_bindings:
            if actual != expected:
                raise StructuralValidationError(
                    f"validation consumption {name} mismatch"
                )

        if (
            consumption.validator_id
            != self.validator_id
        ):
            raise StructuralValidationError(
                "validation consumption validator identity mismatch"
            )

        if (
            consumption.validator_version
            != self.validator_version
        ):
            raise StructuralValidationError(
                "validation consumption validator version mismatch"
            )

        if (
            consumption.authority
            != VALIDATION_AUTHORITY
        ):
            raise StructuralValidationError(
                "validation consumption has wrong authority"
            )

        if consumption.planning_authorized is not False:
            raise StructuralValidationError(
                "validation consumption improperly authorizes planning"
            )

        if consumption.decoding_authorized is not False:
            raise StructuralValidationError(
                "validation consumption improperly authorizes decoding"
            )

        if (
            consumption.source_emission_authorized
            is not False
        ):
            raise StructuralValidationError(
                "validation consumption improperly authorizes source emission"
            )

        if consumption.validation_authorized is not True:
            raise StructuralValidationError(
                "validation consumption lacks validation authority"
            )

        if consumption.execution_authorized is not False:
            raise StructuralValidationError(
                "validation consumption improperly authorizes execution"
            )

        if decoder_plan.authority_granted != 0:
            raise StructuralValidationError(
                "decoder plan improperly grants authority"
            )

        if artifact.authority_granted != 0:
            raise StructuralValidationError(
                "source artifact improperly grants authority"
            )

        if decoder_plan.execution_authorized is not False:
            raise StructuralValidationError(
                "decoder plan improperly authorizes execution"
            )

        if artifact.execution_authorized is not False:
            raise StructuralValidationError(
                "source artifact improperly authorizes execution"
            )

        decision = evaluate_python_ast_policy(
            language=artifact.language,
            source=artifact.source,
            entrypoint=decoder_plan.function_name,
        )

        (
            passed,
            code,
            message,
            details,
        ) = _policy_evidence(
            decision,
            entrypoint=decoder_plan.function_name,
        )

        base = {
            "schema": (
                STRUCTURAL_VALIDATION_EVIDENCE_SCHEMA
            ),
            "source_artifact_digest": (
                artifact.source_artifact_digest
            ),
            "source_sha256": (
                artifact.source_sha256
            ),
            "decoder_plan_digest": (
                decoder_plan.decoder_plan_digest
            ),
            "validation_consumption_digest": (
                consumption.consumption_digest
            ),
            "planning_input_digest": (
                artifact.planning_input_digest
            ),
            "materialization_digest": (
                artifact.materialization_digest
            ),
            "topology_digest": (
                artifact.topology_digest
            ),
            "semantic_input_digest": (
                artifact.semantic_input_digest
            ),
            "request_id": (
                artifact.request_id
            ),
            "validator_id": (
                self.validator_id
            ),
            "validator_version": (
                self.validator_version
            ),
            "passed": (
                passed
            ),
            "code": (
                code
            ),
            "message": (
                message
            ),
            "details": (
                details
            ),
            "authority_applied": (
                VALIDATION_AUTHORITY
            ),
            "authority_granted": 0,
            "planning_authorized": False,
            "decoding_authorized": False,
            "source_emission_authorized": False,
            "validation_authorized": False,
            "execution_authorized": False,
        }

        evidence = (
            StructuralValidationEvidenceV1(
                **base,
                evidence_digest=_domain_digest(
                    _EVIDENCE_DOMAIN,
                    {
                        **base,
                        "details": [
                            [
                                key,
                                value,
                            ]
                            for key, value
                            in details
                        ],
                    },
                ),
            )
        )

        evidence.validate()

        return evidence
