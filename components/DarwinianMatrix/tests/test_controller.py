from __future__ import annotations

import torch

from DarwinianMatrix.controller.verdict import (
    FrameVerdict,
    MetaEpisodeState,
    assess_frame,
    classify,
    classify_trend,
    viability,
)
from DarwinianMatrix.ecology.engine import (
    PRODUCER,
    EcologyState,
)
from DarwinianMatrix.geometry import MATRIX_CELLS


def test_viability_uses_only_active_positive_energy() -> None:
    state = EcologyState()

    state.ctype[0] = PRODUCER
    state.energy[0] = 2.0
    state.genome[0] = 0.5
    state.lineage[0] = 1

    state.ctype[1] = PRODUCER
    state.energy[1] = -4.0
    state.genome[1] = 0.5
    state.lineage[1] = 2

    # Empty sites must not contribute even with positive energy.
    state.energy[2] = 100.0

    capacity = torch.ones(
        MATRIX_CELLS,
        dtype=torch.float32,
    )
    capacity[0] = 0.5

    assert viability(state, capacity) == 1.0


def test_resolved_verdict() -> None:
    assessment = assess_frame(
        meta_id="meta-1",
        history=(1.0, 2.0, 5.0),
        target_viability=5.0,
        attempt_index=3,
        attempt_budget=3,
    )

    assert assessment.verdict == FrameVerdict.RESOLVED
    assert assessment.terminal
    assert assessment.budget_exhausted
    assert assessment.reason_codes == (
        "VIABILITY_TARGET_REACHED",
    )


def test_resolution_precedes_budget_exhaustion() -> None:
    assessment = assess_frame(
        meta_id="meta-1",
        history=(1.0, 2.0),
        target_viability=2.0,
        attempt_index=2,
        attempt_budget=2,
    )

    assert assessment.verdict == FrameVerdict.RESOLVED


def test_improving_trend() -> None:
    assert classify_trend(
        (1.0, 1.5, 2.25, 3.0)
    ) == FrameVerdict.IMPROVING


def test_degrading_trend() -> None:
    assert classify_trend(
        (4.0, 3.0, 2.0, 1.0)
    ) == FrameVerdict.DEGRADING


def test_stalled_trend() -> None:
    assert classify_trend(
        (1.0, 1.0001, 0.9999, 1.0002),
        epsilon=1e-3,
        window=4,
    ) == FrameVerdict.STALLED


def test_oscillating_trend() -> None:
    assert classify_trend(
        (1.0, 2.0, 1.0, 2.0)
    ) == FrameVerdict.OSCILLATING


def test_flat_sequence_is_not_oscillation() -> None:
    assert classify_trend(
        (1.0, 1.0, 1.0, 1.0)
    ) == FrameVerdict.STALLED


def test_budget_exhaustion_preserves_underlying_trend() -> None:
    assessment = assess_frame(
        meta_id="meta-budget",
        history=(1.0, 1.5, 2.0),
        target_viability=10.0,
        attempt_index=3,
        attempt_budget=3,
    )

    assert assessment.verdict == FrameVerdict.BUDGET_EXHAUSTED
    assert assessment.underlying_trend == FrameVerdict.IMPROVING
    assert assessment.terminal
    assert assessment.reason_codes == (
        "ATTEMPT_BUDGET_EXHAUSTED",
        "UNDERLYING_TREND_IMPROVING",
    )


def test_meta_episode_state_is_immutable_across_frames() -> None:
    initial = MetaEpisodeState(
        meta_id="meta-clock",
        attempt_budget=3,
    )

    next_state, assessment = initial.record_frame(
        viability_value=1.0,
        target_viability=5.0,
    )

    assert initial.attempt_index == 0
    assert initial.viability_history == ()
    assert not initial.closed

    assert next_state.attempt_index == 1
    assert next_state.viability_history == (1.0,)
    assert not next_state.closed
    assert assessment.verdict == FrameVerdict.IMPROVING


def test_meta_episode_closes_on_resolution() -> None:
    state = MetaEpisodeState(
        meta_id="meta-resolve",
        attempt_budget=4,
    )

    state, _ = state.record_frame(
        viability_value=1.0,
        target_viability=3.0,
    )
    state, assessment = state.record_frame(
        viability_value=3.0,
        target_viability=3.0,
    )

    assert state.closed
    assert state.final_verdict == FrameVerdict.RESOLVED
    assert assessment.verdict == FrameVerdict.RESOLVED

    try:
        state.record_frame(
            viability_value=4.0,
            target_viability=3.0,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "Closed meta episode accepted another frame."
        )


def test_meta_episode_closes_at_attempt_budget() -> None:
    state = MetaEpisodeState(
        meta_id="meta-exhaust",
        attempt_budget=2,
    )

    state, _ = state.record_frame(
        viability_value=1.0,
        target_viability=10.0,
    )
    state, assessment = state.record_frame(
        viability_value=2.0,
        target_viability=10.0,
    )

    assert state.closed
    assert state.final_verdict == FrameVerdict.BUDGET_EXHAUSTED
    assert assessment.verdict == FrameVerdict.BUDGET_EXHAUSTED


def test_assessment_digest_is_deterministic_and_sensitive() -> None:
    first = assess_frame(
        meta_id="meta-digest",
        history=(1.0, 2.0, 3.0),
        target_viability=10.0,
        attempt_index=3,
        attempt_budget=5,
    )
    second = assess_frame(
        meta_id="meta-digest",
        history=(1.0, 2.0, 3.0),
        target_viability=10.0,
        attempt_index=3,
        attempt_budget=5,
    )
    changed = assess_frame(
        meta_id="meta-digest",
        history=(1.0, 2.0, 3.1),
        target_viability=10.0,
        attempt_index=3,
        attempt_budget=5,
    )

    assert first.digest() == second.digest()
    assert first.digest() != changed.digest()


def test_meta_state_digest_is_deterministic() -> None:
    first = MetaEpisodeState(
        meta_id="meta-state",
        attempt_budget=5,
        attempt_index=2,
        viability_history=(1.0, 2.0),
    )
    second = MetaEpisodeState(
        meta_id="meta-state",
        attempt_budget=5,
        attempt_index=2,
        viability_history=(1.0, 2.0),
    )

    assert first.digest() == second.digest()


def test_history_length_must_match_attempt_index() -> None:
    try:
        assess_frame(
            meta_id="meta-invalid",
            history=(1.0, 2.0),
            target_viability=10.0,
            attempt_index=1,
            attempt_budget=3,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Mismatched history and attempt index were accepted."
        )


def test_nonfinite_history_is_rejected() -> None:
    try:
        classify(
            (1.0, float("nan")),
            target=5.0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("NaN history was accepted.")


def test_compatibility_classifier() -> None:
    assert classify(
        (1.0, 2.0),
        target=2.0,
    ) == FrameVerdict.RESOLVED

    assert classify(
        (1.0, 2.0),
        target=5.0,
    ) == FrameVerdict.IMPROVING
