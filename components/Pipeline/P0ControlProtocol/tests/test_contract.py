import pytest

from elpis_p0.contracts import (
    StructuralProjection,
)


def test_projection_rejects_wrong_grid_size():
    projection = StructuralProjection(
        grid81=(0,) * 80,
        semantic_rows=(
            "row",
        ) * 9,
        features=(),
        digest="bad",
    )

    with pytest.raises(
        ValueError
    ):
        projection.validate()
