from __future__ import annotations

import ctypes
import ctypes.util
import errno
import ipaddress
import socket
import struct
import threading
import traceback
import os

# Allowed IPv4 loopback range
_LOOPBACK_V4 = ipaddress.IPv4Network("127.0.0.0/8")
# Allowed IPv6 loopback
_LOOPBACK_V6_ADDR = ipaddress.IPv6Address("::1")

# Configured health targets
ALLOWED_HEALTH_TARGETS = {
    ("127.0.0.1", 8080),
    ("127.0.0.1", 8081),
}

# Audit log
_audit_lock = threading.Lock()
_audit_log: list[dict] = []


def _is_allowed_destination(
    addr_family: int,
    addr: tuple,
) -> bool:
    """Check if a socket destination is allowed under airgap policy."""
    if addr_family == socket.AF_INET:
        ip_str = addr[0]
        try:
            ip = ipaddress.IPv4Address(ip_str)
            return ip in _LOOPBACK_V4
        except ValueError:
            return False

    if addr_family == socket.AF_INET6:
        ip_str = addr[0]
        try:
            ip = ipaddress.IPv6Address(ip_str)
            return ip == _LOOPBACK_V6_ADDR
        except ValueError:
            return False

    # UNIX-domain sockets are permitted but separately reported
    if addr_family == socket.AF_UNIX:
        return True

    return False


def _audit_entry(
    operation: str,
    addr_family: int,
    addr: tuple,
    allowed: bool,
    stack_summary: str | None = None,
) -> dict:
    entry = {
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


_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex
_original_create_connection = socket.create_connection
_original_asyncio_open_connection = None


class AirgapViolationError(Exception):
    """Raised when a non-loopback connection is attempted."""


def instrument_airgap() -> None:
    """Instrument all socket connection paths for airgap enforcement."""
    global _original_connect, _original_connect_ex

    def _guarded_connect(self, address):
        family = self.family

        if family in (socket.AF_INET, socket.AF_INET6):
            allowed = _is_allowed_destination(family, address)
            _audit_entry(
                "connect",
                family,
                address,
                allowed,
                _get_stack_summary(),
            )

            if not allowed:
                raise AirgapViolationError(
                    f"Blocked connection to {address} "
                    f"(family={family}). "
                    "Only loopback addresses permitted."
                )

        return _original_connect(self, address)

    def _guarded_connect_ex(self, address, *args):
        family = self.family

        if family in (socket.AF_INET, socket.AF_INET6):
            allowed = _is_allowed_destination(family, address)
            _audit_entry(
                "connect_ex",
                family,
                address,
                allowed,
                _get_stack_summary(),
            )

            if not allowed:
                return errno.EACCES

        return _original_connect_ex(self, address, *args)

    socket.socket.connect = _guarded_connect
    socket.socket.connect_ex = _guarded_connect_ex

    # Guard asyncio.open_connection if available
    global _original_asyncio_open_connection
    try:
        import asyncio
        _original_asyncio_open_connection = (
            asyncio.open_connection
        )

        async def _guarded_asyncio_open(
            host=None, port=None, **kwargs
        ):
            # Resolve to IP to check
            if host and not isinstance(host, int):
                try:
                    ipaddress.IPv4Address(host)
                    family = socket.AF_INET
                except ValueError:
                    try:
                        ipaddress.IPv6Address(host)
                        family = socket.AF_INET6
                    except ValueError:
                        # hostname requires DNS - blocked
                        _audit_entry(
                            "asyncio.open_connection",
                            socket.AF_INET,
                            (host, port),
                            False,
                            "DNS hostname not permitted",
                        )
                        raise AirgapViolationError(
                            f"DNS hostname blocked: {host}"
                        )
                addr = (host, port)
                allowed = _is_allowed_destination(family, addr)
                _audit_entry(
                    "asyncio.open_connection",
                    family,
                    addr,
                    allowed,
                )
                if not allowed:
                    raise AirgapViolationError(
                        f"Blocked asyncio connection to {host}:{port}"
                    )

            return await _original_asyncio_open_connection(
                host, port, **kwargs
            )

        asyncio.open_connection = _guarded_asyncio_open
    except Exception:
        pass


def uninstrument_airgap() -> None:
    """Restore original socket functions."""
    global _original_connect, _original_connect_ex

    socket.socket.connect = _original_connect
    socket.socket.connect_ex = _original_connect_ex

    if _original_asyncio_open_connection is not None:
        try:
            import asyncio
            asyncio.open_connection = (
                _original_asyncio_open_connection
            )
        except Exception:
            pass


def get_audit_log() -> list[dict]:
    with _audit_lock:
        return list(_audit_log)


def clear_audit_log() -> None:
    with _audit_lock:
        _audit_log.clear()


# ─── Subprocess policy ──────────────────────────────────────────────────

ALLOWED_EXECUTABLES = {"nvidia-smi"}


def check_subprocess_allowed(argv: list[str]) -> bool:
    """Check if a subprocess invocation is allowed."""
    if not argv:
        return False

    exe = argv[0]
    basename = os.path.basename(exe)

    if basename not in ALLOWED_EXECUTABLES:
        return False

    # If absolute path, verify realpath
    if os.path.isabs(exe):
        try:
            real = os.path.realpath(exe)
            if os.path.basename(real) != basename:
                return False
        except (OSError, ValueError):
            return False

    return True
