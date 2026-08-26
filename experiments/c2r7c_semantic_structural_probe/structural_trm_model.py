"""Experimental C2R7-C structural Tiny Recursive Model.

Neural authority:
    propose writable Grid81 tokens only.

Deterministic authority remains external:
    frozen loci, transition validation, residual recomputation, resolution.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import torch
from torch import nn
import torch.nn.functional as F

from structural_trm_features import FEATURE_WIDTH


GRID_SIZE = 81
TOKEN_VOCAB = 10
HIDDEN_SIZE = 64


@dataclass(frozen=True)
class Carry:
    z_h: torch.Tensor
    z_l: torch.Tensor


class RMSNorm(nn.Module):
    def __init__(self, eps: float = 1e-5):
        super().__init__()
        self.eps = eps

    def forward(self, x):
        return x * torch.rsqrt(
            x.square().mean(dim=-1, keepdim=True) + self.eps
        )


class Block(nn.Module):
    def __init__(self, hidden: int, heads: int, expansion: int):
        super().__init__()
        self.n1 = RMSNorm()
        self.attn = nn.MultiheadAttention(
            hidden,
            heads,
            dropout=0.0,
            batch_first=True,
        )
        self.n2 = RMSNorm()

        ff = hidden * expansion
        self.gate_up = nn.Linear(hidden, ff * 2)
        self.down = nn.Linear(ff, hidden)

    def forward(self, x):
        h = self.n1(x)
        a, _ = self.attn(h, h, h, need_weights=False)
        x = x + a

        h = self.n2(x)
        gate, value = self.gate_up(h).chunk(2, dim=-1)
        return x + self.down(F.silu(gate) * value)


class Reasoning(nn.Module):
    def __init__(self, hidden: int, heads: int, expansion: int, layers: int):
        super().__init__()
        self.layers = nn.ModuleList(
            Block(hidden, heads, expansion)
            for _ in range(layers)
        )

    def forward(self, state, injection):
        state = state + injection
        for layer in self.layers:
            state = layer(state)
        return state


class StructuralTRM64(nn.Module):
    def __init__(
        self,
        *,
        hidden: int = HIDDEN_SIZE,
        heads: int = 4,
        expansion: int = 2,
        layers: int = 2,
        h_cycles: int = 3,
        l_cycles: int = 6,
    ):
        super().__init__()

        if hidden % heads:
            raise ValueError("hidden must divide evenly by heads")

        self.hidden = hidden
        self.h_cycles = h_cycles
        self.l_cycles = l_cycles

        self.token_emb = nn.Embedding(TOKEN_VOCAB, hidden)
        self.mask_emb = nn.Embedding(2, hidden)
        self.pos_emb = nn.Embedding(GRID_SIZE, hidden)

        self.declared_emb = nn.Embedding(FEATURE_WIDTH, hidden)
        self.residual_emb = nn.Embedding(FEATURE_WIDTH, hidden)

        self.reasoning = Reasoning(
            hidden,
            heads,
            expansion,
            layers,
        )

        self.h_init = nn.Parameter(
            torch.randn(hidden) / math.sqrt(hidden)
        )
        self.l_init = nn.Parameter(
            torch.randn(hidden) / math.sqrt(hidden)
        )

        self.out_norm = RMSNorm()
        self.lm_head = nn.Linear(hidden, TOKEN_VOCAB)
        self.q_head = nn.Linear(hidden, 2)

    @staticmethod
    def _constraint_context(bits, embedding):
        if bits.ndim != 2 or bits.shape[1] != FEATURE_WIDTH:
            raise ValueError(
                f"constraint features must be [B,{FEATURE_WIDTH}]"
            )

        weights = bits.to(embedding.weight.dtype)
        count = weights.sum(dim=1, keepdim=True).clamp_min(1.0)

        return (weights @ embedding.weight) / count.sqrt()

    def initial_carry(self, batch: int, device, dtype):
        shape = (batch, GRID_SIZE, self.hidden)

        return Carry(
            z_h=self.h_init.to(device=device, dtype=dtype)
                .expand(shape).clone(),
            z_l=self.l_init.to(device=device, dtype=dtype)
                .expand(shape).clone(),
        )

    def forward(
        self,
        grid81,
        writable_mask81,
        declared529,
        residual529,
        carry=None,
    ):
        if grid81.ndim != 2 or grid81.shape[1] != GRID_SIZE:
            raise ValueError("grid81 must be [B,81]")

        if writable_mask81.shape != grid81.shape:
            raise ValueError("writable mask must match grid81")

        batch = grid81.shape[0]
        positions = torch.arange(
            GRID_SIZE,
            device=grid81.device,
        )[None, :]

        x = (
            self.token_emb(grid81.long())
            + self.mask_emb(writable_mask81.long())
            + self.pos_emb(positions)
        )

        declared = self._constraint_context(
            declared529,
            self.declared_emb,
        )
        active = self._constraint_context(
            residual529,
            self.residual_emb,
        )

        x = x + declared[:, None, :] + active[:, None, :]

        if carry is None:
            carry = self.initial_carry(
                batch,
                x.device,
                x.dtype,
            )

        z_h, z_l = carry.z_h, carry.z_l

        for _ in range(self.h_cycles):
            for _ in range(self.l_cycles):
                z_l = self.reasoning(
                    z_l,
                    z_h + x,
                )
            z_h = self.reasoning(
                z_h,
                z_l,
            )

        state = self.out_norm(z_h)

        return Carry(
            z_h=z_h.detach(),
            z_l=z_l.detach(),
        ), {
            "logits": self.lm_head(state),
            "q_logits": self.q_head(state.mean(dim=1)),
        }

    @torch.no_grad()
    def propose(
        self,
        grid81,
        writable_mask81,
        declared529,
        residual529,
        carry=None,
    ):
        carry, output = self(
            grid81,
            writable_mask81,
            declared529,
            residual529,
            carry,
        )

        prediction = output["logits"].argmax(dim=-1)

        proposed = torch.where(
            writable_mask81.bool(),
            prediction,
            grid81.long(),
        )

        return carry, proposed, output


def self_test():
    torch.manual_seed(20260826)

    model = StructuralTRM64().eval()

    grid = torch.zeros((2, 81), dtype=torch.long)
    grid[:, 0] = 1
    grid[:, 80] = 9

    mask = torch.ones_like(grid)
    mask[:, 0] = 0
    mask[:, 80] = 0

    declared = torch.zeros((2, FEATURE_WIDTH))
    residual = torch.zeros_like(declared)

    declared[:, 0] = 1
    declared[:, 10] = 1

    residual[0, 10] = 1
    residual[1, 11] = 1

    carry, output = model(
        grid,
        mask,
        declared,
        residual,
    )

    assert output["logits"].shape == (2, 81, 10)
    assert carry.z_h.shape == (2, 81, 64)
    assert carry.z_l.shape == (2, 81, 64)

    delta = (
        output["logits"][0] - output["logits"][1]
    ).abs().max().item()
    assert delta > 1e-7

    _, proposed, _ = model.propose(
        grid,
        mask,
        declared,
        residual,
    )

    frozen = mask == 0
    assert torch.equal(proposed[frozen], grid[frozen])

    params = sum(p.numel() for p in model.parameters())
    assert params < 250_000

    print(
        "TRM0_MODEL_SELFTEST=PASS "
        f"hidden=64 "
        f"params={params} "
        f"logits={tuple(output['logits'].shape)} "
        f"context_delta={delta:.8f} "
        "frozen_invariant=PASS"
    )


if __name__ == "__main__":
    self_test()
