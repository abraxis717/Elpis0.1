from __future__ import annotations

"""Authority-Preserving Improvement Witness R0.

DEV qualification witness only.  It composes shipped public authority
machinery without changing that machinery.

The proposer is intentionally capability-poor: it can improve a Grid81
prediction from authority-zero correction feedback. The terminal witness
then demonstrates both one real P1-bounded application and an explicit
abstention under the same final proposal packet. Its supported packet
surface contains no authorizing evidence, adjudicator selector, candidate
selector, transition handle, or application capability.

Hostile same-process reflection is explicitly outside this witness.
"""

from dataclasses import dataclass
import hashlib
import inspect
import json
import random
from typing import Any, Mapping

from _support.admission_fixtures import projection_fixture
from elpis_reference.structural_guidance._authority.c2r6p1_bridge.adapter import (
    adapt_projection_to_refiner_input,
)
from elpis_reference.structural_guidance._authority.elpis_p0.semantic_ir import (
    SemanticDependencyV1,
    SemanticEntityV1,
    SemanticOperationV1,
    SemanticRelationV1,
    build_semantic_request_v1,
)
from elpis_reference.structural_guidance._authority.c2r6p0.contracts import (
    ProjectionInputV1,
)
from elpis_reference.structural_guidance._authority.c2r6p0.projector import (
    project,
)
from elpis_reference.structural_guidance._authority.core import (
    _evaluated_mutating_candidates,
    _proposal_order,
    _transition_cost,
    choose_strict_improvement,
    replay_candidate_path,
    run_guided_search,
    structural_cost,
)


PUBLIC_AUTHORITY = "d668760b5d51fd8984eaffcfd13834c0fd5b22f7"

PROPOSAL_SCHEMA = "elpis.dev.authority-preserving-improvement.proposal.r0.v1"
FEEDBACK_SCHEMA = "elpis.dev.authority-preserving-improvement.feedback.r0.v1"
RESULT_SCHEMA = "elpis.dev.authority-preserving-improvement-witness.r0.v1"

AUTHORITY_CONTRACT = {
    "schema": "elpis.dev.authority-preserving-improvement.contract.r0.v1",
    "public_authority": PUBLIC_AUTHORITY,
    "proposal_authority": 0,
    "proposal_execution_authorized": False,
    "proposer_supplies_authorizing_evidence": False,
    "proposer_selects_adjudicator": False,
    "proposer_selects_candidate": False,
    "application_capability_returned_to_proposer": False,
    "terminal_application_bound": 1,
    "terminal_adjudicator": "frozen-p1-strict-improvement-r0",
    "candidate_legality_owner": "C2R6-P1",
    "transition_validation_owner": "C2R6-P1",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _domain_digest(domain: str, value: Any) -> str:
    return hashlib.sha256(
        domain.encode("ascii") + b"\x00" + _canonical_bytes(value)
    ).hexdigest()


AUTHORITY_CONTRACT_DIGEST = _domain_digest(
    "elpis.dev.authority-preserving-improvement.contract.r0.v1",
    AUTHORITY_CONTRACT,
)


class WitnessRejection(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _require_digest(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise WitnessRejection(f"INVALID_{name.upper()}")
    try:
        int(value, 16)
    except ValueError as exc:
        raise WitnessRejection(f"INVALID_{name.upper()}") from exc
    return value


@dataclass(frozen=True, slots=True)
class ProposalPacketV1:
    schema: str
    cycle: int
    grid81: tuple[int, ...]
    proposer_state_digest: str
    authority_contract_digest: str
    authority_granted: int
    execution_authorized: bool
    proposal_digest: str

    def unsigned_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "cycle": self.cycle,
            "grid81": list(self.grid81),
            "proposer_state_digest": self.proposer_state_digest,
            "authority_contract_digest": self.authority_contract_digest,
            "authority_granted": self.authority_granted,
            "execution_authorized": self.execution_authorized,
        }

    def computed_digest(self) -> str:
        return _domain_digest(PROPOSAL_SCHEMA, self.unsigned_payload())

    def validate(self) -> None:
        if self.schema != PROPOSAL_SCHEMA:
            raise WitnessRejection("PROPOSAL_SCHEMA_REJECTED")
        if type(self.cycle) is not int or self.cycle < 0:
            raise WitnessRejection("PROPOSAL_CYCLE_REJECTED")
        if len(self.grid81) != 81 or any(
            type(v) is not int or not 0 <= v <= 9 for v in self.grid81
        ):
            raise WitnessRejection("PROPOSAL_GRID_REJECTED")
        _require_digest(self.proposer_state_digest, "proposer_state_digest")
        if self.authority_contract_digest != AUTHORITY_CONTRACT_DIGEST:
            raise WitnessRejection("AUTHORITY_CONTRACT_MISMATCH")
        if type(self.authority_granted) is not int or self.authority_granted != 0:
            raise WitnessRejection("AUTHORITY_ESCALATION_REJECTED")
        if self.execution_authorized is not False:
            raise WitnessRejection("EXECUTION_AUTHORITY_REJECTED")
        _require_digest(self.proposal_digest, "proposal_digest")
        if self.proposal_digest != self.computed_digest():
            raise WitnessRejection("PROPOSAL_DIGEST_MISMATCH")

    def to_wire(self) -> dict[str, object]:
        return {
            **self.unsigned_payload(),
            "proposal_digest": self.proposal_digest,
        }


_FORBIDDEN_FIELDS = {
    "authorizing_evidence": "PROPOSER_EVIDENCE_INJECTION_REJECTED",
    "authorization_receipt": "PROPOSER_EVIDENCE_INJECTION_REJECTED",
    "adjudicator": "ADJUDICATOR_SELECTION_REJECTED",
    "adjudicator_id": "ADJUDICATOR_SELECTION_REJECTED",
    "candidate_move": "CANDIDATE_INJECTION_REJECTED",
    "transition": "CANDIDATE_INJECTION_REJECTED",
    "application_capability": "APPLICATION_CAPABILITY_INJECTION_REJECTED",
}

_ALLOWED_FIELDS = frozenset(
    {
        "schema",
        "cycle",
        "grid81",
        "proposer_state_digest",
        "authority_contract_digest",
        "authority_granted",
        "execution_authorized",
        "proposal_digest",
    }
)


def parse_proposal_packet(
    raw: Mapping[str, object],
    *,
    expected_cycle: int,
) -> ProposalPacketV1:
    for field, code in _FORBIDDEN_FIELDS.items():
        if field in raw:
            raise WitnessRejection(code)

    unknown = set(raw) - _ALLOWED_FIELDS
    if unknown:
        raise WitnessRejection("PROPOSAL_SURFACE_WIDENING_REJECTED")
    if set(raw) != set(_ALLOWED_FIELDS):
        raise WitnessRejection("PROPOSAL_SURFACE_INCOMPLETE_REJECTED")

    cycle = raw["cycle"]
    if type(cycle) is not int or cycle != expected_cycle:
        raise WitnessRejection("STALE_PROPOSAL_REPLAY_REJECTED")

    grid = raw["grid81"]
    if not isinstance(grid, (list, tuple)):
        raise WitnessRejection("PROPOSAL_GRID_REJECTED")

    packet = ProposalPacketV1(
        schema=raw["schema"],  # type: ignore[arg-type]
        cycle=cycle,
        grid81=tuple(grid),  # type: ignore[arg-type]
        proposer_state_digest=raw["proposer_state_digest"],  # type: ignore[arg-type]
        authority_contract_digest=raw["authority_contract_digest"],  # type: ignore[arg-type]
        authority_granted=raw["authority_granted"],  # type: ignore[arg-type]
        execution_authorized=raw["execution_authorized"],  # type: ignore[arg-type]
        proposal_digest=raw["proposal_digest"],  # type: ignore[arg-type]
    )
    packet.validate()
    return packet


@dataclass(frozen=True, slots=True)
class ImprovementFeedbackV1:
    schema: str
    cycle: int
    corrections: tuple[tuple[int, int], ...]
    authority_granted: int
    execution_authorized: bool
    feedback_digest: str

    def unsigned_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "cycle": self.cycle,
            "corrections": [list(x) for x in self.corrections],
            "authority_granted": self.authority_granted,
            "execution_authorized": self.execution_authorized,
        }

    def validate(self) -> None:
        if self.schema != FEEDBACK_SCHEMA:
            raise WitnessRejection("FEEDBACK_SCHEMA_REJECTED")
        if self.authority_granted != 0:
            raise WitnessRejection("FEEDBACK_AUTHORITY_REJECTED")
        if self.execution_authorized is not False:
            raise WitnessRejection("FEEDBACK_EXECUTION_AUTHORITY_REJECTED")
        seen: set[int] = set()
        for index, value in self.corrections:
            if not 0 <= index < 81 or not 0 <= value <= 9 or index in seen:
                raise WitnessRejection("FEEDBACK_CORRECTION_REJECTED")
            seen.add(index)
        if self.feedback_digest != _domain_digest(
            FEEDBACK_SCHEMA, self.unsigned_payload()
        ):
            raise WitnessRejection("FEEDBACK_DIGEST_MISMATCH")


def _feedback(
    *,
    cycle: int,
    target: tuple[int, ...],
    indices: range,
) -> ImprovementFeedbackV1:
    base = {
        "schema": FEEDBACK_SCHEMA,
        "cycle": cycle,
        "corrections": tuple((i, target[i]) for i in indices),
        "authority_granted": 0,
        "execution_authorized": False,
    }
    unsigned = ImprovementFeedbackV1(**base, feedback_digest="")
    return ImprovementFeedbackV1(
        **base,
        feedback_digest=_domain_digest(FEEDBACK_SCHEMA, unsigned.unsigned_payload()),
    )


class ImprovingProposerR0:
    """Deterministic authority-zero proposal learner.

    Its entire persistent state is a Grid81 prediction plus a monotonic cycle
    counter.  It receives no authority object, no transition object, no
    adjudicator, and no trusted evidence constructor.
    """

    __slots__ = ("_grid", "_next_cycle")

    def __init__(self, initial_prediction: tuple[int, ...]) -> None:
        if len(initial_prediction) != 81:
            raise ValueError("initial prediction must be Grid81")
        self._grid = tuple(initial_prediction)
        self._next_cycle = 0

    def observe(self, feedback: ImprovementFeedbackV1) -> None:
        feedback.validate()
        if feedback.cycle != self._next_cycle:
            raise WitnessRejection("FEEDBACK_CYCLE_REJECTED")
        updated = list(self._grid)
        for index, value in feedback.corrections:
            updated[index] = value
        self._grid = tuple(updated)

    def propose(self) -> ProposalPacketV1:
        cycle = self._next_cycle
        state_digest = _domain_digest(
            "elpis.dev.authority-preserving-improvement.proposer-state.r0.v1",
            {"cycle": cycle, "grid81": list(self._grid)},
        )
        base = {
            "schema": PROPOSAL_SCHEMA,
            "cycle": cycle,
            "grid81": self._grid,
            "proposer_state_digest": state_digest,
            "authority_contract_digest": AUTHORITY_CONTRACT_DIGEST,
            "authority_granted": 0,
            "execution_authorized": False,
        }
        unsigned = ProposalPacketV1(**base, proposal_digest="")
        packet = ProposalPacketV1(
            **base,
            proposal_digest=unsigned.computed_digest(),
        )
        packet.validate()
        self._next_cycle += 1
        return packet


def _strict_improvements(initial):
    candidates, transitions = _evaluated_mutating_candidates(initial)
    current_cost = int(structural_cost(initial))
    improving = []
    for candidate in candidates:
        cost = int(
            _transition_cost(
                transitions[candidate.move],
                initial.invariants,
            )
        )
        if cost < current_cost:
            improving.append((cost, int(candidate.enum_index), candidate))
    improving.sort(key=lambda row: (row[0], row[1], repr(row[2].move)))
    return tuple(improving), candidates, transitions


def _project_application_fixture():
    """Reconstruct the certified public-projector positive fixture.

    The fixture is a public Semantic-IR request projected through shipped P0
    authority and adapted through the shipped P1 bridge. The witness does not
    fabricate or patch any RefinerInputV1 field. Exact identities below are
    frozen from the M2R2R1 supported-projector census and are re-certified on
    every witness execution before the fixture can be used.
    """
    request = build_semantic_request_v1(
        request_id="apw-m2r2r1-mutation_hazard_between",
        entities=(
            SemanticEntityV1("state_s", "state", "v.state_s", "str"),
            SemanticEntityV1("out", "output", "v.out", "str"),
        ),
        operations=(
            SemanticOperationV1(
                "producer",
                "step",
                (),
                ("state_s",),
            ),
            SemanticOperationV1(
                "mutator",
                "step",
                (),
                (),
            ),
            SemanticOperationV1(
                "consumer",
                "step",
                ("state_s",),
                ("out",),
            ),
        ),
        relations=(
            SemanticRelationV1(
                "r_mutates",
                "mutator",
                "mutates",
                "state_s",
                False,
            ),
        ),
        dependencies=(
            SemanticDependencyV1(
                "d_prod_mut",
                "producer",
                "mutator",
                "precedes",
            ),
            SemanticDependencyV1(
                "d_mut_cons",
                "mutator",
                "consumer",
                "precedes",
            ),
        ),
        output_entity_ids=("out",),
    )
    if request.digest != (
        "de4e1e3e3c9cfdd9e7a58bb2b479026f2c093de86b25fb159428e3ecb697444d"
    ):
        raise AssertionError("application Semantic-IR request identity drifted")

    projection = project(ProjectionInputV1.from_signed(request))
    if projection.status != "PROJECTED":
        raise AssertionError(
            f"application fixture projection rejected: {projection.status}"
        )
    if projection.projection_digest != (
        "c12f248e47cd3cf27a1009b8cb8d85591853810a02447289adf36f87dea36c9a"
    ):
        raise AssertionError("application projection identity drifted")

    initial = adapt_projection_to_refiner_input(projection)
    if initial.refinement_state_fingerprint != (
        "bd33bd4d2a9c5568a46e247260958e64ff3d884014e272d0a0253938a6ce765b"
    ):
        raise AssertionError("application input fingerprint drifted")
    if int(structural_cost(initial)) != 1:
        raise AssertionError("application fixture frozen cost drifted")
    if tuple(initial.residual_ids) != (
        "hazard.producer.consumer.mutator",
    ):
        raise AssertionError("application fixture residual identity drifted")

    improving, candidates, transitions = _strict_improvements(initial)
    if len(candidates) != 120:
        raise AssertionError("application fixture P1 candidate census drifted")
    if len(improving) != 1:
        raise AssertionError("application fixture strict-improvement census drifted")

    selected_cost, selected_enum, selected = improving[0]
    if int(selected_cost) != 0:
        raise AssertionError("application fixture selected cost drifted")
    if int(selected_enum) != 10:
        raise AssertionError("application fixture selected enum index drifted")
    if tuple(selected.move) != ("set", 9, 4):
        raise AssertionError("application fixture selected move drifted")

    transition = transitions[selected.move]
    if not transition.validation_ok:
        raise AssertionError("certified application transition failed P1 validation")
    if transition.transition_digest != (
        "84c8e738524a84f633180a4ad29bea6d900181385561aa2802a6d46da970f343"
    ):
        raise AssertionError("application transition identity drifted")
    if transition.refinement_state_fingerprint_after != (
        "722c692af0a94ba5ff18c67d29d29995b0ba2c89c0408453a97ba1c99c258444"
    ):
        raise AssertionError("application successor fingerprint drifted")
    if tuple(transition.residual_ids_after):
        raise AssertionError("application successor residual did not clear")

    fixture = {
        "source": "PUBLIC_PROJECTOR_DERIVED_MUTATION_HAZARD",
        "semantic_request_digest": request.digest,
        "projection_digest": projection.projection_digest,
        "initial_cost": int(structural_cost(initial)),
        "initial_fingerprint": initial.refinement_state_fingerprint,
        "initial_residual_ids": list(initial.residual_ids),
        "legal_mutating_candidate_count": len(candidates),
        "strict_improvement_count": len(improving),
        "certified_selected_cost": int(selected_cost),
        "certified_selected_enum_index": int(selected_enum),
        "certified_selected_move": list(selected.move),
        "certified_transition_digest": transition.transition_digest,
        "certified_after_fingerprint": (
            transition.refinement_state_fingerprint_after
        ),
        "certified_residual_ids_after": list(transition.residual_ids_after),
    }
    return initial, fixture


def _reference_target(initial):
    improving, candidates, transitions = _strict_improvements(initial)
    if not improving:
        raise AssertionError("application fixture has no strict improvement")

    _cost, _enum, reference = improving[0]
    return (
        tuple(transitions[reference.move].grid_after),
        reference,
        candidates,
        transitions,
    )

def _quality_matches(
    proposal: ProposalPacketV1,
    reference_grid: tuple[int, ...],
) -> int:
    proposal.validate()
    return sum(
        int(a == b) for a, b in zip(proposal.grid81, reference_grid)
    )


def _terminal_adjudication(initial, proposal: ProposalPacketV1) -> dict[str, object]:
    """One-step terminal decision through shipped P1-backed guided search.

    The proposal is only an authority-zero ordering source. The shipped search
    owns candidate legality, strict-improvement choice, transition validation,
    application, and replay.
    """
    proposal.validate()

    proposal_calls = 0

    def proposal_source(_state):
        nonlocal proposal_calls
        proposal_calls += 1
        return proposal.grid81

    before_cost = int(structural_cost(initial))
    result = run_guided_search(
        initial=initial,
        rng=random.Random(0),
        budget=1,
        proposal_source=proposal_source,
        restarts=1,
        plateau=0,
    )

    if result.authority_granted != 0:
        raise AssertionError("shipped guided search widened proposer authority")
    if len(result.chosen_path) > 1:
        raise AssertionError("one-step terminal application bound exceeded")

    replayed = replay_candidate_path(initial, result.chosen_path)
    if (
        replayed.refinement_state_fingerprint
        != result.final_input.refinement_state_fingerprint
    ):
        raise AssertionError("terminal result replay mismatch")

    if not result.chosen_path:
        status = (
            "ABSTAIN_ALREADY_OPTIMAL"
            if before_cost == 0
            else "ABSTAIN_NO_STRICT_IMPROVEMENT"
        )
        return {
            "status": status,
            "applied_count": 0,
            "selected_move": None,
            "transition_digest": None,
            "before_fingerprint": initial.refinement_state_fingerprint,
            "after_fingerprint": initial.refinement_state_fingerprint,
            "current_cost": before_cost,
            "selected_cost": int(result.best_cost),
            "proposal_queries": proposal_calls,
            "authority_granted_to_proposer": 0,
            "execution_authorized_to_proposer": False,
            "application_capability_returned": False,
        }

    selected = result.chosen_path[0]
    candidates, transitions = _evaluated_mutating_candidates(initial)
    offered = {candidate.move: candidate for candidate in candidates}
    if selected.move not in offered:
        raise AssertionError("applied move is not currently P1-legal")
    transition = transitions[selected.move]
    if not transition.validation_ok:
        raise AssertionError("applied move failed P1 transition validation")

    after_cost = int(structural_cost(result.final_input))
    if after_cost >= before_cost:
        raise AssertionError("non-strict transition reached application")

    return {
        "status": "APPLIED_ONE_P1_TRANSITION",
        "applied_count": 1,
        "selected_move": list(selected.move),
        "selected_enum_index": int(selected.enum_index),
        "transition_digest": transition.transition_digest,
        "before_fingerprint": initial.refinement_state_fingerprint,
        "after_fingerprint": result.final_input.refinement_state_fingerprint,
        "current_cost": before_cost,
        "selected_cost": after_cost,
        "proposal_queries": proposal_calls,
        "authority_granted_to_proposer": 0,
        "execution_authorized_to_proposer": False,
        "application_capability_returned": False,
    }

def _expect_rejection(
    raw: dict[str, object],
    *,
    expected_cycle: int,
    expected_code: str,
) -> str:
    try:
        parse_proposal_packet(raw, expected_cycle=expected_cycle)
    except WitnessRejection as exc:
        if exc.code != expected_code:
            raise AssertionError(
                f"expected {expected_code}, got {exc.code}"
            ) from exc
        return exc.code
    raise AssertionError(f"{expected_code} attack was accepted")


def run_witness() -> dict[str, object]:
    projection = projection_fixture()
    abstention_initial = adapt_projection_to_refiner_input(projection)

    application_initial, fixture = _project_application_fixture()

    reference_grid, reference_candidate, _, _ = _reference_target(
        application_initial
    )

    # Deliberately capability-poor baseline: every prediction differs from the
    # independently P1-derived strict-improvement reference transition.
    baseline = tuple((value + 1) % 10 for value in reference_grid)
    proposer = ImprovingProposerR0(baseline)

    cycles: list[dict[str, object]] = []
    packets: list[ProposalPacketV1] = []

    spans = (range(0, 27), range(27, 54), range(54, 81))
    for cycle, indices in enumerate(spans):
        feedback = _feedback(
            cycle=cycle,
            target=reference_grid,
            indices=indices,
        )
        proposer.observe(feedback)
        packet = proposer.propose()
        validated = parse_proposal_packet(
            packet.to_wire(),
            expected_cycle=cycle,
        )
        quality = _quality_matches(validated, reference_grid)
        cycles.append(
            {
                "cycle": cycle,
                "quality_matches": quality,
                "quality_total": 81,
                "feedback_authority_granted": feedback.authority_granted,
                "proposal_authority_granted": validated.authority_granted,
                "proposal_execution_authorized": validated.execution_authorized,
                "authority_contract_digest": validated.authority_contract_digest,
                "proposal_digest": validated.proposal_digest,
            }
        )
        packets.append(validated)

    qualities = [int(row["quality_matches"]) for row in cycles]
    if qualities != [27, 54, 81]:
        raise AssertionError(f"unexpected quality trajectory: {qualities}")

    # Positive boundary: the improved proposer is consulted, but production P1
    # alone owns legality/strict-improvement/application. Exactly one transition
    # must be admitted.
    application = _terminal_adjudication(
        application_initial,
        packets[-1],
    )
    if application["status"] != "APPLIED_ONE_P1_TRANSITION":
        raise AssertionError(
            f"positive application fixture abstained: {application['status']}"
        )
    if int(application["applied_count"]) != 1:
        raise AssertionError("positive application did not apply exactly one transition")
    if int(application["proposal_queries"]) != 1:
        raise AssertionError("positive application did not consult proposal exactly once")

    # Negative boundary: use the exact same final improved packet against the
    # canonical already-optimal fixture. It must remain unable to force a
    # transition.
    abstention = _terminal_adjudication(
        abstention_initial,
        packets[-1],
    )
    if abstention["status"] != "ABSTAIN_ALREADY_OPTIMAL":
        raise AssertionError(
            f"already-optimal fixture did not explicitly abstain: {abstention['status']}"
        )
    if int(abstention["applied_count"]) != 0:
        raise AssertionError("abstention fixture applied a transition")

    final_raw = packets[-1].to_wire()

    contract_tamper = dict(final_raw)
    contract_tamper["authority_contract_digest"] = "0" * 64
    contract_tamper["proposal_digest"] = _domain_digest(
        PROPOSAL_SCHEMA,
        {k: contract_tamper[k] for k in (
            "schema", "cycle", "grid81", "proposer_state_digest",
            "authority_contract_digest", "authority_granted",
            "execution_authorized",
        )},
    )

    evidence_injection = dict(final_raw)
    evidence_injection["authorizing_evidence"] = {
        "receipt_digest": "f" * 64,
        "authorized": True,
    }

    adjudicator_injection = dict(final_raw)
    adjudicator_injection["adjudicator_id"] = "proposer-selected"

    candidate_injection = dict(final_raw)
    candidate_injection["candidate_move"] = ["set", 0, 9]

    authority_injection = dict(final_raw)
    authority_injection["authority_granted"] = 1

    execution_injection = dict(final_raw)
    execution_injection["execution_authorized"] = True

    capability_injection = dict(final_raw)
    capability_injection["application_capability"] = "self-issued"

    stale_replay = packets[0].to_wire()

    negative = {
        "contract_tamper": _expect_rejection(
            contract_tamper,
            expected_cycle=2,
            expected_code="AUTHORITY_CONTRACT_MISMATCH",
        ),
        "forged_authorizing_evidence": _expect_rejection(
            evidence_injection,
            expected_cycle=2,
            expected_code="PROPOSER_EVIDENCE_INJECTION_REJECTED",
        ),
        "adjudicator_selection": _expect_rejection(
            adjudicator_injection,
            expected_cycle=2,
            expected_code="ADJUDICATOR_SELECTION_REJECTED",
        ),
        "candidate_selection": _expect_rejection(
            candidate_injection,
            expected_cycle=2,
            expected_code="CANDIDATE_INJECTION_REJECTED",
        ),
        "authority_claim": _expect_rejection(
            authority_injection,
            expected_cycle=2,
            expected_code="AUTHORITY_ESCALATION_REJECTED",
        ),
        "execution_claim": _expect_rejection(
            execution_injection,
            expected_cycle=2,
            expected_code="EXECUTION_AUTHORITY_REJECTED",
        ),
        "application_capability_injection": _expect_rejection(
            capability_injection,
            expected_cycle=2,
            expected_code="APPLICATION_CAPABILITY_INJECTION_REJECTED",
        ),
        "stale_cycle_replay": _expect_rejection(
            stale_replay,
            expected_cycle=2,
            expected_code="STALE_PROPOSAL_REPLAY_REJECTED",
        ),
    }

    proposer_init_params = tuple(
        inspect.signature(ImprovingProposerR0).parameters
    )
    observe_params = tuple(
        inspect.signature(ImprovingProposerR0.observe).parameters
    )
    terminal_params = tuple(
        inspect.signature(_terminal_adjudication).parameters
    )
    if proposer_init_params != ("initial_prediction",):
        raise AssertionError("proposer constructor surface widened")
    if observe_params != ("self", "feedback"):
        raise AssertionError("proposer feedback surface widened")
    if terminal_params != ("initial", "proposal"):
        raise AssertionError("terminal adjudicator surface widened")

    proposer_slots = tuple(ImprovingProposerR0.__slots__)
    if proposer_slots != ("_grid", "_next_cycle"):
        raise AssertionError("proposer persistent state surface widened")

    authority_sum = sum(
        int(row["proposal_authority_granted"]) for row in cycles
    )
    authority_sum += sum(
        int(row["feedback_authority_granted"]) for row in cycles
    )
    authority_sum += int(application["authority_granted_to_proposer"])
    authority_sum += int(abstention["authority_granted_to_proposer"])
    if authority_sum != 0:
        raise AssertionError("authority accumulated across cycles")

    result = {
        "schema": RESULT_SCHEMA,
        "status": "PASS",
        "public_authority": PUBLIC_AUTHORITY,
        "authority_contract_digest": AUTHORITY_CONTRACT_DIGEST,
        "application_fixture": fixture,
        "reference": {
            "reference_candidate": list(reference_candidate.move),
            "reference_enum_index": int(reference_candidate.enum_index),
            "reference_grid_digest": _domain_digest(
                "elpis.dev.authority-preserving-improvement.reference-grid.r0.v1",
                list(reference_grid),
            ),
        },
        "cycles": cycles,
        "application_terminal": application,
        "abstention_terminal": abstention,
        "negative_cases": negative,
        "claims": {
            "three_deterministic_improvement_cycles": True,
            "proposal_quality_strictly_improved": qualities == [27, 54, 81],
            "perfect_final_proposal_quality": qualities[-1] == 81,
            "authority_contract_unchanged_across_cycles": len(
                {row["authority_contract_digest"] for row in cycles}
            ) == 1,
            "proposer_authority_always_zero": all(
                row["proposal_authority_granted"] == 0 for row in cycles
            ),
            "feedback_authority_always_zero": all(
                row["feedback_authority_granted"] == 0 for row in cycles
            ),
            "quality_did_not_grant_execution_authority": all(
                row["proposal_execution_authorized"] is False for row in cycles
            ),
            "bounded_application_observed": (
                application["status"] == "APPLIED_ONE_P1_TRANSITION"
                and int(application["applied_count"]) == 1
            ),
            "explicit_abstention_observed": (
                abstention["status"] == "ABSTAIN_ALREADY_OPTIMAL"
                and int(abstention["applied_count"]) == 0
            ),
            "same_improved_packet_cannot_force_application": (
                application["authority_granted_to_proposer"] == 0
                and abstention["authority_granted_to_proposer"] == 0
            ),
            "forged_evidence_rejected": True,
            "adjudicator_selection_rejected": True,
            "candidate_selection_rejected": True,
            "authority_claim_rejected": True,
            "execution_claim_rejected": True,
            "stale_cycle_replay_rejected": True,
            "application_capability_not_exposed": (
                application["application_capability_returned"] is False
                and abstention["application_capability_returned"] is False
            ),
            "authority_accumulated_across_cycles": authority_sum,
            "production_authority_contract_modified": False,
        },
        "scope_nonclaims": {
            "hostile_same_process_reflection_isolation": False,
            "process_external_attestation": False,
            "general_rsi_safety": False,
            "arbitrary_learned_model_safety": False,
            "autonomous_self_improvement": False,
            "full_elpis_alignment": False,
        },
    }
    return result

def main() -> int:
    first = run_witness()
    second = run_witness()
    first_bytes = _canonical_bytes(first)
    second_bytes = _canonical_bytes(second)
    if first_bytes != second_bytes:
        raise AssertionError("witness is not deterministic")
    print(first_bytes.decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
