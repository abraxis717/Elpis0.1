from __future__ import annotations

import argparse
import json
from pathlib import Path

from .canonical import to_jsonable
from .contracts import RequestContext
from .factory import (
    build_default_controller,
)
from .replay import (
    assert_deterministic_replay,
    write_result,
)


def load_request(
    path: str | Path,
) -> RequestContext:
    payload = json.loads(
        Path(path).read_text(
            encoding="utf-8"
        )
    )

    return RequestContext(
        request_id=str(
            payload["request_id"]
        ),
        prompt=str(
            payload["prompt"]
        ),
        domain=str(
            payload.get(
                "domain",
                "python",
            )
        ),
        entrypoint=str(
            payload.get(
                "entrypoint",
                "solution",
            )
        ),
        parameters=tuple(
            str(value)
            for value
            in payload.get(
                "parameters",
                (),
            )
        ),
        decoder_hints=tuple(
            sorted(
                (
                    str(key),
                    str(value),
                )
                for key, value
                in payload.get(
                    "decoder_hints",
                    {},
                ).items()
            )
        ),
        allowed_experts=tuple(
            str(value)
            for value
            in payload.get(
                "allowed_experts",
                (
                    "python.codegen",
                    "python.ast",
                    "python.tests",
                    "python.typing",
                ),
            )
        ),
        max_tokens=int(
            payload.get(
                "max_tokens",
                512,
            )
        ),
        budget_units=int(
            payload.get(
                "budget_units",
                32,
            )
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the P0 shadow-only "
            "structural/TRM control protocol"
        )
    )

    parser.add_argument(
        "request",
        help="request JSON file",
    )

    parser.add_argument(
        "--output",
        help=(
            "optional result JSON path"
        ),
    )

    parser.add_argument(
        "--replay-check",
        action="store_true",
        help=(
            "run the request twice and "
            "require identical result digests"
        ),
    )

    arguments = parser.parse_args()

    context = load_request(
        arguments.request
    )

    controller = (
        build_default_controller()
    )

    if arguments.replay_check:
        result, _ = (
            assert_deterministic_replay(
                controller,
                context,
            )
        )

    else:
        result = controller.run(
            context
        )

    if arguments.output:
        write_result(
            arguments.output,
            result,
        )

    print(
        json.dumps(
            to_jsonable(result),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
