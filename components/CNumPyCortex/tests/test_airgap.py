"""Test airgap enforcement."""
from __future__ import annotations

import errno
import socket
import pytest

from c_numpy_cortex.airgap import (
    AirgapViolationError,
    instrument_airgap,
    uninstrument_airgap,
    get_audit_log,
    clear_audit_log,
    _is_allowed_destination,
)


def test_loopback_ipv4_allowed():
    assert _is_allowed_destination(
        socket.AF_INET, ("127.0.0.1", 8080)
    ) is True
    assert _is_allowed_destination(
        socket.AF_INET, ("127.255.0.1", 8080)
    ) is True


def test_loopback_ipv6_allowed():
    assert _is_allowed_destination(
        socket.AF_INET6, ("::1", 8080)
    ) is True


def test_non_loopback_ipv4_rejected():
    assert _is_allowed_destination(
        socket.AF_INET, ("192.168.1.1", 8080)
    ) is False
    assert _is_allowed_destination(
        socket.AF_INET, ("10.0.0.1", 8080)
    ) is False
    assert _is_allowed_destination(
        socket.AF_INET, ("8.8.8.8", 53)
    ) is False
    assert _is_allowed_destination(
        socket.AF_INET, ("169.254.169.254", 80)
    ) is False  # metadata service


def test_non_loopback_ipv6_rejected():
    assert _is_allowed_destination(
        socket.AF_INET6, ("2001:db8::1", 8080)
    ) is False


def test_hostname_dns_bypass_rejected():
    """Hostnames requiring DNS are blocked."""
    assert _is_allowed_destination(
        socket.AF_INET, ("example.com", 80)
    ) is False


def test_unix_socket_allowed():
    assert _is_allowed_destination(
        socket.AF_UNIX, ("/tmp/socket",)
    ) is True


def test_instrumented_connect_blocks_non_loopback():
    """Connect is instrumented to reject non-loopback."""
    clear_audit_log()
    instrument_airgap()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(AirgapViolationError):
            s.connect(("192.168.1.1", 12345))
        s.close()

        log = get_audit_log()
        assert len(log) >= 1
        assert log[-1]["allowed"] is False

    finally:
        uninstrument_airgap()


def test_instrumented_connect_ex_blocks_non_loopback():
    """Connect_ex is instrumented."""
    clear_audit_log()
    instrument_airgap()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = s.connect_ex(("192.168.1.1", 12345))
        assert result == errno.EACCES
        s.close()

        log = get_audit_log()
        assert len(log) >= 1

    finally:
        uninstrument_airgap()


def test_instrumented_connect_allows_loopback():
    """Loopback IPv4 connect is allowed (may fail with connection refused)."""
    clear_audit_log()
    instrument_airgap()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # This should NOT raise AirgapViolationError
        # (it may raise connection refused, which is fine)
        try:
            s.connect(("127.0.0.1", 54321))
        except AirgapViolationError:
            pytest.fail("Loopback should be allowed")
        except OSError:
            pass  # Connection refused is expected
        s.close()

    finally:
        uninstrument_airgap()


def test_instrumented_connect_allows_loopback_ipv6():
    """Loopback IPv6 connect is allowed."""
    clear_audit_log()
    instrument_airgap()

    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        try:
            s.connect(("::1", 54321))
        except AirgapViolationError:
            pytest.fail("Loopback IPv6 should be allowed")
        except OSError:
            pass
        s.close()

    finally:
        uninstrument_airgap()
