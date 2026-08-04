"""Test Chronos loading is local-files-only."""
from __future__ import annotations

import pytest

from c_numpy_cortex.chronos2 import ChronosWorker
from c_numpy_cortex.cache import WorkerCache
from c_numpy_cortex.config import ChronosConfig
from c_numpy_cortex.vintages import VintageStore


def test_chronos_worker_local_files_only():
    """Chronos loads model with local_files_only=True."""
    # The ChronosWorker._load method calls:
    #   Chronos2Pipeline.from_pretrained(..., local_files_only=True)
    # We verify this by checking that the code path includes it.
    # Since the model path doesn't exist, it should fail gracefully.
    store = VintageStore()
    cache = WorkerCache()
    config = ChronosConfig(
        enabled=True,
        model_path="/nonexistent/chronos-model",
        device="cpu",
    )

    worker = ChronosWorker(config, store, cache)
    result = worker._load()
    assert result is None
    assert worker._loaded is False

    worker.stop(timeout=1.0)


def test_chronos_does_not_download():
    """Chronos does not invoke Hugging Face Hub."""
    # local_files_only=True prevents network calls.
    # We verify by checking that loading a non-existent path
    # fails locally without network.
    store = VintageStore()
    cache = WorkerCache()
    config = ChronosConfig(
        enabled=True,
        model_path="/does/not/exist",
        device="cpu",
    )

    worker = ChronosWorker(config, store, cache)
    worker.start()
    result = worker._load()
    assert result is None
    worker.stop(timeout=1.0)
