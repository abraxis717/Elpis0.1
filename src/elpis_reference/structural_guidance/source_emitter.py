"""Deterministic source emitter for structural guidance.

This is the first component in the new structural-guidance path permitted
to construct source text.

It requires three independently validated and digest-bound inputs:

* DecoderSpecificPlanV1;
* DecoderSourceInputV1; and
* SourceEmissionConsumptionV1 carrying DECODING/source-emission authority.

The source construction semantics match the established deterministic
Python template:

* normalized function and parameter identifiers already come from the
  decoder adapter;
* the prompt-derived docstring summary already comes from the source-input
  binding;
* body lines are indented without interpretation;
* the final source is newline-normalized exactly once.

The emitter does not parse, validate, import, compile, execute, or invoke
the emitted source.

Authority remains non-transitive. The returned source artifact carries
zero reusable authority and explicitly does not authorize execution.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from .decoder_adapter import (
    DecoderSpecificPlanV1,
)
from .decoding_authority import (
    DECODING_AUTHORITY,
)
from .source_emission_authority import (
    SourceEmissionConsumptionV1,
)
from .source_input import (
    DecoderSourceInputV1,
)


DECODED_SOURCE_ARTIFACT_SCHEMA = (
    "elpis.structural-guidance."
    "decoded-source-artifact.v1"
)

DETERMINISTIC_SOURCE_EMITTER_ID = (
    "elpis.structural-guidance."
    "deterministic-source-emitter"
)

DETERMINISTIC_SOURCE_EMITTER_VERSION = "v1"

_SOURCE_ARTIFACT_DOMAIN = (
    "elpis.structural-guidance."
    "decoded-source-artifact.v1"
)

_ID = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
)


class SourceEmitterError(ValueError):
    """Fail-closed source-emitter rejection."""


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
        raise SourceEmitterError(
            f"{name} must be SHA-256 hex"
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise SourceEmitterError(
            f"{name} must be SHA-256 hex"
        ) from exc


def _require_nonempty(
    name: str,
    value: str,
) -> None:
    if not isinstance(value, str) or not value:
        raise SourceEmitterError(
            f"{name} cannot be empty"
        )


def _source_sha256(
    source: str,
) -> str:
    return hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class DecodedSourceArtifactV1:
    """Digest-bound emitted source with zero execution authority."""

    schema: str

    decoder_plan_digest: str
    source_input_digest: str
    source_emission_consumption_digest: str

    planning_input_digest: str
    materialization_digest: str
    topology_digest: str
    semantic_input_digest: str

    request_id: str

    source_emitter_id: str
    source_emitter_version: str

    language: str
    source: str
    source_sha256: str

    authority_applied: str
    authority_granted: int

    planning_authorized: bool
    decoding_authorized: bool
    source_emission_authorized: bool
    execution_authorized: bool

    source_artifact_digest: str

    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "decoder_plan_digest": (
                self.decoder_plan_digest
            ),
            "source_input_digest": (
                self.source_input_digest
            ),
            "source_emission_consumption_digest": (
                self.source_emission_consumption_digest
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
            "source_emitter_id": (
                self.source_emitter_id
            ),
            "source_emitter_version": (
                self.source_emitter_version
            ),
            "language": (
                self.language
            ),
            "source": (
                self.source
            ),
            "source_sha256": (
                self.source_sha256
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

    def source_artifact_digest_computed(
        self,
    ) -> str:
        return _domain_digest(
            _SOURCE_ARTIFACT_DOMAIN,
            self.payload(),
        )

    def validate(
        self,
    ) -> None:
        if (
            self.schema
            != DECODED_SOURCE_ARTIFACT_SCHEMA
        ):
            raise SourceEmitterError(
                "unsupported decoded source artifact schema"
            )

        for name, value in (
            (
                "decoder_plan_digest",
                self.decoder_plan_digest,
            ),
            (
                "source_input_digest",
                self.source_input_digest,
            ),
            (
                "source_emission_consumption_digest",
                self.source_emission_consumption_digest,
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
                "source_sha256",
                self.source_sha256,
            ),
            (
                "source_artifact_digest",
                self.source_artifact_digest,
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
            self.source_emitter_id
        ):
            raise SourceEmitterError(
                "invalid source_emitter_id"
            )

        if not _ID.fullmatch(
            self.source_emitter_version
        ):
            raise SourceEmitterError(
                "invalid source_emitter_version"
            )

        if self.language != "python":
            raise SourceEmitterError(
                "unsupported source language"
            )

        if not isinstance(
            self.source,
            str,
        ):
            raise SourceEmitterError(
                "source must be a string"
            )

        if not self.source:
            raise SourceEmitterError(
                "source cannot be empty"
            )

        if not self.source.endswith(
            "\n"
        ):
            raise SourceEmitterError(
                "source must end with exactly normalized newline"
            )

        if (
            self.source_sha256
            != _source_sha256(
                self.source
            )
        ):
            raise SourceEmitterError(
                "source SHA-256 mismatch"
            )

        if (
            self.authority_applied
            != DECODING_AUTHORITY
        ):
            raise SourceEmitterError(
                "source artifact has wrong applied authority"
            )

        if self.authority_granted != 0:
            raise SourceEmitterError(
                "source artifact may not grant authority"
            )

        if self.planning_authorized is not False:
            raise SourceEmitterError(
                "source artifact may not authorize planning"
            )

        if self.decoding_authorized is not False:
            raise SourceEmitterError(
                "source artifact may not propagate decoding authority"
            )

        if (
            self.source_emission_authorized
            is not False
        ):
            raise SourceEmitterError(
                "source artifact may not propagate source-emission authority"
            )

        if self.execution_authorized is not False:
            raise SourceEmitterError(
                "source artifact may not authorize execution"
            )

        if (
            self.source_artifact_digest
            != self.source_artifact_digest_computed()
        ):
            raise SourceEmitterError(
                "source artifact digest mismatch"
            )

    def validate_digest(
        self,
    ) -> bool:
        try:
            self.validate()
        except SourceEmitterError:
            return False

        return True


@dataclass(frozen=True, slots=True)
class DeterministicSourceEmitterV1:
    """Emit deterministic Python source without executing it."""

    source_emitter_id: str = (
        DETERMINISTIC_SOURCE_EMITTER_ID
    )

    source_emitter_version: str = (
        DETERMINISTIC_SOURCE_EMITTER_VERSION
    )

    def __post_init__(
        self,
    ) -> None:
        if not _ID.fullmatch(
            self.source_emitter_id
        ):
            raise SourceEmitterError(
                "invalid source_emitter_id"
            )

        if not _ID.fullmatch(
            self.source_emitter_version
        ):
            raise SourceEmitterError(
                "invalid source_emitter_version"
            )

    def emit(
        self,
        decoder_plan: DecoderSpecificPlanV1,
        source_input: DecoderSourceInputV1,
        consumption: SourceEmissionConsumptionV1,
    ) -> DecodedSourceArtifactV1:
        if not isinstance(
            decoder_plan,
            DecoderSpecificPlanV1,
        ):
            raise TypeError(
                "decoder_plan must be DecoderSpecificPlanV1"
            )

        decoder_plan.validate()

        if not decoder_plan.validate_digest():
            raise SourceEmitterError(
                "decoder plan digest is invalid"
            )

        if not isinstance(
            source_input,
            DecoderSourceInputV1,
        ):
            raise TypeError(
                "source_input must be DecoderSourceInputV1"
            )

        source_input.validate()

        if not source_input.validate_digest():
            raise SourceEmitterError(
                "source input digest is invalid"
            )

        if not isinstance(
            consumption,
            SourceEmissionConsumptionV1,
        ):
            raise TypeError(
                "consumption must be SourceEmissionConsumptionV1"
            )

        consumption.validate()

        plan_input_bindings = (
            (
                "decoder_plan_digest",
                source_input.decoder_plan_digest,
                decoder_plan.decoder_plan_digest,
            ),
            (
                "planning_input_digest",
                source_input.planning_input_digest,
                decoder_plan.planning_input_digest,
            ),
            (
                "materialization_digest",
                source_input.materialization_digest,
                decoder_plan.materialization_digest,
            ),
            (
                "topology_digest",
                source_input.topology_digest,
                decoder_plan.topology_digest,
            ),
            (
                "semantic_input_digest",
                source_input.semantic_input_digest,
                decoder_plan.semantic_input_digest,
            ),
            (
                "request_id",
                source_input.request_id,
                decoder_plan.request_id,
            ),
        )

        for name, actual, expected in plan_input_bindings:
            if actual != expected:
                raise SourceEmitterError(
                    f"source input {name} mismatch"
                )

        consumption_bindings = (
            (
                "source_input_digest",
                consumption.source_input_digest,
                source_input.source_input_digest,
            ),
            (
                "decoder_plan_digest",
                consumption.decoder_plan_digest,
                decoder_plan.decoder_plan_digest,
            ),
            (
                "planning_input_digest",
                consumption.planning_input_digest,
                decoder_plan.planning_input_digest,
            ),
            (
                "materialization_digest",
                consumption.materialization_digest,
                decoder_plan.materialization_digest,
            ),
            (
                "topology_digest",
                consumption.topology_digest,
                decoder_plan.topology_digest,
            ),
            (
                "semantic_input_digest",
                consumption.semantic_input_digest,
                decoder_plan.semantic_input_digest,
            ),
            (
                "request_id",
                consumption.request_id,
                decoder_plan.request_id,
            ),
            (
                "prompt_digest",
                consumption.prompt_digest,
                source_input.prompt_digest,
            ),
            (
                "request_sidecar_digest",
                consumption.request_sidecar_digest,
                source_input.request_sidecar_digest,
            ),
        )

        for name, actual, expected in consumption_bindings:
            if actual != expected:
                raise SourceEmitterError(
                    f"source-emission consumption {name} mismatch"
                )

        if (
            consumption.source_emitter_id
            != self.source_emitter_id
        ):
            raise SourceEmitterError(
                "source-emission consumption emitter identity mismatch"
            )

        if (
            consumption.source_emitter_version
            != self.source_emitter_version
        ):
            raise SourceEmitterError(
                "source-emission consumption emitter version mismatch"
            )

        if consumption.authority != DECODING_AUTHORITY:
            raise SourceEmitterError(
                "source-emission consumption has wrong authority"
            )

        if consumption.planning_authorized is not False:
            raise SourceEmitterError(
                "source-emission consumption improperly authorizes planning"
            )

        if consumption.decoding_authorized is not True:
            raise SourceEmitterError(
                "source-emission consumption lacks decoding authority"
            )

        if (
            consumption.source_emission_authorized
            is not True
        ):
            raise SourceEmitterError(
                "source-emission consumption lacks source-emission authority"
            )

        if consumption.execution_authorized is not False:
            raise SourceEmitterError(
                "source-emission consumption improperly authorizes execution"
            )

        for obj, label in (
            (
                decoder_plan,
                "decoder plan",
            ),
            (
                source_input,
                "source input",
            ),
        ):
            if obj.execution_authorized is not False:
                raise SourceEmitterError(
                    f"{label} improperly authorizes execution"
                )

        if decoder_plan.authority_granted != 0:
            raise SourceEmitterError(
                "decoder plan improperly grants authority"
            )

        if source_input.authority_granted != 0:
            raise SourceEmitterError(
                "source input improperly grants authority"
            )

        lines = [
            (
                f"def {decoder_plan.function_name}"
                f"({', '.join(decoder_plan.parameters)}):"
            ),
            (
                '    """'
                f"{source_input.docstring_summary}"
                '"""'
            ),
        ]

        lines.extend(
            (
                f"    {line}"
                if line.strip()
                else ""
            )
            for line in decoder_plan.body_lines
        )

        source = (
            "\n".join(lines)
            .rstrip()
            + "\n"
        )

        base = {
            "schema": (
                DECODED_SOURCE_ARTIFACT_SCHEMA
            ),
            "decoder_plan_digest": (
                decoder_plan.decoder_plan_digest
            ),
            "source_input_digest": (
                source_input.source_input_digest
            ),
            "source_emission_consumption_digest": (
                consumption.consumption_digest
            ),
            "planning_input_digest": (
                decoder_plan.planning_input_digest
            ),
            "materialization_digest": (
                decoder_plan.materialization_digest
            ),
            "topology_digest": (
                decoder_plan.topology_digest
            ),
            "semantic_input_digest": (
                decoder_plan.semantic_input_digest
            ),
            "request_id": (
                decoder_plan.request_id
            ),
            "source_emitter_id": (
                self.source_emitter_id
            ),
            "source_emitter_version": (
                self.source_emitter_version
            ),
            "language": (
                decoder_plan.language
            ),
            "source": (
                source
            ),
            "source_sha256": (
                _source_sha256(
                    source
                )
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

        artifact = DecodedSourceArtifactV1(
            **base,
            source_artifact_digest=_domain_digest(
                _SOURCE_ARTIFACT_DOMAIN,
                base,
            ),
        )

        artifact.validate()

        return artifact
