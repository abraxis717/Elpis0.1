from __future__ import annotations

from pathlib import Path

from c2r6p1_bridge.adapter import (
    adapt_projection_to_refiner_input,
)

from guided_refiner import (
    EXPECTED_CHECKPOINT_SHA256,
    FrozenTRM0ProposalSource,
    TRM0GuidedRefiner,
    replay_candidate_path,
)

CHECKPOINT = Path(
    "/mnt/primesauce/Elpis0.1/"
    "work/C2R7C_TRM0_FROZEN_952d3bff676f/"
    "best.pt"
)


def test_live_frozen_trm0_proposal_and_tiny_search(
    one_projected,
):
    ri = adapt_projection_to_refiner_input(
        one_projected
    )

    source = FrozenTRM0ProposalSource.from_checkpoint(
        CHECKPOINT,
        expected_sha256=EXPECTED_CHECKPOINT_SHA256,
    )

    proposal = source(ri)

    assert len(proposal) == 81
    assert source.checkpoint_epoch == 320
    assert (
        source.checkpoint_sha256
        == EXPECTED_CHECKPOINT_SHA256
    )

    refiner = TRM0GuidedRefiner(
        proposal_source=source,
        seed=20260904,
        budget=2,
        restarts=1,
        plateau=1,
    )

    result = refiner.refine(ri)

    replayed = replay_candidate_path(
        ri,
        result.chosen_path,
    )

    assert (
        replayed.refinement_state_fingerprint
        == result.final_input.refinement_state_fingerprint
    )
    assert result.authority_granted == 0
    assert result.stats["authority_granted"] == 0
