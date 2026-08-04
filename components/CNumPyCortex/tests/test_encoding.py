import numpy as np

from c_numpy_cortex.encoding import (
    Grid81Compiler,
    decode_digit_bits,
)


def test_grid81_shape_range_and_binary_roundtrip():
    channels = tuple(
        f"temp.core_{index}"
        for index in range(9)
    )

    compiler = Grid81Compiler(
        channels
    )

    wall_time = np.arange(
        32,
        dtype=np.int64,
    )

    values = np.arange(
        32 * 9,
        dtype=np.float32,
    ).reshape(
        32,
        9,
    )

    packet = compiler.compile(
        wall_time,
        values,
    )

    packet.validate()

    assert packet.tokens81.shape == (
        81,
    )

    assert packet.digits.min() >= 0
    assert packet.digits.max() <= 9

    assert np.array_equal(
        decode_digit_bits(packet.bits),
        packet.digits,
    )
