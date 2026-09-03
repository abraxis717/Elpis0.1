from typing import List

import math
import torch
from torch import nn

from .layers import rms_norm, CastedLinear


class LoopAttn(nn.Module):
    """Attention over the loop axis (Kimi AttnRes, arXiv:2603.15031), two impls.

    Sources are {x_embed, o_1, ..., o_t} (token embedding + per-loop outputs); the
    softmax runs over the loop index, per token position, and the result replaces
    (or, in residual-mix mode, corrects) the cross-loop residual.

    impl="lite": the paper's lightweight form — one learned pseudo-query `w`,
      keys = RMSNorm(sources), values = raw sources, single head, no projections.
    impl="mha": a stronger version — multi-head with learned K/V/O projections and
      a learned per-head query. More expressive routing (tests whether the lite
      single-pseudo-query is the bottleneck).

    Both add a recency-decay bias (newest source favored at init) so the loop
    starts ~residual-like and large windows can train. `gate` is for the caller's
    residual-mix mode.
    """

    # recency_decay_init defaults to 0.0 = PAPER-FAITHFUL: zero-init query w gives a
    # uniform average over sources at step 0 (the AttnRes stabilizer per Kimi
    # arXiv:2603.15031). The paper has NO recency bias; its sliding-window/recency
    # ablation is the WEAKEST variant ("selecting distant sources matters most").
    # Keep this 0 unless explicitly A/B-testing a recency prior.
    def __init__(self, hidden_size: int, num_heads: int = 8, impl: str = "lite",
                 eps: float = 1e-6, recency_decay_init: float = 0.0):
        super().__init__()
        self.impl = impl
        self.eps = eps
        self.recency_decay = nn.Parameter(torch.tensor(float(recency_decay_init)))
        self.gate = nn.Parameter(torch.tensor(-4.0))  # residual-mix gate (sigmoid ~ 0 at init)
        if impl == "lite":
            self.w = nn.Parameter(torch.zeros(hidden_size))  # learned pseudo-query (uniform init)
        elif impl == "mha":
            assert hidden_size % num_heads == 0
            self.num_heads = num_heads
            self.head_dim = hidden_size // num_heads
            self.k_proj = CastedLinear(hidden_size, hidden_size, bias=False)
            self.v_proj = CastedLinear(hidden_size, hidden_size, bias=False)
            self.o_proj = CastedLinear(hidden_size, hidden_size, bias=False)
            self.q = nn.Parameter(torch.zeros(num_heads, self.head_dim))  # per-head query (uniform init)
        else:
            raise ValueError(f"Unknown loop_attnres_impl {impl!r}")

    def forward(self, sources: List[torch.Tensor]) -> torch.Tensor:
        # AttnRes over the source axis. Zero-init query w => uniform average at
        # init (the AttnRes stabilizer). Optional learnable recency bias: with
        # recency_decay>0 the softmax starts ~one-hot on the most-recent source
        # (= carry-last baseline at init), free to reach back to distant sources
        # as recency_decay shrinks during training.
        v = torch.stack(sources, dim=0)                              # [S, B, T, D]
        S = v.shape[0]
        dist = torch.arange(S - 1, -1, -1, device=v.device, dtype=torch.float32)  # [S]: oldest=S-1 .. newest=0
        rbias = (-self.recency_decay.float() * dist)                 # [S]

        if self.impl == "lite":
            logits = torch.einsum("d,sbtd->sbt", self.w.to(v.dtype), rms_norm(v, self.eps)).float()
            logits = logits + rbias.view(S, 1, 1)
            a = logits.softmax(dim=0).to(v.dtype)
            return torch.einsum("sbt,sbtd->btd", a, v)

        # mha
        B, T, D = v.shape[1], v.shape[2], v.shape[3]
        H, hd = self.num_heads, self.head_dim
        K = self.k_proj(rms_norm(v, self.eps)).view(S, B, T, H, hd)
        V = self.v_proj(v).view(S, B, T, H, hd)
        logits = (torch.einsum("hd,sbthd->sbth", self.q.to(v.dtype), K) / math.sqrt(hd)).float()  # [S,B,T,H]
        logits = logits + rbias.view(S, 1, 1, 1)
        a = logits.softmax(dim=0).to(v.dtype)
        out = torch.einsum("sbth,sbthd->bthd", a, V).reshape(B, T, D)
        return self.o_proj(out)


class CrossRouter(nn.Module):
    """Per-layer routed residual over the (depth x iteration) trajectory ('cross' grid).

    Every layer input in the L-cycle — the cycle-boundary carry (router 0, feeding
    layer 0 of the next iteration) and each within-block hop (router l, feeding layer
    l) — is REPLACED by a softmax mixture over a fixed cross-shaped slot layout:

      slot 0                    : anchor — the state that entered the cycle
      slots 1..n_layers         : the last n_layers states in computation order
                                  (slot 1 = the natural predecessor = baseline input)
      slots n_layers+1..+window : the input source's own history — outputs of the SAME
                                  producing layer at the last `window` earlier iterations

    One learned pseudo-query per router (zero-init), RMSNorm keys, raw values; a
    learned per-slot bias replaces factorized layer/recency terms (slot semantics are
    fixed). bias[:, 1] = recency_init => every softmax starts ~one-hot on the natural
    predecessor => the whole model equals the carry-last baseline at init. Absent
    slots (early iterations) are simply not stacked. The slot count is bounded, so
    the softmax stays bounded at any eval loop depth (no growing-history OOD blowup).
    """

    def __init__(self, hidden_size: int, n_layers: int, window: int,
                 recency_init: float, temp: float, eps: float = 1e-6):
        super().__init__()
        self.n_layers = n_layers
        self.window = window
        self.temp = temp
        self.eps = eps
        self.w = nn.Parameter(torch.zeros(n_layers, hidden_size))
        bias = torch.zeros(n_layers, 1 + n_layers + window)
        bias[:, 1] = recency_init
        self.bias = nn.Parameter(bias)

    def forward(self, r: int, tail: List[torch.Tensor], col: List[torch.Tensor],
                anchor: torch.Tensor) -> torch.Tensor:
        # tail: recent computation states, newest first (tail[0] = natural predecessor);
        # col: the input source's outputs at earlier iterations, newest first.
        col = col[:self.window]
        srcs = [anchor] + tail + col
        slots = [0] + list(range(1, 1 + len(tail))) + list(range(1 + self.n_layers, 1 + self.n_layers + len(col)))
        v = torch.stack(srcs, dim=0)                                 # [S, B, T, D]
        logits = torch.einsum("d,sbtd->sbt", self.w[r].to(v.dtype), rms_norm(v, self.eps)).float() / self.temp
        logits = logits + self.bias[r, slots].float().view(-1, 1, 1)
        a = logits.softmax(dim=0).to(v.dtype)
        return torch.einsum("sbt,sbtd->btd", a, v)


class CarrySourceAttn(nn.Module):
    """Single-softmax simplex routing that REPLACES the loop residual ('carrysource').

    At each loop step the next input is a convex mixture over the sources
        S = { z_last (the carry = natural predecessor), o[l, i] for the windowed layer x
              iteration history }
    with NO external additive residual (values are the RAW states, so the mixture stays in
    their convex hull). The routing is:

        logit_i = q(RMSNorm(z_last)) . k(key_i) / temp
                  + bias_2d(layer_i, age_i)                 # history slots
                  + carry_bias                              # the z_last slot only
        beta    = softmax_i(logit)      ;   z_in = Σ_i beta_i . state_i

    `q` is zero-init so at step 0 the content term is 0 and the softmax is driven by the
    bias alone; `carry_bias` (large init) then makes beta ~one-hot on z_last => the whole
    model equals the carry-last baseline at init, free to spread mass onto the trajectory.

    dkey: the KEY input is augmented with motion — [RMSNorm(state), RMSNorm(delta),
    ||delta||] where delta = state - (same slot one iteration earlier). Values stay the raw
    states; only source *selection* sees the trajectory velocity.
    """

    def __init__(self, hidden_size: int, n_layers: int, window: int,
                 carry_bias_init: float, recency_init: float, temp: float,
                 dkey: bool = False, eps: float = 1e-6):
        super().__init__()
        self.n_layers = n_layers
        self.window = window
        self.temp = temp
        self.dkey = dkey
        self.eps = eps
        self.q_proj = CastedLinear(hidden_size, hidden_size, bias=False)  # query from z_last
        key_in = hidden_size * (2 if dkey else 1) + (1 if dkey else 0)    # dkey: [z, delta, ||delta||]
        self.k_proj = CastedLinear(key_in, hidden_size, bias=False)       # key from source (+motion)
        self.carry_bias = nn.Parameter(torch.tensor(float(carry_bias_init)))
        self.recency_decay = nn.Parameter(torch.tensor(float(recency_init)))
        self.layer_bias = nn.Parameter(torch.zeros(n_layers))
        with torch.no_grad():
            self.q_proj.weight.zero_()   # content off at init => pure-bias (carry-last) start

    def _key(self, state, delta):
        if not self.dkey:
            return self.k_proj(rms_norm(state, self.eps))
        dn = ((delta * delta).mean(dim=-1, keepdim=True) + self.eps).sqrt()   # [B,T,1] ||delta||
        feat = torch.cat([rms_norm(state, self.eps), rms_norm(delta, self.eps), dn.to(state.dtype)], dim=-1)
        return self.k_proj(feat)

    def forward(self, z_last: torch.Tensor, hist: List[List[torch.Tensor]]) -> torch.Tensor:
        # hist[i] = [o_{0,i}, ..., o_{L-1,i}] for kept iteration i (oldest..newest), windowed
        # by the caller. z_last = the carry (newest block output = natural predecessor).
        H = len(hist)
        srcs, keys, bias = [z_last], [self._key(z_last, torch.zeros_like(z_last))], [self.carry_bias]
        for i, layer_states in enumerate(hist):
            age = float(H - 1 - i)                       # 0 = most-recent iteration
            prev = hist[i - 1] if i > 0 else None        # same-layer state one iteration earlier
            for l, s in enumerate(layer_states):
                delta = s - prev[l] if prev is not None else torch.zeros_like(s)
                srcs.append(s)
                keys.append(self._key(s, delta))
                bias.append(self.layer_bias[l] - self.recency_decay * age)

        v = torch.stack(srcs, dim=0)                     # [S, B, T, D]
        k = torch.stack(keys, dim=0)                     # [S, B, T, D]
        q = self.q_proj(rms_norm(z_last, self.eps))      # [B, T, D]
        logits = torch.einsum("btd,sbtd->sbt", q, k).float() / (self.temp * math.sqrt(k.shape[-1]))
        logits = logits + torch.stack(bias, dim=0).float().view(-1, 1, 1)
        a = logits.softmax(dim=0).to(v.dtype)
        return torch.einsum("sbt,sbtd->btd", a, v)


class CrossLite(nn.Module):
    """Low-capacity per-layer routing — the 'crosslite' cross rescue.

    Same cross-shaped slot geometry and per-layer routing as CrossRouter (router l feeds
    layer l; slots = {anchor, last-L computation tail, the input source's own window-capped
    history}), but the capacity that made full cross overfit is stripped:
      - ONE content query `w` shared across all L routers (not per-layer),
      - a factorized slot bias: slot_bias[slot] + layer_gain[r] * slot_bias (rank-1
        layer x slot interaction) instead of a full [L, S] bias table,
      - a per-layer scalar temperature.
    Values are raw states; bias[1] (natural-predecessor slot) is recency-init'd so every
    router starts ~carry-last => the model equals the baseline at init.
    """

    def __init__(self, hidden_size: int, n_layers: int, window: int,
                 recency_init: float, temp: float, eps: float = 1e-6):
        super().__init__()
        self.n_layers = n_layers
        self.window = window
        self.eps = eps
        self.w = nn.Parameter(torch.zeros(hidden_size))              # shared content query
        slot_bias = torch.zeros(1 + n_layers + window)
        slot_bias[1] = recency_init
        self.slot_bias = nn.Parameter(slot_bias)                     # shared across routers
        self.layer_gain = nn.Parameter(torch.zeros(n_layers))       # rank-1 layer modulation
        self.log_temp = nn.Parameter(torch.full((n_layers,), math.log(temp)))  # per-layer temp

    def forward(self, r: int, tail: List[torch.Tensor], col: List[torch.Tensor],
                anchor: torch.Tensor) -> torch.Tensor:
        col = col[:self.window]
        srcs = [anchor] + tail + col
        slots = [0] + list(range(1, 1 + len(tail))) + list(range(1 + self.n_layers, 1 + self.n_layers + len(col)))
        v = torch.stack(srcs, dim=0)                                 # [S, B, T, D]
        logits = torch.einsum("d,sbtd->sbt", self.w.to(v.dtype), rms_norm(v, self.eps)).float()
        logits = logits / self.log_temp[r].exp().float()
        sb = self.slot_bias[slots].float()
        logits = logits + (sb * (1.0 + self.layer_gain[r].float())).view(-1, 1, 1)
        a = logits.softmax(dim=0).to(v.dtype)
        return torch.einsum("sbt,sbtd->btd", a, v)


class TrajectoryAttn(nn.Module):
    """Structured 2D attention over the {layers x iterations} reasoning trajectory.

    Sources are all per-layer outputs o[l, t] over the (windowed) loop history plus the
    anchor state entering the cycle. A single learned pseudo-query `w` scores each source
    (RMSNorm keys, raw values); the softmax runs over ALL sources per token position and
    the mixture replaces the cross-loop carry — a 2D generalisation of LoopAttn, which
    attends over one axis only.

    The iteration-recency bias is ALWAYS applied (it is the stabilizer + the iteration-axis
    structure; without it a zero-init query over the whole windowed grid over-averages and
    diverges). `structured` toggles the DEPTH/LAYER axis:
    structured=False -> logit = w.RMSNorm(o)/temp - recency_decay*age[t]. A 1D pool over the
      flattened layer states with no layer distinction (the ablation baseline).
    structured=True  -> + layer_bias[l]: the SEPARATE layer-index bias adds the second
      (depth) axis, giving the router which-layer-at-which-iteration 2D structure — the point.

    Stability (the self-attn host diverges past the trained depth with an unbounded
    softmax over a growing OOD history): the iteration history is capped to the last
    `window` iterations and the logits are temperature-scaled.
    """

    def __init__(self, hidden_size: int, n_layers: int, structured: bool = True,
                 window: int = 16, recency_decay_init: float = 1.0, temp: float = 1.0,
                 eps: float = 1e-6):
        super().__init__()
        self.structured = structured
        self.window = window
        self.temp = temp
        self.eps = eps
        self.w = nn.Parameter(torch.zeros(hidden_size))          # learned pseudo-query
        self.recency_decay = nn.Parameter(torch.tensor(float(recency_decay_init)))
        # +1 slot for the anchor (the state entering the cycle)
        self.layer_bias = nn.Parameter(torch.zeros(n_layers + 1))

    def forward(self, anchor: torch.Tensor, hist: List[List[torch.Tensor]]) -> torch.Tensor:
        # hist[i] = [o_{0,i}, ..., o_{L-1,i}] for kept iteration i (newest last), already
        # windowed by the caller. Build the flat source stack + per-source (layer, age).
        L = len(hist[0])
        H = len(hist)
        srcs, lidx, age = [], [], []
        for i, layer_states in enumerate(hist):
            a = H - 1 - i                      # 0 = most-recent iteration
            for l, s in enumerate(layer_states):
                srcs.append(s); lidx.append(l); age.append(a)
        srcs.append(anchor); lidx.append(L); age.append(H)        # anchor = oldest, own bias slot

        v = torch.stack(srcs, dim=0)                               # [S, B, T, D]
        S = v.shape[0]
        logits = torch.einsum("d,sbtd->sbt", self.w.to(v.dtype), rms_norm(v, self.eps)).float() / self.temp
        age_t = torch.tensor(age, device=v.device, dtype=torch.float32)
        logits = logits - self.recency_decay.float() * age_t.view(S, 1, 1)   # iteration axis (always)
        if self.structured:                                                  # + depth/layer axis
            lidx_t = torch.tensor(lidx, device=v.device)
            logits = logits + self.layer_bias[lidx_t].float().view(S, 1, 1)
        a = logits.softmax(dim=0).to(v.dtype)
        return torch.einsum("sbt,sbtd->btd", a, v)


class DecayTrajAttn(nn.Module):
    """Trajectory attention with the decay fused INTO the softmax ('ema' grid).

    The pseudo-query is fixed per head, so the geometric-decay softmax over the
    ENTIRE {layers x iterations} history + anchor

        weight(source at age a) ∝ exp(w_h · RMSNorm(source) / temp) · beta_h^a

    is EXACTLY a running exponentially-weighted average — an O(1) recurrence over
    a per-head numerator/denominator, no window, no source stacking:

        N ← beta·N + Σ_l e^{s_l}·o_l ;  D ← beta·D + Σ_l e^{s_l} ;  read = N/D.

    heads=1 with beta=e^{-recency_decay} equals 'flat' at window→∞ (a strict
    generalization of the adjudication winner; the trained flat solution IS
    beta≈e^{-0.70}≈0.5 plus a weak content term). beta = sigmoid(logit), learnable
    per head — heads>1 reads the trajectory at multiple timescales (per-head decay
    a la RetNet, but on the loop axis, replacing the carry). w is zero-init (pure
    decay-weighted average at step 0); content=False freezes w at 0 (the pure
    learned-beta EMA ablation). Values are the raw states, so the read stays in
    their convex hull — bounded at any depth, and N/D saturates with depth (deep
    eval sees no OOD source-count growth).
    """

    def __init__(self, hidden_size: int, heads: int, beta_init: float, temp: float,
                 content: bool = True, score_norm: bool = True, score_noise: float = 0.0,
                 mode_sigma: float = 0.0, eps: float = 1e-6):
        super().__init__()
        assert hidden_size % heads == 0
        self.heads = heads
        self.hdim = hidden_size // heads
        self.temp = temp
        self.score_norm = score_norm
        self.score_noise = score_noise
        self.mode_sigma = mode_sigma
        self.eps = eps
        self.w = nn.Parameter(torch.zeros(heads, hidden_size), requires_grad=content)
        # heads==1: beta_init. heads>1: multi-timescale spread (fast..slow).
        beta = torch.full((heads,), float(beta_init)) if heads == 1 else torch.linspace(0.2, 0.9, heads)
        self.beta_logit = nn.Parameter(torch.logit(beta))

    def _weight(self, s: torch.Tensor, dw=None) -> torch.Tensor:
        # exp(content logit), fp32 [B, T, H, 1]; clamp keeps e^s finite in fp32.
        # score_norm=False scores the RAW state: the query sees magnitude, matching
        # the value path (values are unnormed states) at the cost of scale-sensitivity.
        q_in = rms_norm(s, self.eps) if self.score_norm else s
        logit = torch.einsum("hd,btd->bth", self.w.to(s.dtype), q_in).float() / self.temp
        # Coherent query mode (P2-lite): dw is one random query perturbation per
        # sample, shared by EVERY write of the cycle — a persistent routing mode,
        # unlike the independent per-source noise below (which tested negative).
        if dw is not None:
            logit = logit + torch.einsum("bhd,btd->bth", dw.to(q_in.dtype), q_in).float() / self.temp
        # Write-time-fixed source noise: each source is written into N/D exactly once,
        # so noise drawn here persists in the accumulators for the source's lifetime —
        # a persistent stochastic routing pattern, NOT per-read noise (which would need
        # the full history and break the O(1) folding). Train-time only.
        if self.training and self.score_noise > 0:
            logit = logit + self.score_noise * torch.randn_like(logit)
        return logit.clamp(-8.0, 8.0).exp().unsqueeze(-1)

    def init_state(self, anchor: torch.Tensor):
        B, T, H = anchor.shape
        dw = None
        if self.training and self.mode_sigma > 0:
            # unit-RMS query direction: logit perturbation std ~= mode_sigma
            dw = self.mode_sigma * torch.randn(B, self.heads, H, device=anchor.device) / (H ** 0.5)
        e = self._weight(anchor, dw)
        return e * anchor.view(B, T, self.heads, self.hdim).float(), e, dw

    def forward(self, layer_states: List[torch.Tensor], state):
        N, D, dw = state
        beta = self.beta_logit.sigmoid().float().view(1, 1, self.heads, 1)
        N, D = beta * N, beta * D
        for o in layer_states:
            B, T, _ = o.shape
            e = self._weight(o, dw)
            N = N + e * o.view(B, T, self.heads, self.hdim).float()
            D = D + e
        out = (N / D).flatten(2).to(layer_states[-1].dtype)
        return out, (N, D, dw)
