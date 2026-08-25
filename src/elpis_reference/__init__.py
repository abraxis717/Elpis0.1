"""Runnable public reference runtime for Elpis.

Platform/bootstrap helpers and semantic refinement contracts are importable
without importing learned-runtime dependencies. Existing public symbols remain
available through lazy attribute loading.
"""

from __future__ import annotations

from importlib import import_module


__all__ = [
    "MODEL_REPO",
    "MODEL_REVISION",
    "MODEL_SHA256",
    "RefinementResult",
    "RefinementStep",
    "solve_sudoku",
    "parse_puzzle",
    "validate",
]


_MODEL_NAMES = {
    "MODEL_REPO",
    "MODEL_REVISION",
    "MODEL_SHA256",
}

_REFINEMENT_NAMES = {
    "RefinementResult",
    "RefinementStep",
    "solve_sudoku",
}

_SUDOKU_NAMES = {
    "parse_puzzle",
    "validate",
}


def __getattr__(name: str):
    if name in _MODEL_NAMES:
        module = import_module(".model", __name__)
        return getattr(module, name)

    if name in _REFINEMENT_NAMES:
        module = import_module(".refinement", __name__)
        return getattr(module, name)

    if name in _SUDOKU_NAMES:
        module = import_module(".sudoku", __name__)
        return getattr(module, name)

    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )
