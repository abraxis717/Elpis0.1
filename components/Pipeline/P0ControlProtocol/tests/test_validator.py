from elpis_p0.contracts import (
    ArtifactCandidate,
    RequestContext,
)
from elpis_p0.validators import (
    PythonASTValidator,
)


def test_ast_validator_rejects_banned_eval_call():
    context = RequestContext(
        request_id="p0-validator",
        prompt="Validate a function.",
        entrypoint="solution",
    )

    artifact = ArtifactCandidate(
        language="python",
        source=(
            "def solution(value):\n"
            "    return eval(value)\n"
        ),
        digest="test",
    )

    evidence = (
        PythonASTValidator()
        .validate(
            context,
            artifact,
        )
    )

    assert evidence.passed is False

    assert (
        evidence.code
        == "BANNED_CALL"
    )
