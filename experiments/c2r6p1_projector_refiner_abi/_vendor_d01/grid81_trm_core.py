"""Native Elpis experimental core: Grid81TRMCore.

A faithful transplant of the Blackhao/Samsung Tiny Recursive Model
(TRM ACT V1, MLP-t) recursive body:

    hidden = 512, expansion = 4, L_layers = 2,
    H_cycles = 3, L_cycles = 6, sequence length = 97 (16 + 81)

The recursive block mechanism is preserved exactly as in the donor
(``models/recursive_reasoning/trm.py`` at the Blackhao snapshot,
reconciled against upstream c011037):

    * input injection:  state = state + injection
    * sequence-axis MLP-t SwiGLU on transposed activations, residual,
      then RMS-norm (post-norm), transpose back
    * hidden-axis SwiGLU, residual, then RMS-norm (post-norm)
    * RMS-norm computed in float32, cast back to input dtype

Recursive schedule (no-grad prefix, final cycle with gradient):

    with no_grad:
        for _H in range(H_cycles - 1):          # 2 full H-cycles, no grad
            for _L in range(L_cycles):           # 6 L-updates each
                z_L = L_level(z_L, z_H + x)
            z_H = L_level(z_H, z_L)               # H update via same module
    for _L in range(L_cycles):                    # final cycle, with grad
        z_L = L_level(z_L, z_H + x)
    z_H = L_level(z_H, z_L)                        # final H update, with grad

Intentional adapter-boundary differences vs the donor (recorded, not
silently reinterpreted):

* The donor's ACT wrapper (q_head halting, steps, reset_carry,
  no_ACT_continue) is omitted. D0 uses a FIXED externally specified
  number of outer recursive passes (exactly one inner pass here).
  Learned ACT must NOT decide structural resolution; the deterministic
  Elpis residual oracle remains the authority.
* embed_tokens / lm_head / puzzle_emb / q_head (task-facing Sudoku
  surfaces) are NOT part of the core; the Grid81 adapter owns I/O.
* H_init / L_init are persistent nn.Buffers, exactly as in the donor.

The single shared recursive module (L_level) is used for both L and H
updates, exactly as in the donor. 21 module invocations per pass.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import torch
import torch.nn.functional as F
from torch import nn

from c2r7d0_constants import (
    EXPANSION,
    HIDDEN_SIZE,
    H_CYCLES,
    L_CYCLES,
    L_LAYERS,
    PREFIX_LEN,
    RMS_NORM_EPS,
    SEQ_LEN_GRID,
    SEQ_LEN_TOTAL,
)


def _find_multiple(a: int, b: int) -> int:
    # Donor semantics: smallest multiple of b >= a.
    return (-(a // -b)) * b


def _swiglu_intermediate(hidden_size: int, expansion: float) -> int:
    # Donor layers.py SwiGLU: round(expansion * hidden * 2 / 3) rounded up
    # to a multiple of 256.
    return _find_multiple(round(expansion * hidden_size * 2 / 3), 256)


def trunc_normal_init_(tensor: torch.Tensor, std: float = 1.0,
                       lower: float = -2.0, upper: float = 2.0) -> torch.Tensor:
    # Faithful port of the donor models/common.py truncated normal init
    # (jax/flax-style, NOT nn.init.trunc_normal_).
    with torch.no_grad():
        if std == 0:
            tensor.zero_()
        else:
            sqrt2 = math.sqrt(2)
            a = math.erf(lower / sqrt2)
            b = math.erf(upper / sqrt2)
            z = (b - a) / 2

            c = (2 * math.pi) ** -0.5
            pdf_u = c * math.exp(-0.5 * lower ** 2)
            pdf_l = c * math.exp(-0.5 * upper ** 2)
            comp_std = std / math.sqrt(
                1 - (upper * pdf_u - lower * pdf_l) / z
                - ((pdf_u - pdf_l) / z) ** 2
            )

            tensor.uniform_(a, b)
            tensor.erfinv_()
            tensor.mul_(sqrt2 * comp_std)
            tensor.clip_(lower * comp_std, upper * comp_std)
    return tensor


def rms_norm(hidden_states: torch.Tensor,
             variance_epsilon: float = RMS_NORM_EPS) -> torch.Tensor:
    # Faithful port of the donor models/layers.py rms_norm:
    # computed in float32, cast back to the input dtype.
    input_dtype = hidden_states.dtype
    hidden_states = hidden_states.to(torch.float32)

    variance = hidden_states.square().mean(-1, keepdim=True)
    hidden_states = hidden_states * torch.rsqrt(variance + variance_epsilon)
    return hidden_states.to(input_dtype)


class SwiGLU(nn.Module):
    """Donor layers.py SwiGLU: gate_up_proj (2*inter, hidden), down_proj
    (hidden, inter), silu(gate) * up -> down. No bias."""

    def __init__(self, hidden_size: int, expansion: float):
        super().__init__()
        inter = _swiglu_intermediate(hidden_size, expansion)
        self.gate_up_proj = nn.Linear(hidden_size, inter * 2, bias=False)
        self.down_proj = nn.Linear(inter, hidden_size, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        gate, up = self.gate_up_proj(x).chunk(2, dim=-1)
        return self.down_proj(F.silu(gate) * up)


class RecursiveBlock(nn.Module):
    """One donor TinyRecursiveReasoningModel_ACTV1Block (mlp_t variant).

    Attribute names are kept identical to the donor so state_dict keys
    match: ``mlp_t.*`` (sequence axis) and ``mlp.*`` (hidden axis).
    """

    def __init__(self, config: "Grid81TRMCoreConfig"):
        super().__init__()
        if config.mlp_t is not True:
            raise ValueError("D0 is the MLP-t transplant; mlp_t must be True")
        self.mlp_t = SwiGLU(
            hidden_size=config.seq_len + config.puzzle_emb_len,  # L axis
            expansion=config.expansion,
        )
        self.mlp = SwiGLU(
            hidden_size=config.hidden_size,
            expansion=config.expansion,
        )
        self.norm_eps = config.rms_norm_eps

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        # hidden_states: [B, L, D]
        # Post Norm (donor order preserved exactly)
        hidden_states = hidden_states.transpose(1, 2)
        out = self.mlp_t(hidden_states)
        hidden_states = rms_norm(
            hidden_states + out, variance_epsilon=self.norm_eps
        )
        hidden_states = hidden_states.transpose(1, 2)
        # Fully Connected
        out = self.mlp(hidden_states)
        hidden_states = rms_norm(
            hidden_states + out, variance_epsilon=self.norm_eps
        )
        return hidden_states


class ReasoningModule(nn.Module):
    """Donor TinyRecursiveReasoningModel_ACTV1ReasoningModule:
    input injection then the L_layers blocks. Attribute name ``layers``
    is preserved so state_dict keys match the donor."""

    def __init__(self, layers: nn.ModuleList):
        super().__init__()
        self.layers = layers

    def forward(self, hidden_states: torch.Tensor,
                input_injection: torch.Tensor) -> torch.Tensor:
        hidden_states = hidden_states + input_injection
        for layer in self.layers:
            hidden_states = layer(hidden_states)
        return hidden_states


class Grid81TRMCoreConfig:
    """Frozen config mirroring the Blackhao all_config.yaml arch section
    for the recursive body (MLP-t)."""

    def __init__(self) -> None:
        self.hidden_size = HIDDEN_SIZE
        self.expansion = float(EXPANSION)
        self.L_layers = L_LAYERS
        self.H_cycles = H_CYCLES
        self.L_cycles = L_CYCLES
        self.seq_len = SEQ_LEN_GRID
        self.puzzle_emb_len = PREFIX_LEN
        self.total_seq_len = SEQ_LEN_TOTAL
        self.rms_norm_eps = RMS_NORM_EPS
        self.mlp_t = True

    @property
    def seq_len_plus_prefix(self) -> int:
        return self.seq_len + self.puzzle_emb_len


class Grid81TRMCore(nn.Module):
    """Native recursive core. state_dict layout (recursive body only):

        H_init                      [512]
        L_init                      [512]
        L_level.layers.0.mlp_t.gate_up_proj.weight  [1024, 97]
        L_level.layers.0.mlp_t.down_proj.weight     [97, 512]
        L_level.layers.0.mlp.gate_up_proj.weight    [3072, 512]
        L_level.layers.0.mlp.down_proj.weight       [512, 1536]
        L_level.layers.1.mlp_t.*  (same shapes)
        L_level.layers.1.mlp.*    (same shapes)

    10 tensors, 5,017,600 elements.
    """

    def __init__(self, config: Optional[Grid81TRMCoreConfig] = None):
        super().__init__()
        self.config = config or Grid81TRMCoreConfig()
        cfg = self.config

        if cfg.hidden_size != HIDDEN_SIZE:
            raise ValueError(f"hidden_size must be {HIDDEN_SIZE}")
        if cfg.seq_len != SEQ_LEN_GRID:
            raise ValueError(f"seq_len must be {SEQ_LEN_GRID}")
        if cfg.puzzle_emb_len != PREFIX_LEN:
            raise ValueError(f"prefix length must be {PREFIX_LEN}")
        if cfg.total_seq_len != SEQ_LEN_TOTAL:
            raise ValueError(f"total sequence length must be {SEQ_LEN_TOTAL}")

        # Donor: L_level is the single shared recursive module used for
        # both L and H updates.
        self.L_level = ReasoningModule(
            nn.ModuleList(
                RecursiveBlock(cfg) for _ in range(cfg.L_layers)
            )
        )

        # Donor: persistent buffers with truncated-normal std=1 init.
        self.H_init = nn.Buffer(
            trunc_normal_init_(torch.empty(cfg.hidden_size), std=1),
            persistent=True,
        )
        self.L_init = nn.Buffer(
            trunc_normal_init_(torch.empty(cfg.hidden_size), std=1),
            persistent=True,
        )

    # ------------------------------------------------------------------
    # Recursive body (parity-critical path)
    # ------------------------------------------------------------------

    def empty_carry(self, batch_size: int, device: torch.device,
                    dtype: torch.dtype) -> Tuple[torch.Tensor, torch.Tensor]:
        shape = (batch_size, self.config.total_seq_len,
                 self.config.hidden_size)
        return (
            torch.empty(shape, device=device, dtype=dtype),
            torch.empty(shape, device=device, dtype=dtype),
        )

    def reset_carry(self, reset_flag: torch.Tensor,
                    carry: Tuple[torch.Tensor, torch.Tensor]
                    ) -> Tuple[torch.Tensor, torch.Tensor]:
        # Donor reset_carry semantics: where(reset, H_init/L_init, carry).
        z_H, z_L = carry
        return (
            torch.where(reset_flag.view(-1, 1, 1), self.H_init, z_H),
            torch.where(reset_flag.view(-1, 1, 1), self.L_init, z_L),
        )

    def forward(
        self,
        carry: Tuple[torch.Tensor, torch.Tensor],
        input_injection: torch.Tensor,
    ) -> Tuple[Tuple[torch.Tensor, torch.Tensor], torch.Tensor]:
        """Run exactly one recursive pass with the fixed schedule.

        Args:
            carry: (z_H, z_L) [B, 97, 512]
            input_injection: [B, 97, 512] (the packed Grid81 input)

        Returns:
            ((z_H, z_L) detached, final z_H with grad)

        The final z_H (with gradient) is returned alongside the detached
        new carry, mirroring the donor where lm_head consumes z_H with
        grad while the new carry is detached.
        """
        cfg = self.config
        if input_injection.ndim != 3 or input_injection.shape[1:] != (
                cfg.total_seq_len, cfg.hidden_size):
            raise ValueError(
                "input_injection must be [B, 97, 512], got "
                f"{tuple(input_injection.shape)}"
            )
        z_H, z_L = carry

        # H_cycles-1 without grad (2 full cycles)
        with torch.no_grad():
            for _h_step in range(cfg.H_cycles - 1):
                for _l_step in range(cfg.L_cycles):
                    z_L = self.L_level(z_L, z_H + input_injection)
                z_H = self.L_level(z_H, z_L)
        # Final cycle with grad
        for _l_step in range(cfg.L_cycles):
            z_L = self.L_level(z_L, z_H + input_injection)
        z_H = self.L_level(z_H, z_L)

        new_carry = (z_H.detach(), z_L.detach())
        return new_carry, z_H

    # ------------------------------------------------------------------
    # Parameter accounting
    # ------------------------------------------------------------------

    def recursive_core_elements(self) -> int:
        """Recursive-body element count: parameters + persistent buffers
        (H_init, L_init). Matches the donor census: 5,017,600."""
        total = sum(p.numel() for p in self.parameters())
        total += sum(b.numel() for b in self.buffers())
        return total

    def state_key_census(self) -> dict:
        out = {}
        for name, p in self.state_dict().items():
            out[name] = (tuple(p.shape), str(p.dtype))
        return out
