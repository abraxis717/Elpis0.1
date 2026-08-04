"""Deterministic non-neural Sudoku reference adapter.

This adapter exists only to qualify the structural-refinement contract. It is
not the production TRM and must not be used as evidence that TRM reconciliation
provides value.
"""

from __future__ import annotations

import hashlib
import json

from .contract import (
    REFINEMENT_ACCEPTED,
    REFINEMENT_REJECTED,
    StructuralAdapterManifest,
    StructuralRefinementRequest,
    StructuralRefinementResult,
    build_refinement_result,
)


FULL_DIGIT_MASK = sum(
    1 << digit
    for digit in range(1, 10)
)


class DeterministicSudokuReferenceAdapter:
    """Deterministic depth-first qualification oracle."""

    def __init__(
        self,
        *,
        max_search_nodes: int = 1_000_000,
    ) -> None:
        if max_search_nodes < 0:
            raise ValueError(
                "max_search_nodes cannot be negative."
            )

        self._max_search_nodes = int(
            max_search_nodes
        )

        implementation_payload = {
            "algorithm": (
                "MRV_ROW_MAJOR_TIE_PREVIOUS_VALUE_FIRST_V1"
            ),
            "max_search_nodes": self._max_search_nodes,
        }

        implementation_digest = hashlib.sha256(
            b"darwinian.reference-sudoku-solver.v1\x00"
            + json.dumps(
                implementation_payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        self._manifest = StructuralAdapterManifest(
            adapter_id=(
                "DETERMINISTIC_SUDOKU_REFERENCE_ADAPTER"
            ),
            adapter_version="1.0.0",
            solver_family="REFERENCE_SUDOKU_ORACLE",
            implementation_digest=(
                implementation_digest
            ),
        )

    @property
    def manifest(self) -> StructuralAdapterManifest:
        return self._manifest

    @property
    def max_search_nodes(self) -> int:
        """Return the deterministic replay parameter."""
        return self._max_search_nodes

    def refine(
        self,
        request: StructuralRefinementRequest,
    ) -> StructuralRefinementResult:
        previous = [
            int(value)
            for value in request.previous_grid.tolist()
        ]
        clamp_values = [
            int(value)
            for value in request.clamp_values.tolist()
        ]
        clamp_mask = [
            bool(value)
            for value in request.clamp_mask.tolist()
        ]

        if all(
            (not clamp_mask[index])
            or previous[index] == clamp_values[index]
            for index in range(81)
        ):
            return build_refinement_result(
                request=request,
                manifest=self._manifest,
                outcome=REFINEMENT_ACCEPTED,
                reason_codes=(
                    "PREVIOUS_GRID_ALREADY_SATISFIES_CLAMPS",
                ),
                iteration_count=0,
                output_grid=previous,
            )

        board = [0] * 81
        row_masks = [0] * 9
        col_masks = [0] * 9
        box_masks = [0] * 9

        for index in range(81):
            if not clamp_mask[index]:
                continue

            digit = clamp_values[index]
            row = index // 9
            col = index % 9
            box = (row // 3) * 3 + col // 3
            bit = 1 << digit

            if (
                row_masks[row] & bit
                or col_masks[col] & bit
                or box_masks[box] & bit
            ):
                return build_refinement_result(
                    request=request,
                    manifest=self._manifest,
                    outcome=REFINEMENT_REJECTED,
                    reason_codes=(
                        "UNSATISFIABLE_CLAMP_CONSTELLATION",
                    ),
                    iteration_count=0,
                )

            board[index] = digit
            row_masks[row] |= bit
            col_masks[col] |= bit
            box_masks[box] |= bit

        node_count = 0
        budget_exhausted = False

        def candidate_mask(index: int) -> int:
            row = index // 9
            col = index % 9
            box = (row // 3) * 3 + col // 3

            used = (
                row_masks[row]
                | col_masks[col]
                | box_masks[box]
            )

            return FULL_DIGIT_MASK & ~used

        def choose_cell() -> tuple[int, int]:
            selected_index = -1
            selected_mask = 0
            selected_count = 10

            for index in range(81):
                if board[index] != 0:
                    continue

                mask = candidate_mask(index)
                count = mask.bit_count()

                if count == 0:
                    return index, 0

                if count < selected_count:
                    selected_index = index
                    selected_mask = mask
                    selected_count = count

                    if count == 1:
                        break

            return selected_index, selected_mask

        def ordered_digits(
            index: int,
            mask: int,
        ) -> tuple[int, ...]:
            preferred = previous[index]
            digits = []

            if mask & (1 << preferred):
                digits.append(preferred)

            for digit in range(1, 10):
                if digit == preferred:
                    continue

                if mask & (1 << digit):
                    digits.append(digit)

            return tuple(digits)

        def search() -> bool:
            nonlocal node_count
            nonlocal budget_exhausted

            index, mask = choose_cell()

            if index == -1:
                return True

            if mask == 0:
                return False

            row = index // 9
            col = index % 9
            box = (row // 3) * 3 + col // 3

            for digit in ordered_digits(index, mask):
                if node_count >= self._max_search_nodes:
                    budget_exhausted = True
                    return False

                node_count += 1
                bit = 1 << digit

                board[index] = digit
                row_masks[row] |= bit
                col_masks[col] |= bit
                box_masks[box] |= bit

                if search():
                    return True

                board[index] = 0
                row_masks[row] &= ~bit
                col_masks[col] &= ~bit
                box_masks[box] &= ~bit

                if budget_exhausted:
                    return False

            return False

        solved = search()

        if solved:
            return build_refinement_result(
                request=request,
                manifest=self._manifest,
                outcome=REFINEMENT_ACCEPTED,
                reason_codes=(
                    "REFERENCE_REFINEMENT_ACCEPTED",
                ),
                iteration_count=node_count,
                output_grid=board,
            )

        reason = (
            "SEARCH_BUDGET_EXHAUSTED"
            if budget_exhausted
            else "UNSATISFIABLE_CLAMP_CONSTELLATION"
        )

        return build_refinement_result(
            request=request,
            manifest=self._manifest,
            outcome=REFINEMENT_REJECTED,
            reason_codes=(reason,),
            iteration_count=node_count,
        )
