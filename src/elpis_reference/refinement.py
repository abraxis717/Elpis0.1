from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import torch

from .model import load_model
from .sudoku import decode_model_ids, encode_model_input, validate


@dataclass(frozen=True)
class RefinementStep:
    step: int
    valid: bool
    complete: bool
    conflicts: tuple[str, ...]
    proposal: tuple[int, ...]


@dataclass(frozen=True)
class RefinementResult:
    status: str
    solution: tuple[int, ...] | None
    steps: tuple[RefinementStep, ...]
    device: str


def solve_sudoku(
    puzzle: tuple[int, ...],
    model_path: Path | None = None,
    device: str = "auto",
    max_steps: int = 16,
) -> RefinementResult:
    if max_steps < 1 or max_steps > 16:
        raise ValueError("max_steps must be between 1 and 16 for the pinned TRM")

    model, target_device = load_model(model_path=model_path, device=device)

    inputs = torch.tensor(
        [encode_model_input(puzzle)],
        dtype=torch.int64,
        device=target_device,
    )
    puzzle_identifiers = torch.zeros(
        (1,),
        dtype=torch.int64,
        device=target_device,
    )
    batch = {
        "inputs": inputs,
        "puzzle_identifiers": puzzle_identifiers,
    }

    with torch.inference_mode():
        carry = model.initial_carry(batch)
        trace: list[RefinementStep] = []

        for step in range(1, max_steps + 1):
            carry, outputs = model(carry=carry, batch=batch)

            ids = tuple(
                int(value)
                for value in torch.argmax(
                    outputs["logits"],
                    dim=-1,
                )[0].detach().cpu().tolist()
            )

            if any(value < 1 or value > 10 for value in ids):
                trace.append(
                    RefinementStep(
                        step=step,
                        valid=False,
                        complete=False,
                        conflicts=("model-token-domain",),
                        proposal=(),
                    )
                )
            else:
                proposal = decode_model_ids(ids)
                verdict = validate(puzzle, proposal)

                trace.append(
                    RefinementStep(
                        step=step,
                        valid=verdict.valid,
                        complete=verdict.complete,
                        conflicts=verdict.conflicts,
                        proposal=proposal,
                    )
                )

                if verdict.valid:
                    return RefinementResult(
                        "SOLVED",
                        proposal,
                        tuple(trace),
                        str(target_device),
                    )

            if bool(carry.halted.all().item()):
                break

    return RefinementResult(
        "BUDGET_EXHAUSTED",
        None,
        tuple(trace),
        str(target_device),
    )
