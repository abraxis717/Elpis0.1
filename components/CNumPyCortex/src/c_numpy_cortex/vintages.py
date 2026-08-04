from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Protocol

from .contracts import (
    ForecastEvaluation,
    ForecastStatus,
    ForecastVintage,
)


# ─── Forecast protocol ──────────────────────────────────────────────────

class ForecastPort(Protocol):
    """Deterministic synthetic forecast interface for testing.

    A real Chronos implementation or a synthetic test port
    can implement this interface.
    """

    def forecast(
        self,
        context_data: dict[str, Any],
        channels: tuple[str, ...],
        target_count: int,
    ) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
        """Return (q10, q50, q90) tuples for each channel."""
        ...

    def model_digest(self) -> str:
        ...


class SyntheticForecastPort:
    """Deterministic synthetic forecast port for testing."""

    def __init__(
        self,
        base_values: dict[str, tuple[float, float, float]] | None = None,
        drift: float = 0.0,
        error: str | None = None,
    ):
        self._base = base_values or {}
        self._drift = drift
        self._error = error

    def forecast(
        self,
        context_data: dict[str, Any],
        channels: tuple[str, ...],
        target_count: int,
    ) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
        if self._error:
            raise RuntimeError(self._error)

        q10s: list[float] = []
        q50s: list[float] = []
        q90s: list[float] = []

        for ch in channels:
            base = self._base.get(ch, (0.0, 1.0, 2.0))
            q10s.append(base[0] + self._drift)
            q50s.append(base[1] + self._drift)
            q90s.append(base[2] + self._drift)

        return (
            tuple(q10s),
            tuple(q50s),
            tuple(q90s),
        )

    def model_digest(self) -> str:
        return hashlib.sha256(
            json.dumps(
                {"type": "synthetic", "drift": self._drift},
                sort_keys=True,
            ).encode()
        ).hexdigest()


# ─── Vintage store ──────────────────────────────────────────────────────

class VintageStore:
    """Store and query forecast vintages."""

    def __init__(self):
        self._vintages: list[ForecastVintage] = []
        self._next_id = 0

    def add(self, vintage: ForecastVintage) -> None:
        self._vintages.append(vintage)

    def get_all(self) -> tuple[ForecastVintage, ...]:
        return tuple(self._vintages)

    def get_by_id(self, vintage_id: str) -> ForecastVintage | None:
        for v in self._vintages:
            if v.vintage_id == vintage_id:
                return v
        return None

    def next_id(self) -> str:
        self._next_id += 1
        return f"vintage_{self._next_id:04d}"

    def create_vintage(
        self,
        base_generation: int,
        created_monotonic_ns: int,
        resample_rule: str,
        target_monotonic_ns: tuple[int, ...],
        channels: tuple[str, ...],
        q10: tuple[float, ...],
        q50: tuple[float, ...],
        q90: tuple[float, ...],
        model_digest: str,
        context_digest: str,
        channel_schema_digest: str,
        normalizer_state_digest: str,
    ) -> ForecastVintage:
        vintage_id = self.next_id()

        vintage = ForecastVintage(
            vintage_id=vintage_id,
            base_generation=base_generation,
            created_monotonic_ns=created_monotonic_ns,
            resample_rule=resample_rule,
            target_monotonic_ns=target_monotonic_ns,
            channels=channels,
            q10=q10,
            q50=q50,
            q90=q90,
            model_digest=model_digest,
            context_digest=context_digest,
            channel_schema_digest=channel_schema_digest,
            normalizer_state_digest=normalizer_state_digest,
        )

        self.add(vintage)
        return vintage


# ─── Maturity evaluator ─────────────────────────────────────────────────

def evaluate_vintage(
    vintage: ForecastVintage,
    current_monotonic_ns: int,
    realizations: dict[str, float],
    current_schema_digest: str,
    current_normalizer_digest: str,
    required_channels: set[str],
) -> ForecastEvaluation:
    """Evaluate a vintage against realizations.

    Status precedence:
    - SCHEMA_MISMATCH if digests don't match
    - STALE_FORECAST if targets are past fresh deadline
    - NO_MATURE_VINTAGE if no targets have been reached
    - NO_REALIZATION if targets reached but no data
    - MODEL_ERROR on exception
    - OK if valid realizations exist
    """
    # Schema check
    if (
        vintage.channel_schema_digest != current_schema_digest
    ):
        return ForecastEvaluation(
            vintage_id=vintage.vintage_id,
            status=ForecastStatus.SCHEMA_MISMATCH,
            score=None,
            horizon_steps=len(vintage.target_monotonic_ns),
            channels_evaluated=0,
            reason_codes=("SCHEMA_DIGEST_CHANGED",),
        )

    if (
        vintage.normalizer_state_digest
        != current_normalizer_digest
    ):
        return ForecastEvaluation(
            vintage_id=vintage.vintage_id,
            status=ForecastStatus.SCHEMA_MISMATCH,
            score=None,
            horizon_steps=len(vintage.target_monotonic_ns),
            channels_evaluated=0,
            reason_codes=("NORMALIZER_DIGEST_CHANGED",),
        )

    # Find matured targets
    matured_targets = [
        t for t in vintage.target_monotonic_ns
        if t <= current_monotonic_ns
    ]

    if not matured_targets:
        return ForecastEvaluation(
            vintage_id=vintage.vintage_id,
            status=ForecastStatus.NO_MATURE_VINTAGE,
            score=None,
            horizon_steps=len(vintage.target_monotonic_ns),
            channels_evaluated=0,
            reason_codes=("NO_TARGETS_MATURED",),
        )

    # Check for realizations
    valid_realizations: list[float] = []
    channels_evaluated = 0

    for ch_idx, ch in enumerate(vintage.channels):
        if ch not in realizations:
            continue

        x = realizations[ch]

        q10 = vintage.q10[ch_idx]
        q90 = vintage.q90[ch_idx]

        # Score: out-of-band distance normalized by prediction width
        width = max(q90 - q10, 1e-6)
        score = (
            max(q10 - x, 0) + max(x - q90, 0)
        ) / width

        valid_realizations.append(score)
        channels_evaluated += 1

    if not valid_realizations:
        return ForecastEvaluation(
            vintage_id=vintage.vintage_id,
            status=ForecastStatus.NO_REALIZATION,
            score=None,
            horizon_steps=len(matured_targets),
            channels_evaluated=0,
            reason_codes=("NO_REALIZATION_DATA",),
        )

    aggregate_score = float(
        sum(valid_realizations) / len(valid_realizations)
    )

    return ForecastEvaluation(
        vintage_id=vintage.vintage_id,
        status=ForecastStatus.OK,
        score=aggregate_score,
        horizon_steps=len(matured_targets),
        channels_evaluated=channels_evaluated,
        reason_codes=(),
    )
