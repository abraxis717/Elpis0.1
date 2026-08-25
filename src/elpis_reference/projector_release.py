"""Canonical Projector RELEASE adapter for resolved task residuals.

This module promotes the qualified R7A release-planning mechanism while
preserving the public semantic-refinement module as a Projector-free contract
layer.

Structural selection is not performed here. Target cells must already have
been resolved through the qualified reverse-trace contract. Only currently
active resolved support is eligible for RELEASE, and each proposal derives its
owner from the current canonical ClampState.

The ClampProposal evidence_digest binds the release request to the originating
task diagnostic. ClampState does not retain the historical per-cell evidence
digest that originally created a clamp, so this adapter does not claim to
cryptographically verify that historical evidence identity.
"""

from __future__ import annotations

from dataclasses import dataclass

from DarwinianMatrix.projector.constraints import (
    ClampOperation,
    ClampProposal,
    ClampState,
    ClampTransaction,
)

from .semantic_refinement import (
    ResolvedTaskResidualV1,
    TaskResidualV1,
    domain_digest,
)


@dataclass(frozen=True)
class ReleasePlanV1:
    task_residual_digest: str
    resolution_digest: str
    clamp_state_before_digest: str
    target_cells: tuple[int, ...]
    target_owners: tuple[str, ...]
    transaction_digest: str | None
    plan_digest: str


def build_release_transaction(
    *,
    residual: TaskResidualV1,
    resolved: ResolvedTaskResidualV1,
    clamp_state: ClampState,
) -> tuple[
    ReleasePlanV1,
    ClampTransaction | None,
]:
    if residual.digest() != resolved.task_residual_digest:
        raise ValueError(
            "Resolved residual is bound to another task residual."
        )

    mask = clamp_state.active_mask
    owners = clamp_state.owners

    targets: list[tuple[int, str]] = []

    for cell in resolved.P7_cell_indices:
        if not bool(mask[cell]):
            continue

        owner = owners[cell]

        if not isinstance(owner, str) or not owner:
            raise RuntimeError(
                "Active clamp has no owner."
            )

        targets.append(
            (
                cell,
                owner,
            )
        )

    targets = sorted(
        set(targets),
        key=lambda item: (
            item[0],
            item[1],
        ),
    )

    proposals = []

    for cell, owner in targets:
        proposal_id = domain_digest(
            "elpis.task-residual-release-proposal.r7a.v1",
            {
                "cell_index": cell,
                "owner": owner,
                "resolution_digest": resolved.resolution_digest,
                "task_residual_digest": residual.digest(),
            },
        )

        proposals.append(
            ClampProposal(
                proposal_id=proposal_id,
                operation=ClampOperation.RELEASE,
                slot_id=owner,
                evidence_digest=residual.diagnostic_digest,
                cell_index=cell,
                value=None,
            )
        )

    transaction = None

    if proposals:
        transaction_id = (
            "task-residual-release-"
            + domain_digest(
                "elpis.task-residual-release-transaction.r7a.v1",
                {
                    "clamp_state_digest": clamp_state.digest(),
                    "proposal_digests": [
                        proposal.digest()
                        for proposal in proposals
                    ],
                    "resolution_digest": resolved.resolution_digest,
                },
            )[:32]
        )

        transaction = ClampTransaction(
            transaction_id=transaction_id,
            episode_id=clamp_state.episode_id,
            expected_state_digest=clamp_state.digest(),
            proposals=tuple(proposals),
        )

    transaction_digest = (
        transaction.digest()
        if transaction is not None
        else None
    )

    cells = tuple(
        cell
        for cell, _ in targets
    )

    target_owners = tuple(
        owner
        for _, owner in targets
    )

    payload = {
        "clamp_state_before_digest": clamp_state.digest(),
        "resolution_digest": resolved.resolution_digest,
        "target_cells": list(cells),
        "target_owners": list(target_owners),
        "task_residual_digest": residual.digest(),
        "transaction_digest": transaction_digest,
    }

    return (
        ReleasePlanV1(
            task_residual_digest=residual.digest(),
            resolution_digest=resolved.resolution_digest,
            clamp_state_before_digest=clamp_state.digest(),
            target_cells=cells,
            target_owners=target_owners,
            transaction_digest=transaction_digest,
            plan_digest=domain_digest(
                "elpis.task-residual-release-plan.r7a.v1",
                payload,
            ),
        ),
        transaction,
    )
