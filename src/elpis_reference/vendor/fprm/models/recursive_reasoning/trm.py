from typing import Tuple, Dict, Optional
from dataclasses import dataclass
import math
import torch
import torch.nn.functional as F
from torch import nn
from pydantic import BaseModel
from ..common import trunc_normal_init_
from ..layers import RotaryEmbedding, CastedEmbedding, CastedLinear
from ..sparse_embedding import CastedSparseEmbedding

from ..transformer import FixedPointTransformer
from ..loop_attnres import LoopAttn, TrajectoryAttn, CrossRouter, CarrySourceAttn, CrossLite, DecayTrajAttn
from ..config import ReasoningModelConfig

IGNORE_LABEL_ID = -100

@dataclass
class TinyRecursiveReasoningModel_ACTV1InnerCarry:
    z_H: torch.Tensor
    z_L: torch.Tensor


@dataclass
class TinyRecursiveReasoningModel_ACTV1Carry:
    inner_carry: TinyRecursiveReasoningModel_ACTV1InnerCarry
    
    steps: torch.Tensor
    halted: torch.Tensor
    
    current_data: Dict[str, torch.Tensor]


class TinyRecursiveReasoningModel_ACTV1_Inner(nn.Module):
    def __init__(self, config: ReasoningModelConfig) -> None:
        super().__init__()
        self.config = config
        self.forward_dtype = getattr(torch, self.config.forward_dtype)

        # I/O

        self.embed_scale = math.sqrt(self.config.hidden_size)
        embed_init_std = 1.0 / self.embed_scale

        self.embed_tokens = CastedEmbedding(self.config.vocab_size, self.config.hidden_size, init_std=embed_init_std, cast_to=self.forward_dtype)
        self.lm_head      = CastedLinear(self.config.hidden_size, self.config.vocab_size, bias=False)
        self.q_head       = CastedLinear(self.config.hidden_size, 2, bias=True)

        self.puzzle_emb_len = -(self.config.puzzle_emb_ndim // -self.config.hidden_size)  if self.config.puzzle_emb_len == 0 else self.config.puzzle_emb_len  # ceil div
        if self.config.puzzle_emb_ndim > 0:
            # Zero init puzzle embeddings
            self.puzzle_emb = CastedSparseEmbedding(self.config.num_puzzle_identifiers, self.config.puzzle_emb_ndim,
                                                    batch_size=self.config.batch_size, init_std=0, cast_to=self.forward_dtype)

        # LM Blocks
        if self.config.pos_encodings == "rope":
            self.rotary_emb = RotaryEmbedding(dim=self.config.hidden_size // self.config.num_heads,
                                              max_position_embeddings=self.config.seq_len + self.puzzle_emb_len,
                                              base=self.config.rope_theta)
        elif self.config.pos_encodings == "learned":
            self.embed_pos = CastedEmbedding(self.config.seq_len + self.puzzle_emb_len, self.config.hidden_size, init_std=embed_init_std, cast_to=self.forward_dtype)
        else:
            pass

        # Reasoning Layers
        self.L_level = FixedPointTransformer(config=config, n_layers=self.config.L_layers)

        # Loop-AttnRes: replaces the carry-last connection between L-steps in the
        # with-grad cycle with attention over the loop-state history. zero-init
        # pseudo-query => uniform average over sources at init (AttnRes stabilizer).
        if self.config.loop_attnres:
            assert self.config.loop_attnres_mode == "state", "only 'state' mode wired for TRM loop-attn"
            grid = self.config.loop_attnres_grid
            if grid == "loop1d":
                self.loop_attn = LoopAttn(self.config.hidden_size, self.config.num_heads,
                                          self.config.loop_attnres_impl,
                                          recency_decay_init=self.config.loop_attnres_recency_init)
            elif grid == "cross":
                self.loop_attn = CrossRouter(
                    self.config.hidden_size, self.config.L_layers,
                    window=self.config.loop_attnres_window,
                    recency_init=self.config.loop_attnres_recency_init,
                    temp=self.config.loop_attnres_temp)
            elif grid == "crosslite":
                self.loop_attn = CrossLite(
                    self.config.hidden_size, self.config.L_layers,
                    window=self.config.loop_attnres_window,
                    recency_init=self.config.loop_attnres_recency_init,
                    temp=self.config.loop_attnres_temp)
            elif grid == "carrysource":
                self.loop_attn = CarrySourceAttn(
                    self.config.hidden_size, self.config.L_layers,
                    window=self.config.loop_attnres_window,
                    carry_bias_init=self.config.loop_attnres_carry_bias_init,
                    recency_init=self.config.loop_attnres_recency_init,
                    temp=self.config.loop_attnres_temp,
                    dkey=self.config.loop_attnres_dkey)
            elif grid == "ema":
                self.loop_attn = DecayTrajAttn(
                    self.config.hidden_size,
                    heads=self.config.loop_attnres_ema_heads,
                    beta_init=self.config.loop_attnres_beta_init,
                    temp=self.config.loop_attnres_temp,
                    content=self.config.loop_attnres_content,
                    score_norm=self.config.loop_attnres_score_norm,
                    score_noise=self.config.loop_attnres_score_noise,
                    mode_sigma=self.config.loop_attnres_mode_sigma)
            elif grid in ("flat", "struct"):
                self.loop_attn = TrajectoryAttn(
                    self.config.hidden_size, self.config.L_layers,
                    structured=(grid == "struct"),
                    window=self.config.loop_attnres_window,
                    recency_decay_init=self.config.loop_attnres_recency_init,
                    temp=self.config.loop_attnres_temp)
            else:
                raise ValueError(f"Unknown loop_attnres_grid {grid!r}")
        else:
            self.loop_attn = None

        # Initial states
        self.H_init = nn.Buffer(trunc_normal_init_(torch.empty(self.config.hidden_size, dtype=self.forward_dtype), std=1), persistent=True)
        self.L_init = nn.Buffer(trunc_normal_init_(torch.empty(self.config.hidden_size, dtype=self.forward_dtype), std=1), persistent=True)

        # Q head special init
        # Init Q to (almost) zero for faster learning during bootstrapping
        with torch.no_grad():
            self.q_head.weight.zero_()
            self.q_head.bias.fill_(-5)  # type: ignore

    def _input_embeddings(self, input: torch.Tensor, puzzle_identifiers: torch.Tensor):
        # Token embedding
        embedding = self.embed_tokens(input.to(torch.int32))

        # Puzzle embeddings
        if self.config.puzzle_emb_ndim > 0:
            puzzle_embedding = self.puzzle_emb(puzzle_identifiers)
            
            pad_count = self.puzzle_emb_len * self.config.hidden_size - puzzle_embedding.shape[-1]
            if pad_count > 0:
                puzzle_embedding = F.pad(puzzle_embedding, (0, pad_count))

            embedding = torch.cat((puzzle_embedding.view(-1, self.puzzle_emb_len, self.config.hidden_size), embedding), dim=-2)

        # Position embeddings
        if self.config.pos_encodings == "learned":
            # scale by 1/sqrt(2) to maintain forward variance
            embedding = 0.707106781 * (embedding + self.embed_pos.embedding_weight.to(self.forward_dtype))

        # Scale
        return self.embed_scale * embedding

    def empty_carry(self, batch_size: int):
        return TinyRecursiveReasoningModel_ACTV1InnerCarry(
            z_H=torch.empty(batch_size, self.config.seq_len + self.puzzle_emb_len, self.config.hidden_size, dtype=self.forward_dtype),
            z_L=torch.empty(batch_size, self.config.seq_len + self.puzzle_emb_len, self.config.hidden_size, dtype=self.forward_dtype),
        )
        
    def reset_carry(self, reset_flag: torch.Tensor, carry: TinyRecursiveReasoningModel_ACTV1InnerCarry):
        return TinyRecursiveReasoningModel_ACTV1InnerCarry(
            z_H=torch.where(reset_flag.view(-1, 1, 1), self.H_init, carry.z_H),
            z_L=torch.where(reset_flag.view(-1, 1, 1), self.L_init, carry.z_L),
        )

    def _l_cycle(self, z_L, z_H, input_embeddings, seq_info, n_steps):
        """One L-cycle of n_steps. Baseline: carry-last recurrence. Loop-AttnRes:
        the state fed to each step is a softmax-attention mixture over the full
        loop-state history {z_L_in, o_1, ..., o_t} (replaces the cross-loop
        residual; no sliding window — distant sources matter most)."""
        inj = z_H + input_embeddings
        if self.loop_attn is None:            # carry-last baseline
            for _ in range(n_steps):
                z_L = self.L_level(z_L, inj, **seq_info)
            return z_L
        if self.config.loop_attnres_grid == "loop1d":   # 1D loop-axis attention (LoopAttn)
            sources = [z_L]                   # distant anchor = state entering the cycle
            z_in = z_L
            for _ in range(n_steps):
                o = self.L_level(z_in, inj, **seq_info)
                sources.append(o)
                z_in = self.loop_attn(sources)
            return z_in
        if self.config.loop_attnres_grid == "ema":
            # Decay-fused trajectory attention as an exact O(1) recurrence: no window,
            # no history buffer — carry the softmax numerator/denominator instead.
            state = self.loop_attn.init_state(z_L)
            z_in = z_L
            for _ in range(n_steps):
                _, layer_states = self.L_level(z_in, inj, collect_layers=True, **seq_info)
                z_in, state = self.loop_attn(layer_states, state)
            return z_in
        if self.config.loop_attnres_grid in ("cross", "crosslite"):
            # Cross-shaped per-layer routing (CrossRouter / CrossLite): every layer input — the
            # within-block hops AND the cycle-boundary carry — is a routed read over
            # {anchor, last-L computation tail, the input source's own W-iteration
            # history}. Router l feeds layer l; its column is layer (l-1) mod L, the
            # layer that produces its input.
            L = len(self.L_level.layers)
            cols = [[] for _ in range(L)]     # cols[j] = layer-j outputs at past iterations, oldest..newest
            prev = []                         # trailing computation states from earlier iterations

            def route(l, cur_states):
                tail = (prev + cur_states)[-L:][::-1]        # newest first
                return self.loop_attn(l, tail, cols[(l - 1) % L][::-1], z_L)

            z_in = z_L
            for _ in range(n_steps):
                _, layer_states = self.L_level(z_in, inj, collect_layers=True, route_fn=route, **seq_info)
                z_in = route(0, layer_states)                # boundary carry for the next iteration
                W = self.config.loop_attnres_window
                for j, s in enumerate(layer_states):
                    cols[j] = (cols[j] + [s])[-W:]
                prev = (prev + layer_states)[-L:]
            return z_in
        W = self.config.loop_attnres_window
        if self.config.loop_attnres_grid == "carrysource":
            # Single-softmax simplex over {z_last (the carry), layer x iteration history}.
            # Replaces the residual with a convex trajectory read; the carry slot's large
            # bias makes it start = carry-last. z_last = the newest block output o.
            hist, z_in = [], z_L
            for _ in range(n_steps):
                o, layer_states = self.L_level(z_in, inj, collect_layers=True, **seq_info)
                hist.append(layer_states)
                if len(hist) > W:
                    hist = hist[-W:]
                z_in = self.loop_attn(o, hist)
            return z_in
        # 2D trajectory (flat / struct): attend over the {layers x iterations} grid,
        # with the iteration history capped to loop_attnres_window for stability.
        hist, z_in = [], z_L
        for _ in range(n_steps):
            _o, layer_states = self.L_level(z_in, inj, collect_layers=True, **seq_info)
            hist.append(layer_states)
            if len(hist) > W:
                hist = hist[-W:]
            z_in = self.loop_attn(z_L, hist)   # anchor = state entering the cycle
        return z_in

    def forward(self, carry: TinyRecursiveReasoningModel_ACTV1InnerCarry, batch: Dict[str, torch.Tensor]) -> Tuple[TinyRecursiveReasoningModel_ACTV1InnerCarry, torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        seq_info = dict(
            cos_sin=self.rotary_emb() if hasattr(self, "rotary_emb") else None, 
            puzzle_emb_len=self.puzzle_emb_len
        )

        # Input encoding
        input_embeddings = self._input_embeddings(batch["inputs"], batch["puzzle_identifiers"])

        # Forward iterations
        z_H, z_L = carry.z_H, carry.z_L
        # Random-depth training (depthdrop): one warmup loop depth per forward, sampled
        # from the menu. Grad cycles stay at n_backwards_L (constant BPTT memory); the
        # graded segment learns to refine from variable-depth prefixes, which is what
        # eval-time depth scaling exercises. Eval keeps the configured/scanned depth.
        warmup_L, grad_L = self.config.L_cycles, self.config.n_backwards_L
        if self.training and self.config.loop_depthdrop:
            choices = [int(x) for x in self.config.loop_depthdrop.split(",") if x.strip()]
            warmup_L = choices[int(torch.randint(len(choices), (1,)).item())]
        if self.training and self.config.loop_depthdrop_grad:
            choices = [int(x) for x in self.config.loop_depthdrop_grad.split(",") if x.strip()]
            grad_L = choices[int(torch.randint(len(choices), (1,)).item())]
        # H_cycles-1 without grad
        with torch.no_grad():
            for _H_step in range(self.config.H_cycles-1):
                z_L = self._l_cycle(z_L, z_H, input_embeddings, seq_info, warmup_L)
                z_H = self.L_level(z_H, z_L, **seq_info)
        # 1 with grad
        z_L = self._l_cycle(z_L, z_H, input_embeddings, seq_info, grad_L)
        z_H = self.L_level(z_H, z_L, **seq_info)

        # LM Outputs
        new_carry = TinyRecursiveReasoningModel_ACTV1InnerCarry(z_H=z_H.detach(), z_L=z_L.detach())  # New carry no grad
        output = self.lm_head(z_H)[:, self.puzzle_emb_len:]
        
        if self.config.q_logit_detach_model is True:
            z_H = z_H.detach()
        
        if self.config.q_logit_from_puzzle_emb is True:
            q_logits = self.q_head(z_H[:, 0]).to(torch.float32) # Q-head; uses the first puzzle_emb position
        else:
            q_logits = self.q_head(z_H[:, self.puzzle_emb_len:].mean(dim=1))
        return new_carry, output, (q_logits[..., 0], q_logits[..., 1])


class TinyRecursiveReasoningModel_ACTV1(nn.Module):
    """ACT wrapper."""

    def __init__(self, config_dict: dict):
        super().__init__()
        self.config = ReasoningModelConfig(**config_dict)
        self.inner = TinyRecursiveReasoningModel_ACTV1_Inner(self.config)

    @property
    def puzzle_emb(self):
        return self.inner.puzzle_emb

    def initial_carry(self, batch: Dict[str, torch.Tensor]):
        batch_size = batch["inputs"].shape[0]

        return TinyRecursiveReasoningModel_ACTV1Carry(
            inner_carry=self.inner.empty_carry(batch_size),  # Empty is expected, it will be reseted in first pass as all sequences are halted.
            
            steps=torch.zeros((batch_size, ), dtype=torch.int32),
            halted=torch.ones((batch_size, ), dtype=torch.bool),  # Default to halted
            
            current_data={k: torch.empty_like(v) for k, v in batch.items()}
        )
        
    def forward(self, carry: TinyRecursiveReasoningModel_ACTV1Carry, batch: Dict[str, torch.Tensor]) -> Tuple[TinyRecursiveReasoningModel_ACTV1Carry, Dict[str, torch.Tensor]]:

        # Update data, carry (removing halted sequences)
        new_inner_carry = self.inner.reset_carry(carry.halted, carry.inner_carry)
        
        new_steps = torch.where(carry.halted, 0, carry.steps)

        new_current_data = {k: torch.where(carry.halted.view((-1, ) + (1, ) * (batch[k].ndim - 1)), batch[k], v) for k, v in carry.current_data.items()}

        # Forward inner model
        new_inner_carry, logits, (q_halt_logits, q_continue_logits) = self.inner(new_inner_carry, new_current_data)

        outputs = {
            "logits": logits,
            "q_halt_logits": q_halt_logits,
            "q_continue_logits": q_continue_logits
        }

        with torch.no_grad():
            # Step
            new_steps = new_steps + 1
            is_last_step = new_steps >= self.config.halt_max_steps
            
            halted = is_last_step

            # if training, and ACT is enabled
            if self.training and (self.config.halt_max_steps > 1):

                # Halt signal
                # NOTE: During evaluation, always use max steps, this is to guarantee the same halting steps inside a batch for batching purposes
                
                if self.config.no_ACT_continue:
                    halted = halted | (q_halt_logits > 0)
                else:
                    halted = halted | (q_halt_logits > q_continue_logits)

                # Exploration
                min_halt_steps = (torch.rand_like(q_halt_logits) < self.config.halt_exploration_prob) * torch.randint_like(new_steps, low=2, high=self.config.halt_max_steps + 1)
                halted = halted & (new_steps >= min_halt_steps)

                if not self.config.no_ACT_continue:
                    # Compute target Q
                    # NOTE: No replay buffer and target networks for computing target Q-value.
                    # As batch_size is large, there're many parallel envs.
                    # Similar concept as PQN https://arxiv.org/abs/2407.04811
                    _, _, (next_q_halt_logits, next_q_continue_logits), _, _ = self.inner(new_inner_carry, new_current_data)
                    outputs["target_q_continue"] = torch.sigmoid(torch.where(is_last_step, next_q_halt_logits, torch.maximum(next_q_halt_logits, next_q_continue_logits)))

        return TinyRecursiveReasoningModel_ACTV1Carry(new_inner_carry, new_steps, halted, new_current_data), outputs
