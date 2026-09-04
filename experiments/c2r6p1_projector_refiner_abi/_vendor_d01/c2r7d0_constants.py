"""C2R7-D0 constants: donor identities, donor tensor map, architecture invariants.

All identities are verified at runtime by the test suite; this file is the
single normative record for the milestone.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Tuple

# ----------------------------------------------------------------------
# Donor package identities (verified against the on-disk package)
# ----------------------------------------------------------------------

DONOR_ROOT = Path(
    "/mnt/primesauce/models/TRM/01_Sudoku_TRM_MLP_Blackhao_50K"
)
DONOR_CHECKPOINT_PATH = DONOR_ROOT / "checkpoint" / "weights.pt"
DONOR_CHECKPOINT_SHA256 = (
    "7c5c57428e1bd837dee931bbf669198a25014af409d721b9cfed9d774ea3abfd"
)
DONOR_SOURCE_TRM_SHA256 = (
    "bb2b59249939816127cd69c636cdb92194bc7e10aee49613cacf63c2d3319337"
)
DONOR_CONFIG_SHA256 = (
    "df07ec7dc069012f2f09eecaa4b4161a496fb801d98259327037966e15c08078"
)
SECONDARY_CHECKPOINT_PATH = Path(
    "/mnt/primesauce/models/TRM/"
    "02_Sudoku_TRM_MLP_AlphaXiv_50K/checkpoint/step_32550_sudoku_epoch50k.pt"
)
SECONDARY_CHECKPOINT_SHA256 = (
    "5a5e37d7b1a8d16a9c9f24961ac7cfd83c7c58ecd62fdfbacf968f71ea91ea4e"
)

UPSTREAM_REPO = "SamsungSAILMontreal/TinyRecursiveModels"
UPSTREAM_PIN = "c01103738605ba39d1430519b1ee0c62f4c707f8"

# ----------------------------------------------------------------------
# C2R7-C authority (structural ABI)
# ----------------------------------------------------------------------

FEATURE_ABI_SHA256 = (
    "dff5506be69bec65e121778274ea59c9900d843c334588bc72854f40c98a94d0"
)
FEATURE_WIDTH = 529  # declared features = 529 bits, active residual = 529 bits

# The 415-row file D0 mislabeled as the historical C2R7-C training corpus.
# C2R7-D0.1: this is the LEGACY identity (a 3-case truncated corpus),
# superseded by the canonical 952d identity below (see
# corpus_reconciliation.py). Kept for historical evidence only.
HISTORICAL_CORPUS_PATH = Path(
    "/mnt/primesauce/Elpis0.1/work/"
    "C2R7C_TRM0_GENERALIZATION_R0_1/artifacts/C2R7C_TRM0_TRAIN.jsonl"
)
HISTORICAL_CORPUS_SHA256 = (
    "e898f4f0d8f7558eeaa5fbc3208681daff9852e73a2a933141e6d63e498199f9"
)
HISTORICAL_CORPUS_ROWS = 415

# ----------------------------------------------------------------------
# Recursive core architecture (must match the Blackhao checkpoint exactly)
# ----------------------------------------------------------------------

HIDDEN_SIZE = 512
EXPANSION = 4
L_LAYERS = 2
H_CYCLES = 3
L_CYCLES = 6
SEQ_LEN_GRID = 81
PREFIX_LEN = 16
SEQ_LEN_TOTAL = 97  # 16 prefix + 81 grid positions
RMS_NORM_EPS = 1e-5

TOKEN_VOCAB = 10  # BasisToken 0..9 (Grid81-specific adapter, not Sudoku's 11)
MASK_VOCAB = 2

# ----------------------------------------------------------------------
# Donor tensor map
# ----------------------------------------------------------------------
# The checkpoint stores keys under the `_orig_mod.model.inner.` prefix
# (torch.compile artifact of the donor's training wrapper).

_DONOR_PREFIX = "_orig_mod.model.inner."

# Native core attribute name -> donor checkpoint key (no prefix stripping
# ambiguity: exact donor keys are listed here).
TRANSFER_KEY_MAP: Dict[str, str] = {
    "H_init": _DONOR_PREFIX + "H_init",
    "L_init": _DONOR_PREFIX + "L_init",
    "L_level.layers.0.mlp_t.gate_up_proj.weight": (
        _DONOR_PREFIX
        + "L_level.layers.0.mlp_t.gate_up_proj.weight"
    ),
    "L_level.layers.0.mlp_t.down_proj.weight": (
        _DONOR_PREFIX + "L_level.layers.0.mlp_t.down_proj.weight"
    ),
    "L_level.layers.0.mlp.gate_up_proj.weight": (
        _DONOR_PREFIX + "L_level.layers.0.mlp.gate_up_proj.weight"
    ),
    "L_level.layers.0.mlp.down_proj.weight": (
        _DONOR_PREFIX + "L_level.layers.0.mlp.down_proj.weight"
    ),
    "L_level.layers.1.mlp_t.gate_up_proj.weight": (
        _DONOR_PREFIX + "L_level.layers.1.mlp_t.gate_up_proj.weight"
    ),
    "L_level.layers.1.mlp_t.down_proj.weight": (
        _DONOR_PREFIX + "L_level.layers.1.mlp_t.down_proj.weight"
    ),
    "L_level.layers.1.mlp.gate_up_proj.weight": (
        _DONOR_PREFIX + "L_level.layers.1.mlp.gate_up_proj.weight"
    ),
    "L_level.layers.1.mlp.down_proj.weight": (
        _DONOR_PREFIX + "L_level.layers.1.mlp.down_proj.weight"
    ),
}

# Task-facing donor tensors that MUST NOT be transferred.
SKIPPED_TASK_FACING_KEYS: Tuple[str, ...] = (
    _DONOR_PREFIX + "embed_tokens.embedding_weight",
    _DONOR_PREFIX + "lm_head.weight",
    _DONOR_PREFIX + "q_head.weight",
    _DONOR_PREFIX + "q_head.bias",
    _DONOR_PREFIX + "puzzle_emb.weights",
)

EXPECTED_DONOR_TENSOR_COUNT = 15
EXPECTED_DONOR_ELEMENT_COUNT = 5030402
EXPECTED_TRANSFER_TENSOR_COUNT = 10
EXPECTED_TRANSFER_ELEMENT_COUNT = 5017600

# ----------------------------------------------------------------------
# Deterministic prefix packing rule (documented, fixed scaling)
# C2R7-D0.1 LOSSLESS RULE (replaces the D0 OR-fold, which aliased bits
# 512..528 onto channels 0..16 of the same position):
#
#   position 0 (PREFIX_DECLARED_LO):   declared bits 0..511   -> ch 0..511
#   position 1 (PREFIX_DECLARED_HI):   declared bits 512..528 -> ch 0..16
#                                       channels 17..511 = 0
#   position 2 (PREFIX_RESIDUAL_LO):   active bits 0..511   -> ch 0..511
#   position 3 (PREFIX_RESIDUAL_HI):   active bits 512..528 -> ch 0..16
#                                       channels 17..511 = 0
#   positions 4..15: zero (reserved)
#
# Direct index copy per slot, fixed scaling 1.0. No learned projection,
# no hashing, no folding, no OR collisions. Injective: the 529 declared
# one-hot vectors map to 529 unique position-0/1 patterns and the 529
# active one-hot vectors to 529 unique position-2/3 patterns.
PREFIX_DECLARED_LO = 0
PREFIX_DECLARED_HI = 1
PREFIX_RESIDUAL_LO = 2
PREFIX_RESIDUAL_HI = 3
PREFIX_RESERVED_POS = tuple(range(4, PREFIX_LEN))
# Back-compat aliases used by D0-era consumers/tests.
PREFIX_DECLARED_POS = PREFIX_DECLARED_LO
PREFIX_RESIDUAL_POS = PREFIX_RESIDUAL_LO
PREFIX_SCALE = 1.0
# Number of channels the HI slots use (bits 512..528).
OVERFLOW_BITS = FEATURE_WIDTH - HIDDEN_SIZE  # 17

# ----------------------------------------------------------------------
# Canonical corpus identity (C2R7-D0.1 identity repair)
# ----------------------------------------------------------------------
# The D0 sanity probe mislabeled a 415-row file (SHA e898f4f0..., a
# 3-case truncated corpus) as the historical training corpus. The
# canonical C2R7-C training identity, reproduced exactly from the C2R7-C
# authority generator (structural_trm_dataset.py --cases 12 --budget 250
# --seed 20260826), is:
#   raw teacher export:        416 rows, SHA c4095811...
#   canonical dedup (first-wins): 415 rows, SHA 952d3bff...
# e898f4f0 is a CONTENT_DIFFERENCE (not relabeled canonical).
RAW_CORPUS_SHA256 = (
    "c4095811ff39dec1cd63f59d023215d0cf62ebe2de342bc5bde0f240dffbecd8"
)
RAW_CORPUS_ROWS = 416
CANONICAL_CORPUS_SHA256 = (
    "952d3bff676fd4c74f0bb1684ec23e70f261025d8ffb9adca59cf3a7850f1230"
)
CANONICAL_CORPUS_ROWS = 415
LEGACY_E898_CORPUS_SHA256 = HISTORICAL_CORPUS_SHA256


def feature_abi_digest() -> str:
    """Recompute the C2R7-C feature ABI digest from its normative source."""
    source = (
        Path(__file__).resolve().parents[1]
        / "c2r7c_semantic_structural_probe"
        / "structural_trm_features.py"
    )
    return hashlib.sha256(source.read_bytes()).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
