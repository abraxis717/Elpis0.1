"""Deterministic non-executable planner for structural guidance.

The planner requires:

* one valid authority-zero PlanningInputV1; and
* one consumed PLANNING capability bound to that exact input and planner.

It produces a StructuralPlanningArtifactV1 only.

Important boundary:

This planner deliberately does NOT construct the legacy decoder-specific plan contract.
In particular it does not sanitize requested identifiers, construct Python
source, decode an artifact, or execute anything. Requested entrypoint and
parameter names remain data at this layer.

A future DECODING-authorized adapter may transform this planning artifact
into decoder-specific input.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from .planning_authority import (
    PLANNING_AUTHORITY,
    PlanningConsumptionV1,
)
from .planning_input import (
    PlanningInputV1,
)


STRUCTURAL_PLANNING_ARTIFACT_SCHEMA = (
    "elpis.structural-guidance."
    "structural-planning-artifact.v1"
)

DETERMINISTIC_STRUCTURAL_PLANNER_ID = (
    "elpis.structural-guidance.deterministic-planner"
)

DETERMINISTIC_STRUCTURAL_PLANNER_VERSION = "v1"

DETERMINISTIC_PYTHON_TEMPLATE_TARGET = (
    "deterministic-python-template-v1"
)

_PLANNING_ARTIFACT_DOMAIN = (
    "elpis.structural-guidance."
    "structural-planning-artifact.v1"
)

_ID = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
)


class StructuralPlanningError(ValueError):
    """Fail-closed deterministic-planning rejection."""


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
        raise StructuralPlanningError(
            f"{name} must be SHA-256 hex"
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise StructuralPlanningError(
            f"{name} must be SHA-256 hex"
        ) from exc


def _require_nonempty(
    name: str,
    value: object,
) -> str:
    if not isinstance(value, str) or not value:
        raise StructuralPlanningError(
            f"{name} must be a non-empty string"
        )

    return value


def _require_string_tuple(
    name: str,
    values: tuple[str, ...],
) -> None:
    if not isinstance(values, tuple):
        raise StructuralPlanningError(
            f"{name} must be a tuple"
        )

    for value in values:
        if not isinstance(value, str):
            raise StructuralPlanningError(
                f"{name} entries must be strings"
            )


@dataclass(frozen=True, slots=True)
class StructuralPlanningArtifactV1:
    """Digest-bound planning result with no decoding/execution authority."""

    schema: str

    planning_input_digest: str
    planning_consumption_digest: str

    materialization_digest: str
    topology_digest: str
    semantic_input_digest: str

    request_id: str
    request_sidecar_digest: str
    expert_selection_digest: str

    planner_id: str
    planner_version: str

    target_language: str
    backend_target: str

    requested_entrypoint: str
    requested_parameters: tuple[str, ...]
    body_lines: tuple[str, ...]
    selected_experts: tuple[str, ...]
    max_tokens: int

    authority: str
    planning_authorized: bool
    decoding_authorized: bool
    execution_authorized: bool

    planning_artifact_digest: str

    def payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "planning_input_digest": (
                self.planning_input_digest
            ),
            "planning_consumption_digest": (
                self.planning_consumption_digest
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
            "request_id": self.request_id,
            "request_sidecar_digest": (
                self.request_sidecar_digest
            ),
            "expert_selection_digest": (
                self.expert_selection_digest
            ),
            "planner_id": self.planner_id,
            "planner_version": (
                self.planner_version
            ),
            "target_language": (
                self.target_language
            ),
            "backend_target": (
                self.backend_target
            ),
            "requested_entrypoint": (
                self.requested_entrypoint
            ),
            "requested_parameters": list(
                self.requested_parameters
            ),
            "body_lines": list(
                self.body_lines
            ),
            "selected_experts": list(
                self.selected_experts
            ),
            "max_tokens": self.max_tokens,
            "authority": self.authority,
            "planning_authorized": (
                self.planning_authorized
            ),
            "decoding_authorized": (
                self.decoding_authorized
            ),
            "execution_authorized": (
                self.execution_authorized
            ),
        }

    def planning_artifact_digest_computed(
        self,
    ) -> str:
        return _domain_digest(
            _PLANNING_ARTIFACT_DOMAIN,
            self.payload(),
        )

    def validate(self) -> None:
        if (
            self.schema
            != STRUCTURAL_PLANNING_ARTIFACT_SCHEMA
        ):
            raise StructuralPlanningError(
                "unsupported structural planning artifact schema"
            )

        for name, value in (
            (
                "planning_input_digest",
                self.planning_input_digest,
            ),
            (
                "planning_consumption_digest",
                self.planning_consumption_digest,
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
                "request_sidecar_digest",
                self.request_sidecar_digest,
            ),
            (
                "expert_selection_digest",
                self.expert_selection_digest,
            ),
            (
                "planning_artifact_digest",
                self.planning_artifact_digest,
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
            self.planner_id
        ):
            raise StructuralPlanningError(
                "invalid planner_id"
            )

        if not _ID.fullmatch(
            self.planner_version
        ):
            raise StructuralPlanningError(
                "invalid planner_version"
            )

        if self.target_language != "python":
            raise StructuralPlanningError(
                "unsupported target language"
            )

        if (
            self.backend_target
            != DETERMINISTIC_PYTHON_TEMPLATE_TARGET
        ):
            raise StructuralPlanningError(
                "unsupported backend target"
            )

        _require_nonempty(
            "requested_entrypoint",
            self.requested_entrypoint,
        )

        _require_string_tuple(
            "requested_parameters",
            self.requested_parameters,
        )

        _require_string_tuple(
            "body_lines",
            self.body_lines,
        )

        if not self.body_lines:
            raise StructuralPlanningError(
                "body_lines cannot be empty"
            )

        _require_string_tuple(
            "selected_experts",
            self.selected_experts,
        )

        if len(
            set(self.selected_experts)
        ) != len(
            self.selected_experts
        ):
            raise StructuralPlanningError(
                "selected_experts contains duplicates"
            )

        for expert in self.selected_experts:
            if not _ID.fullmatch(expert):
                raise StructuralPlanningError(
                    "invalid selected expert identifier"
                )

        if (
            not isinstance(self.max_tokens, int)
            or isinstance(self.max_tokens, bool)
            or self.max_tokens <= 0
        ):
            raise StructuralPlanningError(
                "max_tokens must be a positive integer"
            )

        if self.authority != PLANNING_AUTHORITY:
            raise StructuralPlanningError(
                "planning artifact has wrong authority"
            )

        if self.planning_authorized is not True:
            raise StructuralPlanningError(
                "planning artifact must reflect planning authorization"
            )

        if self.decoding_authorized is not False:
            raise StructuralPlanningError(
                "planning artifact may not authorize decoding"
            )

        if self.execution_authorized is not False:
            raise StructuralPlanningError(
                "planning artifact may not authorize execution"
            )

        if (
            self.planning_artifact_digest
            != self.planning_artifact_digest_computed()
        ):
            raise StructuralPlanningError(
                "planning artifact digest mismatch"
            )

    def validate_digest(self) -> bool:
        try:
            self.validate()
        except StructuralPlanningError:
            return False

        return True


@dataclass(frozen=True, slots=True)
class DeterministicStructuralPlannerV1:
    """Pure deterministic planner with PLANNING authority only."""

    planner_id: str = (
        DETERMINISTIC_STRUCTURAL_PLANNER_ID
    )
    planner_version: str = (
        DETERMINISTIC_STRUCTURAL_PLANNER_VERSION
    )

    def __post_init__(self) -> None:
        if not _ID.fullmatch(
            self.planner_id
        ):
            raise StructuralPlanningError(
                "invalid planner_id"
            )

        if not _ID.fullmatch(
            self.planner_version
        ):
            raise StructuralPlanningError(
                "invalid planner_version"
            )

    def plan(
        self,
        planning_input: PlanningInputV1,
        consumption: PlanningConsumptionV1,
    ) -> StructuralPlanningArtifactV1:
        if not isinstance(
            planning_input,
            PlanningInputV1,
        ):
            raise TypeError(
                "planning_input must be PlanningInputV1"
            )

        planning_input.validate()

        if not planning_input.validate_digest():
            raise StructuralPlanningError(
                "planning input digest is invalid"
            )

        if not isinstance(
            consumption,
            PlanningConsumptionV1,
        ):
            raise TypeError(
                "consumption must be PlanningConsumptionV1"
            )

        consumption.validate()

        bindings = (
            (
                "planning_input_digest",
                consumption.planning_input_digest,
                planning_input.planning_input_digest,
            ),
            (
                "materialization_digest",
                consumption.materialization_digest,
                planning_input.materialization_digest,
            ),
            (
                "topology_digest",
                consumption.topology_digest,
                planning_input.topology_digest,
            ),
            (
                "request_id",
                consumption.request_id,
                planning_input.request_id,
            ),
        )

        for name, actual, expected in bindings:
            if actual != expected:
                raise StructuralPlanningError(
                    f"planning consumption {name} mismatch"
                )

        if consumption.planner_id != self.planner_id:
            raise StructuralPlanningError(
                "planning consumption planner identity mismatch"
            )

        if (
            consumption.planner_version
            != self.planner_version
        ):
            raise StructuralPlanningError(
                "planning consumption planner version mismatch"
            )

        if consumption.authority != PLANNING_AUTHORITY:
            raise StructuralPlanningError(
                "planning consumption has wrong authority"
            )

        if consumption.planning_authorized is not True:
            raise StructuralPlanningError(
                "planning consumption does not authorize planning"
            )

        if consumption.decoding_authorized is not False:
            raise StructuralPlanningError(
                "planning consumption improperly authorizes decoding"
            )

        if consumption.execution_authorized is not False:
            raise StructuralPlanningError(
                "planning consumption improperly authorizes execution"
            )

        if planning_input.authority_granted != 0:
            raise StructuralPlanningError(
                "planning input improperly carries authority"
            )

        if (
            planning_input.planning_authorized
            or planning_input.decoding_authorized
            or planning_input.execution_authorized
        ):
            raise StructuralPlanningError(
                "planning input improperly carries authorization"
            )

        if planning_input.domain != "python":
            raise StructuralPlanningError(
                "deterministic planner currently supports python only"
            )

        hints = dict(
            planning_input.decoder_hints
        )

        body = hints.get(
            "body",
            "return None",
        )

        body_lines = (
            tuple(
                body.splitlines()
            )
            or ("return None",)
        )

        base = {
            "schema": (
                STRUCTURAL_PLANNING_ARTIFACT_SCHEMA
            ),
            "planning_input_digest": (
                planning_input.planning_input_digest
            ),
            "planning_consumption_digest": (
                consumption.consumption_digest
            ),
            "materialization_digest": (
                planning_input.materialization_digest
            ),
            "topology_digest": (
                planning_input.topology_digest
            ),
            "semantic_input_digest": (
                planning_input.semantic_input_digest
            ),
            "request_id": (
                planning_input.request_id
            ),
            "request_sidecar_digest": (
                planning_input.request_sidecar_digest
            ),
            "expert_selection_digest": (
                planning_input.expert_selection_digest
            ),
            "planner_id": self.planner_id,
            "planner_version": (
                self.planner_version
            ),
            "target_language": "python",
            "backend_target": (
                DETERMINISTIC_PYTHON_TEMPLATE_TARGET
            ),
            "requested_entrypoint": (
                planning_input.entrypoint
            ),
            "requested_parameters": (
                planning_input.parameters
            ),
            "body_lines": body_lines,
            "selected_experts": (
                planning_input.selected_experts
            ),
            "max_tokens": (
                planning_input.max_tokens
            ),
            "authority": PLANNING_AUTHORITY,
            "planning_authorized": True,
            "decoding_authorized": False,
            "execution_authorized": False,
        }

        artifact = StructuralPlanningArtifactV1(
            **base,
            planning_artifact_digest=_domain_digest(
                _PLANNING_ARTIFACT_DOMAIN,
                base,
            ),
        )

        artifact.validate()

        return artifact
