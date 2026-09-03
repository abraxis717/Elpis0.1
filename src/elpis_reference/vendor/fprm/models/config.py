from pydantic import BaseModel
from typing import Optional

class ReasoningModelConfig(BaseModel):
    batch_size: int
    seq_len: int
    puzzle_emb_ndim: int = 0
    num_puzzle_identifiers: int
    vocab_size: int

    H_cycles: int
    L_cycles: int
    n_backwards_L: int = 1   # number of with-grad L-level steps in the final pass; was implicitly L_cycles before

    H_layers: int # ignored
    L_layers: int

    # Transformer config
    hidden_size: int
    expansion: float
    num_heads: int
    pos_encodings: str

    rms_norm_eps: float = 1e-5
    rope_theta: float = 10000.0
    
    # Halting Q-learning config
    halt_max_steps: int
    halt_exploration_prob: float

    forward_dtype: str = "bfloat16"

    # Alexia: added
    mlp_t: bool = False # use mlp on L instead of transformer
    puzzle_emb_len: int = 16 # if non-zero, its specified to this value
    no_ACT_continue: bool =  True # No continue ACT loss, only use the sigmoid of the halt which makes much more sense

    # Q-head input source: True -> read from z_H[:, 0] (first puzzle_emb register, original behavior).
    # False -> mean-pool z_H over the non-puzzle_emb token positions.
    q_logit_from_puzzle_emb: bool = True
    # When True, q-head loss only updates the q-head itself, not the reasoning trunk.
    q_logit_detach_model: bool = False

    # When True, self-attention uses a causal mask (left-to-right). Default False
    # for non-autoregressive tasks (ARC, sudoku, maze); set True for tasks like
    # state tracking where prefix-k accuracy from a single forward is desired.
    causal: bool = False

    # Fields introduced by FPTRM.
    # Defaults reproduce the original TRM block: post-norm, no conv, no residual scaling.
    softmax_temp: float = 1.0
    norm_type: str = "post-norm"            # 'pre-norm' | 'peri-norm' | 'post-norm'
    norm_placement: str = "none"            # 'input' | 'output' | 'none'
    conv_type: str = "none"                 # 'conv1d' | 'conv2d' | 'none'
    conv_kernel_size: int = 4
    conv_bias: bool = False
    residual_scale: Optional[str] = None    # None | 'fixed' | 'input-independent' | 'input-dependent'
    alpha_1_init: float = 0.5
    alpha_2_init: float = 0.5
    normalize_input_injection: bool = False
    use_spec_norm_linear: bool = False

    # When True, only alpha_2 (the outer input-injection mix) is learnable;
    # the per-block alpha_1/beta_1 are pinned to 1 so blocks behave as plain residuals.
    outer_only: bool = False

    # DropConnect-style weight dropout applied to the trunk CastedLinear layers
    # (Attention.qkv_proj/o_proj and SwiGLU.gate_up_proj/down_proj). 0.0 = off.
    # The mask is resampled per training batch by the train loop.
    weight_dropout: float = 0.0

    # Loop-AttnRes (Kimi AttnRes ported to the loop axis). When True, the carry
    # between L-steps in the with-grad cycle is REPLACED by softmax attention over
    # the full history of loop states {z_L_in, o_1, ..., o_t} (no sliding window:
    # the AttnRes ablation shows distant sources matter most). Off => standard
    # carry-last recurrence.
    loop_attnres: bool = False
    loop_attnres_mode: str = "state"   # 'state' (attend over raw loop states); 'delta' reserved
    loop_attnres_impl: str = "lite"    # 'lite' (paper-faithful single pseudo-query) | 'mha'
    # Trajectory (2D depth x loop) attention. 'loop1d' = attend over per-iteration L_level
    # outputs only (LoopAttn, the current 1D mechanism). 'flat' = attend over the flat
    # {layers x iterations} pool, content-only (Depth-Attention-style ablation baseline).
    # 'struct' = the same grid with factorized layer + iteration-recency biases (structured
    # 2D). 'flat'/'struct' collect per-layer states and cap the iteration history to
    # loop_attnres_window for stability on the (divergence-prone) self-attn host.
    # 'cross' = per-layer routing (CrossRouter): EVERY layer input (incl. the cycle-boundary
    # carry) is a routed read over {anchor, last-L computation tail, the input source's own
    # window-capped iteration history}; bounded slot count => bounded softmax at any depth.
    # 'carrysource' = single-softmax simplex routing over {z_last (the carry / natural
    # predecessor), the layer x iteration history}. Content query FROM z_last, keys from
    # the sources, values = raw states (convex hull, no external additive residual). A
    # dedicated carry-slot bias (loop_attnres_carry_bias_init, large) makes the softmax
    # start ~one-hot on z_last => carry-last baseline at init, then learn a bounded
    # trajectory read. 'crosslite' = shared-query low-capacity per-layer routing (the
    # cross rescue: shared content query + factorized layer/slot bias + per-layer temp).
    # 'ema' (DecayTrajAttn) = the decay fused INTO the softmax: per-head learnable
    # geometric decay beta in the logits; the fixed pseudo-query makes the windowless
    # trajectory softmax an exact O(1) recurrence (numerator/denominator EMA). Strict
    # generalization of 'flat' (heads=1, beta=e^{-recency_decay}, window->inf).
    loop_attnres_grid: str = "loop1d"
    loop_attnres_ema_heads: int = 1       # ema: decay heads (>1 = multi-timescale, linspace 0.2..0.9)
    loop_attnres_beta_init: float = 0.5   # ema, heads==1: decay init (flat's learned e^-0.70 ~ 0.5)
    loop_attnres_content: bool = True     # ema: False freezes the pseudo-query at 0 (pure learned-beta EMA)
    loop_attnres_score_norm: bool = True  # ema: False scores raw states (no RMSNorm) — score sees magnitude, like the values
    loop_attnres_score_noise: float = 0.0 # ema: train-time write-fixed source-logit noise sigma (persistent stochastic routing)
    loop_attnres_mode_sigma: float = 0.0  # ema: train-time coherent query-mode sigma (one dw per sample per cycle, all writes share it)
    loop_attnres_window: int = 16
    loop_attnres_temp: float = 1.0     # softmax temperature for the 2D modes (stability)
    # carrysource: dedicated bias on the z_last slot (large => carry-last at init).
    loop_attnres_carry_bias_init: float = 6.0
    # carrysource: fold motion (delta = state - its value one iteration earlier) into the
    # KEYS only (values stay raw states). Tests whether trajectory motion improves source
    # selection.
    loop_attnres_dkey: bool = False
    # Random-depth training (depthdrop): comma-separated depths, e.g. "6,9,12" (empty =
    # off). Each TRAIN forward samples the loop depth (both warmup L_cycles and grad
    # n_backwards_L) uniformly from the list. Eval is unaffected (uses the configured /
    # scanned depth). Directly trains deep-eval stability. A str (not List) so it survives
    # the ArchConfig passthrough + yaml config dump (an OmegaConf ListConfig does not).
    loop_depthdrop: str = ""
    # Same menu, but sampled for the GRADED cycle. loop_depthdrop only randomizes the
    # no-grad warmup, so beta (whose only gradient comes from the graded cycle) never
    # sees a horizon other than n_backwards_L — which is why the beta attractor is
    # insensitive to it. This one varies the horizon beta actually learns from, at the
    # cost of BPTT memory scaling with the deepest menu entry.
    loop_depthdrop_grad: str = ""
    # Learnable recency bias init. 0.0 = paper-faithful uniform average at init.
    # >0 (e.g. 4.0) => softmax starts ~one-hot on the most-recent source, i.e. the
    # model equals the carry-last baseline at init, then learns to attend to
    # distant loop states. Fixes the uniform-average init mismatch on this substrate.
    loop_attnres_recency_init: float = 0.0
