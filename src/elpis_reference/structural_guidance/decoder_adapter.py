"""Deterministic decoder-plan adapter for structural guidance.

This adapter consumes a DECODING capability bound to one exact structural
planning artifact and adapter identity.

It performs only decoder-plan normalization:
* normalize requested Python identifiers;
* preserve the already-bound body lines;
* preserve the exact expert set and token bound;
* bind the resulting plan to the explicit structural-guidance lineage.

It does not emit source and does not execute anything.

Authority is deliberately non-transitive. Consuming DECODING authority
allows this adapter invocation, but the resulting plan carries authority
zero. A later source-emission boundary must authorize its own operation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import keyword
import re

from .decoding_authority import (
    DECODING_AUTHORITY,
    DecodingConsumptionV1,
)
from .planner import (
    DETERMINISTIC_PYTHON_TEMPLATE_TARGET,
    StructuralPlanningArtifactV1,
)


DECODER_SPECIFIC_PLAN_SCHEMA = (
    "elpis.structural-guidance.decoder-specific-plan.v1"
)

DETERMINISTIC_DECODER_ADAPTER_ID = (
    "elpis.structural-guidance."
    "deterministic-decoder-adapter"
)

DETERMINISTIC_DECODER_ADAPTER_VERSION = "v1"

_DECODER_PLAN_DOMAIN = (
    "elpis.structural-guidance."
    "decoder-specific-plan.v1"
)

_IDENTIFIER = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*"
)

_EXPERT_ID = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
)

_ID = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
)


class DecoderAdapterError(ValueError):
    """Fail-closed decoder-adapter rejection."""


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
    if not isinstance(value, str) or len(value) != 64:
        raise DecoderAdapterError(
            f"{name} must be SHA-256 hex"
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise DecoderAdapterError(
            f"{name} must be SHA-256 hex"
        ) from exc


def _require_nonempty(
    name: str,
    value: str,
) -> None:
    if not isinstance(value, str) or not value:
        raise DecoderAdapterError(
            f"{name} cannot be empty"
        )


def _safe_identifier(
    value: str,
    fallback: str,
) -> str:
    """Match the established deterministic Python identifier semantics."""

    value = value.strip()

    if (
        _IDENTIFIER.fullmatch(value)
        and not keyword.iskeyword(value)
    ):
        return value

    return fallback


@dataclass(frozen=True, slots=True)
class DecoderSpecificPlanV1:
    """Normalized decoder input with no reusable authority."""

    schema: str

    planning_artifact_digest: str
    decoding_consumption_digest: str

    planning_input_digest: str
    materialization_digest: str
    topology_digest: str
    semantic_input_digest: str

    request_id: str

    decoder_adapter_id: str
    decoder_adapter_version: str

    backend: str
    language: str
    temperature: float
    max_tokens: int

    selected_experts: tuple[str, ...]

    function_name: str
    parameters: tuple[str, ...]
    body_lines: tuple[str, ...]

    authority_applied: str
    authority_granted: int

    planning_authorized: bool
    decoding_authorized: bool
    source_emission_authorized: bool
    execution_authorized: bool

    decoder_plan_digest: str

    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "planning_artifact_digest": (
                self.planning_artifact_digest
            ),
            "decoding_consumption_digest": (
                self.decoding_consumption_digest
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
            "decoder_adapter_id": (
                self.decoder_adapter_id
            ),
            "decoder_adapter_version": (
                self.decoder_adapter_version
            ),
            "backend": (
                self.backend
            ),
            "language": (
                self.language
            ),
            "temperature": (
                self.temperature
            ),
            "max_tokens": (
                self.max_tokens
            ),
            "selected_experts": list(
                self.selected_experts
            ),
            "function_name": (
                self.function_name
            ),
            "parameters": list(
                self.parameters
            ),
            "body_lines": list(
                self.body_lines
            ),
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
            "execution_authorized": (
                self.execution_authorized
            ),
        }

    def decoder_plan_digest_computed(
        self,
    ) -> str:
        return _domain_digest(
            _DECODER_PLAN_DOMAIN,
            self.payload(),
        )

    def validate(
        self,
    ) -> None:
        if (
            self.schema
            != DECODER_SPECIFIC_PLAN_SCHEMA
        ):
            raise DecoderAdapterError(
                "unsupported decoder-specific plan schema"
            )

        for name, value in (
            (
                "planning_artifact_digest",
                self.planning_artifact_digest,
            ),
            (
                "decoding_consumption_digest",
                self.decoding_consumption_digest,
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
                "decoder_plan_digest",
                self.decoder_plan_digest,
            ),
        ):
            _require_digest(
                name,
                value,
            )

        _require_nonempty(
            "request_id",
            self.request_id,
        )

        if not _ID.fullmatch(
            self.decoder_adapter_id
        ):
            raise DecoderAdapterError(
                "invalid decoder_adapter_id"
            )

        if not _ID.fullmatch(
            self.decoder_adapter_version
        ):
            raise DecoderAdapterError(
                "invalid decoder_adapter_version"
            )

        if (
            self.backend
            != DETERMINISTIC_PYTHON_TEMPLATE_TARGET
        ):
            raise DecoderAdapterError(
                "unsupported decoder backend"
            )

        if self.language != "python":
            raise DecoderAdapterError(
                "unsupported decoder language"
            )

        if self.temperature != 0.0:
            raise DecoderAdapterError(
                "deterministic decoder temperature must be zero"
            )

        if (
            not isinstance(self.max_tokens, int)
            or isinstance(self.max_tokens, bool)
            or self.max_tokens <= 0
        ):
            raise DecoderAdapterError(
                "max_tokens must be a positive integer"
            )

        if (
            not isinstance(
                self.selected_experts,
                tuple,
            )
        ):
            raise DecoderAdapterError(
                "selected_experts must be a tuple"
            )

        if (
            len(set(self.selected_experts))
            != len(self.selected_experts)
        ):
            raise DecoderAdapterError(
                "selected_experts contains duplicates"
            )

        for expert in self.selected_experts:
            if (
                not isinstance(expert, str)
                or not _EXPERT_ID.fullmatch(expert)
            ):
                raise DecoderAdapterError(
                    "invalid selected expert identifier"
                )

        if (
            not isinstance(self.function_name, str)
            or not _IDENTIFIER.fullmatch(
                self.function_name
            )
            or keyword.iskeyword(
                self.function_name
            )
        ):
            raise DecoderAdapterError(
                "function_name must be a safe Python identifier"
            )

        if not isinstance(
            self.parameters,
            tuple,
        ):
            raise DecoderAdapterError(
                "parameters must be a tuple"
            )

        for value in self.parameters:
            if (
                not isinstance(value, str)
                or not _IDENTIFIER.fullmatch(value)
                or keyword.iskeyword(value)
            ):
                raise DecoderAdapterError(
                    "parameters must be safe Python identifiers"
                )

        if len(
            set(self.parameters)
        ) != len(
            self.parameters
        ):
            raise DecoderAdapterError(
                "normalized parameters must be unique"
            )

        if not isinstance(
            self.body_lines,
            tuple,
        ):
            raise DecoderAdapterError(
                "body_lines must be a tuple"
            )

        if not self.body_lines:
            raise DecoderAdapterError(
                "body_lines cannot be empty"
            )

        for line in self.body_lines:
            if not isinstance(
                line,
                str,
            ):
                raise DecoderAdapterError(
                    "body_lines entries must be strings"
                )

        if (
            self.authority_applied
            != DECODING_AUTHORITY
        ):
            raise DecoderAdapterError(
                "decoder plan has wrong applied authority"
            )

        if self.authority_granted != 0:
            raise DecoderAdapterError(
                "decoder plan may not grant authority"
            )

        if self.planning_authorized is not False:
            raise DecoderAdapterError(
                "decoder plan may not authorize planning"
            )

        if self.decoding_authorized is not False:
            raise DecoderAdapterError(
                "decoder plan may not propagate decoding authority"
            )

        if (
            self.source_emission_authorized
            is not False
        ):
            raise DecoderAdapterError(
                "decoder plan may not authorize source emission"
            )

        if self.execution_authorized is not False:
            raise DecoderAdapterError(
                "decoder plan may not authorize execution"
            )

        if (
            self.decoder_plan_digest
            != self.decoder_plan_digest_computed()
        ):
            raise DecoderAdapterError(
                "decoder plan digest mismatch"
            )

    def validate_digest(
        self,
    ) -> bool:
        try:
            self.validate()
        except DecoderAdapterError:
            return False

        return True


@dataclass(frozen=True, slots=True)
class DeterministicDecoderAdapterV1:
    """Normalize one authorized structural planning artifact."""

    decoder_adapter_id: str = (
        DETERMINISTIC_DECODER_ADAPTER_ID
    )

    decoder_adapter_version: str = (
        DETERMINISTIC_DECODER_ADAPTER_VERSION
    )

    def __post_init__(
        self,
    ) -> None:
        if not _ID.fullmatch(
            self.decoder_adapter_id
        ):
            raise DecoderAdapterError(
                "invalid decoder_adapter_id"
            )

        if not _ID.fullmatch(
            self.decoder_adapter_version
        ):
            raise DecoderAdapterError(
                "invalid decoder_adapter_version"
            )

    def adapt(
        self,
        planning_artifact: StructuralPlanningArtifactV1,
        consumption: DecodingConsumptionV1,
    ) -> DecoderSpecificPlanV1:
        if not isinstance(
            planning_artifact,
            StructuralPlanningArtifactV1,
        ):
            raise TypeError(
                "planning_artifact must be "
                "StructuralPlanningArtifactV1"
            )

        planning_artifact.validate()

        if not planning_artifact.validate_digest():
            raise DecoderAdapterError(
                "planning artifact digest is invalid"
            )

        if not isinstance(
            consumption,
            DecodingConsumptionV1,
        ):
            raise TypeError(
                "consumption must be DecodingConsumptionV1"
            )

        consumption.validate()

        bindings = (
            (
                "planning_artifact_digest",
                consumption.planning_artifact_digest,
                planning_artifact.planning_artifact_digest,
            ),
            (
                "planning_input_digest",
                consumption.planning_input_digest,
                planning_artifact.planning_input_digest,
            ),
            (
                "planning_consumption_digest",
                consumption.planning_consumption_digest,
                planning_artifact.planning_consumption_digest,
            ),
            (
                "materialization_digest",
                consumption.materialization_digest,
                planning_artifact.materialization_digest,
            ),
            (
                "topology_digest",
                consumption.topology_digest,
                planning_artifact.topology_digest,
            ),
            (
                "semantic_input_digest",
                consumption.semantic_input_digest,
                planning_artifact.semantic_input_digest,
            ),
            (
                "request_id",
                consumption.request_id,
                planning_artifact.request_id,
            ),
        )

        for name, actual, expected in bindings:
            if actual != expected:
                raise DecoderAdapterError(
                    f"decoding consumption {name} mismatch"
                )

        if (
            consumption.decoder_adapter_id
            != self.decoder_adapter_id
        ):
            raise DecoderAdapterError(
                "decoding consumption adapter identity mismatch"
            )

        if (
            consumption.decoder_adapter_version
            != self.decoder_adapter_version
        ):
            raise DecoderAdapterError(
                "decoding consumption adapter version mismatch"
            )

        if consumption.authority != DECODING_AUTHORITY:
            raise DecoderAdapterError(
                "decoding consumption has wrong authority"
            )

        if consumption.planning_authorized is not False:
            raise DecoderAdapterError(
                "decoding consumption improperly authorizes planning"
            )

        if consumption.decoding_authorized is not True:
            raise DecoderAdapterError(
                "decoding consumption lacks decoding authority"
            )

        if consumption.execution_authorized is not False:
            raise DecoderAdapterError(
                "decoding consumption improperly authorizes execution"
            )

        if planning_artifact.decoding_authorized is not False:
            raise DecoderAdapterError(
                "planning artifact unexpectedly carries decoding authority"
            )

        if planning_artifact.execution_authorized is not False:
            raise DecoderAdapterError(
                "planning artifact unexpectedly carries execution authority"
            )

        function_name = _safe_identifier(
            planning_artifact.requested_entrypoint,
            "solution",
        )

        parameters = tuple(
            _safe_identifier(
                value,
                f"arg_{index}",
            )
            for index, value
            in enumerate(
                planning_artifact.requested_parameters
            )
        )

        if len(
            set(parameters)
        ) != len(parameters):
            raise DecoderAdapterError(
                "identifier normalization produced duplicate parameters"
            )

        body_lines = (
            planning_artifact.body_lines
            or ("return None",)
        )

        base = {
            "schema": (
                DECODER_SPECIFIC_PLAN_SCHEMA
            ),
            "planning_artifact_digest": (
                planning_artifact.planning_artifact_digest
            ),
            "decoding_consumption_digest": (
                consumption.consumption_digest
            ),
            "planning_input_digest": (
                planning_artifact.planning_input_digest
            ),
            "materialization_digest": (
                planning_artifact.materialization_digest
            ),
            "topology_digest": (
                planning_artifact.topology_digest
            ),
            "semantic_input_digest": (
                planning_artifact.semantic_input_digest
            ),
            "request_id": (
                planning_artifact.request_id
            ),
            "decoder_adapter_id": (
                self.decoder_adapter_id
            ),
            "decoder_adapter_version": (
                self.decoder_adapter_version
            ),
            "backend": (
                planning_artifact.backend_target
            ),
            "language": (
                planning_artifact.target_language
            ),
            "temperature": 0.0,
            "max_tokens": (
                planning_artifact.max_tokens
            ),
            "selected_experts": (
                planning_artifact.selected_experts
            ),
            "function_name": (
                function_name
            ),
            "parameters": (
                parameters
            ),
            "body_lines": (
                body_lines
            ),
            "authority_applied": (
                DECODING_AUTHORITY
            ),
            "authority_granted": 0,
            "planning_authorized": False,
            "decoding_authorized": False,
            "source_emission_authorized": False,
            "execution_authorized": False,
        }

        plan = DecoderSpecificPlanV1(
            **base,
            decoder_plan_digest=_domain_digest(
                _DECODER_PLAN_DOMAIN,
                base,
            ),
        )

        plan.validate()

        return plan
