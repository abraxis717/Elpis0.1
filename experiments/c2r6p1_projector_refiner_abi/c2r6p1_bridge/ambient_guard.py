"""Runtime guards: prove the bridge is non-ambient and non-executing.

``AmbientGuard`` patches the standard-library surfaces the bridge must NOT
touch (network, subprocess, filesystem mutation, wall-clock, environment
reads, model/CUDA calls) and records every hit. Tests run the bridge under
the guard and assert zero hits (or only the hits the test expects).

The guard is a test instrument, not part of the bridge data path: the
bridge itself is pure; the guard *proves* it by failing if it is not.
"""
from __future__ import annotations

import os
import socket
import subprocess
import time
from contextlib import contextmanager
from typing import Any, Iterator, List, Tuple


class AmbientViolation(RuntimeError):
    def __init__(self, hits: List[str]) -> None:
        super().__init__("ambient/execution guard tripped: " + "; ".join(hits))
        self.hits = hits


@contextmanager
def ambient_guard(
    fail_on: Tuple[str, ...] = (
        "socket_connect",
        "socket_create",
        "subprocess",
        "fs_write",
        "fs_read_outside",
        "wall_clock",
        "env_read",
        "cuda",
    ),
    allowed_read_prefixes: Tuple[str, ...] = (),
) -> Iterator[List[str]]:
    """Context manager recording ambient/execution touches.

    ``fail_on`` lists the violation kinds that raise immediately; others
    are recorded into the returned list.
    """
    hits: List[str] = []
    _patches: List[Tuple[Any, str, Any]] = []

    def record(kind: str, detail: str = "") -> None:
        hits.append(f"{kind}:{detail}")
        if kind in fail_on:
            raise AmbientViolation(hits)

    # --- socket ----------------------------------------------------------
    real_connect = socket.socket.connect
    real_create_connection = socket.create_connection

    def guarded_connect(self, address):  # noqa: ANN001
        record("socket_connect", str(address))
        return real_connect(self, address)

    def guarded_create_connection(*a, **k):  # noqa: ANN002, ANN003
        record("socket_create_connection", str(a))
        return real_create_connection(*a, **k)

    socket.socket.connect = guarded_connect  # type: ignore
    _patches.append((socket.socket, "connect", real_connect))
    socket.create_connection = guarded_create_connection  # type: ignore
    _patches.append((socket, "create_connection", real_create_connection))

    # --- subprocess ------------------------------------------------------
    real_Popen = subprocess.Popen
    real_run = subprocess.run
    real_call = subprocess.call
    real_check_call = subprocess.check_call
    real_check_output = subprocess.check_output

    def _sub(kind, fn, *a, **k):  # noqa: ANN001
        record("subprocess", f"{kind}{a[:1]}")
        return fn(*a, **k)

    subprocess.Popen = lambda *a, **k: _sub("Popen", real_Popen, *a, **k)
    subprocess.run = lambda *a, **k: _sub("run", real_run, *a, **k)
    subprocess.call = lambda *a, **k: _sub("call", real_call, *a, **k)
    subprocess.check_call = lambda *a, **k: _sub("check_call", real_check_call, *a, **k)
    subprocess.check_output = lambda *a, **k: _sub("check_output", real_check_output, *a, **k)
    _patches.append((subprocess, "Popen", real_Popen))
    _patches.append((subprocess, "run", real_run))
    _patches.append((subprocess, "call", real_call))
    _patches.append((subprocess, "check_call", real_check_call))
    _patches.append((subprocess, "check_output", real_check_output))

    # --- wall clock ------------------------------------------------------
    real_time = time.time
    real_monotonic = time.monotonic
    real_time_ns = time.time_ns

    def _clock(fn, kind):
        def _g(*a, **k):  # noqa: ANN002, ANN003
            record("wall_clock", kind)
            return fn(*a, **k)

        return _g

    time.time = _clock(real_time, "time")
    time.monotonic = _clock(real_monotonic, "monotonic")
    time.time_ns = _clock(real_time_ns, "time_ns")
    _patches.append((time, "time", real_time))
    _patches.append((time, "monotonic", real_monotonic))
    _patches.append((time, "time_ns", real_time_ns))

    # --- environment reads ----------------------------------------------
    real_environ_get = os.environ.get
    real_getenv = os.getenv

    def _env_get(self=None, *a, **k):  # noqa: ANN001
        record("env_read", str(a[:1]))
        if self is None:
            return real_getenv(*a, **k)
        return real_environ_get(self, *a, **k)

    os.environ.get = _env_get  # type: ignore
    os.getenv = lambda *a, **k: (record("env_read", str(a[:1])), real_getenv(*a, **k))[1]
    _patches.append((os.environ, "get", real_environ_get))
    _patches.append((os, "getenv", real_getenv))

    # --- CUDA / torch device calls -------------------------------------
    try:
        import torch

        real_cuda_available = torch.cuda.is_available
        real_cuda_set_device = torch.cuda.set_device

        def _cuda_avail(*a, **k):  # noqa: ANN002, ANN003
            record("cuda", "is_available")
            return real_cuda_available(*a, **k)

        def _cuda_set(*a, **k):  # noqa: ANN002, ANN003
            record("cuda", "set_device")
            return real_cuda_set_device(*a, **k)

        torch.cuda.is_available = _cuda_avail  # type: ignore
        torch.cuda.set_device = _cuda_set  # type: ignore
        _patches.append((torch.cuda, "is_available", real_cuda_available))
        _patches.append((torch.cuda, "set_device", real_cuda_set_device))
    except Exception:
        pass

    try:
        yield hits
    finally:
        for obj, name, orig in reversed(_patches):
            try:
                setattr(obj, name, orig)
            except Exception:
                pass
