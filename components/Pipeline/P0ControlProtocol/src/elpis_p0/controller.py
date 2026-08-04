from __future__ import annotations

from .accounts import (
    P0ShadowRequestAccount,
)
from .canonical import digest
from .contracts import (
    BudgetAxis,
    DecoderControlPlan,
    P0RefinementError,
    P0Result,
    RequestContext,
    StructuralProjection,
    TraceEvent,
)
from .decoder import safe_identifier
from .initial_void_scope_provider import (
    InitialVoidScopeProvider,
    ScopeDerivationRecordV1,
)
from .ports import (
    DecoderPort,
    ExpertProposalPort,
    StructuralProjectorPort,
    TRMProposalPort,
    ValidatorPort,
)
from .refinement_proposer import (
    DeterministicShadowRefinementProposer,
    RefinementProposerPort,
)
from .refinement_receipt import (
    RefinementInvocationReceiptV1,
    build_receipt,
)
from .refinement_result import (
    RefinementControllerResultV1,
)
from .refinement_scope import (
    RefinementScopeDecisionV1,
    RefinementScopeProvider,
)
from .refinement_scope_builder import (
    build_refinement_input_from_scope,
)
from .refinement_validation import (
    RefinementValidationRecordV1,
    build_validation_record,
)
from .scoped_refinement_result import (
    ScopedRefinementControllerResultV1,
)


class P0Controller:
    """Controller-owned P0 execution path.

    Authority boundaries:

    - projector describes structure;
    - TRM proposes refinements and expansion markers;
    - expert router proposes candidate experts;
    - controller chooses a static allow-listed plan;
    - decoder emits one offline artifact;
    - validators assess it;
    - governance is never invoked;
    - proposed expansion is never executed;
    - proposed experts are never loaded.
    """

    def __init__(
        self,
        projector: StructuralProjectorPort,
        trm: TRMProposalPort,
        expert_proposer: ExpertProposalPort,
        decoder: DecoderPort,
        validators: tuple[
            ValidatorPort,
            ...],
        refinement_proposer: RefinementProposerPort | None = None,
        scope_provider: RefinementScopeProvider | None = None,
    ):
        if not validators:
            raise ValueError(
                "P0 requires at least one validator"
            )

        self.projector = projector
        self.trm = trm
        self.expert_proposer = (
            expert_proposer
        )
        self.decoder = decoder
        self.validators = validators
        self.refinement_proposer = (
            refinement_proposer
            if refinement_proposer is not None
            else DeterministicShadowRefinementProposer()
        )
        self.scope_provider = scope_provider

    # ------------------------------------------------------------------
    # G3.0 — derive_and_propose_refinement
    # ------------------------------------------------------------------

    def derive_and_propose_refinement(
        self,
        *,
        request: RequestContext,
        projection: StructuralProjection,
        logical_tick: int,
        snapshot_digest: str,
    ) -> ScopedRefinementControllerResultV1:
        """G3 derived refinement path.

        Operation order:
        1. Validate request, projection, tick, snapshot
        2. Invoke production scope provider exactly once
        3. Receive decision and derivation record
        4. Construct sealed P0 refinement input
        5. Invoke refinement proposer exactly once
        6. Validate structural scope exactly once
        7. Build existing Gate-2 invocation receipt
        8. Build G3 controller result binding the derivation record
        9. Return proposal-only result

        Fail-closed if no scope_provider configured.
        Does NOT retry, widen scope, fallback, call oracle,
        mutate state, apply proposal, or commit.
        """
        # 1. Validate scope provider presence — fail closed if absent
        if self.scope_provider is None:
            raise P0RefinementError(
                "BLOCKED_G30_SCOPE_PROVIDER_ABSENT: "
                "controller has no scope_provider configured; "
                "derive_and_propose_refinement requires one"
            )

        # 1b. Validate request
        if not request.request_id:
            raise ValueError(
                "request.request_id must be non-empty"
            )

        # 1c. Validate logical tick
        if logical_tick < 0:
            raise ValueError(
                f"logical_tick must be >= 0, got {logical_tick}"
            )

        # 1d. Validate snapshot digest
        if len(snapshot_digest) != 64:
            raise ValueError(
                f"snapshot_digest must be 64 hex chars, "
                f"got {len(snapshot_digest)}"
            )
        try:
            int(snapshot_digest, 16)
        except ValueError:
            raise ValueError(
                "snapshot_digest contains non-hex characters"
            )

        # 1e. Validate projection
        projection.validate()

        # 2. Invoke scope provider exactly once via decide_scope
        scope_provider = self.scope_provider
        scope_decision = scope_provider.decide_scope(
            request=request,
            projection=projection,
            logical_tick=logical_tick,
            snapshot_digest=snapshot_digest,
        )

        # 3. Construct derivation record from decision
        from .initial_void_scope_provider import (
            ScopeDerivationRecordV1,
            INITIAL_VOID_SCOPE_POLICY_ID,
            INITIAL_VOID_SCOPE_POLICY_VERSION,
            _canonical_bytes,
            _sha256_hex,
        )

        grid81 = projection.grid81
        grid_payload = {"grid81": list(grid81)}
        grid_digest = _sha256_hex(_canonical_bytes(grid_payload))
        mask_digest = scope_decision.mask_digest
        writable_count = sum(scope_decision.writable_mask81)
        locked_count = 81 - writable_count
        if writable_count == 0:
            derivation_status = "NO_WRITABLE_INITIAL_VOID_CELLS"
        else:
            derivation_status = "WRITABLE_INITIAL_VOID_CELLS"

        from .initial_void_scope_provider import (
            InitialVoidScopeProvider as _IVSP,
        )
        derivation_record = ScopeDerivationRecordV1(
            provider_id=_IVSP.provider_id,
            provider_version=_IVSP.provider_version,
            scope_policy_id=INITIAL_VOID_SCOPE_POLICY_ID,
            scope_policy_version=INITIAL_VOID_SCOPE_POLICY_VERSION,
            request_id=request.request_id,
            logical_tick=logical_tick,
            snapshot_digest=snapshot_digest,
            projection_digest=projection.digest,
            grid_digest=grid_digest,
            decision_digest=scope_decision.decision_digest,
            mask_digest=mask_digest,
            writable_count=writable_count,
            locked_count=locked_count,
            derivation_status=derivation_status,
        )

        # 4. Build P0RefinementInputV1 from scope decision
        input_envelope = build_refinement_input_from_scope(
            request=request,
            projection=projection,
            scope_decision=scope_decision,
            logical_tick=logical_tick,
            snapshot_digest=snapshot_digest,
        )

        # 5. Invoke proposer exactly once
        proposer = self.refinement_proposer
        proposal = proposer.propose_refinement(input_envelope)

        # 6. Validate structural scope exactly once
        validation = build_validation_record(
            input_envelope, proposal
        )

        # 7. Build Gate-2 invocation receipt
        receipt = build_receipt(
            request_id=request.request_id,
            logical_tick=logical_tick,
            snapshot_digest=snapshot_digest,
            projection_digest=projection.digest,
            scope_decision=scope_decision,
            input_envelope=input_envelope,
            proposer_id=proposer.proposer_id,
            proposer_version=proposer.proposer_version,
            proposal=proposal,
            validation=validation,
        )

        # 8. Build G3 controller result
        result = ScopedRefinementControllerResultV1(
            scope_decision=scope_decision,
            scope_derivation_record=derivation_record,
            input_envelope=input_envelope,
            proposal=proposal,
            validation=validation,
            receipt=receipt,
        )

        return result

    # ------------------------------------------------------------------
    # Phase F — propose_refinement integration entrypoint
    # ------------------------------------------------------------------

    def propose_refinement(
        self,
        *,
        request: RequestContext,
        projection: StructuralProjection,
        scope_decision: RefinementScopeDecisionV1,
        logical_tick: int,
        snapshot_digest: str,
    ) -> RefinementControllerResultV1:
        """Canonical refinement proposal operation.

        Operation order:
        1. Validate request and projection
        2. Validate explicit scope decision
        3. Build P0RefinementInputV1
        4. Freeze input identity
        5. Invoke proposer exactly once
        6. Verify proposal input binding
        7. Validate structural and scope locality
        8. Emit immutable validation record
        9. Emit immutable receipt
        10. Return proposal-only result

        Does NOT:
        - mutate the projection
        - mutate the scope decision
        - apply the proposed grid
        - call the proposer twice
        - retry with a wider scope
        - call the structural oracle
        - create a child
        - change budgets except for existing proposal charge
        - write ECS components directly
        """
        # 1. Validate request
        if not request.request_id:
            raise ValueError(
                "request.request_id must be non-empty"
            )

        # 2. Validate projection
        projection.validate()

        # 3. Validate scope decision presence — fail closed if absent
        if scope_decision is None:
            raise P0RefinementError(
                "BLOCKED_P0_REFINEMENT_SCOPE_ABSENT: "
                "scope decision must not be None"
            )

        # 4. Build P0RefinementInputV1 from scope decision
        input_envelope = build_refinement_input_from_scope(
            request=request,
            projection=projection,
            scope_decision=scope_decision,
            logical_tick=logical_tick,
            snapshot_digest=snapshot_digest,
        )

        # 5. Freeze input identity
        envelope_digest = input_envelope.envelope_digest

        # 6. Invoke proposer exactly once
        proposer = self.refinement_proposer
        proposal = proposer.propose_refinement(input_envelope)

        # 7. Verify proposal input binding
        # (handled by validation step — will reject mismatched digest)

        # 8. Validate structural and scope locality
        validation = build_validation_record(
            input_envelope, proposal
        )

        # 9. Emit immutable receipt
        receipt = build_receipt(
            request_id=request.request_id,
            logical_tick=logical_tick,
            snapshot_digest=snapshot_digest,
            projection_digest=projection.digest,
            scope_decision=scope_decision,
            input_envelope=input_envelope,
            proposer_id=proposer.proposer_id,
            proposer_version=proposer.proposer_version,
            proposal=proposal,
            validation=validation,
        )

        # 10. Return proposal-only result
        return RefinementControllerResultV1(
            input_envelope=input_envelope,
            scope_decision=scope_decision,
            proposal=proposal,
            validation=validation,
            receipt=receipt,
        )

    # ------------------------------------------------------------------
    # Existing P0.1 run path
    # ------------------------------------------------------------------

    def run(
        self,
        context: RequestContext,
    ) -> P0Result:
        account = P0ShadowRequestAccount(
            request_id=context.request_id,
            units_per_axis=(
                context.budget_units
            ),
        )

        trace: list[TraceEvent] = []

        account.charge(
            BudgetAxis.PROJECTION,
            1,
            "structural projection",
        )

        projection = (
            self.projector.project(
                context
            )
        )

        self._trace(
            trace,
            "projection",
            "produced",
            projection.digest,
        )

        account.charge(
            BudgetAxis.REFINEMENT,
            1,
            "TRM proposal",
        )

        trm_proposal = (
            self.trm.propose(
                context,
                projection,
            )
        )

        self._trace(
            trace,
            "trm",
            "proposal_only",
            trm_proposal.digest,
            (
                (
                    "expansion_count",
                    len(
                        trm_proposal
                        .expansion_cells
                    ),
                ),
            ),
        )

        account.charge(
            BudgetAxis.ROUTING,
            1,
            "expert activation proposal",
        )

        expert_proposal = (
            self.expert_proposer.propose(
                context,
                projection,
                trm_proposal,
            )
        )

        self._trace(
            trace,
            "experts",
            "proposal_only",
            expert_proposal.digest,
        )

        selected_experts = tuple(
            candidate.expert_id
            for candidate
            in expert_proposal.candidates
            if (
                candidate.expert_id
                in context.allowed_experts
            )
        )

        plan = self._compile_plan(
            context,
            projection.digest,
            selected_experts,
        )

        self._trace(
            trace,
            "controller",
            "compiled_static_plan",
            plan.plan_digest,
            (
                (
                    "selected_experts",
                    selected_experts,
                ),
            ),
        )

        if trm_proposal.expansion_cells:
            self._trace(
                trace,
                "controller",
                "expansion_deferred",
                trm_proposal.digest,
                (
                    (
                        "cells",
                        trm_proposal
                        .expansion_cells,
                    ),
                ),
            )

        account.charge(
            BudgetAxis.DECODING,
            1,
            "offline deterministic decode",
        )

        artifact = self.decoder.decode(
            context,
            plan,
        )

        self._trace(
            trace,
            "decoder",
            "artifact_emitted",
            artifact.digest,
        )

        account.charge(
            BudgetAxis.VALIDATION,
            len(self.validators),
            "validator evidence",
        )

        evidence = tuple(
            validator.validate(
                context,
                artifact,
            )
            for validator
            in self.validators
        )

        for item in evidence:
            self._trace(
                trace,
                "validator",
                item.code,
                digest(item),
                (
                    (
                        "passed",
                        item.passed,
                    ),
                    (
                        "validator_id",
                        item.validator_id,
                    ),
                ),
            )

        accepted = all(
            item.passed
            for item in evidence
        )

        accounting = account.events()

        result_payload = {
            "request_id": (
                context.request_id
            ),
            "accepted": accepted,
            "projection": (
                projection.digest
            ),
            "trm": (
                trm_proposal.digest
            ),
            "experts": (
                expert_proposal.digest
            ),
            "plan": plan.plan_digest,
            "artifact": artifact.digest,
            "evidence": evidence,
            "accounting": accounting,
            "trace": tuple(trace),
            "expansion_executed": False,
            "executed_experts": (),
            "governance_invoked": False,
        }

        return P0Result(
            request_id=context.request_id,
            accepted=accepted,
            projection=projection,
            trm_proposal=trm_proposal,
            expert_proposal=(
                expert_proposal
            ),
            decoder_plan=plan,
            artifact=artifact,
            evidence=evidence,
            accounting=accounting,
            trace=tuple(trace),
            proposed_expansions=(
                trm_proposal
                .expansion_cells
            ),
            expansion_executed=False,
            executed_experts=(),
            governance_invoked=False,
            result_digest=digest(
                result_payload
            ),
        )

    @staticmethod
    def _compile_plan(
        context: RequestContext,
        structural_digest: str,
        selected_experts: tuple[
            str,
            ...,
        ],
    ) -> DecoderControlPlan:
        function_name = safe_identifier(
            context.entrypoint,
            "solution",
        )

        parameters = tuple(
            safe_identifier(
                value,
                f"arg_{index}",
            )
            for index, value
            in enumerate(
                context.parameters
            )
        )

        body = context.hint(
            "body",
            "return None",
        )

        body_lines = (
            tuple(
                body.splitlines()
            )
            or ("return None",)
        )

        payload = {
            "backend": (
                "deterministic-"
                "python-template-v1"
            ),
            "language": "python",
            "temperature": 0.0,
            "max_tokens": (
                context.max_tokens
            ),
            "selected_experts": (
                selected_experts
            ),
            "function_name": (
                function_name
            ),
            "parameters": parameters,
            "body_lines": body_lines,
            "structural_digest": (
                structural_digest
            ),
        }

        return DecoderControlPlan(
            backend=payload["backend"],
            language=payload["language"],
            temperature=(
                payload["temperature"]
            ),
            max_tokens=(
                payload["max_tokens"]
            ),
            selected_experts=(
                selected_experts
            ),
            function_name=(
                function_name
            ),
            parameters=parameters,
            body_lines=body_lines,
            structural_digest=(
                structural_digest
            ),
            plan_digest=digest(
                payload
            ),
        )

    @staticmethod
    def _trace(
        trace: list[TraceEvent],
        stage: str,
        action: str,
        event_digest: str,
        details=(),
    ) -> None:
        trace.append(
            TraceEvent(
                sequence=len(trace),
                stage=stage,
                action=action,
                digest=event_digest,
                details=tuple(
                    details
                ),
            )
        )
