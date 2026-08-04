from elpis_p0.contracts import (
    RequestContext,
)
from elpis_p0.factory import (
    build_default_controller,
)


def test_complete_shadow_protocol_accepts_valid_python():
    context = RequestContext(
        request_id="p0-add",
        prompt=(
            "Create a typed deterministic "
            "Python add function and validate "
            "its AST."
        ),
        entrypoint="add",
        parameters=(
            "a",
            "b",
        ),
        decoder_hints=(
            (
                "body",
                "return a + b",
            ),
        ),
    )

    result = (
        build_default_controller()
        .run(context)
    )

    assert result.accepted is True

    assert (
        "def add(a, b):"
        in result.artifact.source
    )

    assert (
        result.evidence[0].code
        == "AST_VALID"
    )

    assert (
        result.expansion_executed
        is False
    )

    assert (
        result.executed_experts
        == ()
    )

    assert (
        result.governance_invoked
        is False
    )

    assert all(
        event.shadow
        for event in result.accounting
    )
