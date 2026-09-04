"""Zero-authority consumer contract for resolved structural topology.

This boundary permits a downstream component to observe an already
resolved structural topology and acknowledge exactly which topology it
observed.

It grants no authority to:

* execute;
* decode;
* materialize executable state;
* choose experts;
* alter topology;
* apply mutations;
* route requests.

Any future transition from resolved topology into an authority-bearing
runtime artifact requires a separate explicit contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Protocol, runtime_checkable

from .resolved import ResolvedStructuralTopologyV1


RESOLVED_TOPOLOGY_CONSUMER_RECEIPT_SCHEMA = (
    "elpis.structural-guidance."
    "resolved-topology-consumer-receipt.v1"
)

AUTHORITY_ZERO = 0

_ALLOWED_OUTCOMES = frozenset(
    {
        "OBSERVED",
        "REJECTED",
    }
)

_ID = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
)


class ResolvedTopologyConsumerContractError(
    ValueError
):
    """Fail-closed consumer-boundary contract error."""


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


def _digest(
    payload: dict[str, object],
) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(payload)
    ).hexdigest()


def _require_digest(
    value: str,
    *,
    name: str,
) -> None:
    if len(value) != 64:
        raise ResolvedTopologyConsumerContractError(
            f"{name} must be a 64-character hexadecimal digest"
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise ResolvedTopologyConsumerContractError(
            f"{name} must be hexadecimal"
        ) from exc


@dataclass(frozen=True)
class ResolvedTopologyConsumerReceiptV1:
    """Authority-zero acknowledgement of one topology observation."""

    schema: str
    outcome: str

    topology_digest: str

    consumer_id: str
    consumer_version: str

    authority_granted: int

    execution_authorized: bool
    decoding_authorized: bool
    materialization_authorized: bool

    receipt_digest: str = ""

    def __post_init__(self) -> None:
        self.validate()

    def payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "outcome": self.outcome,
            "topology_digest": (
                self.topology_digest
            ),
            "consumer_id": self.consumer_id,
            "consumer_version": (
                self.consumer_version
            ),
            "authority_granted": (
                self.authority_granted
            ),
            "execution_authorized": (
                self.execution_authorized
            ),
            "decoding_authorized": (
                self.decoding_authorized
            ),
            "materialization_authorized": (
                self.materialization_authorized
            ),
        }

    def receipt_digest_computed(
        self,
    ) -> str:
        return _digest(
            self.payload()
        )

    def validate(
        self,
    ) -> None:
        if (
            self.schema
            != RESOLVED_TOPOLOGY_CONSUMER_RECEIPT_SCHEMA
        ):
            raise ResolvedTopologyConsumerContractError(
                "unsupported consumer receipt schema"
            )

        if self.outcome not in _ALLOWED_OUTCOMES:
            raise ResolvedTopologyConsumerContractError(
                "unsupported consumer receipt outcome"
            )

        _require_digest(
            self.topology_digest,
            name="topology_digest",
        )

        if not _ID.fullmatch(
            self.consumer_id
        ):
            raise ResolvedTopologyConsumerContractError(
                "invalid consumer_id"
            )

        if not _ID.fullmatch(
            self.consumer_version
        ):
            raise ResolvedTopologyConsumerContractError(
                "invalid consumer_version"
            )

        if self.authority_granted != AUTHORITY_ZERO:
            raise ResolvedTopologyConsumerContractError(
                "resolved topology observation "
                "may never grant authority"
            )

        if self.execution_authorized is not False:
            raise ResolvedTopologyConsumerContractError(
                "consumer receipt may not authorize execution"
            )

        if self.decoding_authorized is not False:
            raise ResolvedTopologyConsumerContractError(
                "consumer receipt may not authorize decoding"
            )

        if (
            self.materialization_authorized
            is not False
        ):
            raise ResolvedTopologyConsumerContractError(
                "consumer receipt may not authorize materialization"
            )

        if self.receipt_digest:
            _require_digest(
                self.receipt_digest,
                name="receipt_digest",
            )

            if (
                self.receipt_digest
                != self.receipt_digest_computed()
            ):
                raise ResolvedTopologyConsumerContractError(
                    "consumer receipt digest mismatch"
                )

    def validate_digest(
        self,
    ) -> bool:
        try:
            self.validate()
        except ResolvedTopologyConsumerContractError:
            return False

        return bool(
            self.receipt_digest
            and self.receipt_digest
            == self.receipt_digest_computed()
        )

    @classmethod
    def observed(
        cls,
        *,
        topology_digest: str,
        consumer_id: str,
        consumer_version: str,
    ) -> "ResolvedTopologyConsumerReceiptV1":
        unsigned = cls(
            schema=(
                RESOLVED_TOPOLOGY_CONSUMER_RECEIPT_SCHEMA
            ),
            outcome="OBSERVED",
            topology_digest=topology_digest,
            consumer_id=consumer_id,
            consumer_version=consumer_version,
            authority_granted=0,
            execution_authorized=False,
            decoding_authorized=False,
            materialization_authorized=False,
            receipt_digest="",
        )

        unsigned.validate()

        return cls(
            **{
                **unsigned.__dict__,
                "receipt_digest": (
                    unsigned.receipt_digest_computed()
                ),
            }
        )

    @classmethod
    def rejected(
        cls,
        *,
        topology_digest: str,
        consumer_id: str,
        consumer_version: str,
    ) -> "ResolvedTopologyConsumerReceiptV1":
        unsigned = cls(
            schema=(
                RESOLVED_TOPOLOGY_CONSUMER_RECEIPT_SCHEMA
            ),
            outcome="REJECTED",
            topology_digest=topology_digest,
            consumer_id=consumer_id,
            consumer_version=consumer_version,
            authority_granted=0,
            execution_authorized=False,
            decoding_authorized=False,
            materialization_authorized=False,
            receipt_digest="",
        )

        unsigned.validate()

        return cls(
            **{
                **unsigned.__dict__,
                "receipt_digest": (
                    unsigned.receipt_digest_computed()
                ),
            }
        )


@runtime_checkable
class ResolvedTopologyConsumerPort(
    Protocol
):
    """Read-only consumer of resolved structural topology.

    Implementations may inspect topology and return an acknowledgement.
    This port does not authorize the implementation to materialize,
    decode, execute, mutate, select, or route anything.
    """

    consumer_id: str
    consumer_version: str

    def observe(
        self,
        topology: ResolvedStructuralTopologyV1,
    ) -> ResolvedTopologyConsumerReceiptV1:
        """Observe one immutable resolved topology."""
        ...
