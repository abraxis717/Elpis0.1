from types import SimpleNamespace

import torch

import elpis_reference.refinement as refinement
from elpis_reference.model import REGISTERED_PARAMETER_COUNT, model_config
from elpis_reference.sudoku import (
    decode_model_ids,
    encode_model_input,
    parse_puzzle,
    validate,
)
from elpis_reference.vendor.trm import TinyRecursiveReasoningModel_ACTV1


SOLVED = "534678912672195348198342567859761423426853791713924856961537284287419635345286179"


def test_sudoku_codec_and_validator():
    puzzle = parse_puzzle("." + SOLVED[1:])
    proposal = parse_puzzle(SOLVED)

    assert encode_model_input(puzzle)[0] == 1
    assert decode_model_ids(tuple(value + 1 for value in proposal)) == proposal

    verdict = validate(puzzle, proposal)
    assert verdict.valid
    assert verdict.complete


def test_model_abi_constructs_on_cpu():
    model = TinyRecursiveReasoningModel_ACTV1(
        model_config(torch.device("cpu"))
    )

    assert model.config.seq_len == 81
    assert model.config.vocab_size == 11
    assert model.config.halt_max_steps == 16
    assert model.config.mlp_t is True
    assert sum(parameter.numel() for parameter in model.parameters()) == REGISTERED_PARAMETER_COUNT

    batch = {
        "inputs": torch.ones((1, 81), dtype=torch.int64),
        "puzzle_identifiers": torch.zeros((1,), dtype=torch.int64),
    }

    carry = model.initial_carry(batch)
    assert tuple(carry.steps.shape) == (1,)


class _FakeModel:
    def __init__(self, token_ids):
        self._token_ids = tuple(token_ids)

    def initial_carry(self, batch):
        del batch
        return SimpleNamespace(
            halted=torch.zeros((1,), dtype=torch.bool)
        )

    def __call__(self, carry, batch):
        del carry, batch

        logits = torch.zeros(
            (1, 81, 11),
            dtype=torch.float32,
        )

        for index, token in enumerate(self._token_ids):
            logits[0, index, token] = 10.0

        return (
            SimpleNamespace(
                halted=torch.ones((1,), dtype=torch.bool)
            ),
            {
                "logits": logits,
                "q_halt_logits": torch.zeros((1,)),
                "q_continue_logits": torch.zeros((1,)),
            },
        )


def test_runtime_rejects_given_violation_instead_of_rewriting(monkeypatch):
    puzzle = parse_puzzle(SOLVED)
    candidate = list(parse_puzzle(SOLVED))
    candidate[0] = 4

    token_ids = tuple(value + 1 for value in candidate)

    monkeypatch.setattr(
        refinement,
        "load_model",
        lambda model_path=None, device="auto": (
            _FakeModel(token_ids),
            torch.device("cpu"),
        ),
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
        lambda model_path=None, device="auto": (
            _FakeModel(token_ids),
            torch.device("cpu"),
        ),
    )

    result = refinement.solve_sudoku(
        puzzle,
        max_steps=1,
    )

    assert result.status == "BUDGET_EXHAUSTED"
    assert result.solution is None
    assert result.steps[0].conflicts == ("model-token-domain",)
