"""C2R6-P0 deterministic Semantic-IR -> Grid81 projector package.

Importing this package installs the pinned authority overlay (see
_bootstrap) before any projector module loads its authority imports.
"""
from __future__ import annotations

from . import _bootstrap

_bootstrap.install()
