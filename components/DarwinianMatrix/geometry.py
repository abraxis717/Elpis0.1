"""Deterministic geometry and TRM-owned climate storage.

The ecological lattice contains 6,561 ordinary sites arranged as an 81×81
plane. Climate is not stored in any ecological site. It is maintained in a
separate 81-region sidecar owned by the upstream TRM/projector transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import torch
from torch import Tensor


GRID_SIDE = 9
GRID_CELLS = GRID_SIDE * GRID_SIDE

PATCH_RADIUS = 4
PATCH_SIDE = 2 * PATCH_RADIUS + 1

MATRIX_SIDE = GRID_SIDE * PATCH_SIDE
MATRIX_CELLS = MATRIX_SIDE * MATRIX_SIDE

DIGIT_MIN = 1
DIGIT_MAX = 9
EMPTY_VALUE = 0

BOUNDARY_REFLECTIVE = "reflective"
BOUNDARY_TOROIDAL = "toroidal"

STENCIL_VON_NEUMANN_4 = "von_neumann4"
STENCIL_MOORE_8 = "moore8"

VALID_BOUNDARY_MODES = frozenset(
    {
        BOUNDARY_REFLECTIVE,
        BOUNDARY_TOROIDAL,
    }
)

NEIGHBOR_OFFSETS = {
    STENCIL_VON_NEUMANN_4: (
        (-1, 0),
        (0, -1),
        (0, 1),
        (1, 0),
    ),
    STENCIL_MOORE_8: (
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
    ),
}


def _require_index(name: str, value: int, upper: int) -> None:
    if not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")
    if not 0 <= value < upper:
        raise ValueError(f"{name} must be in [0, {upper - 1}].")


def grid_index(row: int, col: int) -> int:
    """Return the flat Grid81 index for ``(row, col)``."""
    _require_index("grid row", row, GRID_SIDE)
    _require_index("grid column", col, GRID_SIDE)
    return row * GRID_SIDE + col


def grid_coordinate(index: int) -> tuple[int, int]:
    """Return ``(row, col)`` for a flat Grid81 index."""
    _require_index("grid index", index, GRID_CELLS)
    return divmod(index, GRID_SIDE)


def matrix_index(row: int, col: int) -> int:
    """Return the flat 81×81 lattice index for ``(row, col)``."""
    _require_index("matrix row", row, MATRIX_SIDE)
    _require_index("matrix column", col, MATRIX_SIDE)
    return row * MATRIX_SIDE + col


def matrix_coordinate(index: int) -> tuple[int, int]:
    """Return ``(row, col)`` for a flat ecological-lattice index."""
    _require_index("matrix index", index, MATRIX_CELLS)
    return divmod(index, MATRIX_SIDE)


def patch_origin(grid_row: int, grid_col: int) -> tuple[int, int]:
    """Return the top-left ecological coordinate of one 9×9 region."""
    _require_index("grid row", grid_row, GRID_SIDE)
    _require_index("grid column", grid_col, GRID_SIDE)
    return grid_row * PATCH_SIDE, grid_col * PATCH_SIDE


def patch_membership(
    matrix_row: int,
    matrix_col: int,
) -> tuple[int, int, int, int]:
    """Return ``(region_row, region_col, local_row, local_col)``."""
    _require_index("matrix row", matrix_row, MATRIX_SIDE)
    _require_index("matrix column", matrix_col, MATRIX_SIDE)

    return (
        matrix_row // PATCH_SIDE,
        matrix_col // PATCH_SIDE,
        matrix_row % PATCH_SIDE,
        matrix_col % PATCH_SIDE,
    )


def region_index(matrix_row: int, matrix_col: int) -> int:
    """Return the Grid81 region owning one ecological coordinate."""
    region_row, region_col, _, _ = patch_membership(
        matrix_row,
        matrix_col,
    )
    return grid_index(region_row, region_col)


def region_coordinate(index: int) -> tuple[int, int]:
    """Return the Grid81 coordinate for a region index."""
    return grid_coordinate(index)


def diagnostic_epicenter_coordinate(
    grid_row: int,
    grid_col: int,
) -> tuple[int, int]:
    """Return the diagnostic center coordinate of a 9×9 region.

    This coordinate is not climate storage and is not reserved from ecology.
    """
    origin_row, origin_col = patch_origin(grid_row, grid_col)
    return origin_row + PATCH_RADIUS, origin_col + PATCH_RADIUS


def diagnostic_epicenter_index(index: int) -> int:
    """Return the flat diagnostic epicenter for a Grid81 region index."""
    grid_row, grid_col = grid_coordinate(index)
    matrix_row, matrix_col = diagnostic_epicenter_coordinate(
        grid_row,
        grid_col,
    )
    return matrix_index(matrix_row, matrix_col)


def build_region_map(device: str | torch.device = "cpu") -> Tensor:
    """Return ``int16[6561]`` mapping ecological sites to regions."""
    indices = torch.arange(
        MATRIX_CELLS,
        dtype=torch.int64,
        device=device,
    )
    rows = indices // MATRIX_SIDE
    cols = indices % MATRIX_SIDE

    return (
        (rows // PATCH_SIDE) * GRID_SIDE
        + (cols // PATCH_SIDE)
    ).to(torch.int16)


def build_epicenter_index(
    device: str | torch.device = "cpu",
) -> Tensor:
    """Return the 81 diagnostic epicenter indices."""
    return torch.tensor(
        [
            diagnostic_epicenter_index(index)
            for index in range(GRID_CELLS)
        ],
        dtype=torch.int32,
        device=device,
    )


def build_neighbor_table(
    mode: str = BOUNDARY_REFLECTIVE,
    stencil: str = STENCIL_MOORE_8,
    device: str | torch.device = "cpu",
) -> Tensor:
    """Build a deterministic neighbor table.

    Reflective boundaries represent an out-of-bounds neighbor with the source
    site's own index. Toroidal boundaries wrap across the outer plane.
    """
    if mode not in VALID_BOUNDARY_MODES:
        raise ValueError(
            f"Unsupported boundary mode {mode!r}; "
            f"expected one of {sorted(VALID_BOUNDARY_MODES)}."
        )

    try:
        offsets = NEIGHBOR_OFFSETS[stencil]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported stencil {stencil!r}; "
            f"expected one of {sorted(NEIGHBOR_OFFSETS)}."
        ) from exc

    indices = torch.arange(
        MATRIX_CELLS,
        dtype=torch.int64,
        device=device,
    )
    rows = indices // MATRIX_SIDE
    cols = indices % MATRIX_SIDE

    neighbor_columns: list[Tensor] = []

    for delta_row, delta_col in offsets:
        neighbor_rows = rows + delta_row
        neighbor_cols = cols + delta_col

        if mode == BOUNDARY_TOROIDAL:
            neighbor_rows %= MATRIX_SIDE
            neighbor_cols %= MATRIX_SIDE
            neighbors = neighbor_rows * MATRIX_SIDE + neighbor_cols
        else:
            out_of_bounds = (
                (neighbor_rows < 0)
                | (neighbor_rows >= MATRIX_SIDE)
                | (neighbor_cols < 0)
                | (neighbor_cols >= MATRIX_SIDE)
            )

            safe_rows = neighbor_rows.clamp(0, MATRIX_SIDE - 1)
            safe_cols = neighbor_cols.clamp(0, MATRIX_SIDE - 1)
            neighbors = safe_rows * MATRIX_SIDE + safe_cols
            neighbors = torch.where(
                out_of_bounds,
                indices,
                neighbors,
            )

        neighbor_columns.append(neighbors)

    return torch.stack(neighbor_columns, dim=1).to(torch.int32)


def _as_grid_tensor(
    grid: Tensor | Sequence[int] | Iterable[int],
) -> Tensor:
    """Return a detached CPU ``int64[81]`` copy."""
    if isinstance(grid, Tensor):
        tensor = grid.detach().to(
            device="cpu",
            dtype=torch.int64,
        ).reshape(-1).clone()
    else:
        tensor = torch.tensor(
            tuple(grid),
            dtype=torch.int64,
            device="cpu",
        ).reshape(-1)

    return tensor


def _unit_is_complete(unit: Tensor) -> bool:
    expected = torch.arange(
        DIGIT_MIN,
        DIGIT_MAX + 1,
        dtype=torch.int64,
    )
    return torch.equal(torch.sort(unit).values, expected)


def _unit_is_partial_valid(unit: Tensor) -> bool:
    present = unit[unit != EMPTY_VALUE]
    if present.numel() == 0:
        return True
    return torch.unique(present).numel() == present.numel()


def validate_solved_grid81(
    grid: Tensor | Sequence[int] | Iterable[int],
) -> bool:
    """Return whether ``grid`` is an exact solved 1–9 Sudoku."""
    tensor = _as_grid_tensor(grid)

    if tensor.numel() != GRID_CELLS:
        return False

    if bool(
        ((tensor < DIGIT_MIN) | (tensor > DIGIT_MAX)).any()
    ):
        return False

    matrix = tensor.reshape(GRID_SIDE, GRID_SIDE)

    for row in range(GRID_SIDE):
        if not _unit_is_complete(matrix[row, :]):
            return False

    for col in range(GRID_SIDE):
        if not _unit_is_complete(matrix[:, col]):
            return False

    for box_row in range(0, GRID_SIDE, 3):
        for box_col in range(0, GRID_SIDE, 3):
            box = matrix[
                box_row : box_row + 3,
                box_col : box_col + 3,
            ].reshape(-1)

            if not _unit_is_complete(box):
                return False

    return True


def validate_partial_grid81(
    grid: Tensor | Sequence[int] | Iterable[int],
) -> bool:
    """Return whether a 0-empty partial Sudoku is contradiction-free."""
    tensor = _as_grid_tensor(grid)

    if tensor.numel() != GRID_CELLS:
        return False

    if bool(
        ((tensor < EMPTY_VALUE) | (tensor > DIGIT_MAX)).any()
    ):
        return False

    matrix = tensor.reshape(GRID_SIDE, GRID_SIDE)

    for row in range(GRID_SIDE):
        if not _unit_is_partial_valid(matrix[row, :]):
            return False

    for col in range(GRID_SIDE):
        if not _unit_is_partial_valid(matrix[:, col]):
            return False

    for box_row in range(0, GRID_SIDE, 3):
        for box_col in range(0, GRID_SIDE, 3):
            box = matrix[
                box_row : box_row + 3,
                box_col : box_col + 3,
            ].reshape(-1)

            if not _unit_is_partial_valid(box):
                return False

    return True


def require_solved_grid81(
    grid: Tensor | Sequence[int] | Iterable[int],
) -> Tensor:
    """Return a validated detached ``int64[81]`` grid or raise."""
    tensor = _as_grid_tensor(grid)

    if not validate_solved_grid81(tensor):
        raise ValueError(
            "Grid must be an exact solved 1–9 Sudoku: every row, "
            "column and 3×3 box must contain digits 1 through 9."
        )

    return tensor


def directed_transition_id(
    previous: Tensor | Sequence[int],
    current: Tensor | Sequence[int],
) -> Tensor:
    """Encode ordered 1–9 transitions bijectively into ``0..80``."""
    previous_tensor = torch.as_tensor(
        previous,
        dtype=torch.int64,
    )
    current_tensor = torch.as_tensor(
        current,
        dtype=torch.int64,
    )

    if previous_tensor.shape != current_tensor.shape:
        raise ValueError(
            "Previous and current climate tensors must have equal shapes."
        )

    for name, tensor in (
        ("previous", previous_tensor),
        ("current", current_tensor),
    ):
        if bool(
            ((tensor < DIGIT_MIN) | (tensor > DIGIT_MAX)).any()
        ):
            raise ValueError(
                f"{name} values must all be in "
                f"[{DIGIT_MIN}, {DIGIT_MAX}]."
            )

    return (
        GRID_SIDE * (previous_tensor - DIGIT_MIN)
        + (current_tensor - DIGIT_MIN)
    ).to(torch.int16)


@dataclass(frozen=True)
class ClimateTransitionBatch:
    """Detached result of one TRM-owned climate update."""

    previous: Tensor
    current: Tensor
    transition_ids: Tensor
    changed: Tensor

    def __post_init__(self) -> None:
        for field_name in (
            "previous",
            "current",
            "transition_ids",
            "changed",
        ):
            tensor = getattr(self, field_name)
            if tensor.shape != (GRID_CELLS,):
                raise ValueError(
                    f"{field_name} must have shape ({GRID_CELLS},)."
                )


@dataclass(frozen=True)
class LatticeClimateView:
    """Detached climate values expanded to all ecological sites."""

    previous: Tensor
    current: Tensor
    transition_ids: Tensor
    changed: Tensor

    def __post_init__(self) -> None:
        for field_name in (
            "previous",
            "current",
            "transition_ids",
            "changed",
        ):
            tensor = getattr(self, field_name)
            if tensor.shape != (MATRIX_CELLS,):
                raise ValueError(
                    f"{field_name} must have shape ({MATRIX_CELLS},)."
                )


class ClimateSidecar:
    """TRM-owned regional climate state with no mutable ecology view."""

    def __init__(
        self,
        device: str | torch.device = "cpu",
    ) -> None:
        self._device = torch.device(device)
        self._current = torch.zeros(
            GRID_CELLS,
            dtype=torch.int8,
            device=self._device,
        )
        self._previous = torch.zeros_like(self._current)
        self._transition_ids = torch.zeros(
            GRID_CELLS,
            dtype=torch.int16,
            device=self._device,
        )
        self._changed = torch.zeros(
            GRID_CELLS,
            dtype=torch.bool,
            device=self._device,
        )
        self._initialized = False
        self._locked = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def locked(self) -> bool:
        return self._locked

    @property
    def current(self) -> Tensor:
        return self._current.clone()

    @property
    def previous(self) -> Tensor:
        return self._previous.clone()

    @property
    def transition_ids(self) -> Tensor:
        return self._transition_ids.clone()

    @property
    def changed(self) -> Tensor:
        return self._changed.clone()

    def lock(self) -> None:
        self._locked = True

    def unlock(self) -> None:
        self._locked = False

    def trm_write(
        self,
        grid: Tensor | Sequence[int] | Iterable[int],
    ) -> ClimateTransitionBatch:
        """Commit one validated Grid81 supplied by the TRM boundary."""
        if self._locked:
            raise RuntimeError(
                "Climate write attempted during the ecological phase."
            )

        validated = require_solved_grid81(grid).to(
            device=self._device,
            dtype=torch.int8,
        ).clone()

        if not self._initialized:
            previous = validated.clone()
            changed = torch.zeros_like(
                validated,
                dtype=torch.bool,
            )
        else:
            previous = self._current.clone()
            changed = previous.ne(validated)

        transitions = directed_transition_id(
            previous.to(torch.int64),
            validated.to(torch.int64),
        ).to(self._device)

        self._previous = previous.clone()
        self._current = validated.clone()
        self._transition_ids = transitions.clone()
        self._changed = changed.clone()
        self._initialized = True

        return ClimateTransitionBatch(
            previous=self._previous.clone(),
            current=self._current.clone(),
            transition_ids=self._transition_ids.clone(),
            changed=self._changed.clone(),
        )

    def regional_read_view(self) -> ClimateTransitionBatch:
        """Return detached region-level climate arrays."""
        if not self._initialized:
            raise RuntimeError("Climate sidecar has not been initialized.")

        return ClimateTransitionBatch(
            previous=self._previous.clone(),
            current=self._current.clone(),
            transition_ids=self._transition_ids.clone(),
            changed=self._changed.clone(),
        )

    def lattice_read_view(
        self,
        region_map: Tensor,
    ) -> LatticeClimateView:
        """Return detached climate arrays expanded to 6,561 sites."""
        if not self._initialized:
            raise RuntimeError("Climate sidecar has not been initialized.")

        if region_map.shape != (MATRIX_CELLS,):
            raise ValueError(
                f"Region map must have shape ({MATRIX_CELLS},)."
            )

        region_indices = region_map.to(
            device=self._device,
            dtype=torch.int64,
        )

        if bool(
            ((region_indices < 0) | (region_indices >= GRID_CELLS)).any()
        ):
            raise ValueError("Region map contains an invalid region ID.")

        return LatticeClimateView(
            previous=self._previous[region_indices].clone(),
            current=self._current[region_indices].clone(),
            transition_ids=self._transition_ids[
                region_indices
            ].clone(),
            changed=self._changed[region_indices].clone(),
        )

    def view(
        self,
        region_map: Tensor,
    ) -> tuple[Tensor, Tensor]:
        """Compatibility shim for the original prototype API."""
        lattice = self.lattice_read_view(region_map)
        return lattice.current, lattice.previous
