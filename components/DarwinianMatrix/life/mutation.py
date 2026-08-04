"""Bounded deterministic mutation without implicit randomness."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

from .canonical import (
    payload_digest,
    require_sha256,
)
from .genotype import Genotype


MUTATION_POLICY_SCHEMA = (
    "darwinian.life.mutation-policy.v1"
)

MUTATION_EVENT_SCHEMA = (
    "darwinian.life.mutation-event.v1"
)

MUTATION_RESULT_SCHEMA = (
    "darwinian.life.mutation-result.v1"
)

PPM_SCALE = 1_000_000


def _require_integer(
    value: object,
    *,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(
        value,
        int,
    ):
        raise TypeError(
            field_name + " must be an integer."
        )

    return value


@dataclass(frozen=True)
class MutationPolicyV1:
    """Exact mutation bounds expressed entirely with integers."""

    activation_probability_ppm: int = 100_000
    max_mutated_loci: int = 2
    max_step_multiple: int = 1
    ensure_at_least_one: bool = False
    schema: str = MUTATION_POLICY_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != MUTATION_POLICY_SCHEMA:
            raise ValueError(
                "Unsupported mutation-policy schema."
            )

        probability = _require_integer(
            self.activation_probability_ppm,
            field_name=(
                "activation_probability_ppm"
            ),
        )

        max_loci = _require_integer(
            self.max_mutated_loci,
            field_name="max_mutated_loci",
        )

        max_step = _require_integer(
            self.max_step_multiple,
            field_name="max_step_multiple",
        )

        if not 0 <= probability <= PPM_SCALE:
            raise ValueError(
                "Mutation probability must be between "
                "zero and one million ppm."
            )

        if max_loci <= 0:
            raise ValueError(
                "max_mutated_loci must be positive."
            )

        if max_step <= 0:
            raise ValueError(
                "max_step_multiple must be positive."
            )

        if not isinstance(
            self.ensure_at_least_one,
            bool,
        ):
            raise TypeError(
                "ensure_at_least_one must be boolean."
            )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "activation_probability_ppm": (
                self.activation_probability_ppm
            ),
            "max_mutated_loci": (
                self.max_mutated_loci
            ),
            "max_step_multiple": (
                self.max_step_multiple
            ),
            "ensure_at_least_one": (
                self.ensure_at_least_one
            ),
            "randomness": (
                "SHA256_LEDGER_DERIVED_ONLY"
            ),
        }

    def digest(self) -> str:
        return payload_digest(
            self.canonical_payload()
        )


@dataclass(frozen=True)
class MutationEvent:
    locus_index: int
    gene_name: str
    old_value: int
    new_value: int
    delta: int
    schema: str = MUTATION_EVENT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != MUTATION_EVENT_SCHEMA:
            raise ValueError(
                "Unsupported mutation-event schema."
            )

        locus_index = _require_integer(
            self.locus_index,
            field_name="locus_index",
        )

        if locus_index < 0:
            raise ValueError(
                "locus_index cannot be negative."
            )

        if not isinstance(
            self.gene_name,
            str,
        ) or not self.gene_name:
            raise ValueError(
                "gene_name must be non-empty."
            )

        for field_name, value in (
            ("old_value", self.old_value),
            ("new_value", self.new_value),
            ("delta", self.delta),
        ):
            _require_integer(
                value,
                field_name=field_name,
            )

        if self.new_value - self.old_value != self.delta:
            raise ValueError(
                "Mutation event delta is inconsistent."
            )

        if self.delta == 0:
            raise ValueError(
                "A mutation event must change its locus."
            )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "locus_index": self.locus_index,
            "gene_name": self.gene_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "delta": self.delta,
        }


@dataclass(frozen=True)
class MutationResult:
    parent_genotype_digest: str
    mutation_seed_digest: str
    mutation_policy_digest: str
    child_genotype: Genotype
    events: tuple[MutationEvent, ...]
    schema: str = MUTATION_RESULT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != MUTATION_RESULT_SCHEMA:
            raise ValueError(
                "Unsupported mutation-result schema."
            )

        require_sha256(
            self.parent_genotype_digest,
            field_name=(
                "parent_genotype_digest"
            ),
        )

        require_sha256(
            self.mutation_seed_digest,
            field_name=(
                "mutation_seed_digest"
            ),
        )

        require_sha256(
            self.mutation_policy_digest,
            field_name=(
                "mutation_policy_digest"
            ),
        )

        if not isinstance(
            self.child_genotype,
            Genotype,
        ):
            raise TypeError(
                "child_genotype must be a Genotype."
            )

        events = tuple(self.events)

        if any(
            not isinstance(
                event,
                MutationEvent,
            )
            for event in events
        ):
            raise TypeError(
                "events must contain MutationEvent objects."
            )

        ordered = tuple(
            sorted(
                events,
                key=lambda event: (
                    event.locus_index,
                    event.gene_name,
                ),
            )
        )

        if len(
            {
                event.locus_index
                for event in ordered
            }
        ) != len(ordered):
            raise ValueError(
                "A locus may mutate only once per result."
            )

        object.__setattr__(
            self,
            "events",
            ordered,
        )

    @property
    def mutated(self) -> bool:
        return bool(self.events)

    @property
    def child_genotype_digest(
        self,
    ) -> str:
        return self.child_genotype.digest()

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "parent_genotype_digest": (
                self.parent_genotype_digest
            ),
            "mutation_seed_digest": (
                self.mutation_seed_digest
            ),
            "mutation_policy_digest": (
                self.mutation_policy_digest
            ),
            "child_genotype": (
                self.child_genotype.canonical_payload()
            ),
            "child_genotype_digest": (
                self.child_genotype_digest
            ),
            "events": [
                event.canonical_payload()
                for event in self.events
            ],
        }

    def digest(self) -> str:
        return payload_digest(
            self.canonical_payload()
        )


def _locus_entropy(
    *,
    seed_digest: str,
    genotype_digest: str,
    policy_digest: str,
    locus_index: int,
) -> bytes:
    payload = (
        seed_digest
        + ":"
        + genotype_digest
        + ":"
        + policy_digest
        + ":"
        + str(locus_index)
    ).encode("ascii")

    return hashlib.sha256(payload).digest()


def mutate_genotype(
    *,
    parent: Genotype,
    mutation_seed_digest: str,
    policy: MutationPolicyV1,
) -> MutationResult:
    """Apply a deterministic, bounded mutation transaction."""

    if not isinstance(parent, Genotype):
        raise TypeError(
            "parent must be a Genotype."
        )

    if not isinstance(
        policy,
        MutationPolicyV1,
    ):
        raise TypeError(
            "policy must be a MutationPolicyV1."
        )

    require_sha256(
        mutation_seed_digest,
        field_name="mutation_seed_digest",
    )

    parent_digest = parent.digest()
    policy_digest = policy.digest()

    candidates = []

    for index, gene in enumerate(
        parent.genes
    ):
        if not gene.movable:
            continue

        entropy = _locus_entropy(
            seed_digest=mutation_seed_digest,
            genotype_digest=parent_digest,
            policy_digest=policy_digest,
            locus_index=index,
        )

        activation_score = (
            int.from_bytes(
                entropy[0:8],
                byteorder="big",
                signed=False,
            )
            % PPM_SCALE
        )

        candidates.append(
            (
                activation_score,
                index,
                entropy,
            )
        )

    activated = [
        item
        for item in candidates
        if item[0]
        < policy.activation_probability_ppm
    ]

    if (
        not activated
        and policy.ensure_at_least_one
        and candidates
    ):
        activated = [
            min(
                candidates,
                key=lambda item: (
                    item[0],
                    item[1],
                ),
            )
        ]

    selected = sorted(
        activated,
        key=lambda item: (
            item[0],
            item[1],
        ),
    )[: policy.max_mutated_loci]

    replacements: dict[str, int] = {}
    events = []

    for _, index, entropy in selected:
        gene = parent.genes[index]

        multiple = (
            1
            + entropy[8]
            % policy.max_step_multiple
        )

        direction = (
            1
            if entropy[9] & 1
            else -1
        )

        if (
            gene.value == gene.minimum
            and direction < 0
        ):
            direction = 1

        if (
            gene.value == gene.maximum
            and direction > 0
        ):
            direction = -1

        proposed = (
            gene.value
            + direction
            * multiple
            * gene.step
        )

        new_value = min(
            gene.maximum,
            max(
                gene.minimum,
                proposed,
            ),
        )

        if new_value == gene.value:
            continue

        replacements[gene.name] = new_value

        events.append(
            MutationEvent(
                locus_index=index,
                gene_name=gene.name,
                old_value=gene.value,
                new_value=new_value,
                delta=(
                    new_value
                    - gene.value
                ),
            )
        )

    child = parent.replace_values(
        replacements
    )

    return MutationResult(
        parent_genotype_digest=parent_digest,
        mutation_seed_digest=(
            mutation_seed_digest
        ),
        mutation_policy_digest=(
            policy_digest
        ),
        child_genotype=child,
        events=tuple(events),
    )


__all__ = (
    "MUTATION_POLICY_SCHEMA",
    "MutationEvent",
    "MutationPolicyV1",
    "MutationResult",
    "mutate_genotype",
)
