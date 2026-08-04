from elpis_p0.contracts import (
    RequestContext,
)
from elpis_p0.factory import (
    build_default_controller,
)


def test_expansion_is_proposed_but_never_executed_in_p0():
    context = RequestContext(
        request_id="p0-expansion",
        prompt=(
            (
                "Create a recursive async parallel "
                "typed Python stream processor with "
                "database, network, tests, validation, "
                "cache, and deterministic behavior. "
            )
            * 4
        ),
        entrypoint="process",
        parameters=(
            "stream",
            "config",
        ),
        decoder_hints=(
            (
                "body",
                "return stream",
            ),
        ),
    )

    result = (
        build_default_controller()
        .run(context)
    )

    assert (
        result.proposed_expansions
    )

    assert (
        result.expansion_executed
        is False
    )

    assert any(
        event.action
        == "expansion_deferred"
        for event in result.trace
    )
