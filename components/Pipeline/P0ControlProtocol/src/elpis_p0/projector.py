from __future__ import annotations

import re

from .canonical import digest
from .contracts import (
    BasisToken,
    RequestContext,
    StructuralProjection,
)


_WORD = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*"
)


class DeterministicPythonProjector:
    """Transparent Python request → Grid81 projector.

    This establishes the typed P0 transport before a learned
    structural projector is admitted.
    """

    semantic_rows = (
        "request_contract",
        "input_shape",
        "requested_transform",
        "output_shape",
        "constraints",
        "decomposition",
        "expert_interfaces",
        "validation",
        "resolution_control",
    )

    def project(
        self,
        context: RequestContext,
    ) -> StructuralProjection:
        if context.domain != "python":
            raise ValueError(
                "P0 deterministic projector currently "
                "supports python only"
            )

        words = tuple(
            word.lower()
            for word in _WORD.findall(
                context.prompt
            )
        )

        word_set = set(words)

        complexity = self._complexity(
            context,
            word_set,
        )

        rows = [
            [
                1,
                1 if context.parameters else 0,
                7,
                2,
                3,
                5,
                8,
                9,
                0,
            ],
            self._input_row(
                context,
                word_set,
            ),
            self._transform_row(
                word_set
            ),
            self._output_row(
                word_set
            ),
            self._constraint_row(
                word_set
            ),
            self._decomposition_row(
                complexity,
                word_set,
            ),
            self._interface_row(
                word_set
            ),
            self._validation_row(
                word_set
            ),
            self._resolution_row(
                context,
                complexity,
            ),
        ]

        grid = tuple(
            int(cell)
            for row in rows
            for cell in row
        )

        features = (
            (
                "prompt_chars",
                float(len(context.prompt)),
            ),
            (
                "word_count",
                float(len(words)),
            ),
            (
                "parameter_count",
                float(len(context.parameters)),
            ),
            (
                "complexity",
                float(complexity),
            ),
            (
                "constraint_terms",
                float(
                    sum(
                        term in word_set
                        for term
                        in self._constraint_terms()
                    )
                ),
            ),
        )

        projection_digest = digest(
            {
                "request_id": context.request_id,
                "grid81": grid,
                "semantic_rows": self.semantic_rows,
                "features": features,
            }
        )

        projection = StructuralProjection(
            grid81=grid,
            semantic_rows=self.semantic_rows,
            features=features,
            digest=projection_digest,
        )

        projection.validate()
        return projection

    @staticmethod
    def _constraint_terms() -> tuple[str, ...]:
        return (
            "must",
            "never",
            "without",
            "validate",
            "safe",
            "deterministic",
            "typed",
            "test",
        )

    def _complexity(
        self,
        context: RequestContext,
        words: set[str],
    ) -> int:
        weighted = (
            len(context.prompt) // 120
            + len(context.parameters)
        )

        weighted += sum(
            1
            for term in (
                "async",
                "class",
                "recursive",
                "stream",
                "database",
                "network",
                "parallel",
                "validate",
                "test",
            )
            if term in words
        )

        return min(
            weighted,
            9,
        )

    @staticmethod
    def _input_row(
        context: RequestContext,
        words: set[str],
    ) -> list[int]:
        row = [0] * 9

        for index in range(
            min(
                len(context.parameters),
                4,
            )
        ):
            row[index] = BasisToken.INPUT

        if "json" in words:
            row[4] = BasisToken.INTERFACE

        if "file" in words or "path" in words:
            row[5] = BasisToken.INTERFACE

        if "stream" in words:
            row[6] = BasisToken.INPUT

        row[7] = BasisToken.CONSTRAINT
        row[8] = BasisToken.ROUTE

        return [
            int(value)
            for value in row
        ]

    @staticmethod
    def _transform_row(
        words: set[str],
    ) -> list[int]:
        row = (
            [BasisToken.TRANSFORM] * 3
            + [BasisToken.VOID] * 6
        )

        if "class" in words:
            row[3] = BasisToken.TRANSFORM

        if "async" in words:
            row[4] = BasisToken.INTERFACE

        if "recursive" in words:
            row[5] = BasisToken.EXPANSION

        if "cache" in words or "memory" in words:
            row[6] = BasisToken.MEMORY

        row[7] = BasisToken.CONSTRAINT
        row[8] = BasisToken.OUTPUT

        return [
            int(value)
            for value in row
        ]

    @staticmethod
    def _output_row(
        words: set[str],
    ) -> list[int]:
        row = [
            BasisToken.OUTPUT,
            BasisToken.OUTPUT,
            BasisToken.RESOLUTION,
        ]

        row += [
            BasisToken.VOID
        ] * 6

        if "json" in words:
            row[3] = BasisToken.INTERFACE

        if (
            "iterator" in words
            or "generator" in words
        ):
            row[4] = BasisToken.OUTPUT

        if (
            "typed" in words
            or "type" in words
        ):
            row[5] = BasisToken.CONSTRAINT

        row[7] = BasisToken.CONSTRAINT
        row[8] = BasisToken.RESOLUTION

        return [
            int(value)
            for value in row
        ]

    def _constraint_row(
        self,
        words: set[str],
    ) -> list[int]:
        row = [
            BasisToken.VOID
        ] * 9

        for index, term in enumerate(
            self._constraint_terms()[:8]
        ):
            if term in words:
                row[index] = (
                    BasisToken.CONSTRAINT
                )

        row[8] = BasisToken.CONSTRAINT

        return [
            int(value)
            for value in row
        ]

    @staticmethod
    def _decomposition_row(
        complexity: int,
        words: set[str],
    ) -> list[int]:
        row = (
            [BasisToken.TRANSFORM] * 3
            + [BasisToken.VOID] * 6
        )

        if complexity >= 5:
            row[3] = BasisToken.EXPANSION

        if complexity >= 7:
            row[4] = BasisToken.EXPANSION

        if "parallel" in words:
            row[5] = BasisToken.EXPANSION

        row[6] = BasisToken.ROUTE
        row[7] = BasisToken.CONSTRAINT
        row[8] = BasisToken.RESOLUTION

        return [
            int(value)
            for value in row
        ]

    @staticmethod
    def _interface_row(
        words: set[str],
    ) -> list[int]:
        row = [
            BasisToken.ROUTE,
            BasisToken.INTERFACE,
            BasisToken.INTERFACE,
        ]

        row += [
            BasisToken.VOID
        ] * 6

        if "test" in words:
            row[3] = BasisToken.INTERFACE

        if (
            "typing" in words
            or "typed" in words
        ):
            row[4] = BasisToken.INTERFACE

        row[7] = BasisToken.CONSTRAINT
        row[8] = BasisToken.RESOLUTION

        return [
            int(value)
            for value in row
        ]

    @staticmethod
    def _validation_row(
        words: set[str],
    ) -> list[int]:
        row = [
            BasisToken.CONSTRAINT,
            BasisToken.INTERFACE,
            BasisToken.CONSTRAINT,
        ]

        row += [
            BasisToken.VOID
        ] * 6

        if (
            "ast" in words
            or "python" in words
        ):
            row[3] = BasisToken.INTERFACE

        if "test" in words:
            row[4] = BasisToken.CONSTRAINT

        row[7] = BasisToken.CONSTRAINT
        row[8] = BasisToken.RESOLUTION

        return [
            int(value)
            for value in row
        ]

    @staticmethod
    def _resolution_row(
        context: RequestContext,
        complexity: int,
    ) -> list[int]:
        del context

        row = [
            BasisToken.ROUTE,
            BasisToken.CONSTRAINT,
            BasisToken.RESOLUTION,
        ]

        row += [
            BasisToken.VOID
        ] * 6

        row[3] = (
            BasisToken.EXPANSION
            if complexity >= 8
            else BasisToken.TRANSFORM
        )

        row[4] = BasisToken.CONSTRAINT
        row[5] = BasisToken.INTERFACE
        row[6] = BasisToken.OUTPUT
        row[7] = BasisToken.CONSTRAINT
        row[8] = BasisToken.RESOLUTION

        return [
            int(value)
            for value in row
        ]
