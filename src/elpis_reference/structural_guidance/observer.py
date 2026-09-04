"""Digest-bound production observer for resolved structural topology.

This is the first concrete implementation of ResolvedTopologyConsumerPort.

It validates one immutable ResolvedStructuralTopologyV1 and emits only a
digest-bound authority-zero observation receipt.

It cannot decode, execute, mutate, route, select, solve, or produce an
authority-bearing runtime artifact.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from .consumer import (
    ResolvedTopologyConsumerPort,
    ResolvedTopologyConsumerReceiptV1,
)
from .resolved import (
    ResolvedStructuralTopologyV1,
)


_DEFAULT_CONSUMER_ID = (
    "elpis.structural-guidance.resolved-topology-observer"
)
_DEFAULT_CONSUMER_VERSION = "v1"

_ID = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
)


class ResolvedTopologyObservationError(
    ValueError
):
    """Fail-closed observation-boundary rejection."""


@dataclass(frozen=True)
class DigestBoundResolvedTopologyObserverV1:
    """Concrete authority-zero resolved-topology observer."""

    consumer_id: str = _DEFAULT_CONSUMER_ID
    consumer_version: str = _DEFAULT_CONSUMER_VERSION

    def __post_init__(
        self,
    ) -> None:
        if not _ID.fullmatch(
            self.consumer_id
        ):
            raise ResolvedTopologyObservationError(
                "invalid consumer_id"
            )

        if not _ID.fullmatch(
            self.consumer_version
        ):
            raise ResolvedTopologyObservationError(
                "invalid consumer_version"
            )

    def observe(
        self,
        topology: ResolvedStructuralTopologyV1,
    ) -> ResolvedTopologyConsumerReceiptV1:
        """Validate and acknowledge one immutable resolved topology."""

        if not isinstance(
            topology,
            ResolvedStructuralTopologyV1,
        ):
            raise TypeError(
                "topology must be "
                "ResolvedStructuralTopologyV1"
            )

        try:
            topology.validate()
        except Exception as exc:
            raise ResolvedTopologyObservationError(
                "resolved topology failed validation"
            ) from exc

        if not topology.validate_digest():
            raise ResolvedTopologyObservationError(
                "resolved topology digest is invalid"
            )

        receipt = (
            ResolvedTopologyConsumerReceiptV1
            .observed(
                topology_digest=(
                    topology.topology_digest
                ),
                consumer_id=self.consumer_id,
                consumer_version=(
                    self.consumer_version
                ),
            )
        )

        if (
            receipt.topology_digest
            != topology.topology_digest
        ):
            raise ResolvedTopologyObservationError(
                "observation receipt lost topology identity"
            )

        if receipt.authority_granted != 0:
            raise ResolvedTopologyObservationError(
                "observation receipt widened authority"
            )

        if (
            receipt.execution_authorized
            or receipt.decoding_authorized
            or receipt.materialization_authorized
        ):
            raise ResolvedTopologyObservationError(
                "observation receipt granted forbidden authority"
            )

        if not receipt.validate_digest():
            raise ResolvedTopologyObservationError(
                "observation receipt digest is invalid"
            )

        return receipt


assert issubclass(
    DigestBoundResolvedTopologyObserverV1,
    object,
)
