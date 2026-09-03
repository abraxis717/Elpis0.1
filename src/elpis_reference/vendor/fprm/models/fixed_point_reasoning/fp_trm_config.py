# Config for the official released FP-TRM single-z model (fp_trm_singlez.py).
# It shares the fixed-point config surface with FPRMConfig, but reads a few fields
# our config doesn't declare (n_decode_steps, scale_init, ...). extra='allow' keeps
# every field from the checkpoint's all_config so attribute access never misses.
from pydantic import ConfigDict

from .fprm_config import FPRMConfig


class FPTRMConfig(FPRMConfig):
    model_config = ConfigDict(extra="allow")

    n_decode_steps: int = 0
    scale_init: float = 1.0
