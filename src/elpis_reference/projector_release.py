"""Bounded Projector RELEASE planning for resolved task residuals.

C2R4 red-team hardening changes the release boundary from an owner copied out
of live ClampState to an explicit, state-bound release binding table that must
exist before the diagnostic is converted into a structural mutation.

The binding table is a deterministic record, not a cryptographic attestation.
Production callers remain responsible for constructing it from an authority-
controlled pre-validation trace. A single traversal is hard-capped at one
active RELEASE target. The canonical DarwinianMatrix Projector remains the
mutation authority and still enforces stale-state and owner consistency.
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
    LOCUS_NAMESPACES,
    SEMANTIC_OBJECT,
    TOPOLOGY_VERTEX,
    ResolvedTaskResidualV1,
    TaskResidualV1,
    domain_digest,
    require_digest,
)


MAX_RELEASE_CELLS_PER_TRAVERSAL = 1


@dataclass(frozen=True)
class ReleaseBindingTargetV1:
    cell_index: int
    owner: str
    locus_namespace: str
    locus_identity: str
    binding_digest: str = ""

    def __post_init__(self) -> None:
        if not 0 <= self.cell_index < 81:
            raise ValueError("release binding cell must be in 0..80")
        if not self.owner:
            raise ValueError("release binding owner cannot be empty")
        if self.locus_namespace not in LOCUS_NAMESPACES:
            raise ValueError("release binding has unknown locus namespace")
        if not self.locus_identity:
            raise ValueError("release binding locus identity cannot be empty")
        if self.locus_namespace in (SEMANTIC_OBJECT, TOPOLOGY_VERTEX):
            require_digest("release binding locus identity", self.locus_identity)

        payload = {
            "cell_index": self.cell_index,
            "locus_identity": self.locus_identity,
            "locus_namespace": self.locus_namespace,
            "owner": self.owner,
        }
        computed = domain_digest(
            "elpis.release-binding-target.c2r4.v1",
            payload,
        )
        if self.binding_digest and self.binding_digest != computed:
            raise ValueError("release binding digest mismatch")
        object.__setattr__(self, "binding_digest", computed)

    def payload(self) -> dict[str, object]:
        return {
            "binding_digest": self.binding_digest,
            "cell_index": self.cell_index,
            "locus_identity": self.locus_identity,
            "locus_namespace": self.locus_namespace,
            "owner": self.owner,
        }


@dataclass(frozen=True)
class ReleaseBindingTableV1:
    episode_id: str
    clamp_state_digest: str
    targets: tuple[ReleaseBindingTargetV1, ...]
    max_release_cells: int = MAX_RELEASE_CELLS_PER_TRAVERSAL
    binding_table_digest: str = ""

    def __post_init__(self) -> None:
        if not self.episode_id:
            raise ValueError("release binding episode cannot be empty")
        require_digest("release binding ClampState digest", self.clamp_state_digest)
        if self.max_release_cells != MAX_RELEASE_CELLS_PER_TRAVERSAL:
            raise ValueError("C2R4 release cardinality is fixed at one cell")
        identities = tuple(
            (target.cell_index, target.locus_namespace, target.locus_identity)
            for target in self.targets
        )
        if len(set(identities)) != len(identities):
            raise ValueError("release binding targets must be unique")

        canonical_targets = tuple(
            sorted(
                self.targets,
                key=lambda target: (
                    target.cell_index,
                    target.locus_namespace,
                    target.locus_identity,
                    target.owner,
                    target.binding_digest,
                ),
            )
        )
        object.__setattr__(self, "targets", canonical_targets)

        computed = domain_digest(
            "elpis.release-binding-table.c2r4.v1",
            {
                "clamp_state_digest": self.clamp_state_digest,
                "episode_id": self.episode_id,
                "max_release_cells": self.max_release_cells,
                "targets": [target.payload() for target in canonical_targets],
            },
        )
        if self.binding_table_digest and self.binding_table_digest != computed:
            raise ValueError("release binding table digest mismatch")
        object.__setattr__(self, "binding_table_digest", computed)

    def target_for(
        self,
        *,
        cell_index: int,
        locus_namespace: str,
        locus_identity: str,
    ) -> ReleaseBindingTargetV1:
        matches = tuple(
            target
            for target in self.targets
            if target.cell_index == cell_index
            and target.locus_namespace == locus_namespace
            and target.locus_identity == locus_identity
        )
        if len(matches) != 1:
            raise LookupError(
                "resolved active support lacks exactly one precommitted release binding"
            )
        return matches[0]


@dataclass(frozen=True)
class ReleasePlanV1:
    task_residual_digest: str
    resolution_digest: str
    binding_table_digest: str
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
    release_bindings: ReleaseBindingTableV1,
) -> tuple[ReleasePlanV1, ClampTransaction | None]:
    if residual.digest() != resolved.task_residual_digest:
        raise ValueError("Resolved residual is bound to another task residual.")
    if release_bindings.episode_id != clamp_state.episode_id:
        raise ValueError("release binding episode does not match ClampState")
    if release_bindings.clamp_state_digest != clamp_state.digest():
        raise ValueError("release binding table is not bound to current ClampState")

    mask = clamp_state.active_mask
    owners = clamp_state.owners
    targets: list[tuple[int, str, str]] = []

    for cell in resolved.P7_cell_indices:
        if not bool(mask[cell]):
            continue

        binding = release_bindings.target_for(
            cell_index=cell,
            locus_namespace=residual.locus_namespace,
            locus_identity=residual.locus_identity,
        )
        owner = owners[cell]
        if not isinstance(owner, str) or not owner:
            raise RuntimeError("Active clamp has no owner.")
        if owner != binding.owner:
            raise ValueError("release binding owner does not match ClampState")
        targets.append((cell, binding.owner, binding.binding_digest))

    targets = sorted(set(targets), key=lambda item: (item[0], item[1], item[2]))
    if len(targets) > release_bindings.max_release_cells:
        raise ValueError(
            "resolved active release target cardinality exceeds C2R4 bound of one"
        )

    proposals = []
    for cell, owner, binding_digest in targets:
        proposal_id = domain_digest(
            "elpis.task-residual-release-proposal.c2r4.v1",
            {
                "binding_digest": binding_digest,
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
        transaction_id = "task-residual-release-" + domain_digest(
            "elpis.task-residual-release-transaction.c2r4.v1",
            {
                "binding_table_digest": release_bindings.binding_table_digest,
                "clamp_state_digest": clamp_state.digest(),
                "proposal_digests": [proposal.digest() for proposal in proposals],
                "resolution_digest": resolved.resolution_digest,
            },
        )[:32]
        transaction = ClampTransaction(
            transaction_id=transaction_id,
            episode_id=clamp_state.episode_id,
            expected_state_digest=clamp_state.digest(),
            proposals=tuple(proposals),
        )

    transaction_digest = transaction.digest() if transaction is not None else None
    cells = tuple(cell for cell, _, _ in targets)
    target_owners = tuple(owner for _, owner, _ in targets)
    payload = {
        "binding_table_digest": release_bindings.binding_table_digest,
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
            binding_table_digest=release_bindings.binding_table_digest,
            clamp_state_before_digest=clamp_state.digest(),
            target_cells=cells,
            target_owners=target_owners,
            transaction_digest=transaction_digest,
            plan_digest=domain_digest(
                "elpis.task-residual-release-plan.c2r4.v1",
                payload,
            ),
        ),
        transaction,
    )
