"""Signed authority-zero planning input for structural materialization.

Planning cannot safely be authorized from a structural materialization
alone. The eventual deterministic plan is also affected by request-owned
values such as entrypoint, parameters, body hints, token limit, and the
selected expert set.

This module binds those values to the exact canonical structural
materialization before any PLANNING authority exists.

It does not compile a plan and grants no planning, decoding, or execution
authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Iterable

from .materializer import (
    ResolvedStructuralMaterializationV1,
)


PLANNING_INPUT_SCHEMA = (
    "elpis.structural-guidance.planning-input.v1"
)

_PLANNING_INPUT_DOMAIN = (
    "elpis.structural-guidance.planning-input.v1"
)

_REQUEST_SIDECAR_DOMAIN = (
    "elpis.structural-guidance."
    "planning-request-sidecar.v1"
)

_EXPERT_SELECTION_DOMAIN = (
    "elpis.structural-guidance."
    "planning-expert-selection.v1"
)

_PROMPT_DOMAIN = (
    "elpis.structural-guidance."
    "planning-prompt.v1"
)

AUTHORITY_ZERO = 0

_EXPERT_ID = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
)


class PlanningInputContractError(
    ValueError
):
    """Fail-closed planning-input contract rejection."""


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
    if len(value) != 64:
        raise PlanningInputContractError(
            f"{name} must be SHA-256 hex"
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise PlanningInputContractError(
            f"{name} must be SHA-256 hex"
        ) from exc


def _require_string(
    name: str,
    value: object,
    *,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise PlanningInputContractError(
            f"{name} must be a string"
        )

    if not allow_empty and not value:
        raise PlanningInputContractError(
            f"{name} cannot be empty"
        )

    return value


def _require_string_tuple(
    name: str,
    values: tuple[str, ...],
    *,
    unique: bool = False,
) -> None:
    if not isinstance(values, tuple):
        raise PlanningInputContractError(
            f"{name} must be a tuple"
        )

    for value in values:
        _require_string(
            name,
            value,
            allow_empty=True,
        )

    if unique and len(set(values)) != len(values):
        raise PlanningInputContractError(
            f"{name} contains duplicates"
        )


def _validate_hints(
    hints: tuple[tuple[str, str], ...],
) -> None:
    if not isinstance(hints, tuple):
        raise PlanningInputContractError(
            "decoder_hints must be a tuple"
        )

    keys: list[str] = []

    for item in hints:
        if (
            not isinstance(item, tuple)
            or len(item) != 2
        ):
            raise PlanningInputContractError(
                "decoder_hints entries must be "
                "(key, value) tuples"
            )

        key, value = item

        _require_string(
            "decoder hint key",
            key,
        )
        _require_string(
            "decoder hint value",
            value,
            allow_empty=True,
        )

        keys.append(key)

    if len(set(keys)) != len(keys):
        raise PlanningInputContractError(
            "decoder_hints contains duplicate keys"
        )


def _validate_experts(
    allowed_experts: tuple[str, ...],
    selected_experts: tuple[str, ...],
) -> None:
    _require_string_tuple(
        "allowed_experts",
        allowed_experts,
        unique=True,
    )
    _require_string_tuple(
        "selected_experts",
        selected_experts,
        unique=True,
    )

    for name, values in (
        (
            "allowed_experts",
            allowed_experts,
        ),
        (
            "selected_experts",
            selected_experts,
        ),
    ):
        for value in values:
            if not _EXPERT_ID.fullmatch(value):
                raise PlanningInputContractError(
                    f"invalid {name} identifier"
                )

    allowed = set(
        allowed_experts
    )

    for expert in selected_experts:
        if expert not in allowed:
            raise PlanningInputContractError(
                "selected expert is not allowed"
            )


@dataclass(frozen=True, slots=True)
class PlanningInputV1:
    """Digest-bound request/planning sidecar with authority zero."""

    schema: str

    materialization_digest: str
    topology_digest: str
    semantic_input_digest: str

    request_id: str
    prompt_digest: str
    domain: str

    entrypoint: str
    parameters: tuple[str, ...]
    decoder_hints: tuple[tuple[str, str], ...]

    allowed_experts: tuple[str, ...]
    selected_experts: tuple[str, ...]

    max_tokens: int

    request_sidecar_digest: str
    expert_selection_digest: str

    authority_granted: int
    planning_authorized: bool
    decoding_authorized: bool
    execution_authorized: bool

    planning_input_digest: str

    def request_sidecar_payload(
        self,
    ) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "prompt_digest": self.prompt_digest,
            "domain": self.domain,
            "entrypoint": self.entrypoint,
            "parameters": list(
                self.parameters
            ),
            "decoder_hints": [
                [
                    key,
                    value,
                ]
                for key, value
                in self.decoder_hints
            ],
            "max_tokens": self.max_tokens,
        }

    def expert_selection_payload(
        self,
    ) -> dict[str, object]:
        return {
            "allowed_experts": list(
                self.allowed_experts
            ),
            "selected_experts": list(
                self.selected_experts
            ),
        }

    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "materialization_digest": (
                self.materialization_digest
            ),
            "topology_digest": (
                self.topology_digest
            ),
            "semantic_input_digest": (
                self.semantic_input_digest
            ),
            "request_sidecar_digest": (
                self.request_sidecar_digest
            ),
            "expert_selection_digest": (
                self.expert_selection_digest
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
            "execution_authorized": (
                self.execution_authorized
            ),
        }

    def planning_input_digest_computed(
        self,
    ) -> str:
        return _domain_digest(
            _PLANNING_INPUT_DOMAIN,
            self.payload(),
        )

    def validate(
        self,
    ) -> None:
        if self.schema != PLANNING_INPUT_SCHEMA:
            raise PlanningInputContractError(
                "unsupported planning input schema"
            )

        for name, value in (
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
                "prompt_digest",
                self.prompt_digest,
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
                "planning_input_digest",
                self.planning_input_digest,
            ),
        ):
            _require_digest(
                name,
                value,
            )

        _require_string(
            "request_id",
            self.request_id,
        )
        _require_string(
            "domain",
            self.domain,
        )
        _require_string(
            "entrypoint",
            self.entrypoint,
        )

        _require_string_tuple(
            "parameters",
            self.parameters,
        )

        _validate_hints(
            self.decoder_hints
        )

        _validate_experts(
            self.allowed_experts,
            self.selected_experts,
        )

        if (
            not isinstance(self.max_tokens, int)
            or isinstance(self.max_tokens, bool)
            or self.max_tokens <= 0
        ):
            raise PlanningInputContractError(
                "max_tokens must be a positive integer"
            )

        expected_sidecar = _domain_digest(
            _REQUEST_SIDECAR_DOMAIN,
            self.request_sidecar_payload(),
        )

        if (
            self.request_sidecar_digest
            != expected_sidecar
        ):
            raise PlanningInputContractError(
                "planning request sidecar digest mismatch"
            )

        expected_selection = _domain_digest(
            _EXPERT_SELECTION_DOMAIN,
            self.expert_selection_payload(),
        )

        if (
            self.expert_selection_digest
            != expected_selection
        ):
            raise PlanningInputContractError(
                "expert selection digest mismatch"
            )

        if self.authority_granted != AUTHORITY_ZERO:
            raise PlanningInputContractError(
                "planning input may not grant authority"
            )

        if self.planning_authorized is not False:
            raise PlanningInputContractError(
                "planning input may not authorize planning"
            )

        if self.decoding_authorized is not False:
            raise PlanningInputContractError(
                "planning input may not authorize decoding"
            )

        if self.execution_authorized is not False:
            raise PlanningInputContractError(
                "planning input may not authorize execution"
            )

        if (
            self.planning_input_digest
            != self.planning_input_digest_computed()
        ):
            raise PlanningInputContractError(
                "planning input digest mismatch"
            )

    def validate_digest(
        self,
    ) -> bool:
        try:
            self.validate()
        except PlanningInputContractError:
            return False

        return True


def build_planning_input(
    materialization: ResolvedStructuralMaterializationV1,
    *,
    request_id: str,
    prompt: str,
    domain: str = "python",
    entrypoint: str = "solution",
    parameters: tuple[str, ...] = (),
    decoder_hints: tuple[tuple[str, str], ...] = (),
    allowed_experts: tuple[str, ...] = (),
    selected_experts: tuple[str, ...] = (),
    max_tokens: int = 512,
) -> PlanningInputV1:
    """Bind one canonical structural materialization to planning inputs."""

    if not isinstance(
        materialization,
        ResolvedStructuralMaterializationV1,
    ):
        raise TypeError(
            "materialization must be "
            "ResolvedStructuralMaterializationV1"
        )

    materialization.validate()

    if not materialization.validate_digest():
        raise PlanningInputContractError(
            "structural materialization digest is invalid"
        )

    _require_string(
        "request_id",
        request_id,
    )
    _require_string(
        "prompt",
        prompt,
        allow_empty=True,
    )
    _require_string(
        "domain",
        domain,
    )
    _require_string(
        "entrypoint",
        entrypoint,
    )

    parameters = tuple(
        parameters
    )
    decoder_hints = tuple(
        (
            str(key),
            str(value),
        )
        for key, value
        in decoder_hints
    )
    allowed_experts = tuple(
        allowed_experts
    )
    selected_experts = tuple(
        selected_experts
    )

    _require_string_tuple(
        "parameters",
        parameters,
    )
    _validate_hints(
        decoder_hints
    )
    _validate_experts(
        allowed_experts,
        selected_experts,
    )

    if (
        not isinstance(max_tokens, int)
        or isinstance(max_tokens, bool)
        or max_tokens <= 0
    ):
        raise PlanningInputContractError(
            "max_tokens must be a positive integer"
        )

    structural_payload = (
        materialization.structural_payload()
    )

    semantic_input_digest = structural_payload.get(
        "semantic_input_digest"
    )

    if not isinstance(
        semantic_input_digest,
        str,
    ):
        raise PlanningInputContractError(
            "materialization is missing semantic_input_digest"
        )

    _require_digest(
        "semantic_input_digest",
        semantic_input_digest,
    )

    prompt_digest = _domain_digest(
        _PROMPT_DOMAIN,
        {
            "prompt": prompt,
        },
    )

    sidecar_payload = {
        "request_id": request_id,
        "prompt_digest": prompt_digest,
        "domain": domain,
        "entrypoint": entrypoint,
        "parameters": list(
            parameters
        ),
        "decoder_hints": [
            [
                key,
                value,
            ]
            for key, value
            in decoder_hints
        ],
        "max_tokens": max_tokens,
    }

    request_sidecar_digest = _domain_digest(
        _REQUEST_SIDECAR_DOMAIN,
        sidecar_payload,
    )

    expert_payload = {
        "allowed_experts": list(
            allowed_experts
        ),
        "selected_experts": list(
            selected_experts
        ),
    }

    expert_selection_digest = _domain_digest(
        _EXPERT_SELECTION_DOMAIN,
        expert_payload,
    )

    base = {
        "schema": PLANNING_INPUT_SCHEMA,
        "materialization_digest": (
            materialization.materialization_digest
        ),
        "topology_digest": (
            materialization.topology_digest
        ),
        "semantic_input_digest": (
            semantic_input_digest
        ),
        "request_id": request_id,
        "prompt_digest": prompt_digest,
        "domain": domain,
        "entrypoint": entrypoint,
        "parameters": parameters,
        "decoder_hints": decoder_hints,
        "allowed_experts": allowed_experts,
        "selected_experts": selected_experts,
        "max_tokens": max_tokens,
        "request_sidecar_digest": (
            request_sidecar_digest
        ),
        "expert_selection_digest": (
            expert_selection_digest
        ),
        "authority_granted": 0,
        "planning_authorized": False,
        "decoding_authorized": False,
        "execution_authorized": False,
    }

    provisional = PlanningInputV1(
        **base,
        planning_input_digest="0" * 64,
    )

    digest = provisional.planning_input_digest_computed()

    result = PlanningInputV1(
        **base,
        planning_input_digest=digest,
    )

    result.validate()

    return result
