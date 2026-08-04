import numpy as np
import pytest

from elpis_nanbeige42_host.control_realization import (
    control_code,
    exact_logit_realization,
    hidden_realization,
    seam_ulp_profile,
)
from elpis_nanbeige42_host.errors import ControlShapeMismatch
from elpis_nanbeige42_host.runtime_manifest import SeamULPThresholds


def test_control_realization_shapes():
    code = control_code(1.0, [0.0] * 21)
    hidden = np.zeros((3072, 22), dtype=np.float32)
    hidden[:, 0] = 1.0
    logits = np.zeros((17, 22), dtype=np.float32)
    logits[:, 0] = 2.0
    assert hidden_realization(hidden, code, 0.5).shape == (3072,)
    assert exact_logit_realization(logits, code, 0.5).shape == (17,)


def test_control_code_rejects_wrong_width():
    with pytest.raises(ControlShapeMismatch):
        control_code(0.0, [0.0] * 20)


def test_ulp_profile_is_directional_and_qualified():
    intended = np.ones(100, dtype=np.float32)
    realized = np.ones(100, dtype=np.float32) * 0.99
    spacing = np.ones(100, dtype=np.float32) * 0.1
    profile = seam_ulp_profile(
        intended_vectors=[intended],
        realized_vectors=[realized],
        ulp_vectors=[spacing],
        thresholds=SeamULPThresholds(),
    )
    assert profile.qualified
    assert profile.median_abs_residual_over_ulp == pytest.approx(10.0)
