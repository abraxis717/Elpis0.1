import numpy as np

from c_numpy_cortex.ring import NumPyRingBuffer


def test_ring_preserves_chronological_order_after_wrap():
    ring = NumPyRingBuffer(
        3,
        ("x",),
    )

    for value in range(5):
        ring.append(
            value,
            value,
            {"x": float(value)},
        )

    wall_time, monotonic, values = (
        ring.snapshot()
    )

    assert wall_time.tolist() == [
        2,
        3,
        4,
    ]

    assert monotonic.tolist() == [
        2,
        3,
        4,
    ]

    assert np.allclose(
        values[:, 0],
        [
            2.0,
            3.0,
            4.0,
        ],
    )
