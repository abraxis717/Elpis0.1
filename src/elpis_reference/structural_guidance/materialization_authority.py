"""One-shot authority for resolved-topology structural materialization.

This module introduces the first non-zero authority after structural
guidance. The authority is deliberately narrow:

    STRUCTURAL_MATERIALIZATION

It does not authorize decoding or execution.

Issuance follows the existing Elpis lineage-capability discipline:

1. precommit a validated topology + zero-authority observation;
2. reveal the capability once;
3. consume the capability once against the issuing authority instance.

The authority object and factory remain module-private. A future trusted
composition owner may hold one authority instance. Hostile same-process
reflection/isolation is outside this contract, matching the existing P0
lineage-authority threat model.

This module does not materialize anything.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import secrets
import threading

from .consumer import (
    ResolvedTopologyConsumerReceiptV1,
)
from .resolved import (
    ResolvedStructuralTopologyV1,
)


STRUCTURAL_MATERIALIZATION_AUTHORITY = (
    "STRUCTURAL_MATERIALIZATION"
)

_INTENT_SCHEMA = (
    "elpis.structural-guidance."
    "materialization-intent.v1"
)

_RECEIPT_SCHEMA = (
    "elpis.structural-guidance."
    "materialization-capability-receipt.v1"
)

_CONSUMPTION_SCHEMA = (
    "elpis.structural-guidance."
    "materialization-capability-consumption.v1"
)

_INTENT_DOMAIN = (
    "elpis.structural-guidance."
    "materialization-intent.v1"
)

_INSTANCE_DOMAIN = (
    "elpis.structural-guidance."
    "materialization-authority-instance.v1"
)

_RECEIPT_DOMAIN = (
    "elpis.structural-guidance."
    "materialization-capability-receipt.v1"
)

_CONSUMPTION_DOMAIN = (
    "elpis.structural-guidance."
    "materialization-capability-consumption.v1"
)

_ID = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
)


class ResolvedTopologyMaterializationAuthorityError(
    ValueError
):
    """Fail-closed materialization-authority rejection."""


def _canonical_json_bytes(
    payload: dict[str, object],
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
    payload: dict[str, object],
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
        raise ResolvedTopologyMaterializationAuthorityError(
            f"{name} must be SHA-256 hex"
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise ResolvedTopologyMaterializationAuthorityError(
            f"{name} must be SHA-256 hex"
        ) from exc


def _require_identity(
    name: str,
    value: str,
) -> None:
    if not _ID.fullmatch(value):
        raise ResolvedTopologyMaterializationAuthorityError(
            f"invalid {name}"
        )


@dataclass(frozen=True, slots=True)
class ResolvedTopologyMaterializationIntentV1:
    schema: str

    topology_digest: str
    observation_receipt_digest: str
    observer_consumer_id: str
    observer_consumer_version: str

    materializer_id: str
    materializer_version: str

    intent_digest: str

    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "topology_digest": self.topology_digest,
            "observation_receipt_digest": (
                self.observation_receipt_digest
            ),
            "observer_consumer_id": (
                self.observer_consumer_id
            ),
            "observer_consumer_version": (
                self.observer_consumer_version
            ),
            "materializer_id": self.materializer_id,
            "materializer_version": (
                self.materializer_version
            ),
        }

    def validate(
        self,
    ) -> None:
        if self.schema != _INTENT_SCHEMA:
            raise ResolvedTopologyMaterializationAuthorityError(
                "unsupported materialization intent schema"
            )

        _require_digest(
            "topology_digest",
            self.topology_digest,
        )
        _require_digest(
            "observation_receipt_digest",
            self.observation_receipt_digest,
        )

        _require_identity(
            "observer_consumer_id",
            self.observer_consumer_id,
        )
        _require_identity(
            "observer_consumer_version",
            self.observer_consumer_version,
        )
        _require_identity(
            "materializer_id",
            self.materializer_id,
        )
        _require_identity(
            "materializer_version",
            self.materializer_version,
        )

        _require_digest(
            "intent_digest",
            self.intent_digest,
        )

        expected = _domain_digest(
            _INTENT_DOMAIN,
            self.payload(),
        )

        if self.intent_digest != expected:
            raise ResolvedTopologyMaterializationAuthorityError(
                "materialization intent digest mismatch"
            )


@dataclass(frozen=True, slots=True)
class ResolvedTopologyMaterializationCapabilityReceiptV1:
    schema: str

    authority_instance_id: str
    capability_id: str
    issuance_sequence: int

    intent_digest: str
    topology_digest: str
    observation_receipt_digest: str

    materializer_id: str
    materializer_version: str

    authority: str
    materialization_authorized: bool
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
            "capability_id": self.capability_id,
            "issuance_sequence": (
                self.issuance_sequence
            ),
            "intent_digest": self.intent_digest,
            "topology_digest": self.topology_digest,
            "observation_receipt_digest": (
                self.observation_receipt_digest
            ),
            "materializer_id": self.materializer_id,
            "materializer_version": (
                self.materializer_version
            ),
            "authority": self.authority,
            "materialization_authorized": (
                self.materialization_authorized
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
        if self.schema != _RECEIPT_SCHEMA:
            raise ResolvedTopologyMaterializationAuthorityError(
                "unsupported materialization receipt schema"
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
                "topology_digest",
                self.topology_digest,
            ),
            (
                "observation_receipt_digest",
                self.observation_receipt_digest,
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

        if self.issuance_sequence < 0:
            raise ResolvedTopologyMaterializationAuthorityError(
                "issuance_sequence cannot be negative"
            )

        _require_identity(
            "materializer_id",
            self.materializer_id,
        )
        _require_identity(
            "materializer_version",
            self.materializer_version,
        )

        if (
            self.authority
            != STRUCTURAL_MATERIALIZATION_AUTHORITY
        ):
            raise ResolvedTopologyMaterializationAuthorityError(
                "materialization capability has wrong authority"
            )

        if self.materialization_authorized is not True:
            raise ResolvedTopologyMaterializationAuthorityError(
                "materialization capability must authorize "
                "structural materialization"
            )

        if self.decoding_authorized is not False:
            raise ResolvedTopologyMaterializationAuthorityError(
                "materialization capability may not authorize decoding"
            )

        if self.execution_authorized is not False:
            raise ResolvedTopologyMaterializationAuthorityError(
                "materialization capability may not authorize execution"
            )

        expected = _domain_digest(
            _RECEIPT_DOMAIN,
            self.payload(),
        )

        if self.receipt_digest != expected:
            raise ResolvedTopologyMaterializationAuthorityError(
                "materialization capability receipt digest mismatch"
            )


@dataclass(frozen=True, slots=True)
class AuthorizedResolvedTopologyMaterializationV1:
    intent: ResolvedTopologyMaterializationIntentV1
    receipt: ResolvedTopologyMaterializationCapabilityReceiptV1


@dataclass(frozen=True, slots=True)
class ResolvedTopologyMaterializationConsumptionV1:
    schema: str

    authority_instance_id: str
    capability_id: str

    intent_digest: str
    topology_digest: str
    receipt_digest: str

    materializer_id: str
    materializer_version: str

    authority: str
    materialization_authorized: bool
    decoding_authorized: bool
    execution_authorized: bool

    consumption_digest: str

    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "authority_instance_id": (
                self.authority_instance_id
            ),
            "capability_id": self.capability_id,
            "intent_digest": self.intent_digest,
            "topology_digest": self.topology_digest,
            "receipt_digest": self.receipt_digest,
            "materializer_id": self.materializer_id,
            "materializer_version": (
                self.materializer_version
            ),
            "authority": self.authority,
            "materialization_authorized": (
                self.materialization_authorized
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
        if self.schema != _CONSUMPTION_SCHEMA:
            raise ResolvedTopologyMaterializationAuthorityError(
                "unsupported materialization consumption schema"
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
            _require_digest(
                name,
                value,
            )

        _require_identity(
            "materializer_id",
            self.materializer_id,
        )
        _require_identity(
            "materializer_version",
            self.materializer_version,
        )

        if (
            self.authority
            != STRUCTURAL_MATERIALIZATION_AUTHORITY
        ):
            raise ResolvedTopologyMaterializationAuthorityError(
                "consumption has wrong authority"
            )

        if self.materialization_authorized is not True:
            raise ResolvedTopologyMaterializationAuthorityError(
                "consumption must authorize structural materialization"
            )

        if self.decoding_authorized is not False:
            raise ResolvedTopologyMaterializationAuthorityError(
                "consumption may not authorize decoding"
            )

        if self.execution_authorized is not False:
            raise ResolvedTopologyMaterializationAuthorityError(
                "consumption may not authorize execution"
            )

        expected = _domain_digest(
            _CONSUMPTION_DOMAIN,
            self.payload(),
        )

        if self.consumption_digest != expected:
            raise ResolvedTopologyMaterializationAuthorityError(
                "materialization consumption digest mismatch"
            )


def _validate_observation(
    topology: ResolvedStructuralTopologyV1,
    observation: ResolvedTopologyConsumerReceiptV1,
) -> None:
    if not isinstance(
        topology,
        ResolvedStructuralTopologyV1,
    ):
        raise TypeError(
            "topology must be ResolvedStructuralTopologyV1"
        )

    topology.validate()

    if not topology.validate_digest():
        raise ResolvedTopologyMaterializationAuthorityError(
            "resolved topology digest is invalid"
        )

    if not isinstance(
        observation,
        ResolvedTopologyConsumerReceiptV1,
    ):
        raise TypeError(
            "observation must be "
            "ResolvedTopologyConsumerReceiptV1"
        )

    observation.validate()

    if not observation.validate_digest():
        raise ResolvedTopologyMaterializationAuthorityError(
            "observation receipt digest is invalid"
        )

    if observation.outcome != "OBSERVED":
        raise ResolvedTopologyMaterializationAuthorityError(
            "materialization requires OBSERVED topology"
        )

    if (
        observation.topology_digest
        != topology.topology_digest
    ):
        raise ResolvedTopologyMaterializationAuthorityError(
            "observation/topology identity mismatch"
        )

    if observation.authority_granted != 0:
        raise ResolvedTopologyMaterializationAuthorityError(
            "observation widened authority"
        )

    if (
        observation.execution_authorized
        or observation.decoding_authorized
        or observation.materialization_authorized
    ):
        raise ResolvedTopologyMaterializationAuthorityError(
            "observation carried forbidden authority"
        )


def _build_intent(
    topology: ResolvedStructuralTopologyV1,
    observation: ResolvedTopologyConsumerReceiptV1,
    *,
    materializer_id: str,
    materializer_version: str,
) -> ResolvedTopologyMaterializationIntentV1:
    _validate_observation(
        topology,
        observation,
    )

    _require_identity(
        "materializer_id",
        materializer_id,
    )
    _require_identity(
        "materializer_version",
        materializer_version,
    )

    base = {
        "schema": _INTENT_SCHEMA,
        "topology_digest": (
            topology.topology_digest
        ),
        "observation_receipt_digest": (
            observation.receipt_digest
        ),
        "observer_consumer_id": (
            observation.consumer_id
        ),
        "observer_consumer_version": (
            observation.consumer_version
        ),
        "materializer_id": materializer_id,
        "materializer_version": (
            materializer_version
        ),
    }

    intent = ResolvedTopologyMaterializationIntentV1(
        **base,
        intent_digest=_domain_digest(
            _INTENT_DOMAIN,
            base,
        ),
    )

    intent.validate()

    return intent


class _ResolvedTopologyMaterializationAuthority:
    """Private one-shot issuer/consumer state machine."""

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
                ResolvedTopologyMaterializationIntentV1,
                ResolvedTopologyMaterializationCapabilityReceiptV1,
            ],
        ] = {}

        self.__sequence = 0
        self.__lock = threading.RLock()

    def _precommit_from_owner(
        self,
        topology: ResolvedStructuralTopologyV1,
        observation: ResolvedTopologyConsumerReceiptV1,
        *,
        materializer_id: str,
        materializer_version: str,
    ) -> ResolvedTopologyMaterializationIntentV1:
        intent = _build_intent(
            topology,
            observation,
            materializer_id=materializer_id,
            materializer_version=materializer_version,
        )

        key = id(intent)

        with self.__lock:
            if key in self.__pending:
                raise ResolvedTopologyMaterializationAuthorityError(
                    "materialization intent already precommitted"
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
                "schema": _RECEIPT_SCHEMA,
                "authority_instance_id": (
                    self.__instance_id
                ),
                "capability_id": capability,
                "issuance_sequence": sequence,
                "intent_digest": (
                    intent.intent_digest
                ),
                "topology_digest": (
                    intent.topology_digest
                ),
                "observation_receipt_digest": (
                    intent.observation_receipt_digest
                ),
                "materializer_id": (
                    intent.materializer_id
                ),
                "materializer_version": (
                    intent.materializer_version
                ),
                "authority": (
                    STRUCTURAL_MATERIALIZATION_AUTHORITY
                ),
                "materialization_authorized": True,
                "decoding_authorized": False,
                "execution_authorized": False,
            }

            receipt = (
                ResolvedTopologyMaterializationCapabilityReceiptV1(
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
        intent: ResolvedTopologyMaterializationIntentV1,
    ) -> AuthorizedResolvedTopologyMaterializationV1:
        if not isinstance(
            intent,
            ResolvedTopologyMaterializationIntentV1,
        ):
            raise TypeError(
                "intent must be "
                "ResolvedTopologyMaterializationIntentV1"
            )

        intent.validate()

        with self.__lock:
            entry = self.__pending.get(
                id(intent)
            )

            if entry is None:
                raise ResolvedTopologyMaterializationAuthorityError(
                    "intent was not precommitted by "
                    "this authority instance"
                )

            stored, receipt = entry

            if stored is not intent:
                raise ResolvedTopologyMaterializationAuthorityError(
                    "intent object differs from precommit"
                )

            intent.validate()

            if (
                receipt.intent_digest
                != intent.intent_digest
            ):
                raise ResolvedTopologyMaterializationAuthorityError(
                    "receipt/intent identity mismatch"
                )

            del self.__pending[
                id(intent)
            ]

            return (
                AuthorizedResolvedTopologyMaterializationV1(
                    intent=intent,
                    receipt=receipt,
                )
            )

    def _consume_from_owner(
        self,
        authorized: AuthorizedResolvedTopologyMaterializationV1,
    ) -> ResolvedTopologyMaterializationConsumptionV1:
        if not isinstance(
            authorized,
            AuthorizedResolvedTopologyMaterializationV1,
        ):
            raise TypeError(
                "authorized must be "
                "AuthorizedResolvedTopologyMaterializationV1"
            )

        intent = authorized.intent
        receipt = authorized.receipt

        intent.validate()
        receipt.validate()

        if (
            receipt.authority_instance_id
            != self.__instance_id
        ):
            raise ResolvedTopologyMaterializationAuthorityError(
                "receipt belongs to another "
                "materialization authority instance"
            )

        if (
            receipt.intent_digest
            != intent.intent_digest
        ):
            raise ResolvedTopologyMaterializationAuthorityError(
                "receipt intent mismatch"
            )

        if (
            receipt.topology_digest
            != intent.topology_digest
        ):
            raise ResolvedTopologyMaterializationAuthorityError(
                "receipt topology mismatch"
            )

        if (
            receipt.observation_receipt_digest
            != intent.observation_receipt_digest
        ):
            raise ResolvedTopologyMaterializationAuthorityError(
                "receipt observation mismatch"
            )

        if (
            receipt.materializer_id
            != intent.materializer_id
        ):
            raise ResolvedTopologyMaterializationAuthorityError(
                "receipt materializer identity mismatch"
            )

        if (
            receipt.materializer_version
            != intent.materializer_version
        ):
            raise ResolvedTopologyMaterializationAuthorityError(
                "receipt materializer version mismatch"
            )

        with self.__lock:
            active = self.__active.get(
                receipt.capability_id
            )

            if active is None:
                raise ResolvedTopologyMaterializationAuthorityError(
                    "materialization capability is not active"
                )

            if active != receipt.receipt_digest:
                raise ResolvedTopologyMaterializationAuthorityError(
                    "materialization capability receipt mismatch"
                )

            del self.__active[
                receipt.capability_id
            ]

        base = {
            "schema": _CONSUMPTION_SCHEMA,
            "authority_instance_id": (
                receipt.authority_instance_id
            ),
            "capability_id": (
                receipt.capability_id
            ),
            "intent_digest": intent.intent_digest,
            "topology_digest": (
                intent.topology_digest
            ),
            "receipt_digest": (
                receipt.receipt_digest
            ),
            "materializer_id": (
                intent.materializer_id
            ),
            "materializer_version": (
                intent.materializer_version
            ),
            "authority": (
                STRUCTURAL_MATERIALIZATION_AUTHORITY
            ),
            "materialization_authorized": True,
            "decoding_authorized": False,
            "execution_authorized": False,
        }

        consumption = (
            ResolvedTopologyMaterializationConsumptionV1(
                **base,
                consumption_digest=_domain_digest(
                    _CONSUMPTION_DOMAIN,
                    base,
                ),
            )
        )

        consumption.validate()

        return consumption


def _new_resolved_topology_materialization_authority(
) -> _ResolvedTopologyMaterializationAuthority:
    """Create one private materialization authority instance."""
    return _ResolvedTopologyMaterializationAuthority()
