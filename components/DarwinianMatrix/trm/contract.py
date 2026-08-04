"""Frozen structural-refinement adapter contract.

The adapter boundary is deliberately ignorant of ecology. A request contains
only the previous solved Grid81 and projector-owned clamp tensors.

This module does not load or implement the production TRM.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Protocol, Sequence, runtime_checkable

import torch
from torch import Tensor

from ..geometry import (
    GRID_CELLS,
    require_solved_grid81,
    validate_partial_grid81,
)
from ..projector.constraints import ClampState


REQUEST_SCHEMA = "darwinian.structural-refinement-request.v1"
RESULT_SCHEMA = "darwinian.structural-refinement-result.v1"
MANIFEST_SCHEMA = "darwinian.structural-adapter-manifest.v1"

REFINEMENT_ACCEPTED = "REFINEMENT_ACCEPTED"
REFINEMENT_REJECTED = "REFINEMENT_REJECTED"


def canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def domain_digest(domain: str, payload: object) -> str:
    return hashlib.sha256(
        domain.encode("utf-8")
        + b"\x00"
        + canonical_json_bytes(payload)
    ).hexdigest()


def require_digest(name: str, value: str) -> None:
    if len(value) != 64:
        raise ValueError(
            f"{name} must be a 64-character SHA-256 digest."
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be hexadecimal."
        ) from exc


@dataclass(frozen=True)
class StructuralAdapterManifest:
    adapter_id: str
    adapter_version: str
    solver_family: str
    implementation_digest: str

    frozen: bool = True
    input_contract: str = REQUEST_SCHEMA
    output_contract: str = RESULT_SCHEMA

    def __post_init__(self) -> None:
        if not self.adapter_id:
            raise ValueError("adapter_id cannot be empty.")

        if not self.adapter_version:
            raise ValueError(
                "adapter_version cannot be empty."
            )

        if not self.solver_family:
            raise ValueError(
                "solver_family cannot be empty."
            )

        require_digest(
            "implementation_digest",
            self.implementation_digest,
        )

        if not self.frozen:
            raise ValueError(
                "Structural adapters must be frozen."
            )

        if self.input_contract != REQUEST_SCHEMA:
            raise ValueError(
                "Unsupported structural input contract."
            )

        if self.output_contract != RESULT_SCHEMA:
            raise ValueError(
                "Unsupported structural output contract."
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "frozen": self.frozen,
            "implementation_digest": (
                self.implementation_digest
            ),
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "schema_version": MANIFEST_SCHEMA,
            "solver_family": self.solver_family,
        }

    def digest(self) -> str:
        return domain_digest(
            MANIFEST_SCHEMA,
            self.canonical_payload(),
        )


class StructuralRefinementRequest:
    """Immutable-by-interface structural request."""

    __slots__ = (
        "_episode_id",
        "_frame_index",
        "_previous_grid",
        "_clamp_values",
        "_clamp_mask",
    )

    def __init__(
        self,
        *,
        episode_id: str,
        frame_index: int,
        previous_grid: Tensor | Sequence[int],
        clamp_values: Tensor | Sequence[int],
        clamp_mask: Tensor | Sequence[bool],
    ) -> None:
        if not episode_id:
            raise ValueError(
                "episode_id cannot be empty."
            )

        if frame_index < 0:
            raise ValueError(
                "frame_index cannot be negative."
            )

        self._episode_id = episode_id
        self._frame_index = int(frame_index)

        self._previous_grid = require_solved_grid81(
            previous_grid
        ).to(
            device="cpu",
            dtype=torch.int8,
        ).clone()

        self._clamp_values = torch.as_tensor(
            clamp_values,
            dtype=torch.int8,
            device="cpu",
        ).reshape(-1).clone()

        self._clamp_mask = torch.as_tensor(
            clamp_mask,
            dtype=torch.bool,
            device="cpu",
        ).reshape(-1).clone()

        if self._clamp_values.shape != (GRID_CELLS,):
            raise ValueError(
                "clamp_values must have shape (81,)."
            )

        if self._clamp_mask.shape != (GRID_CELLS,):
            raise ValueError(
                "clamp_mask must have shape (81,)."
            )

        inactive = ~self._clamp_mask
        active = self._clamp_mask

        if bool(
            self._clamp_values[inactive].ne(0).any()
        ):
            raise ValueError(
                "Inactive clamp values must equal zero."
            )

        if bool(
            (
                active
                & (
                    (self._clamp_values < 1)
                    | (self._clamp_values > 9)
                )
            ).any()
        ):
            raise ValueError(
                "Active clamp values must remain within 1..9."
            )

        partial = torch.where(
            self._clamp_mask,
            self._clamp_values.long(),
            torch.zeros(
                GRID_CELLS,
                dtype=torch.int64,
            ),
        )

        if not validate_partial_grid81(partial):
            raise ValueError(
                "Clamp constellation is locally contradictory."
            )

    @classmethod
    def from_clamp_state(
        cls,
        *,
        previous_grid: Tensor | Sequence[int],
        clamp_state: ClampState,
        frame_index: int,
    ) -> "StructuralRefinementRequest":
        if clamp_state.closed:
            raise ValueError(
                "Closed clamp state cannot create a "
                "structural-refinement request."
            )

        values, mask = clamp_state.trm_inputs()

        return cls(
            episode_id=clamp_state.episode_id,
            frame_index=frame_index,
            previous_grid=previous_grid,
            clamp_values=values,
            clamp_mask=mask,
        )

    @property
    def episode_id(self) -> str:
        return self._episode_id

    @property
    def frame_index(self) -> int:
        return self._frame_index

    @property
    def previous_grid(self) -> Tensor:
        return self._previous_grid.clone()

    @property
    def clamp_values(self) -> Tensor:
        return self._clamp_values.clone()

    @property
    def clamp_mask(self) -> Tensor:
        return self._clamp_mask.clone()

    @property
    def active_clamp_count(self) -> int:
        return int(self._clamp_mask.sum().item())

    def canonical_payload(self) -> dict[str, object]:
        return {
            "clamp_mask": [
                bool(value)
                for value in self._clamp_mask.tolist()
            ],
            "clamp_values": [
                int(value)
                for value in self._clamp_values.tolist()
            ],
            "episode_id": self._episode_id,
            "frame_index": self._frame_index,
            "previous_grid": [
                int(value)
                for value in self._previous_grid.tolist()
            ],
            "schema_version": REQUEST_SCHEMA,
        }

    def digest(self) -> str:
        return domain_digest(
            REQUEST_SCHEMA,
            self.canonical_payload(),
        )


@dataclass(frozen=True)
class StructuralRefinementResult:
    outcome: str
    reason_codes: tuple[str, ...]

    request_digest: str
    adapter_manifest_digest: str

    output_values: tuple[int, ...] | None
    iteration_count: int

    result_digest: str

    def __post_init__(self) -> None:
        if self.outcome not in (
            REFINEMENT_ACCEPTED,
            REFINEMENT_REJECTED,
        ):
            raise ValueError(
                "Unsupported refinement outcome."
            )

        if tuple(
            sorted(set(self.reason_codes))
        ) != self.reason_codes:
            raise ValueError(
                "reason_codes must be sorted and unique."
            )

        if not self.reason_codes:
            raise ValueError(
                "Refinement result requires a reason code."
            )

        require_digest(
            "request_digest",
            self.request_digest,
        )
        require_digest(
            "adapter_manifest_digest",
            self.adapter_manifest_digest,
        )
        require_digest(
            "result_digest",
            self.result_digest,
        )

        if self.iteration_count < 0:
            raise ValueError(
                "iteration_count cannot be negative."
            )

        if self.outcome == REFINEMENT_ACCEPTED:
            if self.output_values is None:
                raise ValueError(
                    "Accepted refinement requires output."
                )

            if len(self.output_values) != GRID_CELLS:
                raise ValueError(
                    "Accepted output must contain 81 values."
                )

        elif self.output_values is not None:
            raise ValueError(
                "Rejected refinement cannot contain output."
            )

    def output_grid(self) -> Tensor | None:
        if self.output_values is None:
            return None

        return torch.tensor(
            self.output_values,
            dtype=torch.int64,
        )

    def semantic_payload(self) -> dict[str, object]:
        return {
            "adapter_manifest_digest": (
                self.adapter_manifest_digest
            ),
            "iteration_count": self.iteration_count,
            "outcome": self.outcome,
            "output_values": (
                list(self.output_values)
                if self.output_values is not None
                else None
            ),
            "reason_codes": list(self.reason_codes),
            "request_digest": self.request_digest,
            "schema_version": RESULT_SCHEMA,
        }

    def recompute_digest(self) -> str:
        return domain_digest(
            RESULT_SCHEMA,
            self.semantic_payload(),
        )

    def validate_digest(self) -> bool:
        return (
            self.result_digest
            == self.recompute_digest()
        )


def build_refinement_result(
    *,
    request: StructuralRefinementRequest,
    manifest: StructuralAdapterManifest,
    outcome: str,
    reason_codes: Sequence[str],
    iteration_count: int,
    output_grid: Tensor | Sequence[int] | None = None,
) -> StructuralRefinementResult:
    output_values: tuple[int, ...] | None

    if outcome == REFINEMENT_ACCEPTED:
        if output_grid is None:
            raise ValueError(
                "Accepted refinement requires output_grid."
            )

        validated = require_solved_grid81(
            output_grid
        )

        mask = request.clamp_mask
        values = request.clamp_values

        if not torch.equal(
            validated[mask].long(),
            values[mask].long(),
        ):
            raise ValueError(
                "Refinement output violates active clamps."
            )

        output_values = tuple(
            int(value)
            for value in validated.tolist()
        )

    elif outcome == REFINEMENT_REJECTED:
        if output_grid is not None:
            raise ValueError(
                "Rejected refinement cannot contain output_grid."
            )

        output_values = None

    else:
        raise ValueError(
            "Unsupported refinement outcome."
        )

    partial = StructuralRefinementResult(
        outcome=outcome,
        reason_codes=tuple(
            sorted(set(reason_codes))
        ),
        request_digest=request.digest(),
        adapter_manifest_digest=manifest.digest(),
        output_values=output_values,
        iteration_count=int(iteration_count),
        result_digest="0" * 64,
    )

    return StructuralRefinementResult(
        outcome=partial.outcome,
        reason_codes=partial.reason_codes,
        request_digest=partial.request_digest,
        adapter_manifest_digest=(
            partial.adapter_manifest_digest
        ),
        output_values=partial.output_values,
        iteration_count=partial.iteration_count,
        result_digest=partial.recompute_digest(),
    )


@runtime_checkable
class FrozenStructuralAdapter(Protocol):
    @property
    def manifest(self) -> StructuralAdapterManifest:
        ...

    def refine(
        self,
        request: StructuralRefinementRequest,
    ) -> StructuralRefinementResult:
        ...


def execute_refinement(
    *,
    adapter: FrozenStructuralAdapter,
    request: StructuralRefinementRequest,
) -> StructuralRefinementResult:
    """Execute an adapter and enforce the frozen structural contract."""
    manifest = adapter.manifest

    if not manifest.frozen:
        raise RuntimeError(
            "Structural adapter is not frozen."
        )

    request_digest_before = request.digest()
    previous_before = request.previous_grid
    values_before = request.clamp_values
    mask_before = request.clamp_mask

    result = adapter.refine(request)

    if request.digest() != request_digest_before:
        raise RuntimeError(
            "Adapter mutated structural request identity."
        )

    if not torch.equal(
        request.previous_grid,
        previous_before,
    ):
        raise RuntimeError(
            "Adapter mutated previous Grid81."
        )

    if not torch.equal(
        request.clamp_values,
        values_before,
    ):
        raise RuntimeError(
            "Adapter mutated clamp values."
        )

    if not torch.equal(
        request.clamp_mask,
        mask_before,
    ):
        raise RuntimeError(
            "Adapter mutated clamp mask."
        )

    if result.request_digest != request.digest():
        raise RuntimeError(
            "Adapter result is bound to the wrong request."
        )

    if (
        result.adapter_manifest_digest
        != manifest.digest()
    ):
        raise RuntimeError(
            "Adapter result is bound to the wrong manifest."
        )

    if not result.validate_digest():
        raise RuntimeError(
            "Adapter result digest is invalid."
        )

    if result.outcome == REFINEMENT_ACCEPTED:
        output = result.output_grid()

        if output is None:
            raise RuntimeError(
                "Accepted result contains no output."
            )

        require_solved_grid81(output)

        mask = request.clamp_mask
        values = request.clamp_values

        if not torch.equal(
            output[mask].long(),
            values[mask].long(),
        ):
            raise RuntimeError(
                "Adapter output violates active clamps."
            )

    return result
