"""Meaningful append/rollback faults and abrupt child-process termination."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys

import pytest

from elpis_ecs.errors import EcsError, PersistenceError
from elpis_ecs.kernel import Kernel
from elpis_ecs.persistence import AppendRolledBackError
from test_integration_hardening import setup

RUNTIME = str(Path(__file__).resolve().parents[1] / "runtime")


def child_env(**values):
    return dict(os.environ, PYTHONPATH=RUNTIME, **values)


@pytest.mark.parametrize("fault", ["zero", "partial_zero", "write_error", "partial_error", "fsync_once", "eintr", "short"])
def test_append_io_matrix(tmp_path, monkeypatch, fault):
    with Kernel(str(tmp_path)) as k:
        a, b = setup(k)
        before, size = k.snapshot(), Path(k.log_path).stat().st_size
        write, sync = os.write, os.fsync
        calls = 0
        def injected_write(fd, data):
            nonlocal calls
            calls += 1
            if fault == "eintr" and calls == 1:
                raise InterruptedError()
            if fault == "short":
                return write(fd, data[:7])
            if fault.startswith("partial") and calls == 1:
                return write(fd, data[:13])
            if fault in {"zero", "partial_zero"}:
                return 0
            if fault in {"write_error", "partial_error"}:
                raise OSError("injected write failure")
            return write(fd, data)
        sync_calls = 0
        def injected_sync(fd):
            nonlocal sync_calls
            sync_calls += 1
            if fault == "fsync_once" and sync_calls == 1:
                raise OSError("injected fsync failure")
            return sync(fd)
        with monkeypatch.context() as m:
            m.setattr(os, "write", injected_write)
            m.setattr(os, "fsync", injected_sync)
            if fault in {"short", "eintr"}:
                k.entity_port(a).propose(b, b"durable")
                assert k.mailbox_size(b) == 1
            else:
                with pytest.raises(AppendRolledBackError):
                    k.entity_port(a).propose(b, b"rejected")
                assert k.snapshot() == before
                assert Path(k.log_path).stat().st_size == size
        k.entity_port(a).propose(b, b"after-fault")
        root = k.state_root_digest()
    with Kernel(str(tmp_path)) as k:
        assert k.state_root_digest() == root


@pytest.mark.parametrize("failure", ["rollback_truncate", "rollback_sync", "install"])
def test_indeterminate_failure_invalidates_until_recovery(tmp_path, monkeypatch, failure):
    with Kernel(str(tmp_path)) as k:
        a, b = setup(k)
        port = k.entity_port(a)
        pre = k.state_root_digest()
        def fail(*args):
            raise OSError("injected failure")
        with monkeypatch.context() as m:
            if failure == "rollback_truncate":
                m.setattr(os, "fsync", fail)
                m.setattr(os, "ftruncate", fail)
            elif failure == "rollback_sync":
                m.setattr(os, "fsync", fail)
            else:
                m.setattr(k, "_install", fail)
            with pytest.raises((OSError, PersistenceError)):
                port.propose(b, b"uncertain")
        for read in [k.events, k.snapshot, k.state_root_digest]:
            with pytest.raises(EcsError):
                read()
        k.open()
        assert k.mailbox_size(b) == (0 if failure == "rollback_sync" else 1)
        if failure == "rollback_sync":
            assert k.state_root_digest() == pre
        with pytest.raises(EcsError):
            port.propose(b, b"stale")
        k.entity_port(a).propose(b, b"after-recovery")


@pytest.mark.parametrize("operation", ["found", "lifecycle", "enqueue", "process"])
@pytest.mark.parametrize("boundary", ["before", "header1", "header7", "header8", "partial", "complete", "before_fsync", "after_fsync", "install", "returned"])
def test_real_process_crash_prefix(tmp_path, operation, boundary):
    original = tmp_path / "base"
    with Kernel(str(original)) as k:
        a, b = setup(k)
        if operation == "process":
            k.entity_port(a).propose(b, b"process-me")
        before = k.snapshot()
    expected = tmp_path / "expected"
    shutil.copytree(original, expected)
    with Kernel(str(expected)) as k:
        perform(k, operation, a, b)
        after = k.snapshot()
    script = r'''
import os, sys
from elpis_ecs.kernel import Kernel
k = Kernel(sys.argv[1]).open()
operation, boundary, a, b = sys.argv[2:]
write, sync = os.write, os.fsync
fd = k._log._fd

def die():
    os._exit(77)

def crash_write(target, data):
    if target == fd:
        if boundary == 'before': die()
        cuts = {'header1': 1, 'header7': 7, 'header8': 8, 'partial': len(data)//2, 'complete': len(data)}
        if boundary in cuts:
            # Ensure exactly the selected prefix is in the OS before abrupt exit.
            view = memoryview(data)[:cuts[boundary]]
            while view:
                view = view[write(target, view):]
            die()
    return write(target, data)

def crash_sync(target):
    if target == fd and boundary == 'before_fsync': die()
    sync(target)
    if target == fd and boundary == 'after_fsync': die()

os.write, os.fsync = crash_write, crash_sync
if boundary == 'install': k._install = lambda state: die()
if operation == 'found': k.found_entity('new')
elif operation == 'lifecycle': k.dormant(a)
elif operation == 'enqueue': k.entity_port(a).propose(b, b'new')
elif operation == 'process': k.step()
if boundary == 'returned': die()
raise AssertionError('crash point was not reached')
'''
    result = subprocess.run([sys.executable, "-c", script, str(original), operation, boundary, a, b],
                            env=child_env(), capture_output=True, text=True, timeout=20)
    assert result.returncode == 77, result.stderr
    want = before if boundary in {"before", "header1", "header7", "header8", "partial"} else after
    with Kernel(str(original)) as k:
        assert k.snapshot() == want
        k.found_entity("clean-append-after-crash")
        resumed = k.snapshot()
    with Kernel(str(original)) as k:
        assert k.snapshot() == resumed


def perform(k, operation, a, b):
    if operation == "found":
        k.found_entity("new")
    elif operation == "lifecycle":
        k.dormant(a)
    elif operation == "enqueue":
        k.entity_port(a).propose(b, b"new")
    else:
        k.step()


@pytest.mark.parametrize("boundary", ["write", "fsync", "replace", "directory_sync"])
def test_checkpoint_failure_keeps_history_authoritative(tmp_path, monkeypatch, boundary):
    with Kernel(str(tmp_path)) as k:
        a, b = setup(k)
        k.checkpoint()
        k.entity_port(a).propose(b, b"tail")
        root, data = k.state_root_digest(), Path(k.log_path).read_bytes()
        def fail(*args):
            raise OSError("injected checkpoint failure")
        with monkeypatch.context() as m:
            if boundary == "directory_sync":
                m.setattr("elpis_ecs.persistence._sync_directory", fail)
            else:
                m.setattr(os, {"write": "write", "fsync": "fsync", "replace": "replace"}[boundary], fail)
            with pytest.raises((OSError, PersistenceError)):
                k.checkpoint()
        assert k.state_root_digest() == root
        assert Path(k.log_path).read_bytes() == data
    with Kernel(str(tmp_path)) as k:
        assert k.state_root_digest() == root


def test_directory_sync_failure_releases_owner(tmp_path, monkeypatch):
    def fail(path):
        raise OSError("directory fsync failed")
    k = Kernel(str(tmp_path))
    with monkeypatch.context() as m:
        m.setattr("elpis_ecs.persistence._sync_directory", fail)
        with pytest.raises(OSError):
            k.open()
    assert k._log._fd is None
    with Kernel(str(tmp_path)) as recovered:
        recovered.found_entity("works")


def test_fsync_eintr_retry(tmp_path, monkeypatch):
    with Kernel(str(tmp_path)) as k:
        sync, called = os.fsync, False
        def interrupted(fd):
            nonlocal called
            if not called:
                called = True
                raise InterruptedError()
            return sync(fd)
        monkeypatch.setattr(os, "fsync", interrupted)
        k.found_entity("a")
        root = k.state_root_digest()
    with Kernel(str(tmp_path)) as k:
        assert k.state_root_digest() == root


@pytest.mark.parametrize("fault", ["short", "eintr", "zero"])
def test_read_fault_never_misclassifies_valid_frames(tmp_path, monkeypatch, fault):
    with Kernel(str(tmp_path)) as k:
        k.found_entity("a")
        root = k.state_root_digest()
    path = tmp_path / "events.log"
    before = path.read_bytes()
    original, calls = os.pread, 0
    def injected(fd, count, offset):
        nonlocal calls
        calls += 1
        if fault == "zero":
            return b""
        if fault == "eintr" and calls == 1:
            raise InterruptedError()
        return original(fd, min(count, 3) if fault == "short" else count, offset)
    with monkeypatch.context() as m:
        m.setattr(os, "pread", injected)
        if fault == "zero":
            with pytest.raises(EcsError):
                Kernel(str(tmp_path)).open()
        else:
            with Kernel(str(tmp_path)) as k:
                assert k.state_root_digest() == root
    assert path.read_bytes() == before


def test_close_error_still_invalidates_projection_and_ports(tmp_path, monkeypatch):
    with Kernel(str(tmp_path)) as k:
        a, b = setup(k)
        port = k.entity_port(a)
        close = os.close
        fd = k._log._fd
        def fail_after_close(target):
            close(target)
            if target == fd:
                raise OSError("injected close failure")
        with monkeypatch.context() as m:
            m.setattr(os, "close", fail_after_close)
            with pytest.raises(OSError):
                k.close()
        with pytest.raises(EcsError):
            k.snapshot()
        with pytest.raises(EcsError):
            port.propose(b, b"stale")
        k.open()
        assert k.mailbox_size(b) == 0


def test_live_log_corruption_invalidates_kernel(tmp_path):
    with Kernel(str(tmp_path)) as k:
        k.found_entity("a")
        # Uncooperative file writes are outside the ownership model. If an
        # inspection detects one, it must still close rather than continue.
        with Path(k.log_path).open("ab") as stream:
            stream.write(b"junk")
        with pytest.raises(EcsError):
            k.events()
        with pytest.raises(EcsError):
            k.snapshot()


def test_unexpected_file_length_prevents_successful_mutation(tmp_path):
    with Kernel(str(tmp_path)) as k:
        k.found_entity("a")
        with Path(k.log_path).open("ab") as stream:
            stream.write(b"\0")
        with pytest.raises(EcsError):
            k.found_entity("must-not-succeed")
        with pytest.raises(EcsError):
            k.snapshot()
    with Kernel(str(tmp_path)) as k:
        assert len(k.events()) == 1
