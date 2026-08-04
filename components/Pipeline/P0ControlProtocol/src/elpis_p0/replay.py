from __future__ import annotations

import json
from pathlib import Path

from .canonical import to_jsonable
from .contracts import (
    P0Result,
    RequestContext,
)
from .controller import P0Controller


def write_result(
    path: str | Path,
    result: P0Result,
) -> None:
    output = Path(path)

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = output.with_suffix(
        output.suffix + ".tmp"
    )

    temporary.write_text(
        json.dumps(
            to_jsonable(result),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary.replace(
        output
    )


def assert_deterministic_replay(
    controller: P0Controller,
    context: RequestContext,
) -> tuple[P0Result, P0Result]:
    first = controller.run(
        context
    )

    second = controller.run(
        context
    )

    if (
        first.result_digest
        != second.result_digest
    ):
        raise AssertionError(
            "P0 replay diverged: "
            f"{first.result_digest} != "
            f"{second.result_digest}"
        )

    return first, second
