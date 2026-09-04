"""One-shot DECODING authority for deterministic source emission.

Source emission remains part of DECODING authority, but authority is
non-transitive across the decoder-plan adapter boundary.

This authority accepts one exact authority-zero DecoderSourceInputV1,
binds it to one explicit source-emitter identity, reveals one capability,
and consumes that capability exactly once.

The capability authorizes decoding/source emission only. It never
authorizes planning or execution.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import secrets
import threading

from .decoding_authority import (
    DECODING_AUTHORITY,
)
from .source_input import (
    DecoderSourceInputV1,
)


_SOURCE_EMISSION_INTENT_SCHEMA = (
    "elpis.structural-guidance."
    "source-emission-intent.v1"
)

_SOURCE_EMISSION_RECEIPT_SCHEMA = (
    "elpis.structural-guidance."
    "source-emission-capability-receipt.v1"
)

_SOURCE_EMISSION_CONSUMPTION_SCHEMA = (
    "elpis.structural-guidance."
    "source-emission-capability-consumption.v1"
)

_INTENT_DOMAIN = (
    "elpis.structural-guidance."
    "source-emission-intent.v1"
)

_INSTANCE_DOMAIN = (
    "elpis.structural-guidance."
    "source-emission-authority-instance.v1"
)

_RECEIPT_DOMAIN = (
    "elpis.structural-guidance."
    "source-emission-capability-receipt.v1"
)

_CONSUMPTION_DOMAIN = (
    "elpis.structural-guidance."
    "source-emission-capability-consumption.v1"
)

_ID = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
)


class SourceEmissionAuthorityError(ValueError):
    """Fail-closed source-emission authority rejection."""


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
        raise SourceEmissionAuthorityError(
            f"{name} must be SHA-256 hex"
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise SourceEmissionAuthorityError(
            f"{name} must be SHA-256 hex"
        ) from exc


def _require_identity(
    name: str,
    value: str,
) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise SourceEmissionAuthorityError(
            f"invalid {name}"
        )


def _require_nonempty(
    name: str,
    value: str,
) -> None:
    if not isinstance(value, str) or not value:
        raise SourceEmissionAuthorityError(
            f"{name} cannot be empty"
        )


@dataclass(frozen=True, slots=True)
class SourceEmissionAuthorizationIntentV1:
    schema: str

    source_input_digest: str
    decoder_plan_digest: str
    planning_input_digest: str
    request_sidecar_digest: str
    prompt_digest: str

    materialization_digest: str
    topology_digest: str
    semantic_input_digest: str

    request_id: str

    source_emitter_id: str
    source_emitter_version: str

    intent_digest: str

    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_input_digest": (
                self.source_input_digest
            ),
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
            "source_emitter_id": (
                self.source_emitter_id
            ),
            "source_emitter_version": (
                self.source_emitter_version
            ),
        }

    def validate(
        self,
    ) -> None:
        if (
            self.schema
            != _SOURCE_EMISSION_INTENT_SCHEMA
        ):
            raise SourceEmissionAuthorityError(
                "unsupported source-emission intent schema"
            )

        for name, value in (
            (
                "source_input_digest",
                self.source_input_digest,
            ),
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
                "intent_digest",
                self.intent_digest,
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

        _require_identity(
            "source_emitter_id",
            self.source_emitter_id,
        )
        _require_identity(
            "source_emitter_version",
            self.source_emitter_version,
        )

        expected = _domain_digest(
            _INTENT_DOMAIN,
            self.payload(),
        )

        if self.intent_digest != expected:
            raise SourceEmissionAuthorityError(
                "source-emission intent digest mismatch"
            )


@dataclass(frozen=True, slots=True)
class SourceEmissionCapabilityReceiptV1:
    schema: str

    authority_instance_id: str
    capability_id: str
    issuance_sequence: int

    intent_digest: str
    source_input_digest: str
    decoder_plan_digest: str
    planning_input_digest: str
    prompt_digest: str

    topology_digest: str
    request_id: str

    source_emitter_id: str
    source_emitter_version: str

    authority: str
    planning_authorized: bool
    decoding_authorized: bool
    source_emission_authorized: bool
    execution_authorized: bool

    receipt_digest: str

    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "authority_instance_id": (
                self.authority_instance_id
            ),
            "capability_id": (
                self.capability_id
            ),
            "issuance_sequence": (
                self.issuance_sequence
            ),
            "intent_digest": (
                self.intent_digest
            ),
            "source_input_digest": (
                self.source_input_digest
            ),
            "decoder_plan_digest": (
                self.decoder_plan_digest
            ),
            "planning_input_digest": (
                self.planning_input_digest
            ),
            "prompt_digest": (
                self.prompt_digest
            ),
            "topology_digest": (
                self.topology_digest
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
            "authority": (
                self.authority
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

    def validate(
        self,
    ) -> None:
        if (
            self.schema
            != _SOURCE_EMISSION_RECEIPT_SCHEMA
        ):
            raise SourceEmissionAuthorityError(
                "unsupported source-emission receipt schema"
            )

        for name, value in (
            (
                "authority_instance_id",
                self.authority_instance_id,
            ),
            (
                "capability_id",
                self.capability_id,
            ),
            (
                "intent_digest",
                self.intent_digest,
            ),
            (
                "source_input_digest",
                self.source_input_digest,
            ),
            (
                "decoder_plan_digest",
                self.decoder_plan_digest,
            ),
            (
                "planning_input_digest",
                self.planning_input_digest,
            ),
            (
                "prompt_digest",
                self.prompt_digest,
            ),
            (
                "topology_digest",
                self.topology_digest,
            ),
            (
                "receipt_digest",
                self.receipt_digest,
            ),
        ):
            _require_digest(
                name,
                value,
            )

        if (
            not isinstance(self.issuance_sequence, int)
            or isinstance(self.issuance_sequence, bool)
            or self.issuance_sequence < 0
        ):
            raise SourceEmissionAuthorityError(
                "issuance_sequence cannot be negative"
            )

        _require_nonempty(
            "request_id",
            self.request_id,
        )

        _require_identity(
            "source_emitter_id",
            self.source_emitter_id,
        )
        _require_identity(
            "source_emitter_version",
            self.source_emitter_version,
        )

        if self.authority != DECODING_AUTHORITY:
            raise SourceEmissionAuthorityError(
                "source-emission capability has wrong authority"
            )

        if self.planning_authorized is not False:
            raise SourceEmissionAuthorityError(
                "source-emission capability may not authorize planning"
            )

        if self.decoding_authorized is not True:
            raise SourceEmissionAuthorityError(
                "source-emission capability must authorize decoding"
            )

        if (
            self.source_emission_authorized
            is not True
        ):
            raise SourceEmissionAuthorityError(
                "source-emission capability must authorize source emission"
            )

        if self.execution_authorized is not False:
            raise SourceEmissionAuthorityError(
                "source-emission capability may not authorize execution"
            )

        expected = _domain_digest(
            _RECEIPT_DOMAIN,
            self.payload(),
        )

        if self.receipt_digest != expected:
            raise SourceEmissionAuthorityError(
                "source-emission receipt digest mismatch"
            )


@dataclass(frozen=True, slots=True)
class AuthorizedSourceEmissionV1:
    intent: SourceEmissionAuthorizationIntentV1
    receipt: SourceEmissionCapabilityReceiptV1


@dataclass(frozen=True, slots=True)
class SourceEmissionConsumptionV1:
    schema: str

    authority_instance_id: str
    capability_id: str

    intent_digest: str
    source_input_digest: str
    decoder_plan_digest: str
    planning_input_digest: str
    request_sidecar_digest: str
    prompt_digest: str

    materialization_digest: str
    topology_digest: str
    semantic_input_digest: str

    request_id: str

    source_emitter_id: str
    source_emitter_version: str

    authority: str
    planning_authorized: bool
    decoding_authorized: bool
    source_emission_authorized: bool
    execution_authorized: bool

    receipt_digest: str
    consumption_digest: str

    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "authority_instance_id": (
                self.authority_instance_id
            ),
            "capability_id": (
                self.capability_id
            ),
            "intent_digest": (
                self.intent_digest
            ),
            "source_input_digest": (
                self.source_input_digest
            ),
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
            "source_emitter_id": (
                self.source_emitter_id
            ),
            "source_emitter_version": (
                self.source_emitter_version
            ),
            "authority": (
                self.authority
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
            "receipt_digest": (
                self.receipt_digest
            ),
        }

    def validate(
        self,
    ) -> None:
        if (
            self.schema
            != _SOURCE_EMISSION_CONSUMPTION_SCHEMA
        ):
            raise SourceEmissionAuthorityError(
                "unsupported source-emission consumption schema"
            )

        for name, value in (
            (
                "authority_instance_id",
                self.authority_instance_id,
            ),
            (
                "capability_id",
                self.capability_id,
            ),
            (
                "intent_digest",
                self.intent_digest,
            ),
            (
                "source_input_digest",
                self.source_input_digest,
            ),
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
                "receipt_digest",
                self.receipt_digest,
            ),
            (
                "consumption_digest",
                self.consumption_digest,
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

        _require_identity(
            "source_emitter_id",
            self.source_emitter_id,
        )
        _require_identity(
            "source_emitter_version",
            self.source_emitter_version,
        )

        if self.authority != DECODING_AUTHORITY:
            raise SourceEmissionAuthorityError(
                "source-emission consumption has wrong authority"
            )

        if self.planning_authorized is not False:
            raise SourceEmissionAuthorityError(
                "source-emission consumption may not authorize planning"
            )

        if self.decoding_authorized is not True:
            raise SourceEmissionAuthorityError(
                "source-emission consumption must authorize decoding"
            )

        if (
            self.source_emission_authorized
            is not True
        ):
            raise SourceEmissionAuthorityError(
                "source-emission consumption must authorize source emission"
            )

        if self.execution_authorized is not False:
            raise SourceEmissionAuthorityError(
                "source-emission consumption may not authorize execution"
            )

        expected = _domain_digest(
            _CONSUMPTION_DOMAIN,
            self.payload(),
        )

        if self.consumption_digest != expected:
            raise SourceEmissionAuthorityError(
                "source-emission consumption digest mismatch"
            )


def _build_intent(
    source_input: DecoderSourceInputV1,
    *,
    source_emitter_id: str,
    source_emitter_version: str,
) -> SourceEmissionAuthorizationIntentV1:
    if not isinstance(
        source_input,
        DecoderSourceInputV1,
    ):
        raise TypeError(
            "source_input must be DecoderSourceInputV1"
        )

    source_input.validate()

    if not source_input.validate_digest():
        raise SourceEmissionAuthorityError(
            "source input digest is invalid"
        )

    if source_input.authority_granted != 0:
        raise SourceEmissionAuthorityError(
            "source input improperly grants authority"
        )

    if (
        source_input.planning_authorized
        or source_input.decoding_authorized
        or source_input.source_emission_authorized
        or source_input.execution_authorized
    ):
        raise SourceEmissionAuthorityError(
            "source input already carries authorization"
        )

    _require_identity(
        "source_emitter_id",
        source_emitter_id,
    )
    _require_identity(
        "source_emitter_version",
        source_emitter_version,
    )

    base = {
        "schema": (
            _SOURCE_EMISSION_INTENT_SCHEMA
        ),
        "source_input_digest": (
            source_input.source_input_digest
        ),
        "decoder_plan_digest": (
            source_input.decoder_plan_digest
        ),
        "planning_input_digest": (
            source_input.planning_input_digest
        ),
        "request_sidecar_digest": (
            source_input.request_sidecar_digest
        ),
        "prompt_digest": (
            source_input.prompt_digest
        ),
        "materialization_digest": (
            source_input.materialization_digest
        ),
        "topology_digest": (
            source_input.topology_digest
        ),
        "semantic_input_digest": (
            source_input.semantic_input_digest
        ),
        "request_id": (
            source_input.request_id
        ),
        "source_emitter_id": (
            source_emitter_id
        ),
        "source_emitter_version": (
            source_emitter_version
        ),
    }

    intent = (
        SourceEmissionAuthorizationIntentV1(
            **base,
            intent_digest=_domain_digest(
                _INTENT_DOMAIN,
                base,
            ),
        )
    )

    intent.validate()

    return intent


class _SourceEmissionAuthority:
    """Private instance-bound one-shot source-emission authority."""

    __slots__ = (
        "__instance_id",
        "__active",
        "__pending",
        "__sequence",
        "__lock",
    )

    def __init__(
        self,
    ) -> None:
        seed = secrets.token_hex(32)

        self.__instance_id = _domain_digest(
            _INSTANCE_DOMAIN,
            {
                "seed": seed,
            },
        )

        self.__active: dict[str, str] = {}

        self.__pending: dict[
            int,
            tuple[
                SourceEmissionAuthorizationIntentV1,
                SourceEmissionCapabilityReceiptV1,
            ],
        ] = {}

        self.__sequence = 0
        self.__lock = threading.RLock()

    def _precommit_from_owner(
        self,
        source_input: DecoderSourceInputV1,
        *,
        source_emitter_id: str,
        source_emitter_version: str,
    ) -> SourceEmissionAuthorizationIntentV1:
        intent = _build_intent(
            source_input,
            source_emitter_id=source_emitter_id,
            source_emitter_version=source_emitter_version,
        )

        key = id(intent)

        with self.__lock:
            if key in self.__pending:
                raise SourceEmissionAuthorityError(
                    "source-emission intent already precommitted"
                )

            capability = secrets.token_hex(32)

            while capability in self.__active:
                capability = secrets.token_hex(32)

            _require_digest(
                "capability_id",
                capability,
            )

            sequence = self.__sequence
            self.__sequence += 1

            base = {
                "schema": (
                    _SOURCE_EMISSION_RECEIPT_SCHEMA
                ),
                "authority_instance_id": (
                    self.__instance_id
                ),
                "capability_id": (
                    capability
                ),
                "issuance_sequence": (
                    sequence
                ),
                "intent_digest": (
                    intent.intent_digest
                ),
                "source_input_digest": (
                    intent.source_input_digest
                ),
                "decoder_plan_digest": (
                    intent.decoder_plan_digest
                ),
                "planning_input_digest": (
                    intent.planning_input_digest
                ),
                "prompt_digest": (
                    intent.prompt_digest
                ),
                "topology_digest": (
                    intent.topology_digest
                ),
                "request_id": (
                    intent.request_id
                ),
                "source_emitter_id": (
                    intent.source_emitter_id
                ),
                "source_emitter_version": (
                    intent.source_emitter_version
                ),
                "authority": (
                    DECODING_AUTHORITY
                ),
                "planning_authorized": False,
                "decoding_authorized": True,
                "source_emission_authorized": True,
                "execution_authorized": False,
            }

            receipt = (
                SourceEmissionCapabilityReceiptV1(
                    **base,
                    receipt_digest=_domain_digest(
                        _RECEIPT_DOMAIN,
                        base,
                    ),
                )
            )

            receipt.validate()

            self.__active[
                capability
            ] = receipt.receipt_digest

            self.__pending[
                key
            ] = (
                intent,
                receipt,
            )

        return intent

    def _reveal_from_owner(
        self,
        intent: SourceEmissionAuthorizationIntentV1,
    ) -> AuthorizedSourceEmissionV1:
        if not isinstance(
            intent,
            SourceEmissionAuthorizationIntentV1,
        ):
            raise TypeError(
                "intent must be "
                "SourceEmissionAuthorizationIntentV1"
            )

        intent.validate()

        with self.__lock:
            entry = self.__pending.get(
                id(intent)
            )

            if entry is None:
                raise SourceEmissionAuthorityError(
                    "source-emission intent was not precommitted "
                    "by this authority instance"
                )

            stored, receipt = entry

            if stored is not intent:
                raise SourceEmissionAuthorityError(
                    "source-emission intent object differs from precommit"
                )

            intent.validate()

            if (
                receipt.intent_digest
                != intent.intent_digest
            ):
                raise SourceEmissionAuthorityError(
                    "source-emission receipt/intent identity mismatch"
                )

            del self.__pending[
                id(intent)
            ]

            return AuthorizedSourceEmissionV1(
                intent=intent,
                receipt=receipt,
            )

    def _consume_from_owner(
        self,
        authorized: AuthorizedSourceEmissionV1,
    ) -> SourceEmissionConsumptionV1:
        if not isinstance(
            authorized,
            AuthorizedSourceEmissionV1,
        ):
            raise TypeError(
                "authorized must be AuthorizedSourceEmissionV1"
            )

        intent = authorized.intent
        receipt = authorized.receipt

        intent.validate()
        receipt.validate()

        if (
            receipt.authority_instance_id
            != self.__instance_id
        ):
            raise SourceEmissionAuthorityError(
                "receipt belongs to another "
                "source-emission authority instance"
            )

        for name in (
            "intent_digest",
            "source_input_digest",
            "decoder_plan_digest",
            "planning_input_digest",
            "prompt_digest",
            "topology_digest",
            "request_id",
            "source_emitter_id",
            "source_emitter_version",
        ):
            if (
                getattr(receipt, name)
                != getattr(intent, name)
            ):
                raise SourceEmissionAuthorityError(
                    f"source-emission receipt {name} mismatch"
                )

        with self.__lock:
            active = self.__active.get(
                receipt.capability_id
            )

            if active is None:
                raise SourceEmissionAuthorityError(
                    "source-emission capability is not active"
                )

            if active != receipt.receipt_digest:
                raise SourceEmissionAuthorityError(
                    "source-emission capability receipt mismatch"
                )

            del self.__active[
                receipt.capability_id
            ]

        base = {
            "schema": (
                _SOURCE_EMISSION_CONSUMPTION_SCHEMA
            ),
            "authority_instance_id": (
                receipt.authority_instance_id
            ),
            "capability_id": (
                receipt.capability_id
            ),
            "intent_digest": (
                intent.intent_digest
            ),
            "source_input_digest": (
                intent.source_input_digest
            ),
            "decoder_plan_digest": (
                intent.decoder_plan_digest
            ),
            "planning_input_digest": (
                intent.planning_input_digest
            ),
            "request_sidecar_digest": (
                intent.request_sidecar_digest
            ),
            "prompt_digest": (
                intent.prompt_digest
            ),
            "materialization_digest": (
                intent.materialization_digest
            ),
            "topology_digest": (
                intent.topology_digest
            ),
            "semantic_input_digest": (
                intent.semantic_input_digest
            ),
            "request_id": (
                intent.request_id
            ),
            "source_emitter_id": (
                intent.source_emitter_id
            ),
            "source_emitter_version": (
                intent.source_emitter_version
            ),
            "authority": (
                DECODING_AUTHORITY
            ),
            "planning_authorized": False,
            "decoding_authorized": True,
            "source_emission_authorized": True,
            "execution_authorized": False,
            "receipt_digest": (
                receipt.receipt_digest
            ),
        }

        consumption = (
            SourceEmissionConsumptionV1(
                **base,
                consumption_digest=_domain_digest(
                    _CONSUMPTION_DOMAIN,
                    base,
                ),
            )
        )

        consumption.validate()

        return consumption


def _new_source_emission_authority(
) -> _SourceEmissionAuthority:
    """Create one private source-emission DECODING authority."""
    return _SourceEmissionAuthority()
