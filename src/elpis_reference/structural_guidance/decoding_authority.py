"""One-shot DECODING authority for structural planning artifacts.

This module authorizes exactly one downstream capability:

    DECODING

It does not authorize planning or execution.

The capability is bound to:
* one validated StructuralPlanningArtifactV1;
* its complete upstream digest lineage; and
* one explicit decoder-adapter identity.

The private authority only issues and consumes capabilities. It does not
construct decoder-specific data, emit source, invoke a decoder, or execute
anything.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import secrets
import threading

from .planner import (
    StructuralPlanningArtifactV1,
)


DECODING_AUTHORITY = "DECODING"

_DECODING_INTENT_SCHEMA = (
    "elpis.structural-guidance.decoding-intent.v1"
)

_DECODING_RECEIPT_SCHEMA = (
    "elpis.structural-guidance."
    "decoding-capability-receipt.v1"
)

_DECODING_CONSUMPTION_SCHEMA = (
    "elpis.structural-guidance."
    "decoding-capability-consumption.v1"
)

_INTENT_DOMAIN = (
    "elpis.structural-guidance.decoding-intent.v1"
)

_INSTANCE_DOMAIN = (
    "elpis.structural-guidance."
    "decoding-authority-instance.v1"
)

_RECEIPT_DOMAIN = (
    "elpis.structural-guidance."
    "decoding-capability-receipt.v1"
)

_CONSUMPTION_DOMAIN = (
    "elpis.structural-guidance."
    "decoding-capability-consumption.v1"
)

_ID = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
)


class DecodingAuthorityError(ValueError):
    """Fail-closed decoding-authority rejection."""


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
        raise DecodingAuthorityError(
            f"{name} must be SHA-256 hex"
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise DecodingAuthorityError(
            f"{name} must be SHA-256 hex"
        ) from exc


def _require_identity(
    name: str,
    value: str,
) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise DecodingAuthorityError(
            f"invalid {name}"
        )


def _require_nonempty(
    name: str,
    value: str,
) -> None:
    if not isinstance(value, str) or not value:
        raise DecodingAuthorityError(
            f"{name} cannot be empty"
        )


@dataclass(frozen=True, slots=True)
class DecodingAuthorizationIntentV1:
    schema: str

    planning_artifact_digest: str
    planning_input_digest: str
    planning_consumption_digest: str

    materialization_digest: str
    topology_digest: str
    semantic_input_digest: str

    request_id: str

    decoder_adapter_id: str
    decoder_adapter_version: str

    intent_digest: str

    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "planning_artifact_digest": (
                self.planning_artifact_digest
            ),
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
            "decoder_adapter_id": (
                self.decoder_adapter_id
            ),
            "decoder_adapter_version": (
                self.decoder_adapter_version
            ),
        }

    def validate(
        self,
    ) -> None:
        if self.schema != _DECODING_INTENT_SCHEMA:
            raise DecodingAuthorityError(
                "unsupported decoding intent schema"
            )

        for name, value in (
            (
                "planning_artifact_digest",
                self.planning_artifact_digest,
            ),
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
            "decoder_adapter_id",
            self.decoder_adapter_id,
        )
        _require_identity(
            "decoder_adapter_version",
            self.decoder_adapter_version,
        )

        expected = _domain_digest(
            _INTENT_DOMAIN,
            self.payload(),
        )

        if self.intent_digest != expected:
            raise DecodingAuthorityError(
                "decoding intent digest mismatch"
            )


@dataclass(frozen=True, slots=True)
class DecodingCapabilityReceiptV1:
    schema: str

    authority_instance_id: str
    capability_id: str
    issuance_sequence: int

    intent_digest: str
    planning_artifact_digest: str
    planning_input_digest: str

    materialization_digest: str
    topology_digest: str

    request_id: str

    decoder_adapter_id: str
    decoder_adapter_version: str

    authority: str
    planning_authorized: bool
    decoding_authorized: bool
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
            "planning_artifact_digest": (
                self.planning_artifact_digest
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
            "request_id": (
                self.request_id
            ),
            "decoder_adapter_id": (
                self.decoder_adapter_id
            ),
            "decoder_adapter_version": (
                self.decoder_adapter_version
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
            "execution_authorized": (
                self.execution_authorized
            ),
        }

    def validate(
        self,
    ) -> None:
        if self.schema != _DECODING_RECEIPT_SCHEMA:
            raise DecodingAuthorityError(
                "unsupported decoding receipt schema"
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
                "planning_artifact_digest",
                self.planning_artifact_digest,
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
            raise DecodingAuthorityError(
                "issuance_sequence cannot be negative"
            )

        _require_nonempty(
            "request_id",
            self.request_id,
        )

        _require_identity(
            "decoder_adapter_id",
            self.decoder_adapter_id,
        )
        _require_identity(
            "decoder_adapter_version",
            self.decoder_adapter_version,
        )

        if self.authority != DECODING_AUTHORITY:
            raise DecodingAuthorityError(
                "decoding capability has wrong authority"
            )

        if self.planning_authorized is not False:
            raise DecodingAuthorityError(
                "decoding capability may not authorize planning"
            )

        if self.decoding_authorized is not True:
            raise DecodingAuthorityError(
                "decoding capability must authorize decoding"
            )

        if self.execution_authorized is not False:
            raise DecodingAuthorityError(
                "decoding capability may not authorize execution"
            )

        expected = _domain_digest(
            _RECEIPT_DOMAIN,
            self.payload(),
        )

        if self.receipt_digest != expected:
            raise DecodingAuthorityError(
                "decoding capability receipt digest mismatch"
            )


@dataclass(frozen=True, slots=True)
class AuthorizedDecodingV1:
    intent: DecodingAuthorizationIntentV1
    receipt: DecodingCapabilityReceiptV1


@dataclass(frozen=True, slots=True)
class DecodingConsumptionV1:
    schema: str

    authority_instance_id: str
    capability_id: str

    intent_digest: str
    planning_artifact_digest: str
    planning_input_digest: str
    planning_consumption_digest: str

    materialization_digest: str
    topology_digest: str
    semantic_input_digest: str

    request_id: str

    decoder_adapter_id: str
    decoder_adapter_version: str

    authority: str
    planning_authorized: bool
    decoding_authorized: bool
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
            "planning_artifact_digest": (
                self.planning_artifact_digest
            ),
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
            "request_id": (
                self.request_id
            ),
            "decoder_adapter_id": (
                self.decoder_adapter_id
            ),
            "decoder_adapter_version": (
                self.decoder_adapter_version
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
        if self.schema != _DECODING_CONSUMPTION_SCHEMA:
            raise DecodingAuthorityError(
                "unsupported decoding consumption schema"
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
                "planning_artifact_digest",
                self.planning_artifact_digest,
            ),
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
            "decoder_adapter_id",
            self.decoder_adapter_id,
        )
        _require_identity(
            "decoder_adapter_version",
            self.decoder_adapter_version,
        )

        if self.authority != DECODING_AUTHORITY:
            raise DecodingAuthorityError(
                "decoding consumption has wrong authority"
            )

        if self.planning_authorized is not False:
            raise DecodingAuthorityError(
                "decoding consumption may not authorize planning"
            )

        if self.decoding_authorized is not True:
            raise DecodingAuthorityError(
                "decoding consumption must authorize decoding"
            )

        if self.execution_authorized is not False:
            raise DecodingAuthorityError(
                "decoding consumption may not authorize execution"
            )

        expected = _domain_digest(
            _CONSUMPTION_DOMAIN,
            self.payload(),
        )

        if self.consumption_digest != expected:
            raise DecodingAuthorityError(
                "decoding consumption digest mismatch"
            )


def _build_intent(
    planning_artifact: StructuralPlanningArtifactV1,
    *,
    decoder_adapter_id: str,
    decoder_adapter_version: str,
) -> DecodingAuthorizationIntentV1:
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
        raise DecodingAuthorityError(
            "planning artifact digest is invalid"
        )

    if planning_artifact.planning_authorized is not True:
        raise DecodingAuthorityError(
            "planning artifact lacks planning authority"
        )

    if planning_artifact.decoding_authorized is not False:
        raise DecodingAuthorityError(
            "planning artifact already carries decoding authority"
        )

    if planning_artifact.execution_authorized is not False:
        raise DecodingAuthorityError(
            "planning artifact carries execution authority"
        )

    _require_identity(
        "decoder_adapter_id",
        decoder_adapter_id,
    )
    _require_identity(
        "decoder_adapter_version",
        decoder_adapter_version,
    )

    base = {
        "schema": _DECODING_INTENT_SCHEMA,
        "planning_artifact_digest": (
            planning_artifact.planning_artifact_digest
        ),
        "planning_input_digest": (
            planning_artifact.planning_input_digest
        ),
        "planning_consumption_digest": (
            planning_artifact.planning_consumption_digest
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
            decoder_adapter_id
        ),
        "decoder_adapter_version": (
            decoder_adapter_version
        ),
    }

    intent = DecodingAuthorizationIntentV1(
        **base,
        intent_digest=_domain_digest(
            _INTENT_DOMAIN,
            base,
        ),
    )

    intent.validate()

    return intent


class _DecodingAuthority:
    """Private instance-bound, one-shot DECODING authority."""

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
                DecodingAuthorizationIntentV1,
                DecodingCapabilityReceiptV1,
            ],
        ] = {}

        self.__sequence = 0
        self.__lock = threading.RLock()

    def _precommit_from_owner(
        self,
        planning_artifact: StructuralPlanningArtifactV1,
        *,
        decoder_adapter_id: str,
        decoder_adapter_version: str,
    ) -> DecodingAuthorizationIntentV1:
        intent = _build_intent(
            planning_artifact,
            decoder_adapter_id=decoder_adapter_id,
            decoder_adapter_version=decoder_adapter_version,
        )

        key = id(intent)

        with self.__lock:
            if key in self.__pending:
                raise DecodingAuthorityError(
                    "decoding intent already precommitted"
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
                "schema": _DECODING_RECEIPT_SCHEMA,
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
                "planning_artifact_digest": (
                    intent.planning_artifact_digest
                ),
                "planning_input_digest": (
                    intent.planning_input_digest
                ),
                "materialization_digest": (
                    intent.materialization_digest
                ),
                "topology_digest": (
                    intent.topology_digest
                ),
                "request_id": (
                    intent.request_id
                ),
                "decoder_adapter_id": (
                    intent.decoder_adapter_id
                ),
                "decoder_adapter_version": (
                    intent.decoder_adapter_version
                ),
                "authority": (
                    DECODING_AUTHORITY
                ),
                "planning_authorized": False,
                "decoding_authorized": True,
                "execution_authorized": False,
            }

            receipt = (
                DecodingCapabilityReceiptV1(
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

            self.__pending[key] = (
                intent,
                receipt,
            )

        return intent

    def _reveal_from_owner(
        self,
        intent: DecodingAuthorizationIntentV1,
    ) -> AuthorizedDecodingV1:
        if not isinstance(
            intent,
            DecodingAuthorizationIntentV1,
        ):
            raise TypeError(
                "intent must be DecodingAuthorizationIntentV1"
            )

        intent.validate()

        with self.__lock:
            entry = self.__pending.get(
                id(intent)
            )

            if entry is None:
                raise DecodingAuthorityError(
                    "decoding intent was not precommitted "
                    "by this authority instance"
                )

            stored, receipt = entry

            if stored is not intent:
                raise DecodingAuthorityError(
                    "decoding intent object differs from precommit"
                )

            intent.validate()

            if (
                receipt.intent_digest
                != intent.intent_digest
            ):
                raise DecodingAuthorityError(
                    "decoding receipt/intent identity mismatch"
                )

            del self.__pending[
                id(intent)
            ]

            return AuthorizedDecodingV1(
                intent=intent,
                receipt=receipt,
            )

    def _consume_from_owner(
        self,
        authorized: AuthorizedDecodingV1,
    ) -> DecodingConsumptionV1:
        if not isinstance(
            authorized,
            AuthorizedDecodingV1,
        ):
            raise TypeError(
                "authorized must be AuthorizedDecodingV1"
            )

        intent = authorized.intent
        receipt = authorized.receipt

        intent.validate()
        receipt.validate()

        if (
            receipt.authority_instance_id
            != self.__instance_id
        ):
            raise DecodingAuthorityError(
                "receipt belongs to another "
                "decoding authority instance"
            )

        for name in (
            "intent_digest",
            "planning_artifact_digest",
            "planning_input_digest",
            "materialization_digest",
            "topology_digest",
            "request_id",
            "decoder_adapter_id",
            "decoder_adapter_version",
        ):
            if (
                getattr(receipt, name)
                != getattr(intent, name)
            ):
                raise DecodingAuthorityError(
                    f"decoding receipt {name} mismatch"
                )

        with self.__lock:
            active = self.__active.get(
                receipt.capability_id
            )

            if active is None:
                raise DecodingAuthorityError(
                    "decoding capability is not active"
                )

            if active != receipt.receipt_digest:
                raise DecodingAuthorityError(
                    "decoding capability receipt mismatch"
                )

            del self.__active[
                receipt.capability_id
            ]

        base = {
            "schema": _DECODING_CONSUMPTION_SCHEMA,
            "authority_instance_id": (
                receipt.authority_instance_id
            ),
            "capability_id": (
                receipt.capability_id
            ),
            "intent_digest": (
                intent.intent_digest
            ),
            "planning_artifact_digest": (
                intent.planning_artifact_digest
            ),
            "planning_input_digest": (
                intent.planning_input_digest
            ),
            "planning_consumption_digest": (
                intent.planning_consumption_digest
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
            "decoder_adapter_id": (
                intent.decoder_adapter_id
            ),
            "decoder_adapter_version": (
                intent.decoder_adapter_version
            ),
            "authority": (
                DECODING_AUTHORITY
            ),
            "planning_authorized": False,
            "decoding_authorized": True,
            "execution_authorized": False,
            "receipt_digest": (
                receipt.receipt_digest
            ),
        }

        consumption = DecodingConsumptionV1(
            **base,
            consumption_digest=_domain_digest(
                _CONSUMPTION_DOMAIN,
                base,
            ),
        )

        consumption.validate()

        return consumption


def _new_decoding_authority(
) -> _DecodingAuthority:
    """Create one private DECODING authority instance."""
    return _DecodingAuthority()
