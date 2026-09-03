from pathlib import Path
from types import SimpleNamespace

import torch

import elpis_reference.refinement as refinement
from elpis_reference.model import (
    MODEL_FILENAME,
    MODEL_SHA256,
    REGISTERED_PARAMETER_COUNT,
    load_model,
    verify_model,
)
from elpis_reference.sudoku import (
    decode_model_ids,
    encode_model_input,
    parse_puzzle,
    validate,
)


SOLVED = "534678912672195348198342567859761423426853791713924856961537284287419635345286179"


def test_sudoku_codec_and_validator():
    puzzle = parse_puzzle("." + SOLVED[1:])
    proposal = parse_puzzle(SOLVED)

    assert encode_model_input(puzzle)[0] == 1
    assert decode_model_ids(tuple(value + 1 for value in proposal)) == proposal

    verdict = validate(puzzle, proposal)
    assert verdict.valid
    assert verdict.complete


def test_fprm_model_abi_constructs_on_cpu():
    root = Path(__file__).resolve().parents[1]
    checkpoint = root / "models" / MODEL_FILENAME

    authority = verify_model(checkpoint)

    assert MODEL_FILENAME == "FPRM.Samsung_TRM"
    assert authority["sha256"] == MODEL_SHA256
    assert authority["strict_load"] is True
    assert authority["registered_parameters"] == REGISTERED_PARAMETER_COUNT

    model, device = load_model(
        checkpoint,
        device="cpu",
        seed=0,
    )

    assert device == torch.device("cpu")
    assert model.training is False
    assert model.config.seq_len == 81
    assert model.config.vocab_size == 11
    assert model.config.conv_type == "conv2d"
    assert model.config.conv_kernel_size == 3
    assert model.max_iter == 1000

    assert (
        sum(parameter.numel() for parameter in model.parameters())
        == REGISTERED_PARAMETER_COUNT
    )

    puzzle = parse_puzzle("." + SOLVED[1:])
    batch = refinement._build_fprm_batch(
        puzzle,
        torch.device("cpu"),
    )

    assert batch["inputs"].shape == (32, 81)
    assert batch["puzzle_identifiers"].shape == (32,)

    with torch.device("cpu"):
        carry = model.initial_carry(batch)

    assert tuple(carry.halted.shape) == (32,)


class _FakeModel:
    def __init__(self, token_ids):
        self._token_ids = tuple(token_ids)
        self.max_iter = 1000

    def initial_carry(self, batch):
        return SimpleNamespace(
            halted=torch.zeros(
                (batch["inputs"].shape[0],),
                dtype=torch.bool,
            )
        )

    def __call__(self, carry, batch):
        del carry

        rows = batch["inputs"].shape[0]

        logits = torch.zeros(
            (rows, 81, 11),
            dtype=torch.float32,
        )

        for index, token in enumerate(self._token_ids):
            logits[0, index, token] = 10.0

        return (
            SimpleNamespace(
                halted=torch.ones(
                    (rows,),
                    dtype=torch.bool,
                )
            ),
            {
                "logits": logits,
                "q_halt_logits": torch.zeros((rows,)),
                "q_continue_logits": torch.zeros((rows,)),
            },
        )


def _fake_loader(model):
    def load_model(
        model_path=None,
        device="auto",
        seed=None,
    ):
        del model_path, device, seed
        return model, torch.device("cpu")

    return load_model


def test_runtime_rejects_given_violation_instead_of_rewriting(monkeypatch):
    puzzle = parse_puzzle(SOLVED)
    candidate = list(parse_puzzle(SOLVED))
    candidate[0] = 4

    token_ids = tuple(value + 1 for value in candidate)

    monkeypatch.setattr(
        refinement,
        "load_model",
        _fake_loader(_FakeModel(token_ids)),
    )

    result = refinement.solve_sudoku(
        puzzle,
        max_steps=1,
    )

    assert result.status == "BUDGET_EXHAUSTED"
    assert result.solution is None
    assert "given:0" in result.steps[0].conflicts


def test_runtime_fails_closed_on_out_of_domain_model_token(monkeypatch):
    puzzle = parse_puzzle("." + SOLVED[1:])
    token_ids = [value + 1 for value in parse_puzzle(SOLVED)]
    token_ids[0] = 0

    monkeypatch.setattr(
        refinement,
        "load_model",
        _fake_loader(_FakeModel(token_ids)),
    )

    result = refinement.solve_sudoku(
        puzzle,
        max_steps=1,
    )

    assert result.status == "BUDGET_EXHAUSTED"
    assert result.solution is None
    assert result.steps[0].conflicts == ("model-token-domain",)
