"""One-shot PLANNING authority for signed structural planning inputs.

This module grants exactly one authority:

    PLANNING

It does not authorize decoding or execution.

The capability state machine mirrors the established Elpis lineage pattern:

1. validate and precommit an immutable PlanningInputV1;
2. bind it to one explicit planner identity;
3. reveal one capability exactly once;
4. consume that capability exactly once against the issuing instance.

The private issuer does not compile a plan. A deterministic planner is a
separate downstream component and must consume the resulting proof.

Hostile same-process reflection/isolation is outside this contract, matching
the existing P0 lineage-authority threat model.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import secrets
import threading

from .planning_input import PlanningInputV1


PLANNING_AUTHORITY = "PLANNING"

_PLANNING_INTENT_SCHEMA = (
    "elpis.structural-guidance.planning-intent.v1"
)

_PLANNING_RECEIPT_SCHEMA = (
    "elpis.structural-guidance.planning-capability-receipt.v1"
)

_PLANNING_CONSUMPTION_SCHEMA = (
    "elpis.structural-guidance.planning-capability-consumption.v1"
)

_INTENT_DOMAIN = (
    "elpis.structural-guidance.planning-intent.v1"
)

_INSTANCE_DOMAIN = (
    "elpis.structural-guidance.planning-authority-instance.v1"
)

_RECEIPT_DOMAIN = (
    "elpis.structural-guidance.planning-capability-receipt.v1"
)

_CONSUMPTION_DOMAIN = (
    "elpis.structural-guidance.planning-capability-consumption.v1"
)

_ID = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
)


class PlanningAuthorityError(ValueError):
    """Fail-closed planning-authority rejection."""


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
        raise PlanningAuthorityError(
            f"{name} must be SHA-256 hex"
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise PlanningAuthorityError(
            f"{name} must be SHA-256 hex"
        ) from exc


def _require_identity(
    name: str,
    value: str,
) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise PlanningAuthorityError(
            f"invalid {name}"
        )


@dataclass(frozen=True, slots=True)
class PlanningAuthorizationIntentV1:
    schema: str

    planning_input_digest: str
    materialization_digest: str
    topology_digest: str
    semantic_input_digest: str

    request_id: str
    request_sidecar_digest: str
    expert_selection_digest: str

    planner_id: str
    planner_version: str

    intent_digest: str

    def payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "planning_input_digest": (
                self.planning_input_digest
            ),
            "materialization_digest": (
                self.materialization_digest
            ),
            "topology_digest": self.topology_digest,
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
            "planner_version": self.planner_version,
        }

    def validate(self) -> None:
        if self.schema != _PLANNING_INTENT_SCHEMA:
            raise PlanningAuthorityError(
                "unsupported planning intent schema"
            )

        for name, value in (
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
                "request_sidecar_digest",
                self.request_sidecar_digest,
            ),
            (
                "expert_selection_digest",
                self.expert_selection_digest,
            ),
            (
                "intent_digest",
                self.intent_digest,
            ),
        ):
            _require_digest(name, value)

        _require_identity(
            "request_id",
            self.request_id,
        )
        _require_identity(
            "planner_id",
            self.planner_id,
        )
        _require_identity(
            "planner_version",
            self.planner_version,
        )

        expected = _domain_digest(
            _INTENT_DOMAIN,
            self.payload(),
        )

        if self.intent_digest != expected:
            raise PlanningAuthorityError(
                "planning intent digest mismatch"
            )


@dataclass(frozen=True, slots=True)
class PlanningCapabilityReceiptV1:
    schema: str

    authority_instance_id: str
    capability_id: str
    issuance_sequence: int

    intent_digest: str
    planning_input_digest: str
    materialization_digest: str
    topology_digest: str

    request_id: str

    planner_id: str
    planner_version: str

    authority: str
    planning_authorized: bool
    decoding_authorized: bool
    execution_authorized: bool

    receipt_digest: str

    def payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "authority_instance_id": (
                self.authority_instance_id
            ),
            "capability_id": self.capability_id,
            "issuance_sequence": (
                self.issuance_sequence
            ),
            "intent_digest": self.intent_digest,
            "planning_input_digest": (
                self.planning_input_digest
            ),
            "materialization_digest": (
                self.materialization_digest
            ),
            "topology_digest": self.topology_digest,
            "request_id": self.request_id,
            "planner_id": self.planner_id,
            "planner_version": self.planner_version,
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

    def validate(self) -> None:
        if self.schema != _PLANNING_RECEIPT_SCHEMA:
            raise PlanningAuthorityError(
                "unsupported planning receipt schema"
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
            _require_digest(name, value)

        if (
            not isinstance(self.issuance_sequence, int)
            or isinstance(self.issuance_sequence, bool)
            or self.issuance_sequence < 0
        ):
            raise PlanningAuthorityError(
                "issuance_sequence cannot be negative"
            )

        _require_identity(
            "request_id",
            self.request_id,
        )
        _require_identity(
            "planner_id",
            self.planner_id,
        )
        _require_identity(
            "planner_version",
            self.planner_version,
        )

        if self.authority != PLANNING_AUTHORITY:
            raise PlanningAuthorityError(
                "planning capability has wrong authority"
            )

        if self.planning_authorized is not True:
            raise PlanningAuthorityError(
                "planning capability must authorize planning"
            )

        if self.decoding_authorized is not False:
            raise PlanningAuthorityError(
                "planning capability may not authorize decoding"
            )

        if self.execution_authorized is not False:
            raise PlanningAuthorityError(
                "planning capability may not authorize execution"
            )

        expected = _domain_digest(
            _RECEIPT_DOMAIN,
            self.payload(),
        )

        if self.receipt_digest != expected:
            raise PlanningAuthorityError(
                "planning capability receipt digest mismatch"
            )


@dataclass(frozen=True, slots=True)
class AuthorizedPlanningV1:
    intent: PlanningAuthorizationIntentV1
    receipt: PlanningCapabilityReceiptV1


@dataclass(frozen=True, slots=True)
class PlanningConsumptionV1:
    schema: str

    authority_instance_id: str
    capability_id: str

    intent_digest: str
    planning_input_digest: str
    materialization_digest: str
    topology_digest: str

    request_id: str

    planner_id: str
    planner_version: str

    authority: str
    planning_authorized: bool
    decoding_authorized: bool
    execution_authorized: bool

    receipt_digest: str
    consumption_digest: str

    def payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "authority_instance_id": (
                self.authority_instance_id
            ),
            "capability_id": self.capability_id,
            "intent_digest": self.intent_digest,
            "planning_input_digest": (
                self.planning_input_digest
            ),
            "materialization_digest": (
                self.materialization_digest
            ),
            "topology_digest": self.topology_digest,
            "request_id": self.request_id,
            "planner_id": self.planner_id,
            "planner_version": self.planner_version,
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
            "receipt_digest": self.receipt_digest,
        }

    def validate(self) -> None:
        if self.schema != _PLANNING_CONSUMPTION_SCHEMA:
            raise PlanningAuthorityError(
                "unsupported planning consumption schema"
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
            (
                "consumption_digest",
                self.consumption_digest,
            ),
        ):
            _require_digest(name, value)

        _require_identity(
            "request_id",
            self.request_id,
        )
        _require_identity(
            "planner_id",
            self.planner_id,
        )
        _require_identity(
            "planner_version",
            self.planner_version,
        )

        if self.authority != PLANNING_AUTHORITY:
            raise PlanningAuthorityError(
                "planning consumption has wrong authority"
            )

        if self.planning_authorized is not True:
            raise PlanningAuthorityError(
                "planning consumption must authorize planning"
            )

        if self.decoding_authorized is not False:
            raise PlanningAuthorityError(
                "planning consumption may not authorize decoding"
            )

        if self.execution_authorized is not False:
            raise PlanningAuthorityError(
                "planning consumption may not authorize execution"
            )

        expected = _domain_digest(
            _CONSUMPTION_DOMAIN,
            self.payload(),
        )

        if self.consumption_digest != expected:
            raise PlanningAuthorityError(
                "planning consumption digest mismatch"
            )


def _build_intent(
    planning_input: PlanningInputV1,
    *,
    planner_id: str,
    planner_version: str,
) -> PlanningAuthorizationIntentV1:
    if not isinstance(
        planning_input,
        PlanningInputV1,
    ):
        raise TypeError(
            "planning_input must be PlanningInputV1"
        )

    planning_input.validate()

    if not planning_input.validate_digest():
        raise PlanningAuthorityError(
            "planning input digest is invalid"
        )

    if planning_input.authority_granted != 0:
        raise PlanningAuthorityError(
            "planning input already carries authority"
        )

    if (
        planning_input.planning_authorized
        or planning_input.decoding_authorized
        or planning_input.execution_authorized
    ):
        raise PlanningAuthorityError(
            "planning input carries forbidden authority"
        )

    _require_identity(
        "planner_id",
        planner_id,
    )
    _require_identity(
        "planner_version",
        planner_version,
    )

    base = {
        "schema": _PLANNING_INTENT_SCHEMA,
        "planning_input_digest": (
            planning_input.planning_input_digest
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
        "request_id": planning_input.request_id,
        "request_sidecar_digest": (
            planning_input.request_sidecar_digest
        ),
        "expert_selection_digest": (
            planning_input.expert_selection_digest
        ),
        "planner_id": planner_id,
        "planner_version": planner_version,
    }

    intent = PlanningAuthorizationIntentV1(
        **base,
        intent_digest=_domain_digest(
            _INTENT_DOMAIN,
            base,
        ),
    )

    intent.validate()

    return intent


class _PlanningAuthority:
    """Private instance-bound, one-shot PLANNING capability authority."""

    __slots__ = (
        "__instance_id",
        "__active",
        "__pending",
        "__sequence",
        "__lock",
    )

    def __init__(self) -> None:
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
                PlanningAuthorizationIntentV1,
                PlanningCapabilityReceiptV1,
            ],
        ] = {}

        self.__sequence = 0
        self.__lock = threading.RLock()

    def _precommit_from_owner(
        self,
        planning_input: PlanningInputV1,
        *,
        planner_id: str,
        planner_version: str,
    ) -> PlanningAuthorizationIntentV1:
        intent = _build_intent(
            planning_input,
            planner_id=planner_id,
            planner_version=planner_version,
        )

        key = id(intent)

        with self.__lock:
            if key in self.__pending:
                raise PlanningAuthorityError(
                    "planning intent already precommitted"
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
                "schema": _PLANNING_RECEIPT_SCHEMA,
                "authority_instance_id": (
                    self.__instance_id
                ),
                "capability_id": capability,
                "issuance_sequence": sequence,
                "intent_digest": (
                    intent.intent_digest
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
                "request_id": intent.request_id,
                "planner_id": intent.planner_id,
                "planner_version": (
                    intent.planner_version
                ),
                "authority": PLANNING_AUTHORITY,
                "planning_authorized": True,
                "decoding_authorized": False,
                "execution_authorized": False,
            }

            receipt = PlanningCapabilityReceiptV1(
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

            self.__pending[key] = (
                intent,
                receipt,
            )

        return intent

    def _reveal_from_owner(
        self,
        intent: PlanningAuthorizationIntentV1,
    ) -> AuthorizedPlanningV1:
        if not isinstance(
            intent,
            PlanningAuthorizationIntentV1,
        ):
            raise TypeError(
                "intent must be PlanningAuthorizationIntentV1"
            )

        intent.validate()

        with self.__lock:
            entry = self.__pending.get(
                id(intent)
            )

            if entry is None:
                raise PlanningAuthorityError(
                    "planning intent was not precommitted "
                    "by this authority instance"
                )

            stored, receipt = entry

            if stored is not intent:
                raise PlanningAuthorityError(
                    "planning intent object differs from precommit"
                )

            intent.validate()

            if (
                receipt.intent_digest
                != intent.intent_digest
            ):
                raise PlanningAuthorityError(
                    "planning receipt/intent identity mismatch"
                )

            del self.__pending[
                id(intent)
            ]

            return AuthorizedPlanningV1(
                intent=intent,
                receipt=receipt,
            )

    def _consume_from_owner(
        self,
        authorized: AuthorizedPlanningV1,
    ) -> PlanningConsumptionV1:
        if not isinstance(
            authorized,
            AuthorizedPlanningV1,
        ):
            raise TypeError(
                "authorized must be AuthorizedPlanningV1"
            )

        intent = authorized.intent
        receipt = authorized.receipt

        intent.validate()
        receipt.validate()

        if (
            receipt.authority_instance_id
            != self.__instance_id
        ):
            raise PlanningAuthorityError(
                "receipt belongs to another planning authority instance"
            )

        for name in (
            "intent_digest",
            "planning_input_digest",
            "materialization_digest",
            "topology_digest",
            "request_id",
            "planner_id",
            "planner_version",
        ):
            if (
                getattr(receipt, name)
                != getattr(intent, name)
            ):
                raise PlanningAuthorityError(
                    f"planning receipt {name} mismatch"
                )

        with self.__lock:
            active = self.__active.get(
                receipt.capability_id
            )

            if active is None:
                raise PlanningAuthorityError(
                    "planning capability is not active"
                )

            if active != receipt.receipt_digest:
                raise PlanningAuthorityError(
                    "planning capability receipt mismatch"
                )

            del self.__active[
                receipt.capability_id
            ]

        base = {
            "schema": _PLANNING_CONSUMPTION_SCHEMA,
            "authority_instance_id": (
                receipt.authority_instance_id
            ),
            "capability_id": receipt.capability_id,
            "intent_digest": intent.intent_digest,
            "planning_input_digest": (
                intent.planning_input_digest
            ),
            "materialization_digest": (
                intent.materialization_digest
            ),
            "topology_digest": (
                intent.topology_digest
            ),
            "request_id": intent.request_id,
            "planner_id": intent.planner_id,
            "planner_version": (
                intent.planner_version
            ),
            "authority": PLANNING_AUTHORITY,
            "planning_authorized": True,
            "decoding_authorized": False,
            "execution_authorized": False,
            "receipt_digest": receipt.receipt_digest,
        }

        consumption = PlanningConsumptionV1(
            **base,
            consumption_digest=_domain_digest(
                _CONSUMPTION_DOMAIN,
                base,
            ),
        )

        consumption.validate()

        return consumption


def _new_planning_authority() -> _PlanningAuthority:
    """Create one private PLANNING authority instance."""
    return _PlanningAuthority()
