"""Opaque, use-once actuation capability layer.

Capabilities are runtime objects and are intentionally not serializable. A
packet never carries authority. Evidence stores only an ActuationReceipt.
"""

from __future__ import annotations

from dataclasses import dataclass
import secrets
import threading
from typing import Literal

from .digest import canonical_digest
from .errors import (
    ActuationCapabilityConsumed,
    ActuationCapabilityExpired,
    ActuationCapabilityScopeMismatch,
)
from .schemas import ControlMode


@dataclass(frozen=True, slots=True)
class ActuationReceipt:
    schema: Literal["elpis.actuation-receipt.v1"]
    capability_id: str
    tick_id: str
    mode: ControlMode
    consumed_logical_time: int
    packet_digest: str
    gain: float
    receipt_digest: str = ""

    def with_digest(self) -> "ActuationReceipt":
        digest = canonical_digest(self, digest_field="receipt_digest")
        return ActuationReceipt(
            schema=self.schema,
            capability_id=self.capability_id,
            tick_id=self.tick_id,
            mode=self.mode,
            consumed_logical_time=self.consumed_logical_time,
            packet_digest=self.packet_digest,
            gain=self.gain,
            receipt_digest=digest,
        )


class ActuationCapability:
    __slots__ = (
        "_id", "_tick_id", "_mode", "_not_before", "_not_after",
        "_max_gain", "_consumed", "_lock"
    )

    def __init__(
        self,
        *,
        capability_id: str,
        tick_id: str,
        mode: ControlMode,
        not_before: int,
        not_after: int,
        max_gain: float,
    ) -> None:
        self._id = capability_id
        self._tick_id = tick_id
        self._mode = mode
        self._not_before = not_before
        self._not_after = not_after
        self._max_gain = max_gain
        self._consumed = False
        self._lock = threading.Lock()

    def __reduce__(self):
        raise TypeError("ActuationCapability is intentionally non-serializable")

    def consume(
        self,
        *,
        tick_id: str,
        mode: ControlMode,
        logical_time: int,
        packet_digest: str,
        gain: float,
    ) -> ActuationReceipt:
        with self._lock:
            if self._consumed:
                raise ActuationCapabilityConsumed("capability already consumed")
            if tick_id != self._tick_id or mode != self._mode:
                raise ActuationCapabilityScopeMismatch("capability scope mismatch")
            if not (self._not_before <= logical_time <= self._not_after):
                raise ActuationCapabilityExpired("capability outside logical-time window")
            if not (0.0 <= gain <= self._max_gain):
                raise ActuationCapabilityScopeMismatch("requested gain exceeds capability")
            self._consumed = True
            return ActuationReceipt(
                schema="elpis.actuation-receipt.v1",
                capability_id=self._id,
                tick_id=tick_id,
                mode=mode,
                consumed_logical_time=logical_time,
                packet_digest=packet_digest,
                gain=gain,
            ).with_digest()


class ActuationCapabilityIssuer:
    """Token-layer issuer. A process-local registry prevents nonce reuse."""

    def __init__(self) -> None:
        self._issued: set[str] = set()
        self._lock = threading.Lock()

    def issue(
        self,
        *,
        tick_id: str,
        mode: ControlMode,
        not_before: int,
        not_after: int,
        max_gain: float,
    ) -> ActuationCapability:
        if mode not in (ControlMode.DOCK, ControlMode.POST_LOGIT, ControlMode.HYBRID):
            raise ActuationCapabilityScopeMismatch("non-actuating mode cannot receive capability")
        if not (0.0 <= max_gain <= 8.0):
            raise ActuationCapabilityScopeMismatch("max_gain outside frozen bound")
        with self._lock:
            capability_id = secrets.token_hex(32)
            while capability_id in self._issued:
                capability_id = secrets.token_hex(32)
            self._issued.add(capability_id)
        return ActuationCapability(
            capability_id=capability_id,
            tick_id=tick_id,
            mode=mode,
            not_before=not_before,
            not_after=not_after,
            max_gain=max_gain,
        )
