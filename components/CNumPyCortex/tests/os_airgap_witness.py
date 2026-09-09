#!/usr/bin/env python3
"""Independent Linux OS network-isolation witness.

This file intentionally does not import c_numpy_cortex.airgap. It is executed
inside a dedicated network namespace by hosted CI. The acceptance property is:
test-owned loopback works, while non-loopback IPv4 egress has no route.
"""
from __future__ import annotations

import errno
import socket
import sys
import threading


def _loopback_roundtrip() -> int:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    received: list[bytes] = []

    def accept_once() -> None:
        conn, _ = server.accept()
        try:
            received.append(conn.recv(4))
            conn.sendall(b"pong")
        finally:
            conn.close()

    thread = threading.Thread(target=accept_once, daemon=True)
    thread.start()

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(2.0)
    try:
        client.connect(("127.0.0.1", port))
        client.sendall(b"ping")
        assert client.recv(4) == b"pong"
    finally:
        client.close()
        server.close()

    thread.join(timeout=2.0)
    assert received == [b"ping"]
    return port


def _nonloopback_tcp_refused_by_os() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        rc = sock.connect_ex(("198.51.100.1", 443))
    finally:
        sock.close()

    assert rc != 0, "isolated namespace unexpectedly admitted TCP egress"
    return rc


def _nonloopback_udp_refused_by_os() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        try:
            sock.sendto(b"x", ("198.51.100.1", 9))
        except OSError as exc:
            rc = exc.errno or -1
        else:
            raise AssertionError(
                "isolated namespace unexpectedly admitted UDP egress"
            )
    finally:
        sock.close()

    return rc


def main() -> int:
    assert not any(
        name == "c_numpy_cortex" or name.startswith("c_numpy_cortex.")
        for name in sys.modules
    ), "OS witness must be independent of Python airgap instrumentation"

    port = _loopback_roundtrip()
    tcp_rc = _nonloopback_tcp_refused_by_os()
    udp_rc = _nonloopback_udp_refused_by_os()

    print(
        "PASS_CNUMPYCORTEX_OS_AIRGAP "
        f"loopback_ephemeral_port={port} "
        f"tcp_nonloopback_rc={tcp_rc} "
        f"udp_nonloopback_errno={udp_rc}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
