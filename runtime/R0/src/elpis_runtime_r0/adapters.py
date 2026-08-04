"""R0 adapters — minimal bridges between canonical components and transaction.

Each adapter:
- Imports only from the canonical R1 assembly
- Does not modify canonical source
- Is fail-closed on contract violation
- Produces deterministic output for deterministic input
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .errors import (
    R0Error,
    R0Grid81ReadError,
    R0OracleError,
    R0AdjudicatorError,
    R0DarwinianError,
    R0DecoderError,
    R0ASTValidationFailure,
)


# ---------------------------------------------------------------------------
# Canonical JSON helpers (shared with contracts)
# ---------------------------------------------------------------------------

def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest(obj: Any) -> str:
    return _sha256_hex(_canonical_bytes(obj))


# ---------------------------------------------------------------------------
# Grid81 canonical state adapter
# ---------------------------------------------------------------------------

def read_grid81_canonical_state(
    project_root: str,
) -> tuple[int, str, str, str, str]:
    """Read Grid81 canonical state via promoted reader.

    The canonical reader resolves HEAD at:
        root / "Canonical" / "Grid81" / "HEAD.json"
    The actual canonical state lives under:
        project_root / "Grid81" / "state" / "Canonical" / "Grid81"
    So we pass the Grid81 state directory as the reader root.

    Returns (generation_number, generation_raw_sha256, generation_semantic_digest,
             canonical_digest, transaction_id).
    Raises R0Grid81ReadError on any failure.
    """
    import pathlib

    try:
        from Grid81.canonical_reader import (
            load_current_grid81,
            CanonicalReadError,
        )
    except ImportError as e:
        raise R0Grid81ReadError(
            "CANNOT_IMPORT_CANONICAL_READER",
            f"Cannot import Grid81 canonical reader: {e}",
        ) from e

    # The reader expects: root/Canonical/Grid81/HEAD.json
    # Actual layout: project_root/Grid81/state/Canonical/Grid81/HEAD.json
    root = pathlib.Path(project_root) / "Grid81" / "state"

    if not root.joinpath("Canonical", "Grid81", "HEAD.json").is_file():
        raise R0Grid81ReadError(
            "GRID81_STATE_NOT_FOUND",
            f"Grid81 canonical state directory not found at {root}",
        )

    try:
        state = load_current_grid81(root)
    except CanonicalReadError as e:
        raise R0Grid81ReadError(e.code, e.detail) from e
    except Exception as e:
        raise R0Grid81ReadError("GRID81_READ_FAILED", str(e)) from e

    return (
        state.generation_number,
        state.generation_raw_sha256,
        state.generation_semantic_digest,
        state.canonical_digest,
        state.transaction_id,
    )


# ---------------------------------------------------------------------------
# P0 projection adapter
# ---------------------------------------------------------------------------

def run_p0_projection(
    request_id: str,
    prompt: str,
    domain: str = "python",
    entrypoint: str = "solution",
    parameters: tuple[str, ...] = (),
    decoder_hints: tuple[tuple[str, str], ...] = (),
) -> tuple[str, tuple[int, ...], tuple[str, ...], str]:
    """Run P0 deterministic projection.

    Returns (projection_digest, grid81, semantic_rows, features_digest).
    """
    try:
        from elpis_p0.projector import DeterministicPythonProjector
        from elpis_p0.contracts import RequestContext
    except ImportError as e:
        raise R0Error("P0_IMPORT_FAILED", str(e)) from e

    context = RequestContext(
        request_id=request_id,
        prompt=prompt,
        domain=domain,
        entrypoint=entrypoint,
        parameters=parameters,
        decoder_hints=decoder_hints,
    )

    projector = DeterministicPythonProjector()
    projection = projector.project(context)
    projection.validate()

    features_digest = _digest(list(projection.features))

    return (
        projection.digest,
        projection.grid81,
        projection.semantic_rows,
        features_digest,
    )


# ---------------------------------------------------------------------------
# Scope derivation adapter (InitialVoidScopeProvider)
# ---------------------------------------------------------------------------

def derive_scope(
    grid81: tuple[int, ...],
) -> tuple[str, tuple[int, ...], str]:
    """Derive refinement scope via InitialVoidScopeProvider.

    Returns (mask_digest, writable_mask81, scope_decision_digest).
    """
    try:
        from elpis_p0.initial_void_scope_provider import (
            InitialVoidScopeProvider,
        )
        from elpis_p0.contracts import (
            RequestContext,
            StructuralProjection,
        )
    except ImportError as e:
        raise R0Error("SCOPE_IMPORT_FAILED", str(e)) from e

    # Build minimal projection for scope derivation
    dummy_projection = StructuralProjection(
        grid81=grid81,
        semantic_rows=("x",) * 9,
        features=(),
        digest=_digest(grid81),
    )

    dummy_context = RequestContext(
        request_id="scope_derivation",
        prompt="scope",
    )

    provider = InitialVoidScopeProvider()
    decision = provider.decide_scope(
        request=dummy_context,
        projection=dummy_projection,
        logical_tick=0,
        snapshot_digest="0" * 64,
    )

    return (
        decision.mask_digest,
        decision.writable_mask81,
        decision.decision_digest,
    )


# ---------------------------------------------------------------------------
# StructuralOracle adapter
# ---------------------------------------------------------------------------

def run_oracle_transition(
    grid81: tuple[int, ...],
    writable_mask81: tuple[int, ...],
) -> tuple[str, str, bool, tuple[str, ...], tuple[str, ...], int]:
    """Run StructuralOracle on grid81 state.

    Returns (input_digest, output_digest, quiescence, violation_codes,
             rationale_codes, candidate_count).
    """
    try:
        from elpis_fractal_spine.structural_oracle import (
            StructuralOracle,
        )
        from elpis_fractal_spine.structural_semantics import (
            StructuralGrid,
            StructuralState,
        )
        from elpis_fractal_spine.structural_refinement import (
            GRID_SIZE as FRAC_GRID_SIZE,
        )
    except ImportError as e:
        raise R0OracleError("ORACLE_IMPORT_FAILED", str(e)) from e

    # Validate dimensions
    if len(grid81) != 81:
        raise R0OracleError("INVALID_GRID81", f"Length {len(grid81)} != 81")
    if len(writable_mask81) != 81:
        raise R0OracleError("INVALID_MASK81", f"Length {len(writable_mask81)} != 81")

    # Construct StructuralState
    grid = StructuralGrid(tokens=grid81)
    state = StructuralState(
        grid=grid,
        mask=writable_mask81,
        depth=0,
        provenance=None,
    )

    # Compute input digest
    input_digest = state.grid.digest()

    # Evaluate oracle
    oracle = StructuralOracle()
    transition = oracle.evaluate(state)

    # Extract results
    output_digest = transition.canonical_next_state.digest()
    quiescence = transition.quiescence
    violation_codes = transition.violation_codes
    rationale_codes = transition.rationale_codes
    candidate_count = len(transition.valid_next_states)

    return (
        input_digest,
        output_digest,
        quiescence,
        violation_codes,
        rationale_codes,
        candidate_count,
    )


# ---------------------------------------------------------------------------
# Adjudicator adapter
# ---------------------------------------------------------------------------

def run_adjudication(
    oracle_input_digest: str,
    oracle_output_digest: str,
    oracle_quiescence: bool,
    oracle_violations: tuple[str, ...],
    oracle_rationale: tuple[str, ...],
    candidate_count: int,
) -> tuple[str, str, str, tuple[str, ...]]:
    """Run structural adjudication on Oracle result.

    Constructs a minimal valid 5-proposal set representing the Oracle transition,
    runs it through the adjudicator policy, and returns the adjudication record.

    Returns (adjudication_digest, verdict, outcome, reason_codes).
    """
    try:
        from elpis_grid81_adjudication.canonical import canonical_digest
        from elpis_grid81_adjudication.input_envelope import build_input_envelope
        from elpis_grid81_adjudication.policy import adjudicate_row
        from elpis_grid81_adjudication.dispositions import build_dispositions_for_row
        from elpis_grid81_adjudication.abstention import build_abstention_record
        from elpis_grid81_adjudication.semantic_identity import compute_semantic_identity
        from elpis_grid81_adjudication.adjudication import build_adjudication_record
        from elpis_grid81_adjudication.review_request import build_review_request
    except ImportError as e:
        raise R0AdjudicatorError("ADJUDICATOR_IMPORT_FAILED", str(e)) from e

    # Construct 5 proposals from Oracle result:
    # Proposal 1: TRANSITION_EDIT (the canonical transition)
    # Proposal 2: QUIESCENCE (always present)
    # Proposal 3: TRANSITION_NOOP (null transition)
    # Proposal 4: EXPANSION_DECOMPOSITION (if expansion indicated)
    # Proposal 5: RATIONALE_DIAGNOSTIC (diagnostic)

    # Build proposal payloads
    proposals = []

    # P1: TRANSITION_EDIT — the oracle's canonical transition
    p1_payload = {
        "kind": "TRANSITION_EDIT",
        "oracle_output_digest": oracle_output_digest,
        "oracle_input_digest": oracle_input_digest,
    }
    p1_digest = _digest(p1_payload)
    proposals.append({
        "proposal_digest": p1_digest,
        "group_id": "TRANSITION_EDIT",
        "group_relevant": True,
        "admissible_for_adjudication": True,
        "evidence_digest": p1_digest,
    })

    # P2: QUIESCENCE
    p2_payload = {
        "kind": "QUIESCENCE",
        "quiescence": oracle_quiescence,
    }
    p2_digest = _digest(p2_payload)
    proposals.append({
        "proposal_digest": p2_digest,
        "group_id": "QUIESCENCE",
        "group_relevant": True,
        "admissible_for_adjudication": True,
        "evidence_digest": p2_digest,
    })

    # P3: TRANSITION_NOOP
    p3_payload = {
        "kind": "TRANSITION_NOOP",
        "oracle_input_digest": oracle_input_digest,
    }
    p3_digest = _digest(p3_payload)
    proposals.append({
        "proposal_digest": p3_digest,
        "group_id": "TRANSITION_NOOP",
        "group_relevant": True,
        "admissible_for_adjudication": True,
        "evidence_digest": p3_digest,
    })

    # P4: EXPANSION_DECOMPOSITION
    p4_payload = {
        "kind": "EXPANSION_DECOMPOSITION",
        "candidate_count": candidate_count,
    }
    p4_digest = _digest(p4_payload)
    proposals.append({
        "proposal_digest": p4_digest,
        "group_id": "EXPANSION_DECOMPOSITION",
        "group_relevant": True,
        "admissible_for_adjudication": True,
        "evidence_digest": p4_digest,
    })

    # P5: RATIONALE_DIAGNOSTIC
    p5_payload = {
        "kind": "RATIONALE_DIAGNOSTIC",
        "rationale_codes": list(oracle_rationale),
        "violation_codes": list(oracle_violations),
    }
    p5_digest = _digest(p5_payload)
    proposals.append({
        "proposal_digest": p5_digest,
        "group_id": "RATIONALE_DIAGNOSTIC",
        "group_relevant": True,
        "admissible_for_adjudication": True,
        "evidence_digest": p5_digest,
    })

    # Build conflicts (minimal: shared support between transition edit and noop)
    conflict_payload = {
        "proposal_a": p1_digest,
        "proposal_b": p3_digest,
        "conflict_kind": "SHARED_SUPPORT",
    }
    conflict_digest = _digest(conflict_payload)
    conflicts = [{
        "conflict_kind": "SHARED_SUPPORT",
        "canonical_conflict_digest": conflict_digest,
        "source_row_digest": oracle_input_digest,
    }]

    # Build ordering
    ordering_digest = _digest([p["proposal_digest"] for p in proposals])
    ordering = {
        "ordering_digest": ordering_digest,
        "source_row_digest": oracle_input_digest,
    }

    # Build row index
    row_index = {
        "source_row_digest": oracle_input_digest,
        "source_split": "r0_runtime",
    }

    # Build evidence records (identity mapping from proposals)
    evidence = [
        {
            "canonical_payload_digest": p["evidence_digest"],
            "source_row_digest": oracle_input_digest,
        }
        for p in proposals
    ]

    # Assemble source row data
    source_row_data = {
        "proposals": proposals,
        "evidence": evidence,
        "ordering": ordering,
        "conflicts": conflicts,
        "row_index": row_index,
    }

    # Build input envelope
    source_manifest_sha256 = _digest({"r0_runtime_adjudication": True})
    envelope = build_input_envelope(source_row_data, source_manifest_sha256)

    # Run adjudication policy
    policy_result = adjudicate_row(source_row_data, envelope)

    # Build dispositions
    dispositions = build_dispositions_for_row(proposals, policy_result)

    # Build abstention
    abstention = build_abstention_record(policy_result)

    # Compute semantic identity
    semantic_digest = compute_semantic_identity(
        dispositions, conflicts,
        policy_result["outcome"], policy_result["abstention"],
        policy_result["review_set"], policy_result["request_state"],
        policy_result["reason_codes"],
    )

    # Build adjudication record
    adjudication = build_adjudication_record(
        envelope, dispositions, policy_result, abstention, semantic_digest,
    )

    # Build review request
    review_request = build_review_request(
        envelope, policy_result, adjudication["adjudication_record_digest"],
    )

    # Determine verdict: accepted if REVIEW_SET_FORMED, rejected otherwise
    outcome = policy_result["outcome"]
    verdict = "ACCEPTED" if outcome in ("REVIEW_SET_FORMED", "PRESERVE_ALL") else "REJECTED"

    return (
        adjudication["adjudication_record_digest"],
        verdict,
        outcome,
        tuple(policy_result["reason_codes"]),
    )


# ---------------------------------------------------------------------------
# Darwinian episode adapter
# ---------------------------------------------------------------------------

def run_darwinian_episode(
    adjudication_digest: str,
    adjudication_verdict: str,
) -> tuple[str, str, tuple[str, ...], tuple[str, ...]]:
    """Construct and evaluate a bounded Darwinian episode.

    Returns (episode_digest, verdict, authorities_exercised, authorities_inactive).
    """
    try:
        from DarwinianMatrix.life.organism import OrganismState, ResourceQuantity
        from DarwinianMatrix.life.genotype import Genotype, IntegerGene
        from DarwinianMatrix.life.lineage import (
            LineageIdentity,
            ParentLineageRef,
        )
        from DarwinianMatrix.life.lifecycle import LifecycleState
        from DarwinianMatrix.life.fitness import FitnessObservation
        from DarwinianMatrix.life.selection import SelectionCandidateBinding
        from DarwinianMatrix.controller.verdict import (
            FrameVerdict,
            assess_frame,
        )
    except ImportError as e:
        raise R0DarwinianError("DARWINIAN_IMPORT_FAILED", str(e)) from e

    authorities_exercised = []
    authorities_inactive = []

    try:
        # 1. Genotype construction (uses IntegerGene, not free-form dict)
        gene = IntegerGene(
            name="structural_cell_0",
            value=1,
            minimum=0,
            maximum=9,
        )
        genotype = Genotype(genes=(gene,))
        genotype_digest = genotype.digest()

        # 2. LineageIdentity — founder (no parents, generation 0, no mutation seed)
        lineage = LineageIdentity(
            parents=(),
            generation=0,
            birth_tick=0,
            birth_ordinal=0,
            genotype_digest=genotype_digest,
            mutation_seed_digest=None,
        )

        # 3. OrganismState construction
        organism = OrganismState(
            lineage=lineage,
            genotype=genotype,
            energy=1000,
            resources=(ResourceQuantity(name="compute", amount=32),),
            lifecycle=LifecycleState.ALIVE,
        )
        authorities_exercised.append("organism_construction")

        # 4. Fitness evaluation
        fitness = FitnessObservation(
            window_start_tick=0,
            window_end_tick=1,
            energy_delta=0,
            survival_ticks=1,
            viable_offspring=0,
            resource_efficiency_ppm=1_000_000 if adjudication_verdict == "ACCEPTED" else 0,
            ecological_damage=0,
            failed_actions=0 if adjudication_verdict == "ACCEPTED" else 1,
        )
        authorities_exercised.append("fitness_evaluation")

        # 5. Selection candidate binding
        organism_digest = organism.digest()
        fitness_record_digest = fitness.digest()
        candidate = SelectionCandidateBinding(
            organism_id=organism.lineage.organism_id,
            organism_state_digest=organism_digest,
            genotype_digest=genotype_digest,
            fitness_record_digest=fitness_record_digest,
            scalar_fitness=1_000_000 if adjudication_verdict == "ACCEPTED" else 0,
            novelty=0,
            lifecycle=organism.lifecycle.value,
        )
        authorities_exercised.append("selection_binding")

        # 6. Frame verdict evaluation via assess_frame
        if adjudication_verdict == "ACCEPTED":
            viability = [0.95]
            target_viability = 0.5
        else:
            viability = [0.1]
            target_viability = 0.5

        assessment = assess_frame(
            meta_id="r0_meta_ep_001",
            history=viability,
            target_viability=target_viability,
            attempt_index=1,
            attempt_budget=10,
        )
        frame_verdict = assessment.verdict
        authorities_exercised.append("frame_verdict_evaluation")

        # 7. Episode archive representation
        # SelectionCandidateBinding has canonical_payload() but no digest()
        from DarwinianMatrix.life.canonical import payload_digest as dm_payload_digest
        candidate_digest = dm_payload_digest(candidate.canonical_payload())
        episode_payload = {
            "lineage_id": organism.lineage.organism_id,
            "organism_digest": organism_digest,
            "genotype_digest": genotype_digest,
            "fitness_digest": fitness_record_digest,
            "adjudication_digest": adjudication_digest,
            "frame_verdict": frame_verdict.value,
            "selection_candidate_digest": candidate_digest,
        }
        episode_digest = _digest(episode_payload)

        # Determine Darwinian verdict
        darwinian_verdict = "ACCEPTED" if frame_verdict in (
            FrameVerdict.RESOLVED, FrameVerdict.IMPROVING
        ) else "REJECTED"

        # Identify inactive authorities
        inactive = [
            "reproduction",
            "mutation",
            "retirement",
            "lineage_advancement",
            "ecology_engine",
            "climate_dynamics",
            "clamp_release",
        ]
        authorities_inactive = tuple(inactive)

        return (
            episode_digest,
            darwinian_verdict,
            tuple(authorities_exercised),
            authorities_inactive,
        )

    except Exception as e:
        raise R0DarwinianError("EPISODE_EXECUTION_FAILED", str(e)) from e


# ---------------------------------------------------------------------------
# Decoder adapter
# ---------------------------------------------------------------------------

def run_decoder(
    request_id: str,
    prompt: str,
    entrypoint: str,
    parameters: tuple[str, ...],
    structural_digest: str,
    selected_experts: tuple[str, ...],
    body_hint: str = "return None",
    max_tokens: int = 512,
) -> tuple[str, str, str]:
    """Run DeterministicPythonDecoder.

    Returns (control_plan_digest, artifact_digest, artifact_source).
    """
    try:
        from elpis_p0.decoder import DeterministicPythonDecoder
        from elpis_p0.contracts import (
            RequestContext,
            DecoderControlPlan,
        )
        from elpis_p0.canonical import digest as p0_digest
    except ImportError as e:
        raise R0DecoderError("DECODER_IMPORT_FAILED", str(e)) from e

    context = RequestContext(
        request_id=request_id,
        prompt=prompt,
        entrypoint=entrypoint,
        parameters=parameters,
        decoder_hints=(("body", body_hint),),
        max_tokens=max_tokens,
    )

    # Build decoder control plan
    body_lines = tuple(body_hint.splitlines()) or ("return None",)
    plan = DecoderControlPlan(
        backend="deterministic-python-template-v1",
        language="python",
        temperature=0.0,
        max_tokens=max_tokens,
        selected_experts=selected_experts,
        function_name=entrypoint,
        parameters=parameters,
        body_lines=body_lines,
        structural_digest=structural_digest,
        plan_digest=p0_digest({
            "backend": "deterministic-python-template-v1",
            "language": "python",
            "function_name": entrypoint,
            "parameters": parameters,
            "body_lines": body_lines,
            "structural_digest": structural_digest,
        }),
    )

    # Decode
    decoder = DeterministicPythonDecoder()
    artifact = decoder.decode(context, plan)

    return (
        plan.plan_digest,
        artifact.digest,
        artifact.source,
    )


# ---------------------------------------------------------------------------
# AST validator adapter
# ---------------------------------------------------------------------------

def run_ast_validator(
    request_id: str,
    prompt: str,
    entrypoint: str,
    artifact_source: str,
) -> tuple[bool, str, str, str]:
    """Run PythonASTValidator.

    Returns (passed, code, message, validator_id).
    """
    try:
        from elpis_p0.validators import PythonASTValidator
        from elpis_p0.contracts import (
            RequestContext,
            ArtifactCandidate,
        )
        from elpis_p0.canonical import digest as p0_digest
    except ImportError as e:
        raise R0Error("VALIDATOR_IMPORT_FAILED", str(e)) from e

    context = RequestContext(
        request_id=request_id,
        prompt=prompt,
        entrypoint=entrypoint,
    )

    artifact = ArtifactCandidate(
        language="python",
        source=artifact_source,
        digest=p0_digest({"source": artifact_source}),
    )

    validator = PythonASTValidator()
    evidence = validator.validate(context, artifact)

    return (
        evidence.passed,
        evidence.code,
        evidence.message,
        evidence.validator_id,
    )
