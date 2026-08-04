from __future__ import annotations

from typing import Protocol

from .contracts import (
    ArtifactCandidate,
    BudgetAxis,
    DecoderControlPlan,
    ExpertActivationProposal,
    RequestContext,
    StructuralProjection,
    TRMRefinementProposal,
    ValidatorEvidence,
)


class StructuralProjectorPort(Protocol):
    def project(
        self,
        context: RequestContext,
    ) -> StructuralProjection:
        ...


class TRMProposalPort(Protocol):
    def propose(
        self,
        context: RequestContext,
        projection: StructuralProjection,
    ) -> TRMRefinementProposal:
        ...


class ExpertProposalPort(Protocol):
    def propose(
        self,
        context: RequestContext,
        projection: StructuralProjection,
        trm: TRMRefinementProposal,
    ) -> ExpertActivationProposal:
        ...


class DecoderPort(Protocol):
    def decode(
        self,
        context: RequestContext,
        plan: DecoderControlPlan,
    ) -> ArtifactCandidate:
        ...


class ValidatorPort(Protocol):
    validator_id: str

    def validate(
        self,
        context: RequestContext,
        artifact: ArtifactCandidate,
    ) -> ValidatorEvidence:
        ...


class RequestAccountPort(Protocol):
    def charge(
        self,
        axis: BudgetAxis,
        units: int,
        reason: str,
    ):
        ...

    def events(self):
        ...
