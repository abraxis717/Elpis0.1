"""D0.1 529-bit packer compatibility (mission 7).

Proves encode -> decode == original for BOTH planes across:
  * every one-hot bit 0..528 (529/529)
  * all-zeros, all-ones, boundary bits 511/512/528
  * high-bit plane 512..528 (17/17)
  * representative C2R6-P0 fixture vectors
No collision: distinct vectors -> distinct packed contexts (injective).
"""
from __future__ import annotations

import conftest as C
import torch

from c2r6p1_bridge import (
    BridgeRejectionCode,
    BridgeRejectionError,
    one_hot,
    pack_529,
    roundtrip_529,
)
from _vendored_authority import packer as _p, verify_vendor

W = 529


def test_vendor_verified():
    report = verify_vendor()
    assert len(report) == 5
    for v in report.values():
        assert len(v) == 64


def test_one_hot_all_529_bits_roundtrip():
    for bit in range(W):
        decl, act = one_hot(bit)
        d, a = roundtrip_529(decl, act)
        assert d == decl, f"declared mismatch at bit {bit}"
        assert a == act, f"active mismatch at bit {bit}"


def test_high_bits_512_528_roundtrip():
    for bit in range(512, 529):  # 512..528 inclusive = 17 bits
        decl, act = one_hot(bit)
        d, a = roundtrip_529(decl, act)
        assert d == decl
        # the high bit must land in the HI slot and survive
        assert d[bit] == 1
        assert sum(d) == 1


def test_boundary_bits():
    for bit in (511, 512, 528):
        decl, act = one_hot(bit)
        d, a = roundtrip_529(decl, act)
        assert d == decl


def test_all_zeros_all_ones():
    z = tuple(0 for _ in range(W))
    o = tuple(1 for _ in range(W))
    assert roundtrip_529(z, z) == (z, z)
    assert roundtrip_529(o, o) == (o, o)
    assert roundtrip_529(o, z) == (o, z)
    assert roundtrip_529(z, o) == (z, o)


def test_injective_no_collision_one_hot():
    """529 distinct one-hot vectors -> 529 distinct packed contexts."""
    seen = {}
    for bit in range(W):
        decl, act = one_hot(bit)
        ctx = pack_529(decl, act)
        key = ctx.cpu().numpy().tobytes()
        assert key not in seen, f"collision between bit {seen[key]} and {bit}"
        seen[key] = bit
    assert len(seen) == W


def test_projector_fixture_vectors_roundtrip(project):
    """Representative C2R6-P0 fixture vectors pass the packer losslessly."""
    from c2r6p0 import fixtures as F

    checked = 0
    s = 0
    while checked < 25 and s < 200:
        g = F.gen_valid(s)
        r = project(C.wrap(g, request_id=f"pk_{s}"))
        if r.status == "PROJECTED":
            d, a = roundtrip_529(r.declared_features, r.active_residual)
            assert d == r.declared_features
            assert a == r.active_residual
            checked += 1
        s += 1
    assert checked >= 25


def test_reject_wrong_width():
    act = tuple(0 for _ in range(W))
    for badw in (W - 1, W + 1, 0, 100):  # 528, 530, 0, 100
        decl = tuple(0 for _ in range(badw))
        C.expect_rejection(
            lambda d=decl: pack_529(d, act), BridgeRejectionCode.PACKER_REJECTED
        )
        C.expect_rejection(
            lambda d=decl: roundtrip_529(d, act),
            BridgeRejectionCode.PACKER_REJECTED,
        )


def test_reject_non_binary():
    decl = list(0 for _ in range(W))
    decl[7] = 2  # illegal 0/1 value
    act = tuple(0 for _ in range(W))
    C.expect_rejection(
        lambda: pack_529(tuple(decl), act), BridgeRejectionCode.PACKER_REJECTED
    )


def test_reject_reserved_position_nonzero():
    """Tamper the reserved positions 4..15 -> unpack must fail closed."""
    decl, act = one_hot(520)
    ctx = pack_529(decl, act)
    ctx[5] = 1.0  # reserved position
    try:
        _p().unpack_structural_context(ctx)
        raise AssertionError("expected reserved-position rejection")
    except Exception as e:
        assert "reserved" in str(e).lower()
