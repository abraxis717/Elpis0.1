from __future__ import annotations

import ast

from .contracts import (
    ArtifactCandidate,
    RequestContext,
    ValidatorEvidence,
)


class PythonASTValidator:
    validator_id = "python.ast.v1"

    banned_calls = {
        "eval",
        "exec",
        "compile",
        "open",
        "__import__",
        "breakpoint",
    }

    def validate(
        self,
        context: RequestContext,
        artifact: ArtifactCandidate,
    ) -> ValidatorEvidence:
        if artifact.language != "python":
            return ValidatorEvidence(
                validator_id=self.validator_id,
                passed=False,
                code="LANGUAGE_MISMATCH",
                message=(
                    "PythonASTValidator received "
                    "a non-Python artifact"
                ),
            )

        try:
            tree = ast.parse(
                artifact.source,
                mode="exec",
            )

        except SyntaxError as exc:
            return ValidatorEvidence(
                validator_id=self.validator_id,
                passed=False,
                code="SYNTAX_ERROR",
                message=str(exc),
                details=(
                    (
                        "lineno",
                        exc.lineno or -1,
                    ),
                    (
                        "offset",
                        exc.offset or -1,
                    ),
                ),
            )

        expected = context.entrypoint

        functions = {
            node.name
            for node in ast.walk(tree)
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
        }

        if expected not in functions:
            return ValidatorEvidence(
                validator_id=self.validator_id,
                passed=False,
                code="ENTRYPOINT_MISSING",
                message=(
                    "expected function "
                    f"{expected!r} "
                    "was not defined"
                ),
                details=(
                    (
                        "functions",
                        tuple(
                            sorted(
                                functions
                            )
                        ),
                    ),
                ),
            )

        for node in ast.walk(tree):
            if isinstance(
                node,
                (
                    ast.Import,
                    ast.ImportFrom,
                ),
            ):
                return ValidatorEvidence(
                    validator_id=(
                        self.validator_id
                    ),
                    passed=False,
                    code="IMPORT_FORBIDDEN",
                    message=(
                        "P0 template artifacts "
                        "may not import modules"
                    ),
                    details=(
                        (
                            "lineno",
                            getattr(
                                node,
                                "lineno",
                                -1,
                            ),
                        ),
                    ),
                )

            if isinstance(
                node,
                (
                    ast.Global,
                    ast.Nonlocal,
                ),
            ):
                return ValidatorEvidence(
                    validator_id=(
                        self.validator_id
                    ),
                    passed=False,
                    code=(
                        "SCOPE_MUTATION_FORBIDDEN"
                    ),
                    message=(
                        "global/nonlocal mutation "
                        "is forbidden in P0"
                    ),
                    details=(
                        (
                            "lineno",
                            getattr(
                                node,
                                "lineno",
                                -1,
                            ),
                        ),
                    ),
                )

            if isinstance(
                node,
                ast.Call,
            ):
                name = self._call_name(
                    node.func
                )

                if name in self.banned_calls:
                    return ValidatorEvidence(
                        validator_id=(
                            self.validator_id
                        ),
                        passed=False,
                        code="BANNED_CALL",
                        message=(
                            f"call to {name!r} "
                            "is forbidden in P0"
                        ),
                        details=(
                            (
                                "lineno",
                                getattr(
                                    node,
                                    "lineno",
                                    -1,
                                ),
                            ),
                        ),
                    )

        return ValidatorEvidence(
            validator_id=self.validator_id,
            passed=True,
            code="AST_VALID",
            message=(
                "artifact parsed and passed "
                "P0 static policy"
            ),
            details=(
                (
                    "entrypoint",
                    expected,
                ),
                (
                    "node_count",
                    sum(
                        1
                        for _ in ast.walk(
                            tree
                        )
                    ),
                ),
            ),
        )

    @staticmethod
    def _call_name(
        node: ast.expr,
    ) -> str | None:
        if isinstance(
            node,
            ast.Name,
        ):
            return node.id

        if isinstance(
            node,
            ast.Attribute,
        ):
            return node.attr

        return None
