"""Authority-zero source-emission input for structural guidance.

The deterministic legacy decoder incorporates RequestContext.prompt into
the emitted function docstring. The structural-guidance planning path
deliberately stores only a digest of the prompt.

This contract safely reattaches plaintext for one transformation:

1. require the exact PlanningInputV1 bound to the decoder-specific plan;
2. recompute the canonical planning prompt digest;
3. reject plaintext that does not match that digest;
4. derive the exact normalized/escaped 240-character docstring summary;
5. bind that summary to the exact decoder plan;
6. retain only the bounded normalized docstring summary, not a raw prompt field, and grant no authority.

Actual source emission remains unauthorized.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .decoder_adapter import (
    DecoderSpecificPlanV1,
)
from .planning_input import (
    PlanningInputV1,
)


DECODER_SOURCE_INPUT_SCHEMA = (
    "elpis.structural-guidance.decoder-source-input.v1"
)

_PROMPT_DOMAIN = (
    "elpis.structural-guidance."
    "planning-prompt.v1"
)

_SOURCE_INPUT_DOMAIN = (
    "elpis.structural-guidance."
    "decoder-source-input.v1"
)


class DecoderSourceInputError(ValueError):
    """Fail-closed source-input binding rejection."""


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
        raise DecoderSourceInputError(
            f"{name} must be SHA-256 hex"
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise DecoderSourceInputError(
            f"{name} must be SHA-256 hex"
        ) from exc


def _prompt_digest(
    prompt: str,
) -> str:
    if not isinstance(prompt, str):
        raise TypeError(
            "prompt must be a string"
        )

    return _domain_digest(
        _PROMPT_DOMAIN,
        {
            "prompt": prompt,
        },
    )


def _docstring_summary(
    prompt: str,
) -> str:
    summary = " ".join(
        prompt.strip().split()
    )[:240]

    return summary.replace(
        '"""',
        "'''",
    )


@dataclass(frozen=True, slots=True)
class DecoderSourceInputV1:
    """Digest-bound source input carrying no reusable authority."""

    schema: str

    decoder_plan_digest: str
    planning_input_digest: str
    request_sidecar_digest: str
    prompt_digest: str

    materialization_digest: str
    topology_digest: str
    semantic_input_digest: str

    request_id: str

    docstring_summary: str

    authority_granted: int
    planning_authorized: bool
    decoding_authorized: bool
    source_emission_authorized: bool
    execution_authorized: bool

    source_input_digest: str

    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "decoder_plan_digest": (
                self.decoder_plan_digest
            ),
            "planning_input_digest": (
                self.planning_input_digest
            ),
            "request_sidecar_digest": (
                self.request_sidecar_digest
            ),
            "prompt_digest": (
                self.prompt_digest
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
            "docstring_summary": (
                self.docstring_summary
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

    def source_input_digest_computed(
        self,
    ) -> str:
        return _domain_digest(
            _SOURCE_INPUT_DOMAIN,
            self.payload(),
        )

    def validate(
        self,
    ) -> None:
        if (
            self.schema
            != DECODER_SOURCE_INPUT_SCHEMA
        ):
            raise DecoderSourceInputError(
                "unsupported decoder source input schema"
            )

        for name, value in (
            (
                "decoder_plan_digest",
                self.decoder_plan_digest,
            ),
            (
                "planning_input_digest",
                self.planning_input_digest,
            ),
            (
                "request_sidecar_digest",
                self.request_sidecar_digest,
            ),
            (
                "prompt_digest",
                self.prompt_digest,
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
                "source_input_digest",
                self.source_input_digest,
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
            raise DecoderSourceInputError(
                "request_id cannot be empty"
            )

        if not isinstance(
            self.docstring_summary,
            str,
        ):
            raise DecoderSourceInputError(
                "docstring_summary must be a string"
            )

        if len(
            self.docstring_summary
        ) > 240:
            raise DecoderSourceInputError(
                "docstring_summary exceeds 240 characters"
            )

        if '"""' in self.docstring_summary:
            raise DecoderSourceInputError(
                "docstring_summary contains unsafe delimiter"
            )

        if self.authority_granted != 0:
            raise DecoderSourceInputError(
                "source input may not grant authority"
            )

        if self.planning_authorized is not False:
            raise DecoderSourceInputError(
                "source input may not authorize planning"
            )

        if self.decoding_authorized is not False:
            raise DecoderSourceInputError(
                "source input may not authorize decoding"
            )

        if (
            self.source_emission_authorized
            is not False
        ):
            raise DecoderSourceInputError(
                "source input may not authorize source emission"
            )

        if self.execution_authorized is not False:
            raise DecoderSourceInputError(
                "source input may not authorize execution"
            )

        if (
            self.source_input_digest
            != self.source_input_digest_computed()
        ):
            raise DecoderSourceInputError(
                "decoder source input digest mismatch"
            )

    def validate_digest(
        self,
    ) -> bool:
        try:
            self.validate()
        except DecoderSourceInputError:
            return False

        return True


def build_decoder_source_input(
    decoder_plan: DecoderSpecificPlanV1,
    planning_input: PlanningInputV1,
    *,
    prompt: str,
) -> DecoderSourceInputV1:
    """Verify one raw prompt and retain only its normalized summary."""

    if not isinstance(
        decoder_plan,
        DecoderSpecificPlanV1,
    ):
        raise TypeError(
            "decoder_plan must be DecoderSpecificPlanV1"
        )

    decoder_plan.validate()

    if not decoder_plan.validate_digest():
        raise DecoderSourceInputError(
            "decoder plan digest is invalid"
        )

    if not isinstance(
        planning_input,
        PlanningInputV1,
    ):
        raise TypeError(
            "planning_input must be PlanningInputV1"
        )

    planning_input.validate()

    if not planning_input.validate_digest():
        raise DecoderSourceInputError(
            "planning input digest is invalid"
        )

    bindings = (
        (
            "planning_input_digest",
            decoder_plan.planning_input_digest,
            planning_input.planning_input_digest,
        ),
        (
            "materialization_digest",
            decoder_plan.materialization_digest,
            planning_input.materialization_digest,
        ),
        (
            "topology_digest",
            decoder_plan.topology_digest,
            planning_input.topology_digest,
        ),
        (
            "semantic_input_digest",
            decoder_plan.semantic_input_digest,
            planning_input.semantic_input_digest,
        ),
        (
            "request_id",
            decoder_plan.request_id,
            planning_input.request_id,
        ),
    )

    for name, actual, expected in bindings:
        if actual != expected:
            raise DecoderSourceInputError(
                f"decoder plan {name} mismatch"
            )

    if decoder_plan.authority_granted != 0:
        raise DecoderSourceInputError(
            "decoder plan improperly grants authority"
        )

    if (
        decoder_plan.planning_authorized
        or decoder_plan.decoding_authorized
        or decoder_plan.source_emission_authorized
        or decoder_plan.execution_authorized
    ):
        raise DecoderSourceInputError(
            "decoder plan improperly carries authorization"
        )

    supplied_prompt_digest = _prompt_digest(
        prompt
    )

    if (
        supplied_prompt_digest
        != planning_input.prompt_digest
    ):
        raise DecoderSourceInputError(
            "plaintext prompt does not match bound prompt digest"
        )

    base = {
        "schema": (
            DECODER_SOURCE_INPUT_SCHEMA
        ),
        "decoder_plan_digest": (
            decoder_plan.decoder_plan_digest
        ),
        "planning_input_digest": (
            planning_input.planning_input_digest
        ),
        "request_sidecar_digest": (
            planning_input.request_sidecar_digest
        ),
        "prompt_digest": (
            planning_input.prompt_digest
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
        "docstring_summary": (
            _docstring_summary(prompt)
        ),
        "authority_granted": 0,
        "planning_authorized": False,
        "decoding_authorized": False,
        "source_emission_authorized": False,
        "execution_authorized": False,
    }

    result = DecoderSourceInputV1(
        **base,
        source_input_digest=_domain_digest(
            _SOURCE_INPUT_DOMAIN,
            base,
        ),
    )

    result.validate()

    return result
