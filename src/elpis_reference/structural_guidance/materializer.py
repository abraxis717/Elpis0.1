"""Canonical non-executable materialization of resolved structural topology.

The materializer requires a consumed one-shot STRUCTURAL_MATERIALIZATION
capability bound to the exact topology and exact materializer identity.

Its output is only a canonical JSON representation of the already-resolved
topology plus lineage to the consumed capability.

It does not:
* decode;
* execute;
* select experts;
* invoke models;
* mutate topology;
* solve a domain problem;
* create source code or an executable plan.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from .materialization_authority import (
    STRUCTURAL_MATERIALIZATION_AUTHORITY,
    ResolvedTopologyMaterializationConsumptionV1,
)
from .resolved import (
    ResolvedStructuralTopologyV1,
)


RESOLVED_STRUCTURAL_MATERIALIZATION_SCHEMA = (
    "elpis.structural-guidance."
    "resolved-structural-materialization.v1"
)

CANONICAL_STRUCTURAL_MATERIALIZER_ID = (
    "elpis.structural-guidance.canonical-materializer"
)

CANONICAL_STRUCTURAL_MATERIALIZER_VERSION = "v1"

_MATERIALIZATION_DOMAIN = (
    "elpis.structural-guidance."
    "resolved-structural-materialization.v1"
)

_ID = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
)


class ResolvedStructuralMaterializationError(
    ValueError
):
    """Fail-closed non-executable materialization rejection."""


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


def _sha256(
    payload: object,
) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(payload)
    ).hexdigest()


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
        raise ResolvedStructuralMaterializationError(
            f"{name} must be SHA-256 hex"
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise ResolvedStructuralMaterializationError(
            f"{name} must be SHA-256 hex"
        ) from exc


@dataclass(frozen=True, slots=True)
class ResolvedStructuralMaterializationV1:
    """Canonical, non-executable materialized structural artifact."""

    schema: str

    topology_digest: str
    materialization_consumption_digest: str

    materializer_id: str
    materializer_version: str

    authority: str
    materialization_authorized: bool
    decoding_authorized: bool
    execution_authorized: bool

    structural_payload_json: str

    materialization_digest: str

    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "topology_digest": (
                self.topology_digest
            ),
            "materialization_consumption_digest": (
                self.materialization_consumption_digest
            ),
            "materializer_id": (
                self.materializer_id
            ),
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
            "structural_payload_json": (
                self.structural_payload_json
            ),
        }

    def materialization_digest_computed(
        self,
    ) -> str:
        return _domain_digest(
            _MATERIALIZATION_DOMAIN,
            self.payload(),
        )

    def structural_payload(
        self,
    ) -> dict[str, object]:
        try:
            value = json.loads(
                self.structural_payload_json
            )
        except Exception as exc:
            raise ResolvedStructuralMaterializationError(
                "structural payload is not JSON"
            ) from exc

        if not isinstance(value, dict):
            raise ResolvedStructuralMaterializationError(
                "structural payload must be a JSON object"
            )

        return value

    def validate(
        self,
    ) -> None:
        if (
            self.schema
            != RESOLVED_STRUCTURAL_MATERIALIZATION_SCHEMA
        ):
            raise ResolvedStructuralMaterializationError(
                "unsupported structural materialization schema"
            )

        for name, value in (
            (
                "topology_digest",
                self.topology_digest,
            ),
            (
                "materialization_consumption_digest",
                self.materialization_consumption_digest,
            ),
            (
                "materialization_digest",
                self.materialization_digest,
            ),
        ):
            _require_digest(
                name,
                value,
            )

        if not _ID.fullmatch(
            self.materializer_id
        ):
            raise ResolvedStructuralMaterializationError(
                "invalid materializer_id"
            )

        if not _ID.fullmatch(
            self.materializer_version
        ):
            raise ResolvedStructuralMaterializationError(
                "invalid materializer_version"
            )

        if (
            self.authority
            != STRUCTURAL_MATERIALIZATION_AUTHORITY
        ):
            raise ResolvedStructuralMaterializationError(
                "wrong materialization authority"
            )

        if self.materialization_authorized is not True:
            raise ResolvedStructuralMaterializationError(
                "structural materialization must be authorized"
            )

        if self.decoding_authorized is not False:
            raise ResolvedStructuralMaterializationError(
                "structural materialization may not authorize decoding"
            )

        if self.execution_authorized is not False:
            raise ResolvedStructuralMaterializationError(
                "structural materialization may not authorize execution"
            )

        structural_payload = (
            self.structural_payload()
        )

        canonical = _canonical_json_bytes(
            structural_payload
        ).decode("ascii")

        if (
            canonical
            != self.structural_payload_json
        ):
            raise ResolvedStructuralMaterializationError(
                "structural payload is not canonical JSON"
            )

        if (
            _sha256(structural_payload)
            != self.topology_digest
        ):
            raise ResolvedStructuralMaterializationError(
                "materialized structural payload "
                "does not match topology digest"
            )

        if (
            self.materialization_digest
            != self.materialization_digest_computed()
        ):
            raise ResolvedStructuralMaterializationError(
                "structural materialization digest mismatch"
            )

    def validate_digest(
        self,
    ) -> bool:
        try:
            self.validate()
        except ResolvedStructuralMaterializationError:
            return False

        return True


@dataclass(frozen=True, slots=True)
class CanonicalResolvedTopologyMaterializerV1:
    """Concrete materializer for canonical resolved topology payloads."""

    materializer_id: str = (
        CANONICAL_STRUCTURAL_MATERIALIZER_ID
    )
    materializer_version: str = (
        CANONICAL_STRUCTURAL_MATERIALIZER_VERSION
    )

    def __post_init__(
        self,
    ) -> None:
        if not _ID.fullmatch(
            self.materializer_id
        ):
            raise ResolvedStructuralMaterializationError(
                "invalid materializer_id"
            )

        if not _ID.fullmatch(
            self.materializer_version
        ):
            raise ResolvedStructuralMaterializationError(
                "invalid materializer_version"
            )

    def materialize(
        self,
        topology: ResolvedStructuralTopologyV1,
        consumption: ResolvedTopologyMaterializationConsumptionV1,
    ) -> ResolvedStructuralMaterializationV1:
        """Materialize canonical structural bytes only."""

        if not isinstance(
            topology,
            ResolvedStructuralTopologyV1,
        ):
            raise TypeError(
                "topology must be "
                "ResolvedStructuralTopologyV1"
            )

        topology.validate()

        if not topology.validate_digest():
            raise ResolvedStructuralMaterializationError(
                "resolved topology digest is invalid"
            )

        if not isinstance(
            consumption,
            ResolvedTopologyMaterializationConsumptionV1,
        ):
            raise TypeError(
                "consumption must be "
                "ResolvedTopologyMaterializationConsumptionV1"
            )

        consumption.validate()

        if (
            consumption.topology_digest
            != topology.topology_digest
        ):
            raise ResolvedStructuralMaterializationError(
                "consumption/topology identity mismatch"
            )

        if (
            consumption.authority
            != STRUCTURAL_MATERIALIZATION_AUTHORITY
        ):
            raise ResolvedStructuralMaterializationError(
                "consumption has wrong authority"
            )

        if (
            consumption.materialization_authorized
            is not True
        ):
            raise ResolvedStructuralMaterializationError(
                "consumption does not authorize materialization"
            )

        if (
            consumption.decoding_authorized
            is not False
        ):
            raise ResolvedStructuralMaterializationError(
                "consumption improperly authorizes decoding"
            )

        if (
            consumption.execution_authorized
            is not False
        ):
            raise ResolvedStructuralMaterializationError(
                "consumption improperly authorizes execution"
            )

        if (
            consumption.materializer_id
            != self.materializer_id
        ):
            raise ResolvedStructuralMaterializationError(
                "consumption materializer identity mismatch"
            )

        if (
            consumption.materializer_version
            != self.materializer_version
        ):
            raise ResolvedStructuralMaterializationError(
                "consumption materializer version mismatch"
            )

        structural_payload_json = (
            _canonical_json_bytes(
                topology.canonical_payload()
            ).decode("ascii")
        )

        if (
            hashlib.sha256(
                structural_payload_json.encode(
                    "ascii"
                )
            ).hexdigest()
            != topology.topology_digest
        ):
            raise ResolvedStructuralMaterializationError(
                "canonical topology payload identity mismatch"
            )

        base = {
            "schema": (
                RESOLVED_STRUCTURAL_MATERIALIZATION_SCHEMA
            ),
            "topology_digest": (
                topology.topology_digest
            ),
            "materialization_consumption_digest": (
                consumption.consumption_digest
            ),
            "materializer_id": (
                self.materializer_id
            ),
            "materializer_version": (
                self.materializer_version
            ),
            "authority": (
                STRUCTURAL_MATERIALIZATION_AUTHORITY
            ),
            "materialization_authorized": True,
            "decoding_authorized": False,
            "execution_authorized": False,
            "structural_payload_json": (
                structural_payload_json
            ),
        }

        materialized = (
            ResolvedStructuralMaterializationV1(
                **base,
                materialization_digest=_domain_digest(
                    _MATERIALIZATION_DOMAIN,
                    base,
                ),
            )
        )

        materialized.validate()

        return materialized
