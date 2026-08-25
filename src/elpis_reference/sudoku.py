from __future__ import annotations

from dataclasses import dataclass

DIGITS = frozenset(range(1, 10))


@dataclass(frozen=True)
class SudokuValidation:
    valid: bool
    complete: bool
    conflicts: tuple[str, ...]


def parse_puzzle(text: str) -> tuple[int, ...]:
    compact = "".join(ch for ch in text.strip() if not ch.isspace())
    if len(compact) != 81:
        raise ValueError(f"Sudoku must contain 81 cells, got {len(compact)}")
    values = []
    for i, ch in enumerate(compact):
        if ch in ".0":
            values.append(0)
        elif ch in "123456789":
            values.append(int(ch))
        else:
            raise ValueError(f"invalid Sudoku character at {i}: {ch!r}")
    return tuple(values)


def encode_model_input(puzzle: tuple[int, ...]) -> tuple[int, ...]:
    if len(puzzle) != 81:
        raise ValueError("Sudoku grid must have 81 cells")
    return tuple(value + 1 for value in puzzle)


def decode_model_ids(ids: tuple[int, ...]) -> tuple[int, ...]:
    if len(ids) != 81:
        raise ValueError("TRM proposal must have 81 cells")
    result = tuple(int(value) - 1 for value in ids)
    if any(value < 0 or value > 9 for value in result):
        raise ValueError("TRM proposal contains an out-of-domain token")
    return result


def clamp_givens(puzzle: tuple[int, ...], proposal: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(given if given else proposed for given, proposed in zip(puzzle, proposal))


def validate(puzzle: tuple[int, ...], candidate: tuple[int, ...]) -> SudokuValidation:
    if len(puzzle) != 81 or len(candidate) != 81:
        return SudokuValidation(False, False, ("length",))

    conflicts: list[str] = []
    for i, given in enumerate(puzzle):
        if given and candidate[i] != given:
            conflicts.append(f"given:{i}")

    complete = all(value in DIGITS for value in candidate)

    def check_unit(indices: tuple[int, ...], label: str) -> None:
        values = [candidate[i] for i in indices]
        nonzero = [v for v in values if v != 0]
        if len(nonzero) != len(set(nonzero)):
            conflicts.append(label)
        if complete and set(values) != DIGITS:
            conflicts.append(label + ":incomplete-domain")

    for row in range(9):
        check_unit(tuple(row * 9 + col for col in range(9)), f"row:{row}")
    for col in range(9):
        check_unit(tuple(row * 9 + col for row in range(9)), f"col:{col}")
    for box_row in range(3):
        for box_col in range(3):
            indices = tuple(
                (box_row * 3 + dr) * 9 + (box_col * 3 + dc)
                for dr in range(3)
                for dc in range(3)
            )
            check_unit(indices, f"box:{box_row},{box_col}")

    unique = tuple(dict.fromkeys(conflicts))
    return SudokuValidation(valid=complete and not unique, complete=complete, conflicts=unique)


def format_grid(grid: tuple[int, ...]) -> str:
    rows = []
    for row in range(9):
        values = grid[row * 9 : (row + 1) * 9]
        rows.append("".join(str(v) if v else "." for v in values))
    return "\n".join(rows)
