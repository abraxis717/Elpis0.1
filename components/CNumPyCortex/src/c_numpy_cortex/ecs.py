from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import time
from typing import Any, Callable, TypeVar


T = TypeVar("T")
Entity = int


@dataclass(frozen=True, slots=True)
class ErrorRecord:
    monotonic_ns: int
    system: str
    message: str


class World:
    """Small data-oriented ECS world."""

    def __init__(self):
        self._next_entity = 1

        self._components: dict[
            type[Any],
            dict[Entity, Any],
        ] = defaultdict(dict)

        self.errors: deque[ErrorRecord] = deque(
            maxlen=128
        )

    def create_entity(self) -> Entity:
        entity = self._next_entity
        self._next_entity += 1
        return entity

    def set(
        self,
        entity: Entity,
        component: T,
    ) -> None:
        self._components[
            type(component)
        ][entity] = component

    def get(
        self,
        entity: Entity,
        component_type: type[T],
    ) -> T:
        return self._components[
            component_type
        ][entity]

    def try_get(
        self,
        entity: Entity,
        component_type: type[T],
    ) -> T | None:
        return (
            self._components
            .get(component_type, {})
            .get(entity)
        )


class System:
    def __init__(
        self,
        name: str,
        interval_s: float,
        function: Callable[[World], None],
    ):
        self.name = name

        self.interval_ns = max(
            1,
            int(
                interval_s
                * 1_000_000_000
            ),
        )

        self.function = function
        self.next_due_ns = time.monotonic_ns()

    def run_if_due(
        self,
        world: World,
        now_ns: int,
    ) -> None:
        if now_ns < self.next_due_ns:
            return

        missed = max(
            0,
            (
                now_ns - self.next_due_ns
            ) // self.interval_ns,
        )

        self.next_due_ns += (
            missed + 1
        ) * self.interval_ns

        try:
            self.function(world)

        except Exception as exc:
            world.errors.append(
                ErrorRecord(
                    monotonic_ns=now_ns,
                    system=self.name,
                    message=(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                )
            )


class Scheduler:
    def __init__(
        self,
        systems: list[System],
    ):
        self.systems = systems

    def run_forever(
        self,
        world: World,
    ) -> None:
        while True:
            now_ns = time.monotonic_ns()

            for system in self.systems:
                system.run_if_due(
                    world,
                    now_ns,
                )

            next_due = min(
                system.next_due_ns
                for system in self.systems
            )

            sleep_ns = max(
                0,
                next_due - time.monotonic_ns(),
            )

            time.sleep(
                min(
                    sleep_ns
                    / 1_000_000_000.0,
                    0.01,
                )
            )
