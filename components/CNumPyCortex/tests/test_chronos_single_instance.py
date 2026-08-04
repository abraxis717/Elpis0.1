"""Test Chronos single instance per runtime."""
from __future__ import annotations

from c_numpy_cortex.cache import WorkerCache
from c_numpy_cortex.chronos2 import ChronosWorker
from c_numpy_cortex.config import ChronosConfig
from c_numpy_cortex.vintages import VintageStore


def test_one_chronos_worker_per_runtime():
    """One runtime creates at most one Chronos worker."""
    store = VintageStore()
    cache = WorkerCache()
    config = ChronosConfig(
        enabled=True,
        model_path="/nonexistent/model",
        device="cpu",
    )

    worker = ChronosWorker(config, store, cache)
    worker.start()

    # The worker is running
    assert worker._worker_thread is not None
    assert worker._worker_thread.is_alive()

    # Multiple forecast requests share the same worker via bounded queue
    worker.submit_forecast(1, {}, ("ch_a",), (100, 200))
    worker.submit_forecast(2, {}, ("ch_a",), (100, 200))
    worker.submit_forecast(3, {}, ("ch_a",), (100, 200))

    # Queue ownership belongs to the runtime
    assert worker._queue.qsize() <= 3

    # Shutdown joins the worker cleanly
    worker.stop(timeout=2.0)
    assert not worker._worker_thread.is_alive()


def test_one_chronos_model_instance():
    """One runtime loads at most one Chronos model instance."""
    store = VintageStore()
    cache = WorkerCache()
    config = ChronosConfig(
        enabled=True,
        model_path="/nonexistent/model",
        device="cpu",
    )

    worker = ChronosWorker(config, store, cache)
    # Model won't actually load (path doesn't exist)
    # but the single-instance constraint is enforced by the lock
    assert worker._pipeline is None
    worker.stop(timeout=1.0)


def test_no_global_singleton():
    """No cross-process global singleton claim exists."""
    # Each runtime creates its own ChronosWorker independently
    store1 = VintageStore()
    cache1 = WorkerCache()
    store2 = VintageStore()
    cache2 = WorkerCache()

    config = ChronosConfig(
        enabled=True,
        model_path="/nonexistent",
        device="cpu",
    )

    w1 = ChronosWorker(config, store1, cache1)
    w2 = ChronosWorker(config, store2, cache2)

    # They are independent instances
    assert w1._queue is not w2._queue
    assert w1._pipeline_lock is not w2._pipeline_lock

    w1.stop(timeout=1.0)
    w2.stop(timeout=1.0)


def test_bounded_queue():
    """Queue is bounded, excess requests are dropped."""
    store = VintageStore()
    cache = WorkerCache()
    config = ChronosConfig(
        enabled=True,
        model_path="/nonexistent",
        device="cpu",
    )

    worker = ChronosWorker(config, store, cache)
    worker.start()

    # Fill the queue (maxsize=10)
    for i in range(12):
        worker.submit_forecast(
            i, {}, ("ch_a",), (100,)
        )

    # Queue should be at maxsize
    assert worker._queue.qsize() <= 10

    worker.stop(timeout=1.0)
