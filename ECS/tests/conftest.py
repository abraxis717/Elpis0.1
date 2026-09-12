"""Bootstrap sys.path for the Elpis ECS M1A test suite.

The kernel lives at ECS/runtime/elpis_ecs. This conftest adds ECS/runtime to
sys.path so tests can `import elpis_ecs` without installation.
"""

from __future__ import annotations

import os
import sys

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_RUNTIME_DIR = os.path.join(os.path.dirname(_TESTS_DIR), "runtime")
if _RUNTIME_DIR not in sys.path:
    sys.path.insert(0, _RUNTIME_DIR)
