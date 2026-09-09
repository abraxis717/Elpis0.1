from __future__ import annotations

import asyncio
import errno
import ipaddress
import os
import shutil
import socket
import ssl
import subprocess
import threading
import traceback
from collections.abc import Sequence
from typing import Any

# Python-level instrumentation is defense-in-depth and audit telemetry only.
# Strong network isolation is established independently by the hosted OS witness.

_LOOPBACK_V4 = ipaddress.IPv4Network("127.0.0.0/8")
_LOOPBACK_V6_ADDR = ipaddress.IPv6Address("::1")
FORBIDDEN_DESTINATION_PORTS = frozenset({8080})

_audit_lock = threading.Lock()
_audit_log: list[dict[str, Any]] = []
_instrument_lock = threading.Lock()
_instrumented = False

_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex
_original_sendto = socket.socket.sendto
_original_sendmsg = getattr(socket.socket, "sendmsg", None)
_original_create_connection = socket.create_connection
_original_fromfd = socket.fromfd
_original_asyncio_open_connection = asyncio.open_connection
_original_ssl_connect = ssl.SSLSocket.connect
_original_ssl_connect_ex = ssl.SSLSocket.connect_ex
_original_ssl_wrap_socket = ssl.SSLContext.wrap_socket
_original_subprocess_run = subprocess.run


class AirgapViolationError(PermissionError):
    """Raised when Python-level network policy rejects an operation."""


class SubprocessPolicyError(PermissionError):
    """Raised when CNumPyCortex rejects a subprocess invocation."""


def _address_port(addr: object) -> int | None:
    if (
        isinstance(addr, tuple)
        and len(addr) >= 2
        and isinstance(addr[1], int)
    ):
        return addr[1]
    return None


def _is_allowed_destination(
    addr_family: int,
    addr: tuple,
) -> bool:
    """Return whether a destination is permitted by the Python defense layer."""
    port = _address_port(addr)
    if port in FORBIDDEN_DESTINATION_PORTS:
        return False

    if addr_family == socket.AF_INET:
        ip_str = addr[0]
        try:
            ip = ipaddress.IPv4Address(ip_str)
        except (TypeError, ValueError):
            return False
        return ip in _LOOPBACK_V4

    if addr_family == socket.AF_INET6:
        ip_str = addr[0]
        try:
            ip = ipaddress.IPv6Address(ip_str)
        except (TypeError, ValueError):
            return False
        return ip == _LOOPBACK_V6_ADDR

    # UNIX-domain sockets are local IPC, not network egress.
    if addr_family == socket.AF_UNIX:
        return True

    return False


def _audit_entry(
    operation: str,
    addr_family: int,
    addr: object,
    allowed: bool,
    stack_summary: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "operation": operation,
        "family": addr_family,
        "addr_family_name": {
            socket.AF_INET: "AF_INET",
            socket.AF_INET6: "AF_INET6",
            socket.AF_UNIX: "AF_UNIX",
        }.get(addr_family, f"AF_{addr_family}"),
        "address": str(addr),
        "allowed": allowed,
    }

    if stack_summary:
        entry["stack"] = stack_summary[:500]

    with _audit_lock:
        _audit_log.append(entry)

    return entry


def _get_stack_summary() -> str:
    lines = traceback.format_stack()
    return "".join(lines[-6:-1]) if len(lines) > 6 else "".join(lines)


def _reject_or_audit(
    operation: str,
    family: int,
    address: tuple,
    *,
    connect_ex: bool = False,
) -> int | None:
    allowed = _is_allowed_destination(family, address)
    _audit_entry(
        operation,
        family,
        address,
        allowed,
        _get_stack_summary(),
    )

    if allowed:
        return None

    if connect_ex:
        return errno.EACCES

    raise AirgapViolationError(
        f"Blocked {operation} to {address} (family={family}). "
        "Only permitted loopback destinations are allowed, and "
        "destination port 8080 is forbidden."
    )


def _guard_numeric_host(
    operation: str,
    host: object,
    port: object,
) -> tuple[int, tuple]:
    if not isinstance(port, int):
        raise AirgapViolationError(
            f"{operation} requires an explicit integer destination port"
        )

    try:
        ip = ipaddress.ip_address(host)
    except (TypeError, ValueError):
        _audit_entry(
            operation,
            socket.AF_INET,
            (host, port),
            False,
            "DNS hostname not permitted",
        )
        raise AirgapViolationError(
            f"DNS hostname blocked before resolution: {host}"
        )

    family = (
        socket.AF_INET
        if isinstance(ip, ipaddress.IPv4Address)
        else socket.AF_INET6
    )
    normalized = (str(ip), port)
    _reject_or_audit(operation, family, normalized)
    return family, normalized


def instrument_airgap() -> None:
    """Install process-global Python defense-in-depth socket instrumentation.

    This is not the OS security boundary. Strong airgap claims require the
    independent Linux network-isolation witness in hosted qualification.
    """
    global _instrumented

    with _instrument_lock:
        if _instrumented:
            return

        def _guarded_connect(self, address):
            family = self.family
            if family in (socket.AF_INET, socket.AF_INET6):
                _reject_or_audit("connect", family, address)
            return _original_connect(self, address)

        def _guarded_connect_ex(self, address, *args):
            family = self.family
            if family in (socket.AF_INET, socket.AF_INET6):
                denied = _reject_or_audit(
                    "connect_ex",
                    family,
                    address,
                    connect_ex=True,
                )
                if denied is not None:
                    return denied
            return _original_connect_ex(self, address, *args)

        def _guarded_sendto(self, data, *args):
            # sendto(data, address) or sendto(data, flags, address)
            if not args:
                raise TypeError("sendto requires a destination")
            address = args[-1]
            family = self.family
            if family in (socket.AF_INET, socket.AF_INET6):
                _reject_or_audit("sendto", family, address)
            return _original_sendto(self, data, *args)

        def _guarded_sendmsg(
            self,
            buffers,
            ancdata=(),
            flags=0,
            address=None,
        ):
            family = self.family
            if (
                address is not None
                and family in (socket.AF_INET, socket.AF_INET6)
            ):
                _reject_or_audit("sendmsg", family, address)

            if _original_sendmsg is None:
                raise AttributeError("socket.sendmsg is unavailable")

            if address is None:
                return _original_sendmsg(
                    self,
                    buffers,
                    ancdata,
                    flags,
                )
            return _original_sendmsg(
                self,
                buffers,
                ancdata,
                flags,
                address,
            )

        def _guarded_create_connection(address, *args, **kwargs):
            host, port = address
            _guard_numeric_host("create_connection", host, port)
            return _original_create_connection(
                address,
                *args,
                **kwargs,
            )

        def _guarded_fromfd(fd, family, type, proto=0):
            if family in (socket.AF_INET, socket.AF_INET6):
                _audit_entry(
                    "fromfd",
                    family,
                    ("inherited-fd", fd),
                    False,
                    "network descriptor provenance is not established",
                )
                raise AirgapViolationError(
                    "socket.fromfd for AF_INET/AF_INET6 is blocked: "
                    "Python instrumentation cannot prove inherited descriptor "
                    "provenance"
                )
            return _original_fromfd(fd, family, type, proto)

        async def _guarded_asyncio_open_connection(
            host=None,
            port=None,
            **kwargs,
        ):
            if host is None or port is None:
                raise AirgapViolationError(
                    "asyncio.open_connection requires an explicit numeric "
                    "loopback host and port"
                )
            _guard_numeric_host(
                "asyncio.open_connection",
                host,
                port,
            )
            return await _original_asyncio_open_connection(
                host,
                port,
                **kwargs,
            )

        def _guarded_ssl_connect(self, address):
            family = self.family
            if family in (socket.AF_INET, socket.AF_INET6):
                _reject_or_audit("ssl.connect", family, address)
            return _original_ssl_connect(self, address)

        def _guarded_ssl_connect_ex(self, address):
            family = self.family
            if family in (socket.AF_INET, socket.AF_INET6):
                denied = _reject_or_audit(
                    "ssl.connect_ex",
                    family,
                    address,
                    connect_ex=True,
                )
                if denied is not None:
                    return denied
            return _original_ssl_connect_ex(self, address)

        def _guarded_ssl_wrap_socket(self, sock, *args, **kwargs):
            # Wrapping is not itself egress. The resulting SSLSocket retains
            # guarded connect/connect_ex methods below.
            _audit_entry(
                "ssl.wrap_socket",
                getattr(sock, "family", -1),
                ("local-wrap",),
                True,
            )
            return _original_ssl_wrap_socket(
                self,
                sock,
                *args,
                **kwargs,
            )

        socket.socket.connect = _guarded_connect
        socket.socket.connect_ex = _guarded_connect_ex
        socket.socket.sendto = _guarded_sendto

        if _original_sendmsg is not None:
            socket.socket.sendmsg = _guarded_sendmsg

        socket.create_connection = _guarded_create_connection
        socket.fromfd = _guarded_fromfd
        asyncio.open_connection = _guarded_asyncio_open_connection
        ssl.SSLSocket.connect = _guarded_ssl_connect
        ssl.SSLSocket.connect_ex = _guarded_ssl_connect_ex
        ssl.SSLContext.wrap_socket = _guarded_ssl_wrap_socket

        _instrumented = True


def get_audit_log() -> list[dict[str, Any]]:
    with _audit_lock:
        return list(_audit_log)


def clear_audit_log() -> None:
    with _audit_lock:
        _audit_log.clear()


# ─── Subprocess policy ──────────────────────────────────────────────────

ALLOWED_EXECUTABLES = frozenset({"nvidia-smi"})


def check_subprocess_allowed(argv: Sequence[str]) -> bool:
    """Return whether argv names an allowed executable."""
    if not argv or not all(isinstance(item, str) for item in argv):
        return False

    exe = argv[0]
    basename = os.path.basename(exe)
    if basename not in ALLOWED_EXECUTABLES:
        return False

    if os.path.isabs(exe):
        try:
            real = os.path.realpath(exe)
        except (OSError, ValueError):
            return False
        if os.path.basename(real) != basename:
            return False
        return True

    resolved = shutil.which(exe)
    if not resolved:
        return False

    try:
        return os.path.basename(os.path.realpath(resolved)) == basename
    except (OSError, ValueError):
        return False


def run_allowed_subprocess(
    argv: Sequence[str],
    **kwargs,
) -> subprocess.CompletedProcess:
    """Create a subprocess only after the component policy admits argv."""
    if kwargs.get("shell", False):
        raise SubprocessPolicyError("shell=True is forbidden")

    command = list(argv)
    if not check_subprocess_allowed(command):
        raise SubprocessPolicyError(
            f"subprocess executable is not admitted: "
            f"{command[0] if command else '<empty>'}"
        )

    kwargs["shell"] = False
    return _original_subprocess_run(command, **kwargs)
