"""Persistent deterministic climate dynamics.

This module owns regional climate transition age. Ecological code receives
detached read views and cannot mutate persistent climate state.

A climate transition is committed by producing a new ClimateDynamicsState.
The source state is never modified.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Sequence

import torch
from torch import Tensor

from ..geometry import (
    GRID_CELLS,
    MATRIX_CELLS,
    LatticeClimateView,
    directed_transition_id,
    require_solved_grid81,
)


MAX_TRANSITION_AGE = torch.iinfo(torch.int32).max


def _require_shape(
    name: str,
    tensor: Tensor,
    expected_length: int,
) -> None:
    if tensor.shape != (expected_length,):
        raise ValueError(
            f"{name} must have shape ({expected_length},), "
            f"received {tuple(tensor.shape)}."
        )


def _tensor_digest(
    domain: str,
    tensor: Tensor,
) -> str:
    value = tensor.detach().cpu().contiguous()

    digest = hashlib.sha256()
    digest.update(domain.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(str(value.dtype).encode("ascii"))
    digest.update(b"\x00")
    digest.update(
        json.dumps(
            list(value.shape),
            separators=(",", ":"),
        ).encode("utf-8")
    )
    digest.update(b"\x00")
    digest.update(value.numpy().tobytes())

    return digest.hexdigest()


@dataclass(frozen=True)
class RegionalClimateDynamicsView:
    """Detached regional climate state."""

    previous: Tensor
    current: Tensor
    transition_ids: Tensor
    changed: Tensor
    transition_age: Tensor

    def __post_init__(self) -> None:
        for name in (
            "previous",
            "current",
            "transition_ids",
            "changed",
            "transition_age",
        ):
            _require_shape(
                name,
                getattr(self, name),
                GRID_CELLS,
            )


@dataclass(frozen=True)
class LatticeClimateDynamicsView:
    """Detached climate dynamics expanded over all ecological sites."""

    previous: Tensor
    current: Tensor
    transition_ids: Tensor
    changed: Tensor
    transition_age: Tensor

    def __post_init__(self) -> None:
        for name in (
            "previous",
            "current",
            "transition_ids",
            "changed",
            "transition_age",
        ):
            _require_shape(
                name,
                getattr(self, name),
                MATRIX_CELLS,
            )

    def ecology_inputs(
        self,
    ) -> tuple[LatticeClimateView, Tensor]:
        """Return detached inputs accepted by the ecological transaction."""
        return (
            LatticeClimateView(
                previous=self.previous.clone(),
                current=self.current.clone(),
                transition_ids=self.transition_ids.clone(),
                changed=self.changed.clone(),
            ),
            self.transition_age.clone(),
        )


class ClimateDynamicsState:
    """Persistent immutable-by-interface regional climate state."""

    __slots__ = (
        "_device",
        "_initialized",
        "_previous",
        "_current",
        "_transition_ids",
        "_changed",
        "_transition_age",
    )

    def __init__(
        self,
        *,
        device: str | torch.device = "cpu",
        initialized: bool = False,
        previous: Tensor | None = None,
        current: Tensor | None = None,
        transition_ids: Tensor | None = None,
        changed: Tensor | None = None,
        transition_age: Tensor | None = None,
    ) -> None:
        self._device = torch.device(device)
        self._initialized = bool(initialized)

        if previous is None:
            previous = torch.zeros(
                GRID_CELLS,
                dtype=torch.int8,
                device=self._device,
            )

        if current is None:
            current = torch.zeros(
                GRID_CELLS,
                dtype=torch.int8,
                device=self._device,
            )

        if transition_ids is None:
            transition_ids = torch.zeros(
                GRID_CELLS,
                dtype=torch.int16,
                device=self._device,
            )

        if changed is None:
            changed = torch.zeros(
                GRID_CELLS,
                dtype=torch.bool,
                device=self._device,
            )

        if transition_age is None:
            transition_age = torch.zeros(
                GRID_CELLS,
                dtype=torch.int32,
                device=self._device,
            )

        self._previous = previous.detach().to(
            device=self._device,
            dtype=torch.int8,
        ).reshape(-1).clone()

        self._current = current.detach().to(
            device=self._device,
            dtype=torch.int8,
        ).reshape(-1).clone()

        self._transition_ids = transition_ids.detach().to(
            device=self._device,
            dtype=torch.int16,
        ).reshape(-1).clone()

        self._changed = changed.detach().to(
            device=self._device,
            dtype=torch.bool,
        ).reshape(-1).clone()

        self._transition_age = transition_age.detach().to(
            device=self._device,
            dtype=torch.int32,
        ).reshape(-1).clone()

        self._validate_internal()

    @classmethod
    def empty(
        cls,
        device: str | torch.device = "cpu",
    ) -> "ClimateDynamicsState":
        return cls(
            device=device,
            initialized=False,
        )

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def device(self) -> torch.device:
        return self._device

    @property
    def previous(self) -> Tensor:
        return self._previous.clone()

    @property
    def current(self) -> Tensor:
        return self._current.clone()

    @property
    def transition_ids(self) -> Tensor:
        return self._transition_ids.clone()

    @property
    def changed(self) -> Tensor:
        return self._changed.clone()

    @property
    def transition_age(self) -> Tensor:
        return self._transition_age.clone()

    def _validate_internal(self) -> None:
        for name in (
            "_previous",
            "_current",
            "_transition_ids",
            "_changed",
            "_transition_age",
        ):
            _require_shape(
                name,
                getattr(self, name),
                GRID_CELLS,
            )

        if bool(self._transition_age.lt(0).any()):
            raise ValueError(
                "Climate transition age cannot be negative."
            )

        if self._initialized:
            if bool(
                (
                    (self._previous < 1)
                    | (self._previous > 9)
                    | (self._current < 1)
                    | (self._current > 9)
                ).any()
            ):
                raise ValueError(
                    "Initialized climate values must remain "
                    "inside the Grid81 domain 1..9."
                )

            expected_ids = directed_transition_id(
                self._previous.long(),
                self._current.long(),
            )

            if not torch.equal(
                self._transition_ids,
                expected_ids,
            ):
                raise ValueError(
                    "Climate transition IDs do not match "
                    "previous/current values."
                )

            expected_changed = self._previous.ne(
                self._current
            )

            if not torch.equal(
                self._changed,
                expected_changed,
            ):
                raise ValueError(
                    "Climate changed mask does not match "
                    "previous/current values."
                )

            if bool(
                (
                    self._changed
                    & self._transition_age.ne(0)
                ).any()
            ):
                raise ValueError(
                    "Newly changed climate regions must have "
                    "transition age zero."
                )

    def advance(
        self,
        grid: Tensor | Sequence[int] | Iterable[int],
    ) -> "ClimateDynamicsState":
        """Return the next persistent climate state."""
        validated = require_solved_grid81(grid).to(
            device=self._device,
            dtype=torch.int8,
        ).clone()

        if not self._initialized:
            previous = validated.clone()
            current = validated.clone()

            changed = torch.zeros(
                GRID_CELLS,
                dtype=torch.bool,
                device=self._device,
            )

            transition_age = torch.zeros(
                GRID_CELLS,
                dtype=torch.int32,
                device=self._device,
            )
        else:
            previous = self._current.clone()
            current = validated

            changed = previous.ne(current)

            incremented_age = torch.clamp(
                self._transition_age.to(torch.int64) + 1,
                max=MAX_TRANSITION_AGE,
            ).to(torch.int32)

            transition_age = torch.where(
                changed,
                torch.zeros_like(incremented_age),
                incremented_age,
            )

        transition_ids = directed_transition_id(
            previous.long(),
            current.long(),
        ).to(
            device=self._device,
            dtype=torch.int16,
        )

        return ClimateDynamicsState(
            device=self._device,
            initialized=True,
            previous=previous,
            current=current,
            transition_ids=transition_ids,
            changed=changed,
            transition_age=transition_age,
        )

    def clone(self) -> "ClimateDynamicsState":
        return ClimateDynamicsState(
            device=self._device,
            initialized=self._initialized,
            previous=self._previous,
            current=self._current,
            transition_ids=self._transition_ids,
            changed=self._changed,
            transition_age=self._transition_age,
        )

    def regional_read_view(
        self,
    ) -> RegionalClimateDynamicsView:
        if not self._initialized:
            raise RuntimeError(
                "Climate dynamics state is not initialized."
            )

        return RegionalClimateDynamicsView(
            previous=self._previous.clone(),
            current=self._current.clone(),
            transition_ids=self._transition_ids.clone(),
            changed=self._changed.clone(),
            transition_age=self._transition_age.clone(),
        )

    def lattice_read_view(
        self,
        region_map: Tensor,
    ) -> LatticeClimateDynamicsView:
        if not self._initialized:
            raise RuntimeError(
                "Climate dynamics state is not initialized."
            )

        if region_map.shape != (MATRIX_CELLS,):
            raise ValueError(
                f"Region map must have shape ({MATRIX_CELLS},)."
            )

        indices = region_map.to(
            device=self._device,
            dtype=torch.int64,
        )

        if bool(
            (
                (indices < 0)
                | (indices >= GRID_CELLS)
            ).any()
        ):
            raise ValueError(
                "Region map contains an invalid region ID."
            )

        return LatticeClimateDynamicsView(
            previous=self._previous[indices].clone(),
            current=self._current[indices].clone(),
            transition_ids=self._transition_ids[
                indices
            ].clone(),
            changed=self._changed[indices].clone(),
            transition_age=self._transition_age[
                indices
            ].clone(),
        )

    def digest(self) -> str:
        payload = {
            "changed": _tensor_digest(
                "darwinian.climate-dynamics.changed.v1",
                self._changed,
            ),
            "current": _tensor_digest(
                "darwinian.climate-dynamics.current.v1",
                self._current,
            ),
            "initialized": self._initialized,
            "previous": _tensor_digest(
                "darwinian.climate-dynamics.previous.v1",
                self._previous,
            ),
            "transition_age": _tensor_digest(
                "darwinian.climate-dynamics.age.v1",
                self._transition_age,
            ),
            "transition_ids": _tensor_digest(
                "darwinian.climate-dynamics.transitions.v1",
                self._transition_ids,
            ),
        }

        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

        return hashlib.sha256(
            b"darwinian.climate-dynamics-state.v1\x00"
            + encoded
        ).hexdigest()
