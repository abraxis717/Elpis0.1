from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import torch

from .model import (
    FPRM_MAX_ITER,
    FPRM_RETRY_SEEDS,
    load_model,
)
from .sudoku import decode_model_ids, encode_model_input, validate


VALIDATION_INTERVAL = 20


def _encode_fprm_input(
    puzzle: tuple[int, ...],
) -> tuple[int, ...]:
    return tuple(int(value) + 1 for value in puzzle)


def _build_fprm_batch(
    puzzle: tuple[int, ...],
    target_device: torch.device,
) -> dict[str, torch.Tensor]:
    """Build the exact qualified fprm_eval32 inference geometry.

    Row 0 contains the real native Sudoku encoded as tokens 1..10.
    Rows 1..31 are all-zero padding, exactly matching the qualified
    PuzzleDataset/DataLoader behavior.
    """
    inputs = torch.zeros(
        (FPRM_RUNTIME_BATCH_SIZE, 81),
        dtype=torch.int32,
        device=target_device,
    )
    inputs[0] = torch.tensor(
        _encode_fprm_input(puzzle),
        dtype=torch.int32,
        device=target_device,
    )

    puzzle_identifiers = torch.zeros(
        (FPRM_RUNTIME_BATCH_SIZE,),
        dtype=torch.int32,
        device=target_device,
    )

    return {
        "inputs": inputs,
        "puzzle_identifiers": puzzle_identifiers,
    }


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


def _proposal_from_outputs(
    outputs: dict[str, torch.Tensor],
) -> tuple[int, ...] | None:
    ids = tuple(
        int(value)
        for value in torch.argmax(
            outputs["logits"],
            dim=-1,
        )[0].detach().cpu().tolist()
    )

    if any(value < 1 or value > 10 for value in ids):
        return None

    return decode_model_ids(ids)


FPRM_BULK_STEPS = 20
FPRM_RUNTIME_BATCH_SIZE = 32
FPRM_FP_THRESH = 0.1
FPRM_STEPSIZE_FLOOR = 1e-3


def _fixed_point_done(carry) -> bool:
    z_state = carry.inner_carry.z_L_state
    per_sample_done = (
        (z_state["residues"] < FPRM_FP_THRESH)
        | (z_state["stepsize"].view(-1) < FPRM_STEPSIZE_FLOOR)
    )
    return bool(per_sample_done.all().item())



def _forward(model, carry, batch, target_device):
    if target_device.type == "cuda":
        with torch.autocast(
            device_type="cuda",
            dtype=torch.bfloat16,
        ):
            return model(carry=carry, batch=batch)

    return model(carry=carry, batch=batch)


def _attempt(
    *,
    model,
    target_device: torch.device,
    puzzle: tuple[int, ...],
    batch: dict[str, torch.Tensor],
    seed: int,
    max_steps: int,
) -> tuple[tuple[int, ...] | None, tuple[RefinementStep, ...]]:
    with torch.inference_mode(), torch.device(target_device):
        carry = model.initial_carry(batch)

    limit = min(int(max_steps), int(model.max_iter))

    # Exact qualified stock evaluator bulk structure.
    if target_device.type == "cuda":
        autocast = torch.autocast(
            device_type="cuda",
            dtype=torch.bfloat16,
        )

        def _bulk_step(carry, batch):
            outputs = None
            for _ in range(FPRM_BULK_STEPS):
                with autocast:
                    carry, outputs = model(
                        carry=carry,
                        batch=batch,
                    )
            return carry, outputs

        bulk_step = torch.compile(
            _bulk_step,
            mode="default",
            dynamic=False,
        )
    else:
        def bulk_step(carry, batch):
            outputs = None
            for _ in range(FPRM_BULK_STEPS):
                carry, outputs = model(
                    carry=carry,
                    batch=batch,
                )
            return carry, outputs

    inference_steps = 0
    outputs = None

    with torch.inference_mode():
        while True:
            carry, outputs = bulk_step(carry, batch)
            inference_steps += FPRM_BULK_STEPS

            # Match stock evaluator exactly.
            if bool(carry.halted.all().item()):
                break

            z_L_state = carry.inner_carry.z_L_state
            per_sample_done = (
                (z_L_state["residues"] < FPRM_FP_THRESH)
                | (
                    z_L_state["stepsize"].view(-1)
                    < FPRM_STEPSIZE_FLOOR
                )
            )

            if (
                bool(per_sample_done.all().item())
                or inference_steps >= limit
            ):
                break

    assert outputs is not None

    proposal = _proposal_from_outputs(outputs)

    if proposal is None:
        return None, (
            RefinementStep(
                step=inference_steps,
                valid=False,
                complete=False,
                conflicts=("model-token-domain",),
                proposal=(),
            ),
        )

    verdict = validate(puzzle, proposal)

    step = RefinementStep(
        step=inference_steps,
        valid=verdict.valid,
        complete=verdict.complete,
        conflicts=verdict.conflicts,
        proposal=proposal,
    )

    if verdict.valid:
        return proposal, (step,)

    return None, (step,)

def solve_sudoku(
    puzzle: tuple[int, ...],
    model_path: Path | None = None,
    device: str = "auto",
    max_steps: int = FPRM_MAX_ITER,
) -> RefinementResult:
    if len(puzzle) != 81:
        raise ValueError("Sudoku puzzle must contain exactly 81 cells")

    if any(value < 0 or value > 9 for value in puzzle):
        raise ValueError("Sudoku puzzle cells must remain within 0..9")

    if max_steps < 1 or max_steps > FPRM_MAX_ITER:
        raise ValueError(
            f"max_steps must be between 1 and {FPRM_MAX_ITER} for FPRM"
        )

    full_trace: list[RefinementStep] = []
    last_device = device

    # Match independent stock-evaluator restart semantics:
    # each seed gets a fresh model constructed under that seed.
    for seed in FPRM_RETRY_SEEDS:
        model, target_device = load_model(
            model_path=model_path,
            device=device,
            seed=seed,
        )
        last_device = str(target_device)

        batch = _build_fprm_batch(
            puzzle,
            target_device,
        )

        solution, trace = _attempt(
            model=model,
            target_device=target_device,
            puzzle=puzzle,
            batch=batch,
            seed=seed,
            max_steps=max_steps,
        )

        full_trace.extend(trace)

        if solution is not None:
            return RefinementResult(
                status="SOLVED",
                solution=solution,
                steps=tuple(full_trace),
                device=str(target_device),
            )

        del model
        if target_device.type == "cuda":
            torch.cuda.empty_cache()

    return RefinementResult(
        status="BUDGET_EXHAUSTED",
        solution=None,
        steps=tuple(full_trace),
        device=last_device,
    )
