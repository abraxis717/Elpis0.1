from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any

import numpy as np


# ─── Enums ──────────────────────────────────────────────────────────────

class ObservationValidity(Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    INVALID = "INVALID"
    MISSING = "MISSING"


class PacketLifecycle(Enum):
    WARMING = "WARMING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    INVALID = "INVALID"


class ForecastStatus(Enum):
    OK = "OK"
    WARMING = "WARMING"
    NO_MATURE_VINTAGE = "NO_MATURE_VINTAGE"
    NO_REALIZATION = "NO_REALIZATION"
    MODEL_ERROR = "MODEL_ERROR"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    STALE_FORECAST = "STALE_FORECAST"


# ─── ChannelDescriptor ──────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ChannelDescriptor:
    channel_id: str
    source_kind: str
    unit: str
    sampling_class: str
    expected_period_ns: int
    stale_after_ns: int
    transform_id: str
    required: bool

    def to_canonical_json(self) -> str:
        return json.dumps(
            {
                "channel_id": self.channel_id,
                "source_kind": self.source_kind,
                "unit": self.unit,
                "sampling_class": self.sampling_class,
                "expected_period_ns": self.expected_period_ns,
                "stale_after_ns": self.stale_after_ns,
                "transform_id": self.transform_id,
                "required": self.required,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


MISSING_CHANNEL = ChannelDescriptor(
    channel_id="__MISSING__",
    source_kind="missing",
    unit="none",
    sampling_class="psutil",
    expected_period_ns=50_000_000,
    stale_after_ns=100_000_000,
    transform_id="none",
    required=False,
)


# ─── ChannelSchema ──────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ChannelSchema:
    schema_id: str
    version: str
    rows: tuple[ChannelDescriptor, ...]
    digest: str

    def __post_init__(self):
        if len(self.rows) != 9:
            raise ValueError(
                f"ChannelSchema must have exactly 9 rows, got {len(self.rows)}"
            )
        ids = [r.channel_id for r in self.rows]
        # Allow duplicate __MISSING__ placeholders
        non_missing = [i for i in ids if i != "__MISSING__"]
        if len(non_missing) != len(set(non_missing)):
            raise ValueError(
                f"Duplicate channel_id in ChannelSchema: {non_missing}"
            )
        for r in self.rows:
            if r.expected_period_ns <= 0:
                raise ValueError(
                    f"expected_period_ns must be > 0 for {r.channel_id}"
                )
            if r.stale_after_ns < r.expected_period_ns:
                raise ValueError(
                    f"stale_after_ns >= expected_period_ns for {r.channel_id}"
                )


def compute_schema_digest(
    rows: tuple[ChannelDescriptor, ...],
) -> str:
    payload = [
        r.to_canonical_json() for r in rows
    ]
    canonical = json.dumps(payload, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


# ─── ObservedValue ──────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ObservedValue:
    value: float | None
    observed_monotonic_ns: int
    source_sequence: int
    validity: ObservationValidity
    error_code: str | None


# ─── TensorSpaceIdentity ────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class TensorSpaceIdentity:
    semantic_space: str
    abi_version: str
    shape: tuple[int, ...]
    dtype: str
    vocabulary_size: int
    basis_digest: str
    layout_digest: str

    @staticmethod
    def thermal(
        layout_digest: str,
        basis_digest: str = "",
    ) -> "TensorSpaceIdentity":
        return TensorSpaceIdentity(
            semantic_space="grid81.thermal.ordinal.v1",
            abi_version="cnumpycortex.packet-set.v2",
            shape=(9, 9),
            dtype="uint8",
            vocabulary_size=10,
            basis_digest=basis_digest,
            layout_digest=layout_digest,
        )


# ─── PacketCommitManifest ───────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class PacketCommitManifest:
    abi_version: str
    generation: int
    packet_file: str
    metadata_file: str
    packet_sha256: str
    metadata_sha256: str
    channel_schema_digest: str
    created_monotonic_ns: int
    fresh_until_monotonic_ns: int


# ─── ForecastVintage ────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ForecastVintage:
    vintage_id: str
    base_generation: int
    created_monotonic_ns: int
    resample_rule: str
    target_monotonic_ns: tuple[int, ...]
    channels: tuple[str, ...]
    q10: tuple[float, ...]
    q50: tuple[float, ...]
    q90: tuple[float, ...]
    model_digest: str
    context_digest: str
    channel_schema_digest: str
    normalizer_state_digest: str


# ─── ForecastEvaluation ─────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ForecastEvaluation:
    vintage_id: str
    status: ForecastStatus
    score: float | None
    horizon_steps: int
    channels_evaluated: int
    reason_codes: tuple[str, ...]


# ─── ObservationPacketV2 ────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ObservationPacketV2:
    generation: int
    wall_time_ns: int
    monotonic_ns: int
    lifecycle: PacketLifecycle
    lifecycle_reasons: tuple[str, ...]
    space: TensorSpaceIdentity
    channel_schema_digest: str
    normalizer_state_digest: str
    tokens_sha256: str
    bits_sha256: str
    digit_entropy: float | None
    bit_entropy: tuple[float | None, ...]
    entropy_event_score: float | None
    transition_rate: float | None
    valid_cell_count: int


# ─── Legacy compatibility (read-only) ───────────────────────────────────

@dataclass(frozen=True, slots=True)
class TelemetrySample:
    wall_time_ns: int
    monotonic_ns: int
    values: dict[str, float]


@dataclass(frozen=True, slots=True)
class ForecastResult:
    generated_at_ns: int
    prediction_length: int
    anomaly_score: float
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True, slots=True)
class EntropyState:
    bit_entropy: float
    digit_entropy: float
    transition_rate: float
    temporal_gradient: float
    event_score: float


@dataclass(frozen=True, slots=True)
class GridPacket:
    wall_time_ns: int
    digits: np.ndarray
    bits: np.ndarray
    valid_mask: np.ndarray
    channel_names: tuple[str, ...]
    recursive_signature: np.ndarray

    def validate(self) -> None:
        if self.digits.shape != (9, 9):
            raise ValueError(
                f"digits must be (9, 9), got {self.digits.shape}"
            )
        if self.bits.shape != (4, 9, 9):
            raise ValueError(
                f"bits must be (4, 9, 9), got {self.bits.shape}"
            )
        if self.valid_mask.shape != (9, 9):
            raise ValueError(
                "valid_mask must be (9, 9), "
                f"got {self.valid_mask.shape}"
            )
        if not np.issubdtype(self.digits.dtype, np.integer):
            raise TypeError("digits must be an integer array")
        if (
            self.digits.min(initial=0) < 0
            or self.digits.max(initial=0) > 9
        ):
            raise ValueError("digits must be in [0, 9]")
        if (
            self.bits.min(initial=0) < 0
            or self.bits.max(initial=0) > 1
        ):
            raise ValueError("bits must be binary")
        if len(self.channel_names) != 9:
            raise ValueError("exactly nine channel names are required")

    @property
    def tokens81(self) -> np.ndarray:
        return self.digits.reshape(81).astype(
            np.uint8, copy=False,
        )
