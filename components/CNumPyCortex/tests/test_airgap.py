"""Test Python airgap defense-in-depth instrumentation."""
from __future__ import annotations

import asyncio
import errno
import socket
import ssl

import pytest

import c_numpy_cortex.airgap as airgap
from c_numpy_cortex.airgap import (
    AirgapViolationError,
    clear_audit_log,
    get_audit_log,
    instrument_airgap,
    _is_allowed_destination,
)


@pytest.fixture
def installed_airgap():
    """Install instrumentation and restore it only from test code."""
    clear_audit_log()
    instrument_airgap()

    try:
        yield
    finally:
        socket.socket.connect = airgap._original_connect
        socket.socket.connect_ex = airgap._original_connect_ex
        socket.socket.sendto = airgap._original_sendto
        if airgap._original_sendmsg is not None:
            socket.socket.sendmsg = airgap._original_sendmsg
        socket.create_connection = airgap._original_create_connection
        socket.fromfd = airgap._original_fromfd
        asyncio.open_connection = airgap._original_asyncio_open_connection
        ssl.SSLSocket.connect = airgap._original_ssl_connect
        ssl.SSLSocket.connect_ex = airgap._original_ssl_connect_ex
        ssl.SSLContext.wrap_socket = airgap._original_ssl_wrap_socket
        airgap._instrumented = False
        clear_audit_log()


def test_loopback_ipv4_allowed_on_nonforbidden_port():
    assert _is_allowed_destination(
        socket.AF_INET, ("127.0.0.1", 18081)
    ) is True
    assert _is_allowed_destination(
        socket.AF_INET, ("127.255.0.1", 18081)
    ) is True


def test_loopback_ipv6_allowed_on_nonforbidden_port():
    assert _is_allowed_destination(
        socket.AF_INET6, ("::1", 18081)
    ) is True


def test_forbidden_destination_port_rejected_even_on_loopback():
    assert _is_allowed_destination(
        socket.AF_INET, ("127.0.0.1", 8080)
    ) is False
    assert _is_allowed_destination(
        socket.AF_INET6, ("::1", 8080)
    ) is False


def test_non_loopback_ipv4_rejected():
    assert _is_allowed_destination(
        socket.AF_INET, ("192.168.1.1", 18081)
    ) is False
    assert _is_allowed_destination(
        socket.AF_INET, ("10.0.0.1", 18081)
    ) is False
    assert _is_allowed_destination(
        socket.AF_INET, ("8.8.8.8", 53)
    ) is False
    assert _is_allowed_destination(
        socket.AF_INET, ("169.254.169.254", 80)
    ) is False


def test_non_loopback_ipv6_rejected():
    assert _is_allowed_destination(
        socket.AF_INET6, ("2001:db8::1", 18081)
    ) is False


def test_hostname_dns_bypass_rejected():
    assert _is_allowed_destination(
        socket.AF_INET, ("example.com", 80)
    ) is False


def test_unix_socket_allowed():
    assert _is_allowed_destination(
        socket.AF_UNIX, ("/tmp/socket",)
    ) is True


def test_no_public_uninstrument_escape_hatch():
    assert not hasattr(airgap, "uninstrument_airgap")


def test_instrumented_connect_blocks_non_loopback(installed_airgap):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(AirgapViolationError):
            s.connect(("192.168.1.1", 12345))
    finally:
        s.close()

    log = get_audit_log()
    assert log
    assert log[-1]["operation"] == "connect"
    assert log[-1]["allowed"] is False


def test_instrumented_connect_ex_blocks_non_loopback(installed_airgap):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = s.connect_ex(("192.168.1.1", 12345))
    finally:
        s.close()

    assert result == errno.EACCES
    assert get_audit_log()[-1]["operation"] == "connect_ex"


def test_instrumented_connect_blocks_forbidden_loopback_port(installed_airgap):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(AirgapViolationError):
            s.connect(("127.0.0.1", 8080))
    finally:
        s.close()


def test_udp_sendto_nonloopback_blocked(installed_airgap):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(AirgapViolationError):
            s.sendto(b"x", ("203.0.113.8", 9000))
    finally:
        s.close()

    assert get_audit_log()[-1]["operation"] == "sendto"


def test_sendmsg_nonloopback_blocked(installed_airgap):
    if not hasattr(socket.socket, "sendmsg"):
        pytest.skip("sendmsg unavailable")

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(AirgapViolationError):
            s.sendmsg([b"x"], [], 0, ("203.0.113.8", 9000))
    finally:
        s.close()

    assert get_audit_log()[-1]["operation"] == "sendmsg"


def test_network_fromfd_rejected_as_unproven_inherited_capability(
    installed_airgap,
):
    left, right = socket.socketpair()
    try:
        with pytest.raises(
            AirgapViolationError,
            match="descriptor provenance",
        ):
            socket.fromfd(
                left.fileno(),
                socket.AF_INET,
                socket.SOCK_STREAM,
            )
    finally:
        left.close()
        right.close()

    assert get_audit_log()[-1]["operation"] == "fromfd"


def test_socketpair_local_ipc_preserved(installed_airgap):
    left, right = socket.socketpair()
    try:
        left.sendall(b"x")
        assert right.recv(1) == b"x"
    finally:
        left.close()
        right.close()


def test_create_connection_hostname_blocked_before_resolution(
    installed_airgap,
    monkeypatch,
):
    def forbidden_resolution(*args, **kwargs):
        pytest.fail("getaddrinfo must not run for a hostname")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden_resolution)

    with pytest.raises(
        AirgapViolationError,
        match="blocked before resolution",
    ):
        socket.create_connection(("example.invalid", 443))

    log = get_audit_log()
    assert log[-1]["operation"] == "create_connection"
    assert log[-1]["allowed"] is False


def test_create_connection_nonloopback_numeric_blocked_before_original(
    installed_airgap,
):
    original = airgap._original_create_connection
    called = False

    def forbidden_original(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("original create_connection must not run")

    airgap._original_create_connection = forbidden_original
    try:
        with pytest.raises(AirgapViolationError):
            socket.create_connection(("203.0.113.9", 443))
        assert called is False
    finally:
        airgap._original_create_connection = original


def test_create_connection_loopback_reaches_original_without_resolution(
    installed_airgap,
    monkeypatch,
):
    sentinel = object()
    original = airgap._original_create_connection
    calls = []

    def fake_original(address, *args, **kwargs):
        calls.append((address, args, kwargs))
        return sentinel

    def forbidden_resolution(*args, **kwargs):
        pytest.fail("numeric loopback must not require getaddrinfo")

    airgap._original_create_connection = fake_original
    monkeypatch.setattr(socket, "getaddrinfo", forbidden_resolution)

    try:
        result = socket.create_connection(("127.0.0.1", 18081))
        assert result is sentinel
        assert calls and calls[0][0] == ("127.0.0.1", 18081)
    finally:
        airgap._original_create_connection = original


def test_asyncio_open_connection_nonloopback_rejected(installed_airgap):
    async def attempt():
        await asyncio.open_connection("203.0.113.9", 443)

    with pytest.raises(AirgapViolationError):
        asyncio.run(attempt())


def test_ssl_wrapping_cannot_bypass_rejected_destination(installed_airgap):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    wrapped = context.wrap_socket(
        raw,
        server_hostname=None,
        do_handshake_on_connect=False,
    )
    try:
        with pytest.raises(AirgapViolationError):
            wrapped.connect(("203.0.113.9", 443))
    finally:
        wrapped.close()

    operations = [entry["operation"] for entry in get_audit_log()]
    assert "ssl.wrap_socket" in operations
    assert "ssl.connect" in operations


def test_instrumentation_is_idempotent(installed_airgap):
    first = socket.socket.connect
    instrument_airgap()
    assert socket.socket.connect is first


def test_security_module_has_no_ctypes_dependency():
    source = (__import__("pathlib").Path(airgap.__file__)).read_text()
    assert "import ctypes" not in source
    assert "from ctypes" not in source
