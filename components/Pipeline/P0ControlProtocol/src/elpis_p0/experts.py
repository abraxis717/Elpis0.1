from __future__ import annotations

from .canonical import digest
from .contracts import (
    ExpertActivationProposal,
    ExpertCandidate,
    RequestContext,
    StructuralProjection,
    TRMRefinementProposal,
)


class DeterministicExpertProposer:
    """Propose experts without loading or executing them."""

    def propose(
        self,
        context: RequestContext,
        projection: StructuralProjection,
        trm: TRMRefinementProposal,
    ) -> ExpertActivationProposal:
        prompt = context.prompt.lower()

        candidates = [
            ExpertCandidate(
                expert_id="python.ast",
                score=1.0,
                reason=(
                    "P0 requires AST validation "
                    "for every Python artifact"
                ),
            ),
            ExpertCandidate(
                expert_id="python.codegen",
                score=0.95,
                reason=(
                    "request domain is "
                    "Python generation"
                ),
            ),
        ]

        if (
            "test" in prompt
            or "pytest" in prompt
        ):
            candidates.append(
                ExpertCandidate(
                    expert_id="python.tests",
                    score=0.85,
                    reason=(
                        "request explicitly "
                        "references tests"
                    ),
                )
            )

        if (
            "type" in prompt
            or "typing" in prompt
            or "typed" in prompt
        ):
            candidates.append(
                ExpertCandidate(
                    expert_id="python.typing",
                    score=0.80,
                    reason=(
                        "request explicitly "
                        "references typing"
                    ),
                )
            )

        candidates.sort(
            key=lambda candidate: (
                -candidate.score,
                candidate.expert_id,
            )
        )

        candidate_tuple = tuple(
            candidates
        )

        return ExpertActivationProposal(
            candidates=candidate_tuple,
            digest=digest(
                {
                    "projection": (
                        projection.digest
                    ),
                    "trm": trm.digest,
                    "candidates": (
                        candidate_tuple
                    ),
                }
            ),
        )
