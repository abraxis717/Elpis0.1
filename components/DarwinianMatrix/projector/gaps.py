"""Evidence-slot gap detection over projector-owned clamp state.

A gap is a declared evidence slot that lacks its required owner-bound clamps.
Ecological behavior may strengthen the urgency signal but cannot invent the
missing semantic evidence or select a Grid81 value.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

from .constraints import ClampState


@dataclass(frozen=True)
class EvidenceSlot:
    slot_id: str
    cell_indices: tuple[int, ...]
    question_template: str
    minimum_claimed: int = 1

    def __post_init__(self) -> None:
        if not self.slot_id:
            raise ValueError(
                "slot_id cannot be empty."
            )

        if not self.question_template:
            raise ValueError(
                "question_template cannot be empty."
            )

        if not self.cell_indices:
            raise ValueError(
                "Evidence slot requires at least one Grid81 cell."
            )

        if len(set(self.cell_indices)) != len(
            self.cell_indices
        ):
            raise ValueError(
                "Evidence-slot cell indices must be unique."
            )

        for cell_index in self.cell_indices:
            if not 0 <= cell_index < 81:
                raise ValueError(
                    "Evidence-slot cell index must be in 0..80."
                )

        if not 1 <= self.minimum_claimed <= len(
            self.cell_indices
        ):
            raise ValueError(
                "minimum_claimed must be within the slot cell count."
            )


@dataclass(frozen=True)
class Gap:
    slot_id: str
    question: str
    claimed_count: int
    required_count: int
    signal_codes: tuple[str, ...]


def _recent_cascade_mean(
    cascade_magnitudes: Sequence[float] | Iterable[float],
) -> float | None:
    values = tuple(
        float(value)
        for value in cascade_magnitudes
    )

    if not values:
        return None

    for value in values:
        if not math.isfinite(value):
            raise ValueError(
                "Cascade magnitudes must be finite."
            )

    recent = values[-2:]
    return sum(recent) / len(recent)


def detect_gaps(
    *,
    schema: Sequence[EvidenceSlot],
    clamp_state: ClampState,
    cascade_magnitudes: Sequence[float] = (),
    verdict: str | None = None,
    low_sensitivity_threshold: float = 0.05,
) -> tuple[Gap, ...]:
    """Return missing declared evidence slots.

    A cell counts toward a slot only when:
    - the cell belongs to the slot;
    - that cell is actively clamped;
    - the clamp owner equals the slot ID.
    """
    if low_sensitivity_threshold < 0.0:
        raise ValueError(
            "low_sensitivity_threshold cannot be negative."
        )

    active_mask = clamp_state.active_mask
    owners = clamp_state.owners

    recent_mean = _recent_cascade_mean(
        cascade_magnitudes
    )

    gaps: list[Gap] = []

    seen_slot_ids: set[str] = set()

    for slot in schema:
        if slot.slot_id in seen_slot_ids:
            raise ValueError(
                f"Duplicate evidence slot ID {slot.slot_id!r}."
            )

        seen_slot_ids.add(slot.slot_id)

        claimed_count = sum(
            1
            for cell_index in slot.cell_indices
            if bool(active_mask[cell_index])
            and owners[cell_index] == slot.slot_id
        )

        if claimed_count >= slot.minimum_claimed:
            continue

        signals = {"MISSING_EVIDENCE"}

        if verdict == "STALLED":
            signals.add("FRAME_STALLED")

        if verdict == "OSCILLATING":
            signals.add("FRAME_OSCILLATING")

        if (
            recent_mean is not None
            and recent_mean < low_sensitivity_threshold
        ):
            signals.add("LOW_CASCADE_SENSITIVITY")

        gaps.append(
            Gap(
                slot_id=slot.slot_id,
                question=slot.question_template,
                claimed_count=claimed_count,
                required_count=slot.minimum_claimed,
                signal_codes=tuple(sorted(signals)),
            )
        )

    return tuple(gaps)
