from __future__ import annotations

from .canonical import digest
from .contracts import (
    BasisToken,
    RequestContext,
    StructuralProjection,
    TRMRefinementProposal,
)


class ShadowTRMProposer:
    """Deterministic stand-in for the real Grid81 TRM.

    This component proposes only.

    It cannot:

    - spawn children;
    - consume production authority;
    - load experts;
    - decode language tokens;
    - validate artifacts;
    - authorize STOP;
    - invoke governance.
    """

    def propose(
        self,
        context: RequestContext,
        projection: StructuralProjection,
    ) -> TRMRefinementProposal:
        projection.validate()

        proposed = list(
            projection.grid81
        )

        rationale: list[str] = []

        if proposed[80] != BasisToken.RESOLUTION:
            proposed[80] = int(
                BasisToken.RESOLUTION
            )

            rationale.append(
                "normalized terminal control "
                "cell to RESOLUTION"
            )

        validation_slice = proposed[
            63:72
        ]

        if (
            int(BasisToken.CONSTRAINT)
            not in validation_slice
        ):
            proposed[63] = int(
                BasisToken.CONSTRAINT
            )

            rationale.append(
                "inserted minimum validator "
                "constraint marker"
            )

        expansion_cells = tuple(
            index
            for index, value
            in enumerate(proposed)
            if value == BasisToken.EXPANSION
        )

        residuals = tuple(
            1.0
            if value == BasisToken.VOID
            else 0.125
            for value in proposed
        )

        unresolved = sum(
            value == BasisToken.VOID
            for value in proposed
        )

        halt_score = max(
            0.0,
            min(
                1.0,
                1.0 - unresolved / 81.0,
            ),
        )

        if expansion_cells:
            rationale.append(
                "proposed "
                f"{len(expansion_cells)} "
                "expansion marker(s); "
                "execution deferred"
            )

        if not rationale:
            rationale.append(
                "projection already satisfied "
                "P0 structural invariants"
            )

        proposal_payload = {
            "input_digest": projection.digest,
            "proposed_grid81": tuple(
                proposed
            ),
            "residual81": residuals,
            "halt_score": halt_score,
            "expansion_cells": (
                expansion_cells
            ),
            "rationale": tuple(
                rationale
            ),
            "request_id": context.request_id,
        }

        proposal = TRMRefinementProposal(
            input_digest=projection.digest,
            proposed_grid81=tuple(
                proposed
            ),
            residual81=residuals,
            halt_score=halt_score,
            expansion_cells=(
                expansion_cells
            ),
            rationale=tuple(
                rationale
            ),
            digest=digest(
                proposal_payload
            ),
        )

        proposal.validate()
        return proposal
