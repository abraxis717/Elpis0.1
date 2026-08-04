from __future__ import annotations

import keyword
import re

from .canonical import digest
from .contracts import (
    ArtifactCandidate,
    DecoderControlPlan,
    RequestContext,
)


_IDENTIFIER = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*$"
)


def safe_identifier(
    value: str,
    fallback: str,
) -> str:
    value = value.strip()

    if (
        _IDENTIFIER.fullmatch(value)
        and not keyword.iskeyword(value)
    ):
        return value

    return fallback


class DeterministicPythonDecoder:
    """Offline template decoder for proving the P0 protocol.

    It does not call a language model and does not execute the
    generated source.
    """

    def decode(
        self,
        context: RequestContext,
        plan: DecoderControlPlan,
    ) -> ArtifactCandidate:
        function_name = safe_identifier(
            plan.function_name,
            "solution",
        )

        parameters = tuple(
            safe_identifier(
                value,
                f"arg_{index}",
            )
            for index, value
            in enumerate(
                plan.parameters
            )
        )

        body_lines = (
            plan.body_lines
            or ("return None",)
        )

        summary = " ".join(
            context.prompt
            .strip()
            .split()
        )[:240]

        escaped_summary = (
            summary.replace(
                '"""',
                "'''",
            )
        )

        lines = [
            (
                f"def {function_name}"
                f"({', '.join(parameters)}):"
            ),
            (
                '    """'
                f"{escaped_summary}"
                '"""'
            ),
        ]

        lines.extend(
            (
                f"    {line}"
                if line.strip()
                else ""
            )
            for line in body_lines
        )

        source = (
            "\n".join(lines)
            .rstrip()
            + "\n"
        )

        return ArtifactCandidate(
            language="python",
            source=source,
            digest=digest(
                {
                    "plan_digest": (
                        plan.plan_digest
                    ),
                    "source": source,
                }
            ),
        )
