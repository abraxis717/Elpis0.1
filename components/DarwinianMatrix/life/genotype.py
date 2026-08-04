"""Canonical integer genotype for deterministic artificial organisms."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Sequence

from .canonical import payload_digest


INTEGER_GENE_SCHEMA = (
    "darwinian.life.integer-gene.v1"
)

GENOTYPE_SCHEMA = (
    "darwinian.life.genotype.v1"
)

MAX_GENES = 256

_GENE_NAME_PATTERN = re.compile(
    r"[a-z][a-z0-9_]{0,63}"
)


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
class IntegerGene:
    """One bounded, step-aligned, inherited integer locus."""

    name: str
    value: int
    minimum: int
    maximum: int
    step: int = 1
    schema: str = INTEGER_GENE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != INTEGER_GENE_SCHEMA:
            raise ValueError(
                "Unsupported integer-gene schema."
            )

        if (
            not isinstance(self.name, str)
            or _GENE_NAME_PATTERN.fullmatch(
                self.name
            )
            is None
        ):
            raise ValueError(
                "Gene names must match "
                "[a-z][a-z0-9_]{0,63}."
            )

        value = _require_integer(
            self.value,
            field_name=self.name + ".value",
        )
        minimum = _require_integer(
            self.minimum,
            field_name=self.name + ".minimum",
        )
        maximum = _require_integer(
            self.maximum,
            field_name=self.name + ".maximum",
        )
        step = _require_integer(
            self.step,
            field_name=self.name + ".step",
        )

        if minimum > maximum:
            raise ValueError(
                "Gene minimum cannot exceed maximum."
            )

        if step <= 0:
            raise ValueError(
                "Gene step must be positive."
            )

        if not minimum <= value <= maximum:
            raise ValueError(
                "Gene value lies outside its bounds."
            )

        if (maximum - minimum) % step != 0:
            raise ValueError(
                "Gene bounds must align with step."
            )

        if (value - minimum) % step != 0:
            raise ValueError(
                "Gene value must align with step."
            )

    @property
    def movable(self) -> bool:
        return self.minimum < self.maximum

    def with_value(
        self,
        value: int,
    ) -> "IntegerGene":
        return IntegerGene(
            name=self.name,
            value=value,
            minimum=self.minimum,
            maximum=self.maximum,
            step=self.step,
        )

    def structure_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "name": self.name,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "step": self.step,
        }

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        payload = self.structure_payload()
        payload["value"] = self.value
        return payload


@dataclass(frozen=True)
class Genotype:
    """Immutable, canonically ordered inherited genome."""

    genes: tuple[IntegerGene, ...]
    schema: str = GENOTYPE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != GENOTYPE_SCHEMA:
            raise ValueError(
                "Unsupported genotype schema."
            )

        genes = tuple(self.genes)

        if not genes:
            raise ValueError(
                "A genotype requires at least one gene."
            )

        if len(genes) > MAX_GENES:
            raise ValueError(
                "Genotype exceeds the maximum gene count."
            )

        if any(
            not isinstance(gene, IntegerGene)
            for gene in genes
        ):
            raise TypeError(
                "Every genotype locus must be an IntegerGene."
            )

        ordered = tuple(
            sorted(
                genes,
                key=lambda gene: gene.name,
            )
        )

        names = tuple(
            gene.name
            for gene in ordered
        )

        if len(names) != len(set(names)):
            raise ValueError(
                "Genotype gene names must be unique."
            )

        object.__setattr__(
            self,
            "genes",
            ordered,
        )

    @classmethod
    def from_genes(
        cls,
        genes: Sequence[IntegerGene],
    ) -> "Genotype":
        return cls(genes=tuple(genes))

    @property
    def gene_names(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            gene.name
            for gene in self.genes
        )

    @property
    def values(
        self,
    ) -> tuple[int, ...]:
        return tuple(
            gene.value
            for gene in self.genes
        )

    def gene(
        self,
        name: str,
    ) -> IntegerGene:
        for gene in self.genes:
            if gene.name == name:
                return gene

        raise KeyError(name)

    def replace_values(
        self,
        replacements: Mapping[str, int],
    ) -> "Genotype":
        unknown = set(replacements) - set(
            self.gene_names
        )

        if unknown:
            raise KeyError(
                "Unknown genotype loci: "
                + ", ".join(sorted(unknown))
            )

        return Genotype(
            genes=tuple(
                gene.with_value(
                    replacements.get(
                        gene.name,
                        gene.value,
                    )
                )
                for gene in self.genes
            )
        )

    def structure_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": (
                "darwinian.life.genotype-structure.v1"
            ),
            "genes": [
                gene.structure_payload()
                for gene in self.genes
            ],
        }

    def structure_digest(self) -> str:
        return payload_digest(
            self.structure_payload()
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "genes": [
                gene.canonical_payload()
                for gene in self.genes
            ],
        }

    def digest(self) -> str:
        return payload_digest(
            self.canonical_payload()
        )

    def distance(
        self,
        other: "Genotype",
    ) -> int:
        """Exact step-normalized Manhattan genotype distance."""

        if not isinstance(other, Genotype):
            raise TypeError(
                "other must be a Genotype."
            )

        if (
            self.structure_digest()
            != other.structure_digest()
        ):
            raise ValueError(
                "Genotype distance requires identical "
                "gene structures."
            )

        return sum(
            abs(left.value - right.value)
            // left.step
            for left, right in zip(
                self.genes,
                other.genes,
            )
        )


__all__ = (
    "GENOTYPE_SCHEMA",
    "INTEGER_GENE_SCHEMA",
    "Genotype",
    "IntegerGene",
)
