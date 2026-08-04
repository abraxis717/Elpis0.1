from elpis_p0.contracts import (
    RequestContext,
)
from elpis_p0.factory import (
    build_default_controller,
)
from elpis_p0.replay import (
    assert_deterministic_replay,
)


def test_fresh_controller_replay_is_deterministic():
    context = RequestContext(
        request_id="p0-replay",
        prompt=(
            "Create a deterministic identity "
            "function with AST validation."
        ),
        entrypoint="identity",
        parameters=(
            "value",
        ),
        decoder_hints=(
            (
                "body",
                "return value",
            ),
        ),
    )

    first, second = (
        assert_deterministic_replay(
            build_default_controller(),
            context,
        )
    )

    assert (
        first.result_digest
        == second.result_digest
    )

    assert (
        first.artifact.source
        == second.artifact.source
    )

    assert (
        first.trace
        == second.trace
    )
