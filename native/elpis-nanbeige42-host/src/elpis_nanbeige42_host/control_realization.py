"""Frozen 22-D hidden and exact post-logit realization primitives."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Sequence

import numpy as np

from .errors import ControlShapeMismatch
from .runtime_manifest import SeamULPProfile, SeamULPThresholds, qualify_ulp


def control_code(common: float, structural: Sequence[float]) -> np.ndarray:
    residual = np.asarray(tuple(structural), dtype=np.float32).reshape(-1)
    if residual.shape != (21,):
        raise ControlShapeMismatch(f"expected 21 structural coordinates, got {residual.shape}")
    code = np.concatenate((np.asarray([common], dtype=np.float32), residual))
    if not np.isfinite(code).all():
        raise ControlShapeMismatch("non-finite control code")
    return code


def hidden_realization(hidden_basis: Any, code: Any, gain: float) -> np.ndarray:
    basis = np.asarray(hidden_basis, dtype=np.float32)
    vector = np.asarray(code, dtype=np.float32).reshape(-1)
    if basis.shape != (3072, 22) or vector.shape != (22,):
        raise ControlShapeMismatch(f"hidden realization shape drift: {basis.shape}, {vector.shape}")
    result = (basis @ vector) * np.float32(gain)
    if result.shape != (3072,) or not np.isfinite(result).all():
        raise ControlShapeMismatch("invalid hidden realization")
    return result.astype(np.float32)


def exact_logit_realization(logit_basis: Any, code: Any, gain: float) -> np.ndarray:
    basis = np.asarray(logit_basis, dtype=np.float32)
    vector = np.asarray(code, dtype=np.float32).reshape(-1)
    if basis.ndim != 2 or basis.shape[1] != 22 or vector.shape != (22,):
        raise ControlShapeMismatch(f"post-logit realization shape drift: {basis.shape}, {vector.shape}")
    result = (basis @ vector) * np.float32(gain)
    if not np.isfinite(result).all():
        raise ControlShapeMismatch("invalid exact post-logit realization")
    return result.astype(np.float32)


def _safe_cosine(left: np.ndarray, right: np.ndarray) -> float:
    a = np.asarray(left, dtype=np.float64).reshape(-1)
    b = np.asarray(right, dtype=np.float64).reshape(-1)
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denominator) if denominator > 1e-30 else 0.0


def seam_ulp_profile(
    *,
    intended_vectors: Sequence[np.ndarray],
    realized_vectors: Sequence[np.ndarray],
    ulp_vectors: Sequence[np.ndarray],
    thresholds: SeamULPThresholds,
) -> SeamULPProfile:
    intended = np.concatenate([np.asarray(v, dtype=np.float64).reshape(-1) for v in intended_vectors])
    realized = np.concatenate([np.asarray(v, dtype=np.float64).reshape(-1) for v in realized_vectors])
    ulp = np.concatenate([np.asarray(v, dtype=np.float64).reshape(-1) for v in ulp_vectors])
    valid = np.isfinite(intended) & np.isfinite(realized) & np.isfinite(ulp) & (ulp > 0)
    if not np.any(valid):
        raise ControlShapeMismatch("no valid seam ULP coordinates")
    intended = intended[valid]
    realized = realized[valid]
    ulp = ulp[valid]
    ratio = np.abs(intended) / ulp
    nonzero = np.abs(realized) > 0
    denominator = float(np.linalg.norm(intended))
    relative_l2 = float(np.linalg.norm(realized - intended) / denominator) if denominator > 1e-30 else 0.0
    metrics = {
        "p05_abs_residual_over_ulp": float(np.quantile(ratio, 0.05)),
        "median_abs_residual_over_ulp": float(np.median(ratio)),
        "realized_nonzero_fraction": float(np.mean(nonzero)),
        "realized_direction_cosine": _safe_cosine(realized, intended),
        "realized_relative_l2": relative_l2,
    }
    qualified = qualify_ulp(metrics, thresholds)
    return SeamULPProfile(
        count=int(ratio.size),
        p05_abs_residual_over_ulp=metrics["p05_abs_residual_over_ulp"],
        median_abs_residual_over_ulp=metrics["median_abs_residual_over_ulp"],
        fraction_below_half_ulp=float(np.mean(ratio < 0.5)),
        realized_nonzero_fraction=metrics["realized_nonzero_fraction"],
        realized_direction_cosine=metrics["realized_direction_cosine"],
        realized_relative_l2=metrics["realized_relative_l2"],
        qualified=qualified,
    )
