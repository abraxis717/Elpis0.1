"""One-shot VALIDATION authority for decoded source artifacts.

This authority is intentionally separate from decoding and execution.

It accepts one exact, authority-zero DecodedSourceArtifactV1, binds it to
one explicit validator identity, reveals one validation capability, and
consumes that capability exactly once.

The capability authorizes validation only.

It does not parse source, invoke a validator, compile source, execute
source, mutate state, or authorize execution/refinement.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import secrets
import threading

from .source_emitter import (
    DecodedSourceArtifactV1,
)


VALIDATION_AUTHORITY = "VALIDATION"

_VALIDATION_INTENT_SCHEMA = (
    "elpis.structural-guidance."
    "validation-intent.v1"
)

_VALIDATION_RECEIPT_SCHEMA = (
    "elpis.structural-guidance."
    "validation-capability-receipt.v1"
)

_VALIDATION_CONSUMPTION_SCHEMA = (
    "elpis.structural-guidance."
    "validation-capability-consumption.v1"
)

_INTENT_DOMAIN = (
    "elpis.structural-guidance."
    "validation-intent.v1"
)

_INSTANCE_DOMAIN = (
    "elpis.structural-guidance."
    "validation-authority-instance.v1"
)

_RECEIPT_DOMAIN = (
    "elpis.structural-guidance."
    "validation-capability-receipt.v1"
)

_CONSUMPTION_DOMAIN = (
    "elpis.structural-guidance."
    "validation-capability-consumption.v1"
)

_ID = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
)


class ValidationAuthorityError(ValueError):
    """Fail-closed validation-authority rejection."""


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
        raise ValidationAuthorityError(
            f"{name} must be SHA-256 hex"
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise ValidationAuthorityError(
            f"{name} must be SHA-256 hex"
        ) from exc


def _require_identity(
    name: str,
    value: str,
) -> None:
    if (
        not isinstance(value, str)
        or not _ID.fullmatch(value)
    ):
        raise ValidationAuthorityError(
            f"invalid {name}"
        )


def _require_nonempty(
    name: str,
    value: str,
) -> None:
    if not isinstance(value, str) or not value:
        raise ValidationAuthorityError(
            f"{name} cannot be empty"
        )


@dataclass(frozen=True, slots=True)
class ValidationAuthorizationIntentV1:
    schema: str

    source_artifact_digest: str
    source_sha256: str

    decoder_plan_digest: str
    source_input_digest: str
    planning_input_digest: str

    materialization_digest: str
    topology_digest: str
    semantic_input_digest: str

    request_id: str

    validator_id: str
    validator_version: str

    intent_digest: str

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
            "source_input_digest": (
                self.source_input_digest
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
        }

    def validate(
        self,
    ) -> None:
        if (
            self.schema
            != _VALIDATION_INTENT_SCHEMA
        ):
            raise ValidationAuthorityError(
                "unsupported validation intent schema"
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
                "source_input_digest",
                self.source_input_digest,
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
            "validator_id",
            self.validator_id,
        )

        _require_identity(
            "validator_version",
            self.validator_version,
        )

        expected = _domain_digest(
            _INTENT_DOMAIN,
            self.payload(),
        )

        if self.intent_digest != expected:
            raise ValidationAuthorityError(
                "validation intent digest mismatch"
            )


@dataclass(frozen=True, slots=True)
class ValidationCapabilityReceiptV1:
    schema: str

    authority_instance_id: str
    capability_id: str
    issuance_sequence: int

    intent_digest: str

    source_artifact_digest: str
    source_sha256: str

    decoder_plan_digest: str
    source_input_digest: str
    planning_input_digest: str

    materialization_digest: str
    topology_digest: str
    semantic_input_digest: str

    request_id: str

    validator_id: str
    validator_version: str

    authority: str

    planning_authorized: bool
    decoding_authorized: bool
    source_emission_authorized: bool
    validation_authorized: bool
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
            "source_artifact_digest": (
                self.source_artifact_digest
            ),
            "source_sha256": (
                self.source_sha256
            ),
            "decoder_plan_digest": (
                self.decoder_plan_digest
            ),
            "source_input_digest": (
                self.source_input_digest
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
            "validation_authorized": (
                self.validation_authorized
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
            != _VALIDATION_RECEIPT_SCHEMA
        ):
            raise ValidationAuthorityError(
                "unsupported validation receipt schema"
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
                "source_input_digest",
                self.source_input_digest,
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
                "receipt_digest",
                self.receipt_digest,
            ),
        ):
            _require_digest(
                name,
                value,
            )

        if (
            not isinstance(
                self.issuance_sequence,
                int,
            )
            or isinstance(
                self.issuance_sequence,
                bool,
            )
            or self.issuance_sequence < 0
        ):
            raise ValidationAuthorityError(
                "issuance_sequence cannot be negative"
            )

        _require_nonempty(
            "request_id",
            self.request_id,
        )

        _require_identity(
            "validator_id",
            self.validator_id,
        )

        _require_identity(
            "validator_version",
            self.validator_version,
        )

        if self.authority != VALIDATION_AUTHORITY:
            raise ValidationAuthorityError(
                "validation capability has wrong authority"
            )

        if self.planning_authorized is not False:
            raise ValidationAuthorityError(
                "validation capability may not authorize planning"
            )

        if self.decoding_authorized is not False:
            raise ValidationAuthorityError(
                "validation capability may not authorize decoding"
            )

        if (
            self.source_emission_authorized
            is not False
        ):
            raise ValidationAuthorityError(
                "validation capability may not authorize source emission"
            )

        if self.validation_authorized is not True:
            raise ValidationAuthorityError(
                "validation capability must authorize validation"
            )

        if self.execution_authorized is not False:
            raise ValidationAuthorityError(
                "validation capability may not authorize execution"
            )

        expected = _domain_digest(
            _RECEIPT_DOMAIN,
            self.payload(),
        )

        if self.receipt_digest != expected:
            raise ValidationAuthorityError(
                "validation receipt digest mismatch"
            )


@dataclass(frozen=True, slots=True)
class AuthorizedValidationV1:
    intent: ValidationAuthorizationIntentV1
    receipt: ValidationCapabilityReceiptV1


@dataclass(frozen=True, slots=True)
class ValidationConsumptionV1:
    schema: str

    authority_instance_id: str
    capability_id: str

    intent_digest: str

    source_artifact_digest: str
    source_sha256: str

    decoder_plan_digest: str
    source_input_digest: str
    planning_input_digest: str

    materialization_digest: str
    topology_digest: str
    semantic_input_digest: str

    request_id: str

    validator_id: str
    validator_version: str

    authority: str

    planning_authorized: bool
    decoding_authorized: bool
    source_emission_authorized: bool
    validation_authorized: bool
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
            "source_artifact_digest": (
                self.source_artifact_digest
            ),
            "source_sha256": (
                self.source_sha256
            ),
            "decoder_plan_digest": (
                self.decoder_plan_digest
            ),
            "source_input_digest": (
                self.source_input_digest
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
            "validation_authorized": (
                self.validation_authorized
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
            != _VALIDATION_CONSUMPTION_SCHEMA
        ):
            raise ValidationAuthorityError(
                "unsupported validation consumption schema"
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
                "source_input_digest",
                self.source_input_digest,
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
            "validator_id",
            self.validator_id,
        )

        _require_identity(
            "validator_version",
            self.validator_version,
        )

        if self.authority != VALIDATION_AUTHORITY:
            raise ValidationAuthorityError(
                "validation consumption has wrong authority"
            )

        if self.planning_authorized is not False:
            raise ValidationAuthorityError(
                "validation consumption may not authorize planning"
            )

        if self.decoding_authorized is not False:
            raise ValidationAuthorityError(
                "validation consumption may not authorize decoding"
            )

        if (
            self.source_emission_authorized
            is not False
        ):
            raise ValidationAuthorityError(
                "validation consumption may not authorize source emission"
            )

        if self.validation_authorized is not True:
            raise ValidationAuthorityError(
                "validation consumption must authorize validation"
            )

        if self.execution_authorized is not False:
            raise ValidationAuthorityError(
                "validation consumption may not authorize execution"
            )

        expected = _domain_digest(
            _CONSUMPTION_DOMAIN,
            self.payload(),
        )

        if self.consumption_digest != expected:
            raise ValidationAuthorityError(
                "validation consumption digest mismatch"
            )


def _build_intent(
    artifact: DecodedSourceArtifactV1,
    *,
    validator_id: str,
    validator_version: str,
) -> ValidationAuthorizationIntentV1:
    if not isinstance(
        artifact,
        DecodedSourceArtifactV1,
    ):
        raise TypeError(
            "artifact must be DecodedSourceArtifactV1"
        )

    artifact.validate()

    if not artifact.validate_digest():
        raise ValidationAuthorityError(
            "source artifact digest is invalid"
        )

    if artifact.authority_granted != 0:
        raise ValidationAuthorityError(
            "source artifact improperly grants authority"
        )

    if (
        artifact.planning_authorized
        or artifact.decoding_authorized
        or artifact.source_emission_authorized
        or artifact.execution_authorized
    ):
        raise ValidationAuthorityError(
            "source artifact already carries authorization"
        )

    _require_identity(
        "validator_id",
        validator_id,
    )

    _require_identity(
        "validator_version",
        validator_version,
    )

    base = {
        "schema": (
            _VALIDATION_INTENT_SCHEMA
        ),
        "source_artifact_digest": (
            artifact.source_artifact_digest
        ),
        "source_sha256": (
            artifact.source_sha256
        ),
        "decoder_plan_digest": (
            artifact.decoder_plan_digest
        ),
        "source_input_digest": (
            artifact.source_input_digest
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
            validator_id
        ),
        "validator_version": (
            validator_version
        ),
    }

    intent = ValidationAuthorizationIntentV1(
        **base,
        intent_digest=_domain_digest(
            _INTENT_DOMAIN,
            base,
        ),
    )

    intent.validate()

    return intent


class _ValidationAuthority:
    """Private instance-bound one-shot VALIDATION authority."""

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

        self.__active: dict[
            str,
            str,
        ] = {}

        self.__pending: dict[
            int,
            tuple[
                ValidationAuthorizationIntentV1,
                ValidationCapabilityReceiptV1,
            ],
        ] = {}

        self.__sequence = 0
        self.__lock = threading.RLock()

    def _precommit_from_owner(
        self,
        artifact: DecodedSourceArtifactV1,
        *,
        validator_id: str,
        validator_version: str,
    ) -> ValidationAuthorizationIntentV1:
        intent = _build_intent(
            artifact,
            validator_id=validator_id,
            validator_version=validator_version,
        )

        key = id(intent)

        with self.__lock:
            if key in self.__pending:
                raise ValidationAuthorityError(
                    "validation intent already precommitted"
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
                    _VALIDATION_RECEIPT_SCHEMA
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
                "source_artifact_digest": (
                    intent.source_artifact_digest
                ),
                "source_sha256": (
                    intent.source_sha256
                ),
                "decoder_plan_digest": (
                    intent.decoder_plan_digest
                ),
                "source_input_digest": (
                    intent.source_input_digest
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
                "semantic_input_digest": (
                    intent.semantic_input_digest
                ),
                "request_id": (
                    intent.request_id
                ),
                "validator_id": (
                    intent.validator_id
                ),
                "validator_version": (
                    intent.validator_version
                ),
                "authority": (
                    VALIDATION_AUTHORITY
                ),
                "planning_authorized": False,
                "decoding_authorized": False,
                "source_emission_authorized": False,
                "validation_authorized": True,
                "execution_authorized": False,
            }

            receipt = ValidationCapabilityReceiptV1(
                **base,
                receipt_digest=_domain_digest(
                    _RECEIPT_DOMAIN,
                    base,
                ),
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
        intent: ValidationAuthorizationIntentV1,
    ) -> AuthorizedValidationV1:
        if not isinstance(
            intent,
            ValidationAuthorizationIntentV1,
        ):
            raise TypeError(
                "intent must be ValidationAuthorizationIntentV1"
            )

        intent.validate()

        with self.__lock:
            entry = self.__pending.get(
                id(intent)
            )

            if entry is None:
                raise ValidationAuthorityError(
                    "validation intent was not precommitted "
                    "by this authority instance"
                )

            stored, receipt = entry

            if stored is not intent:
                raise ValidationAuthorityError(
                    "validation intent object differs from precommit"
                )

            intent.validate()

            if (
                receipt.intent_digest
                != intent.intent_digest
            ):
                raise ValidationAuthorityError(
                    "validation receipt/intent identity mismatch"
                )

            del self.__pending[
                id(intent)
            ]

            return AuthorizedValidationV1(
                intent=intent,
                receipt=receipt,
            )

    def _consume_from_owner(
        self,
        authorized: AuthorizedValidationV1,
    ) -> ValidationConsumptionV1:
        if not isinstance(
            authorized,
            AuthorizedValidationV1,
        ):
            raise TypeError(
                "authorized must be AuthorizedValidationV1"
            )

        intent = authorized.intent
        receipt = authorized.receipt

        intent.validate()
        receipt.validate()

        if (
            receipt.authority_instance_id
            != self.__instance_id
        ):
            raise ValidationAuthorityError(
                "receipt belongs to another "
                "validation authority instance"
            )

        for name in (
            "intent_digest",
            "source_artifact_digest",
            "source_sha256",
            "decoder_plan_digest",
            "source_input_digest",
            "planning_input_digest",
            "materialization_digest",
            "topology_digest",
            "semantic_input_digest",
            "request_id",
            "validator_id",
            "validator_version",
        ):
            if (
                getattr(
                    receipt,
                    name,
                )
                != getattr(
                    intent,
                    name,
                )
            ):
                raise ValidationAuthorityError(
                    f"validation receipt {name} mismatch"
                )

        with self.__lock:
            active = self.__active.get(
                receipt.capability_id
            )

            if active is None:
                raise ValidationAuthorityError(
                    "validation capability is not active"
                )

            if active != receipt.receipt_digest:
                raise ValidationAuthorityError(
                    "validation capability receipt mismatch"
                )

            del self.__active[
                receipt.capability_id
            ]

        base = {
            "schema": (
                _VALIDATION_CONSUMPTION_SCHEMA
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
            "source_artifact_digest": (
                intent.source_artifact_digest
            ),
            "source_sha256": (
                intent.source_sha256
            ),
            "decoder_plan_digest": (
                intent.decoder_plan_digest
            ),
            "source_input_digest": (
                intent.source_input_digest
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
            "semantic_input_digest": (
                intent.semantic_input_digest
            ),
            "request_id": (
                intent.request_id
            ),
            "validator_id": (
                intent.validator_id
            ),
            "validator_version": (
                intent.validator_version
            ),
            "authority": (
                VALIDATION_AUTHORITY
            ),
            "planning_authorized": False,
            "decoding_authorized": False,
            "source_emission_authorized": False,
            "validation_authorized": True,
            "execution_authorized": False,
            "receipt_digest": (
                receipt.receipt_digest
            ),
        }

        consumption = ValidationConsumptionV1(
            **base,
            consumption_digest=_domain_digest(
                _CONSUMPTION_DOMAIN,
                base,
            ),
        )

        consumption.validate()

        return consumption


def _new_validation_authority(
) -> _ValidationAuthority:
    """Create one private VALIDATION authority instance."""
    return _ValidationAuthority()
