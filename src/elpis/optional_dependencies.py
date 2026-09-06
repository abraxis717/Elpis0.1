"""Explicit, local entry to the optional learned runtime."""
from importlib import import_module


def require_torch():
    try:
        return import_module('torch')
    except ModuleNotFoundError as exc:
        if exc.name != 'torch':
            raise
        raise ModuleNotFoundError(
            "This operation requires the optional TRM runtime: install elpis[trm]",
            name='torch',
        ) from exc
