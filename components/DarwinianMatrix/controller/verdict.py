"""Deterministic meta-episode and attempt-frame evaluation.

One meta-episode represents one user problem. Each attempt frame represents
one bounded projector → TRM → ecology → evaluation cycle.

This module does not call the projector, TRM, or ecological engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Iterable, Sequence

import torch
from torch import Tensor

from ..geometry import MATRIX_CELLS


class FrameVerdict(str, Enum):
    RESOLVED = "RESOLVED"
    IMPROVING = "IMPROVING"
    DEGRADING = "DEGRADING"
    STALLED = "STALLED"
    OSCILLATING = "OSCILLATING"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


TERMINAL_VERDICTS = frozenset(
    {
        FrameVerdict.RESOLVED,
        FrameVerdict.BUDGET_EXHAUSTED,
    }
)


def _require_finite_number(name: str, value: float) -> float:
    number = float(value)

    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite.")

    return number


def _coerce_history(
    history: Tensor | Sequence[float] | Iterable[float],
) -> tuple[float, ...]:
    if isinstance(history, Tensor):
        tensor = history.detach().to(
            device="cpu",
            dtype=torch.float64,
        ).reshape(-1)

        if not bool(torch.isfinite(tensor).all()):
            raise ValueError(
                "Viability history contains NaN or infinite values."
            )

        values = tuple(float(value) for value in tensor.tolist())
    else:
        values = tuple(
            _require_finite_number("viability value", value)
            for value in history
        )

    if not values:
        raise ValueError("Viability history cannot be empty.")

    return values


def viability(state, capacity_field: Tensor) -> float:
    """Compute the declared scalar ecological viability.

    Viability is telemetry only. It does not mutate the ecological state and
    does not directly authorize projector or TRM writes.
    """
    if capacity_field.shape != (MATRIX_CELLS,):
        raise ValueError(
            f"capacity_field must have shape ({MATRIX_CELLS},)."
        )

    if not bool(torch.isfinite(capacity_field).all()):
        raise ValueError("capacity_field contains NaN or Inf.")

    if bool(capacity_field.lt(0.0).any()):
        raise ValueError("capacity_field cannot be negative.")

    if state.ctype.shape != (MATRIX_CELLS,):
        raise ValueError("state.ctype has an invalid shape.")

    if state.energy.shape != (MATRIX_CELLS,):
        raise ValueError("state.energy has an invalid shape.")

    if not bool(torch.isfinite(state.energy).all()):
        raise ValueError("state.energy contains NaN or Inf.")

    alive = state.ctype.ge(0).to(torch.float64)
    positive_energy = state.energy.clamp_min(0.0).to(torch.float64)
    capacity = capacity_field.to(torch.float64)

    value = (alive * positive_energy * capacity).sum()

    if not bool(torch.isfinite(value)):
        raise ValueError("Computed viability is not finite.")

    return float(value.item())


def classify_trend(
    history: Tensor | Sequence[float] | Iterable[float],
    *,
    epsilon: float = 1e-3,
    window: int = 4,
) -> FrameVerdict:
    """Classify the recent non-terminal trajectory."""
    values = _coerce_history(history)
    epsilon = _require_finite_number("epsilon", epsilon)

    if epsilon <= 0.0:
        raise ValueError("epsilon must be positive.")

    if not isinstance(window, int):
        raise TypeError("window must be an integer.")

    if window < 3:
        raise ValueError("window must be at least three.")

    if len(values) < 2:
        return FrameVerdict.IMPROVING

    recent = values[-window:]
    deltas = tuple(
        recent[index] - recent[index - 1]
        for index in range(1, len(recent))
    )

    # Oscillation requires at least three directed movements. Near-zero
    # movements are excluded so flat telemetry cannot masquerade as ringing.
    if len(recent) >= 4:
        significant = all(
            abs(delta) > epsilon
            for delta in deltas
        )
        signs = tuple(
            1 if delta > 0.0 else -1
            for delta in deltas
        )
        alternating = all(
            signs[index] != signs[index - 1]
            for index in range(1, len(signs))
        )

        if significant and alternating:
            return FrameVerdict.OSCILLATING

    # Stalling is a window-level property. Early frames remain provisional.
    if (
        len(recent) >= window
        and max(recent) - min(recent) <= epsilon
    ):
        return FrameVerdict.STALLED

    mean_delta = sum(deltas) / len(deltas)

    if mean_delta < -epsilon:
        return FrameVerdict.DEGRADING

    if mean_delta > epsilon:
        return FrameVerdict.IMPROVING

    if len(recent) >= window:
        return FrameVerdict.STALLED

    return FrameVerdict.IMPROVING


@dataclass(frozen=True)
class FrameAssessment:
    meta_id: str
    attempt_index: int
    attempt_budget: int

    verdict: FrameVerdict
    underlying_trend: FrameVerdict

    current_viability: float
    previous_viability: float | None
    delta: float | None
    target_viability: float

    budget_exhausted: bool
    reason_codes: tuple[str, ...]
    recent_history: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.meta_id:
            raise ValueError("meta_id cannot be empty.")

        if self.attempt_index < 1:
            raise ValueError("attempt_index must be one-based.")

        if self.attempt_budget < 1:
            raise ValueError("attempt_budget must be positive.")

        if self.attempt_index > self.attempt_budget:
            raise ValueError(
                "attempt_index cannot exceed attempt_budget."
            )

        for name in (
            "current_viability",
            "target_viability",
        ):
            _require_finite_number(name, getattr(self, name))

        if self.previous_viability is not None:
            _require_finite_number(
                "previous_viability",
                self.previous_viability,
            )

        if self.delta is not None:
            _require_finite_number("delta", self.delta)

        if not self.reason_codes:
            raise ValueError(
                "Frame assessment requires at least one reason code."
            )

        if tuple(sorted(set(self.reason_codes))) != self.reason_codes:
            raise ValueError(
                "reason_codes must be sorted and unique."
            )

        if self.verdict == FrameVerdict.RESOLVED:
            if self.current_viability < self.target_viability:
                raise ValueError(
                    "RESOLVED requires target viability."
                )

        if self.verdict == FrameVerdict.BUDGET_EXHAUSTED:
            if not self.budget_exhausted:
                raise ValueError(
                    "BUDGET_EXHAUSTED requires exhausted budget."
                )

    @property
    def terminal(self) -> bool:
        return self.verdict in TERMINAL_VERDICTS

    def canonical_payload(self) -> dict[str, object]:
        return {
            "attempt_budget": self.attempt_budget,
            "attempt_index": self.attempt_index,
            "budget_exhausted": self.budget_exhausted,
            "current_viability": self.current_viability,
            "delta": self.delta,
            "meta_id": self.meta_id,
            "previous_viability": self.previous_viability,
            "reason_codes": list(self.reason_codes),
            "recent_history": list(self.recent_history),
            "target_viability": self.target_viability,
            "terminal": self.terminal,
            "underlying_trend": self.underlying_trend.value,
            "verdict": self.verdict.value,
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

        return hashlib.sha256(
            b"darwinian.frame-assessment.v1\x00" + encoded
        ).hexdigest()


def assess_frame(
    *,
    meta_id: str,
    history: Tensor | Sequence[float] | Iterable[float],
    target_viability: float,
    attempt_index: int,
    attempt_budget: int,
    epsilon: float = 1e-3,
    window: int = 4,
) -> FrameAssessment:
    """Produce one deterministic frame assessment."""
    values = _coerce_history(history)
    target = _require_finite_number(
        "target_viability",
        target_viability,
    )

    if not isinstance(attempt_index, int):
        raise TypeError("attempt_index must be an integer.")

    if not isinstance(attempt_budget, int):
        raise TypeError("attempt_budget must be an integer.")

    if attempt_index < 1:
        raise ValueError("attempt_index must be one-based.")

    if attempt_budget < 1:
        raise ValueError("attempt_budget must be positive.")

    if attempt_index > attempt_budget:
        raise ValueError(
            "attempt_index cannot exceed attempt_budget."
        )

    if len(values) != attempt_index:
        raise ValueError(
            "History length must equal attempt_index."
        )

    current = values[-1]
    previous = values[-2] if len(values) >= 2 else None
    delta = (
        current - previous
        if previous is not None
        else None
    )

    trend = classify_trend(
        values,
        epsilon=epsilon,
        window=window,
    )

    exhausted = attempt_index >= attempt_budget

    if current >= target:
        verdict = FrameVerdict.RESOLVED
        reasons = (
            "VIABILITY_TARGET_REACHED",
        )
    elif exhausted:
        verdict = FrameVerdict.BUDGET_EXHAUSTED
        reasons = (
            "ATTEMPT_BUDGET_EXHAUSTED",
            f"UNDERLYING_TREND_{trend.value}",
        )
    else:
        verdict = trend
        reasons = (
            f"FRAME_TREND_{trend.value}",
        )

    return FrameAssessment(
        meta_id=meta_id,
        attempt_index=attempt_index,
        attempt_budget=attempt_budget,
        verdict=verdict,
        underlying_trend=trend,
        current_viability=current,
        previous_viability=previous,
        delta=delta,
        target_viability=target,
        budget_exhausted=exhausted,
        reason_codes=tuple(sorted(reasons)),
        recent_history=values[-window:],
    )


@dataclass(frozen=True)
class MetaEpisodeState:
    """Immutable two-tier clock for one user meta-task."""

    meta_id: str
    attempt_budget: int

    attempt_index: int = 0
    viability_history: tuple[float, ...] = ()

    closed: bool = False
    final_verdict: FrameVerdict | None = None

    def __post_init__(self) -> None:
        if not self.meta_id:
            raise ValueError("meta_id cannot be empty.")

        if self.attempt_budget < 1:
            raise ValueError("attempt_budget must be positive.")

        if self.attempt_index < 0:
            raise ValueError("attempt_index cannot be negative.")

        if self.attempt_index > self.attempt_budget:
            raise ValueError(
                "attempt_index cannot exceed attempt_budget."
            )

        if len(self.viability_history) != self.attempt_index:
            raise ValueError(
                "viability_history length must equal attempt_index."
            )

        for value in self.viability_history:
            _require_finite_number("viability value", value)

        if self.closed:
            if self.final_verdict not in TERMINAL_VERDICTS:
                raise ValueError(
                    "Closed meta episode requires a terminal verdict."
                )
        elif self.final_verdict is not None:
            raise ValueError(
                "Open meta episode cannot have a final verdict."
            )

    def record_frame(
        self,
        *,
        viability_value: float,
        target_viability: float,
        epsilon: float = 1e-3,
        window: int = 4,
    ) -> tuple["MetaEpisodeState", FrameAssessment]:
        """Append one attempt frame and return a new immutable state."""
        if self.closed:
            raise RuntimeError(
                "Cannot append a frame to a closed meta episode."
            )

        next_attempt = self.attempt_index + 1

        if next_attempt > self.attempt_budget:
            raise RuntimeError(
                "Attempt budget was already exhausted."
            )

        viability_value = _require_finite_number(
            "viability_value",
            viability_value,
        )

        history = self.viability_history + (
            viability_value,
        )

        assessment = assess_frame(
            meta_id=self.meta_id,
            history=history,
            target_viability=target_viability,
            attempt_index=next_attempt,
            attempt_budget=self.attempt_budget,
            epsilon=epsilon,
            window=window,
        )

        terminal = assessment.terminal

        next_state = MetaEpisodeState(
            meta_id=self.meta_id,
            attempt_budget=self.attempt_budget,
            attempt_index=next_attempt,
            viability_history=history,
            closed=terminal,
            final_verdict=(
                assessment.verdict
                if terminal
                else None
            ),
        )

        return next_state, assessment

    def digest(self) -> str:
        payload = {
            "attempt_budget": self.attempt_budget,
            "attempt_index": self.attempt_index,
            "closed": self.closed,
            "final_verdict": (
                self.final_verdict.value
                if self.final_verdict is not None
                else None
            ),
            "meta_id": self.meta_id,
            "viability_history": list(
                self.viability_history
            ),
        }

        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

        return hashlib.sha256(
            b"darwinian.meta-episode-state.v1\x00" + encoded
        ).hexdigest()


def classify(
    history: Tensor | Sequence[float] | Iterable[float],
    target: float,
    epsilon: float = 1e-3,
    window: int = 4,
) -> FrameVerdict:
    """Compatibility wrapper for the original prototype API."""
    values = _coerce_history(history)
    target = _require_finite_number("target", target)

    if values[-1] >= target:
        return FrameVerdict.RESOLVED

    return classify_trend(
        values,
        epsilon=epsilon,
        window=window,
    )
