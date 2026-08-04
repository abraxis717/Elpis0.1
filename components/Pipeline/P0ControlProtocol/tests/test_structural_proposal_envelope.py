from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys

import pytest

# Import the P0 submodules without executing elpis_p0.__init__, whose broad
# convenience imports depend on unrelated full-runtime packages.  The tested
# module itself uses only the narrow P0 and fractal-spine dependencies.
import types

_P0_SRC = Path(__file__).resolve().parents[1] / "src" / "elpis_p0"
_p0_package = types.ModuleType("elpis_p0")
_p0_package.__path__ = [str(_P0_SRC)]
sys.modules.setdefault("elpis_p0", _p0_package)

from elpis_fractal_spine.structural_oracle import StructuralOracle
from elpis_fractal_spine.structural_refinement import StructuralRefinementInputV1
from elpis_p0.structural_oracle_adapter import (
    oracle_transition_to_trm_proposal,
    refinement_input_to_structural_state,
)
from elpis_p0.structural_proposal_envelope import (
    SCHEMA,
    LegacyResidual81Provenance,
    StructuralProposalEnvelopeError,
    build_structural_proposal_envelope,
    evaluate_one_step_with_evidence,
)


def make_input(*, all_void: bool = True) -> StructuralRefinementInputV1:
    grid = (0,) * 81 if all_void else (1,) * 81
    mask = (1,) * 81
    return StructuralRefinementInputV1(grid81=grid, writable_mask81=mask)


def make_envelope(*, all_void: bool = True):
    return evaluate_one_step_with_evidence(make_input(all_void=all_void))


def test_real_oracle_envelope_builds() -> None:
    envelope = make_envelope()
    assert envelope.schema == SCHEMA
    assert envelope.input_digest == envelope.proposal.input_digest
    assert envelope.candidate_count == envelope.transition_fields.valid_next_state_count
    assert envelope.legacy_residual81_provenance is (
        LegacyResidual81Provenance.VOID_MASK_RECODE_V1
    )


def test_complete_identities_are_bound() -> None:
    envelope = make_envelope()
    assert len(envelope.transition_fields.source_state_identity) == 64
    assert len(envelope.transition_fields.oracle_transition_identity) == 64
    assert len(envelope.transition_fields.canonical_target_identity) == 64
    assert len(envelope.envelope_digest) == 64


def test_candidate_count_matches_real_transition() -> None:
    input_v1 = make_input()
    state = refinement_input_to_structural_state(input_v1)
    transition = StructuralOracle().evaluate(state)
    envelope = make_envelope()
    assert envelope.candidate_count == len(transition.valid_next_states)


def test_legacy_residual_provenance_is_exact() -> None:
    envelope = make_envelope()
    expected = tuple(
        1.0 if token == 0 else 0.125
        for token in envelope.proposal.proposed_grid81
    )
    assert envelope.proposal.residual81 == expected


def test_quiescent_real_transition() -> None:
    envelope = make_envelope(all_void=False)
    assert envelope.quiescence is True
    assert envelope.candidate_count == 1
    assert envelope.proposal.halt_score == 1.0


def test_proposal_digest_tamper_rejected() -> None:
    envelope = make_envelope()
    bad_proposal = replace(envelope.proposal, digest="0" * 64)
    with pytest.raises(StructuralProposalEnvelopeError, match="proposal digest mismatch"):
        replace(envelope, proposal=bad_proposal)


def test_input_digest_mismatch_rejected() -> None:
    envelope = make_envelope()
    with pytest.raises(StructuralProposalEnvelopeError, match="input_digest"):
        replace(envelope, input_digest="0" * 64)


def test_residual_tamper_rejected() -> None:
    envelope = make_envelope()
    residual = list(envelope.proposal.residual81)
    residual[0] = 0.5
    bad_proposal = replace(envelope.proposal, residual81=tuple(residual))
    # Recompute the legacy proposal digest to prove provenance validation is independent.
    from elpis_p0.canonical import digest

    bad_proposal = replace(
        bad_proposal,
        digest=digest(
            {
                "input_digest": bad_proposal.input_digest,
                "proposed_grid81": bad_proposal.proposed_grid81,
                "residual81": bad_proposal.residual81,
                "halt_score": bad_proposal.halt_score,
                "expansion_cells": bad_proposal.expansion_cells,
                "rationale": bad_proposal.rationale,
            }
        ),
    )
    with pytest.raises(StructuralProposalEnvelopeError, match="VOID-mask recode"):
        replace(envelope, proposal=bad_proposal)


def test_candidate_count_tamper_rejected() -> None:
    envelope = make_envelope()
    with pytest.raises(StructuralProposalEnvelopeError, match="candidate_count"):
        replace(envelope, candidate_count=envelope.candidate_count + 1)


def test_rationale_mismatch_rejected() -> None:
    envelope = make_envelope()
    with pytest.raises(StructuralProposalEnvelopeError, match="rationale"):
        replace(envelope, rationale_codes=("OTHER",))


def test_envelope_digest_tamper_rejected() -> None:
    envelope = make_envelope()
    with pytest.raises(StructuralProposalEnvelopeError, match="envelope digest"):
        replace(envelope, envelope_digest="0" * 64)


def test_builder_rejects_wrong_canonical_grid() -> None:
    input_v1 = make_input()
    state = refinement_input_to_structural_state(input_v1)
    transition = StructuralOracle().evaluate(state)
    proposal = oracle_transition_to_trm_proposal(
        transition, input_digest=input_v1.combined_digest
    )
    bad_grid = list(proposal.proposed_grid81)
    bad_grid[0] = (bad_grid[0] + 1) % 10
    bad_proposal = replace(proposal, proposed_grid81=tuple(bad_grid))
    with pytest.raises(StructuralProposalEnvelopeError, match="canonical target"):
        build_structural_proposal_envelope(
            state=state,
            transition=transition,
            proposal=bad_proposal,
            input_digest=input_v1.combined_digest,
        )


def test_depth_changes_complete_source_identity() -> None:
    input_v1 = make_input()
    first = evaluate_one_step_with_evidence(input_v1, depth=0)
    second = evaluate_one_step_with_evidence(input_v1, depth=1)
    assert (
        first.transition_fields.source_state_identity
        != second.transition_fields.source_state_identity
    )


def test_replay_is_deterministic() -> None:
    first = make_envelope()
    second = make_envelope()
    assert first == second


def test_fresh_process_replay() -> None:
    # The test command supplies authoritative paths. Preserve them in children.
    current_pythonpath = os.environ["PYTHONPATH"]
    p0_src = str(_P0_SRC)
    code = f"""
import sys, types
pkg = types.ModuleType('elpis_p0')
pkg.__path__ = [{p0_src!r}]
sys.modules['elpis_p0'] = pkg
from elpis_fractal_spine.structural_refinement import StructuralRefinementInputV1
from elpis_p0.structural_proposal_envelope import evaluate_one_step_with_evidence
x = StructuralRefinementInputV1(grid81=(0,)*81, writable_mask81=(1,)*81)
print(evaluate_one_step_with_evidence(x).envelope_digest)
"""
    outputs = []
    for seed in ("0", "977", "1954"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = seed
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = current_pythonpath
        proc = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            text=True,
            capture_output=True,
            env=env,
        )
        outputs.append(proc.stdout.strip())
    assert len(set(outputs)) == 1


def test_no_existing_adapter_api_is_modified() -> None:
    from elpis_p0.structural_oracle_adapter import OneStepAdapterResult, evaluate_one_step

    result = evaluate_one_step(make_input())
    assert isinstance(result, OneStepAdapterResult)
    assert not hasattr(result, "transition_fields")
