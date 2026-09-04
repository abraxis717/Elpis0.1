from __future__ import annotations

from elpis.python_ast_policy import (
    evaluate_python_ast_policy,
    python_call_name,
)

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
        decision = evaluate_python_ast_policy(
            language=artifact.language,
            source=artifact.source,
            entrypoint=context.entrypoint,
            banned_calls=frozenset(
                self.banned_calls
            ),
        )

        if decision.code == "LANGUAGE_MISMATCH":
            return ValidatorEvidence(
                validator_id=self.validator_id,
                passed=False,
                code="LANGUAGE_MISMATCH",
                message=(
                    "PythonASTValidator received "
                    "a non-Python artifact"
                ),
            )

        if decision.code == "SYNTAX_ERROR":
            return ValidatorEvidence(
                validator_id=self.validator_id,
                passed=False,
                code="SYNTAX_ERROR",
                message=decision.syntax_message,
                details=(
                    (
                        "lineno",
                        decision.lineno,
                    ),
                    (
                        "offset",
                        decision.offset,
                    ),
                ),
            )

        if decision.code == "ENTRYPOINT_MISSING":
            return ValidatorEvidence(
                validator_id=self.validator_id,
                passed=False,
                code="ENTRYPOINT_MISSING",
                message=(
                    "expected function "
                    f"{context.entrypoint!r} "
                    "was not defined"
                ),
                details=(
                    (
                        "functions",
                        decision.functions,
                    ),
                ),
            )

        if decision.code == "IMPORT_FORBIDDEN":
            return ValidatorEvidence(
                validator_id=self.validator_id,
                passed=False,
                code="IMPORT_FORBIDDEN",
                message=(
                    "P0 template artifacts "
                    "may not import modules"
                ),
                details=(
                    (
                        "lineno",
                        decision.lineno,
                    ),
                ),
            )

        if decision.code == "SCOPE_MUTATION_FORBIDDEN":
            return ValidatorEvidence(
                validator_id=self.validator_id,
                passed=False,
                code="SCOPE_MUTATION_FORBIDDEN",
                message=(
                    "global/nonlocal mutation "
                    "is forbidden in P0"
                ),
                details=(
                    (
                        "lineno",
                        decision.lineno,
                    ),
                ),
            )

        if decision.code == "BANNED_CALL":
            return ValidatorEvidence(
                validator_id=self.validator_id,
                passed=False,
                code="BANNED_CALL",
                message=(
                    f"call to {decision.call_name!r} "
                    "is forbidden in P0"
                ),
                details=(
                    (
                        "lineno",
                        decision.lineno,
                    ),
                ),
            )

        if decision.code != "AST_VALID" or not decision.passed:
            raise RuntimeError(
                "neutral Python AST policy returned "
                "an unsupported decision"
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
                    context.entrypoint,
                ),
                (
                    "node_count",
                    decision.node_count,
                ),
            ),
        )

    @staticmethod
    def _call_name(node):
        return python_call_name(node)
