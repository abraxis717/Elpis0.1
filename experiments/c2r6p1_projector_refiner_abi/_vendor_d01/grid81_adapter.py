"""Grid81 adapter for the transplanted recursive core (D0).

The adapter owns the task-facing I/O that the Sudoku donor used its own
embeddings for. It is intentionally tiny and contains NO semantic /
request / fixture identity, no seed identity, and no learned lookup key:

    token_embedding : [10, 512]   Grid81 BasisToken vocabulary 0..9
    output_head     : [512, 10]   per-cell BasisToken logits
    mask_embedding  : [2, 512]    writable mask (0 frozen / 1 writable)

Positions 0..15  : deterministic structural-context prefix
                   (see structural_context_packer.py)
Positions 16..96 : 81 Grid81 cells, input = token_embedding + mask_embedding

Adapter parameter count is reported separately from the recursive-core
parameter count (5,017,600).

The model can only emit per-cell logits. It has no RESOLVED output, no
authority-granting head, and no halting head (q_head is intentionally
omitted from the core; recorded as an adapter-boundary difference).
"""
from __future__ import annotations

from typing import Optional, Tuple

import torch
import torch.nn.functional as F
from torch import nn

from c2r7d0_constants import (
    HIDDEN_SIZE,
    MASK_VOCAB,
    PREFIX_LEN,
    SEQ_LEN_GRID,
    SEQ_LEN_TOTAL,
    TOKEN_VOCAB,
)
from grid81_trm_core import Grid81TRMCore, Grid81TRMCoreConfig
from structural_context_packer import (
    pack_batched_context,
    pack_structural_context,
)


class Grid81TRMAdapter(nn.Module):
    """Task-facing adapter (report parameters separately from the core)."""

    def __init__(self):
        super().__init__()
        if TOKEN_VOCAB != 10 or MASK_VOCAB != 2 or HIDDEN_SIZE != 512:
            raise ValueError("D0 adapter vocabulary/dimensions are fixed")
        self.token_embedding = nn.Embedding(TOKEN_VOCAB, HIDDEN_SIZE)
        self.output_head = nn.Linear(HIDDEN_SIZE, TOKEN_VOCAB, bias=False)
        self.mask_embedding = nn.Embedding(MASK_VOCAB, HIDDEN_SIZE)

    def forward(
        self,
        grid81: torch.Tensor,          # [B, 81] int64 tokens 0..9
        writable_mask81: torch.Tensor,  # [B, 81] int64 0/1
        declared529: torch.Tensor,      # [B, 529] 0/1
        active529: torch.Tensor,        # [B, 529] 0/1
    ) -> torch.Tensor:
        """Build the full [B, 97, 512] injection tensor.

        Pure function of (grid81, mask, declared529, active529).
        No other input may reach the recursive core.
        """
        if grid81.ndim != 2 or grid81.shape[1] != SEQ_LEN_GRID:
            raise ValueError(f"grid81 must be [B,{SEQ_LEN_GRID}]")
        if writable_mask81.shape != grid81.shape:
            raise ValueError("writable_mask81 must match grid81")
        if grid81.min() < 0 or grid81.max() >= TOKEN_VOCAB:
            raise ValueError("grid81 tokens must be 0..9")
        if writable_mask81.min() < 0 or writable_mask81.max() > 1:
            raise ValueError("writable_mask81 must be 0/1")

        grid = grid81.long()
        mask = writable_mask81.long()

        if declared529.ndim == 1:
            declared529 = declared529.unsqueeze(0)
        if active529.ndim == 1:
            active529 = active529.unsqueeze(0)
        if declared529.shape[0] == 1 and grid81.shape[0] != 1:
            declared529 = declared529.expand(grid81.shape[0], -1)
        if active529.shape[0] == 1 and grid81.shape[0] != 1:
            active529 = active529.expand(grid81.shape[0], -1)

        # Positions 16..96: grid cells.
        cell_input = (
            self.token_embedding(grid)
            + self.mask_embedding(mask)
        )
        # Positions 0..15: deterministic structural context.
        context = pack_batched_context(
            declared529.contiguous(), active529.contiguous()
        ).to(cell_input.dtype)

        return torch.cat((context, cell_input), dim=1)


class Grid81TRM(nn.Module):
    """Full D0 experimental model: recursive core + Grid81 adapter.

    The model emits per-cell BasisToken logits only. No RESOLVED, no
    authority, no halting: resolution and transition validity are
    deterministic Elpis authority, exercised by the decoder/validator.
    """

    def __init__(self, mode: str = "SCRATCH"):
        super().__init__()
        if mode not in ("SCRATCH", "SUDOKU_CORE_TRANSFER"):
            raise ValueError(
                f"unknown init mode {mode!r}; expected SCRATCH or "
                "SUDOKU_CORE_TRANSFER"
            )
        self.mode = mode
        self.core = Grid81TRMCore()
        self.adapter = Grid81TRMAdapter()

    # ------------------------------------------------------------------
    def build_injection(
        self,
        grid81: torch.Tensor,
        writable_mask81: torch.Tensor,
        declared529: torch.Tensor,
        active529: torch.Tensor,
    ) -> torch.Tensor:
        return self.adapter(
            grid81, writable_mask81, declared529, active529
        )

    def forward(
        self,
        grid81: torch.Tensor,
        writable_mask81: torch.Tensor,
        declared529: torch.Tensor,
        active529: torch.Tensor,
        carry: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
    ) -> Tuple[Tuple[torch.Tensor, torch.Tensor], torch.Tensor]:
        """Returns (new_carry, cell_logits [B, 81, 10]).

        cell_logits = output_head(final z_H)[:, 16:]
        """
        injection = self.build_injection(
            grid81, writable_mask81, declared529, active529
        )
        if carry is None:
            carry = self.core.empty_carry(
                grid81.shape[0], injection.device, injection.dtype
            )
        # Reset from H_init / L_init (donor semantics: all sequences start
        # halted on the first pass; here we always reset because D0 runs
        # one fixed pass per call).
        batch = injection.shape[0]
        reset = torch.ones(batch, dtype=torch.bool, device=injection.device)
        z_H, z_L = self.core.reset_carry(reset, carry)

        new_carry, final_z_H = self.core((z_H, z_L), injection)

        cell_logits = self.adapter.output_head(final_z_H)[:, PREFIX_LEN:]
        return new_carry, cell_logits

    @torch.no_grad()
    def per_cell_logits(
        self,
        grid81: torch.Tensor,
        writable_mask81: torch.Tensor,
        declared529: torch.Tensor,
        active529: torch.Tensor,
    ) -> torch.Tensor:
        _, cell_logits = self.forward(
            grid81, writable_mask81, declared529, active529
        )
        return cell_logits

    # ------------------------------------------------------------------
    # Parameter accounting
    # ------------------------------------------------------------------
    def recursive_core_elements(self) -> int:
        return self.core.recursive_core_elements()

    def adapter_elements(self) -> int:
        return sum(p.numel() for p in self.adapter.parameters())

    def total_elements(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def parameter_report(self) -> dict:
        return {
            "mode": self.mode,
            "recursive_core_elements": self.recursive_core_elements(),
            "adapter_elements": self.adapter_elements(),
            "total_elements": self.total_elements(),
            "recursive_core_tensors": len(dict(self.core.state_dict())),
            "adapter_tensors": len(dict(self.adapter.state_dict())),
        }
