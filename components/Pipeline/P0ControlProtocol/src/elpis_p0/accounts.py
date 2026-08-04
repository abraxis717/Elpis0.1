from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from threading import Lock

from .contracts import (
    AccountingEvent,
    BudgetAxis,
)


@dataclass(slots=True)
class P0ShadowRequestAccount:
    """Non-authoritative accounting surface for P0.

    This is intentionally not the admitted L0 affine RequestAccount.

    It records P0 cost intents and detects local overspend while
    leaving production authority untouched.

    A later adapter may delegate each charge to the admitted L0
    RequestAccount implementation.
    """

    request_id: str
    units_per_axis: int = 32

    _remaining: dict[
        BudgetAxis,
        int,
    ] = field(
        init=False
    )

    _events: list[
        AccountingEvent
    ] = field(
        default_factory=list,
        init=False,
    )

    _lock: Lock = field(
        default_factory=Lock,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if self.units_per_axis <= 0:
            raise ValueError(
                "units_per_axis must be positive"
            )

        self._remaining = {
            axis: self.units_per_axis
            for axis in BudgetAxis
        }

    def charge(
        self,
        axis: BudgetAxis,
        units: int,
        reason: str,
    ) -> AccountingEvent:
        if units <= 0:
            raise ValueError(
                "accounting charge must be positive"
            )

        with self._lock:
            remaining = self._remaining[
                axis
            ]

            if units > remaining:
                raise RuntimeError(
                    "P0 shadow budget exceeded "
                    f"on {axis.value}: "
                    f"requested {units}, "
                    f"remaining {remaining}"
                )

            remaining -= units

            self._remaining[
                axis
            ] = remaining

            event = AccountingEvent(
                sequence=len(
                    self._events
                ),
                axis=axis,
                units=units,
                reason=reason,
                remaining=remaining,
                shadow=True,
            )

            self._events.append(
                event
            )

            return event

    def events(
        self,
    ) -> tuple[AccountingEvent, ...]:
        with self._lock:
            return tuple(
                self._events
            )

    def snapshot(
        self,
    ) -> tuple[tuple[str, int], ...]:
        with self._lock:
            return tuple(
                sorted(
                    (
                        axis.value,
                        units,
                    )
                    for axis, units
                    in self._remaining.items()
                )
            )
