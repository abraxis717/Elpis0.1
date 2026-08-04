"""Pure Grid81 materialization for the frozen P0.1 Sudoku TRM.

This module does not import the legacy Elpis runtime, load a checkpoint, or
perform inference. It converts the sealed Darwinian structural request into
the numerical representation used to train P0.1:

    0   = blank / unknown
    1-9 = Sudoku given

Ecology, viability, telemetry, verdicts, and cascade state are structurally
absent from this interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Sequence

import torch
from torch import Tensor

from .contract import StructuralRefinementRequest


P01_MATERIALIZER_SCHEMA = (
    "darwinian.p01-materializer-policy.v1"
)

P01_MATERIALIZED_INPUT_SCHEMA = (
    "grid81.sudoku.p01.materialized.v1"
)

P01_GRID_CELLS = 81
P01_GRID_SIDE = 9
P01_BLANK_VALUE = 0


def _canonical_json_bytes(
    payload: dict[str, object],
) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _digest_payload(
    payload: dict[str, object],
) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(payload)
    ).hexdigest()


def _as_int_tuple(
    values: Tensor | Sequence[int],
    *,
    name: str,
) -> tuple[int, ...]:
    if isinstance(values, Tensor):
        detached = (
            values.detach()
            .to(device="cpu", dtype=torch.int64)
            .reshape(-1)
        )
        result = tuple(
            int(value)
            for value in detached.tolist()
        )
    else:
        result = tuple(
            int(value)
            for value in values
        )

    if len(result) != P01_GRID_CELLS:
        raise ValueError(
            f"{name} must contain exactly "
            f"{P01_GRID_CELLS} values, "
            f"got {len(result)}."
        )

    return result


def _as_bool_tuple(
    values: Tensor | Sequence[bool],
    *,
    name: str,
) -> tuple[bool, ...]:
    if isinstance(values, Tensor):
        detached = (
            values.detach()
            .to(device="cpu", dtype=torch.bool)
            .reshape(-1)
        )
        result = tuple(
            bool(value)
            for value in detached.tolist()
        )
    else:
        result = tuple(
            bool(value)
            for value in values
        )

    if len(result) != P01_GRID_CELLS:
        raise ValueError(
            f"{name} must contain exactly "
            f"{P01_GRID_CELLS} values, "
            f"got {len(result)}."
        )

    return result


def _units() -> tuple[tuple[int, ...], ...]:
    rows = tuple(
        tuple(
            row * P01_GRID_SIDE + column
            for column in range(P01_GRID_SIDE)
        )
        for row in range(P01_GRID_SIDE)
    )

    columns = tuple(
        tuple(
            row * P01_GRID_SIDE + column
            for row in range(P01_GRID_SIDE)
        )
        for column in range(P01_GRID_SIDE)
    )

    boxes = tuple(
        tuple(
            (box_row + local_row)
            * P01_GRID_SIDE
            + box_column
            + local_column
            for local_row in range(3)
            for local_column in range(3)
        )
        for box_row in (0, 3, 6)
        for box_column in (0, 3, 6)
    )

    return rows + columns + boxes


_SUDOKU_UNITS = _units()


def validate_p01_givens(
    values: Tensor | Sequence[int],
) -> tuple[int, ...]:
    """Validate a partial Sudoku represented with zero-valued blanks."""

    grid = _as_int_tuple(
        values,
        name="P0.1 givens",
    )

    invalid = [
        (index, value)
        for index, value in enumerate(grid)
        if value < 0 or value > 9
    ]

    if invalid:
        raise ValueError(
            "P0.1 givens must contain only "
            "integers in the closed interval [0, 9]; "
            f"invalid entries: {invalid[:8]!r}."
        )

    for unit_index, unit in enumerate(
        _SUDOKU_UNITS
    ):
        nonzero = [
            grid[index]
            for index in unit
            if grid[index] != P01_BLANK_VALUE
        ]

        if len(nonzero) != len(set(nonzero)):
            raise ValueError(
                "P0.1 givens contain a duplicate "
                "nonzero digit in Sudoku unit "
                f"{unit_index}."
            )

    return grid


class P01MaterializationMode(str, Enum):
    """How a sealed request was converted into P0.1 input."""

    PRESERVE_PREVIOUS_SOLVED = (
        "PRESERVE_PREVIOUS_SOLVED"
    )

    ACTIVE_CLAMPS_AS_GIVENS = (
        "ACTIVE_CLAMPS_AS_GIVENS"
    )


@dataclass(frozen=True)
class P01MaterializationPolicyV1:
    """Frozen deterministic policy for P0.1 input construction."""

    schema: str = P01_MATERIALIZER_SCHEMA
    blank_value: int = P01_BLANK_VALUE
    preserve_when_all_active_clamps_match: bool = True
    blank_nonclamped_on_changed_clamp: bool = True

    def __post_init__(self) -> None:
        if self.schema != P01_MATERIALIZER_SCHEMA:
            raise ValueError(
                "Unsupported P0.1 materializer schema: "
                f"{self.schema!r}."
            )

        if self.blank_value != P01_BLANK_VALUE:
            raise ValueError(
                "P0.1 blank value must remain zero."
            )

        if not self.preserve_when_all_active_clamps_match:
            raise ValueError(
                "P0.1 v1 must preserve the previous "
                "solution when all active clamps match."
            )

        if not self.blank_nonclamped_on_changed_clamp:
            raise ValueError(
                "P0.1 v1 must blank non-clamped cells "
                "whenever an active clamp changes the "
                "previous solution."
            )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "blank_value": self.blank_value,
            "preserve_when_all_active_clamps_match": (
                self.preserve_when_all_active_clamps_match
            ),
            "blank_nonclamped_on_changed_clamp": (
                self.blank_nonclamped_on_changed_clamp
            ),
            "input_semantics": {
                "zero": "BLANK_UNKNOWN",
                "one_through_nine": "SUDOKU_GIVEN",
            },
            "forbidden_inputs": [
                "cascade",
                "ecology",
                "telemetry",
                "viability",
                "verdict",
            ],
        }

    def digest(self) -> str:
        return _digest_payload(
            self.canonical_payload()
        )


DEFAULT_P01_MATERIALIZATION_POLICY = (
    P01MaterializationPolicyV1()
)


@dataclass(frozen=True)
class P01MaterializedInput:
    """Immutable canonical P0.1 input produced from one request."""

    request_digest: str
    policy_digest: str
    mode: P01MaterializationMode
    active_clamp_count: int
    changed_clamp_count: int
    grid_values: tuple[int, ...]

    def __post_init__(self) -> None:
        for name, digest in (
            ("request_digest", self.request_digest),
            ("policy_digest", self.policy_digest),
        ):
            if (
                len(digest) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in digest
                )
            ):
                raise ValueError(
                    f"{name} must be a lowercase "
                    "SHA-256 digest."
                )

        if self.active_clamp_count < 0:
            raise ValueError(
                "active_clamp_count cannot be negative."
            )

        if self.changed_clamp_count < 0:
            raise ValueError(
                "changed_clamp_count cannot be negative."
            )

        if (
            self.changed_clamp_count
            > self.active_clamp_count
        ):
            raise ValueError(
                "changed_clamp_count cannot exceed "
                "active_clamp_count."
            )

        validated = validate_p01_givens(
            self.grid_values
        )

        if validated != self.grid_values:
            raise ValueError(
                "grid_values are not canonical."
            )

        if (
            self.mode
            is P01MaterializationMode.PRESERVE_PREVIOUS_SOLVED
            and P01_BLANK_VALUE in self.grid_values
        ):
            raise ValueError(
                "Preserved solved input cannot contain blanks."
            )

        if (
            self.mode
            is P01MaterializationMode.ACTIVE_CLAMPS_AS_GIVENS
            and self.changed_clamp_count == 0
        ):
            raise ValueError(
                "Clamp-givens mode requires at least one "
                "changed active clamp."
            )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": P01_MATERIALIZED_INPUT_SCHEMA,
            "request_digest": self.request_digest,
            "policy_digest": self.policy_digest,
            "mode": self.mode.value,
            "active_clamp_count": (
                self.active_clamp_count
            ),
            "changed_clamp_count": (
                self.changed_clamp_count
            ),
            "shape": [1, P01_GRID_CELLS],
            "dtype": "int64",
            "grid_values": list(self.grid_values),
        }

    def digest(self) -> str:
        return _digest_payload(
            self.canonical_payload()
        )

    def tensor(self) -> Tensor:
        """Return a detached training-native `[1,81]` int64 tensor."""

        return torch.tensor(
            [self.grid_values],
            dtype=torch.int64,
            device="cpu",
        )


def materialize_p01_input(
    request: StructuralRefinementRequest,
    *,
    policy: P01MaterializationPolicyV1 = (
        DEFAULT_P01_MATERIALIZATION_POLICY
    ),
) -> P01MaterializedInput:
    """Materialize one sealed request into frozen P0.1 Sudoku input."""

    if not isinstance(
        request,
        StructuralRefinementRequest,
    ):
        raise TypeError(
            "request must be a "
            "StructuralRefinementRequest."
        )

    if not isinstance(
        policy,
        P01MaterializationPolicyV1,
    ):
        raise TypeError(
            "policy must be a "
            "P01MaterializationPolicyV1."
        )

    previous = _as_int_tuple(
        request.previous_grid,
        name="previous_grid",
    )

    clamp_values = _as_int_tuple(
        request.clamp_values,
        name="clamp_values",
    )

    clamp_mask = _as_bool_tuple(
        request.clamp_mask,
        name="clamp_mask",
    )

    active_indices = tuple(
        index
        for index, active in enumerate(
            clamp_mask
        )
        if active
    )

    for index in active_indices:
        value = clamp_values[index]

        if value < 1 or value > 9:
            raise ValueError(
                "Active P0.1 clamps must contain "
                "digits 1 through 9; "
                f"cell {index} contains {value}."
            )

    changed_indices = tuple(
        index
        for index in active_indices
        if clamp_values[index] != previous[index]
    )

    if not changed_indices:
        materialized = previous
        mode = (
            P01MaterializationMode
            .PRESERVE_PREVIOUS_SOLVED
        )

    else:
        candidate = [
            P01_BLANK_VALUE
        ] * P01_GRID_CELLS

        for index in active_indices:
            candidate[index] = clamp_values[index]

        materialized = tuple(candidate)
        mode = (
            P01MaterializationMode
            .ACTIVE_CLAMPS_AS_GIVENS
        )

    validated = validate_p01_givens(
        materialized
    )

    return P01MaterializedInput(
        request_digest=request.digest(),
        policy_digest=policy.digest(),
        mode=mode,
        active_clamp_count=len(active_indices),
        changed_clamp_count=len(changed_indices),
        grid_values=validated,
    )


__all__ = (
    "DEFAULT_P01_MATERIALIZATION_POLICY",
    "P01_BLANK_VALUE",
    "P01_GRID_CELLS",
    "P01_MATERIALIZED_INPUT_SCHEMA",
    "P01_MATERIALIZER_SCHEMA",
    "P01MaterializationMode",
    "P01MaterializationPolicyV1",
    "P01MaterializedInput",
    "materialize_p01_input",
    "validate_p01_givens",
)
