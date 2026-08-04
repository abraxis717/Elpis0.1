"""Verified selection proposals and atomic population transitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Sequence

from .canonical import (
    payload_digest,
    require_sha256,
)
from .lifecycle import (
    LifecycleState,
    transition_lifecycle,
)
from .organism import OrganismState


POPULATION_STATE_SCHEMA = (
    "darwinian.life.population-state.v1"
)

SELECTION_CANDIDATE_BINDING_SCHEMA = (
    "darwinian.life.selection-candidate-binding.v1"
)

SELECTION_PROPOSAL_SCHEMA = (
    "darwinian.life.selection-proposal.v1"
)

SELECTION_COMMIT_POLICY_SCHEMA = (
    "darwinian.life.selection-commit-policy.v1"
)

SELECTION_COMMIT_RESULT_SCHEMA = (
    "darwinian.life.selection-commit-result.v1"
)


def _require_nonnegative_integer(
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

    if value < 0:
        raise ValueError(
            field_name + " cannot be negative."
        )

    return value


def _parse_fraction(
    value: Fraction | int | str,
    *,
    field_name: str,
) -> Fraction:
    if isinstance(value, bool):
        raise TypeError(
            field_name + " cannot be boolean."
        )

    if isinstance(value, Fraction):
        return value

    if isinstance(value, int):
        return Fraction(value)

    if isinstance(value, str):
        try:
            return Fraction(value.strip())
        except (
            ValueError,
            ZeroDivisionError,
        ) as exc:
            raise ValueError(
                "Invalid rational value for "
                + field_name
                + "."
            ) from exc

    raise TypeError(
        field_name
        + " must be an integer, rational string, "
        "or Fraction."
    )


def _fraction_text(
    value: Fraction,
) -> str:
    value = Fraction(value)

    if value.denominator == 1:
        return str(value.numerator)

    return (
        str(value.numerator)
        + "/"
        + str(value.denominator)
    )


class SelectionSolverKind(str, Enum):
    EXACT_CLASSICAL_ORACLE_V1 = (
        "EXACT_CLASSICAL_ORACLE_V1"
    )

    LOCAL_STATEVECTOR_QAOA_VERIFIED_V1 = (
        "LOCAL_STATEVECTOR_QAOA_VERIFIED_V1"
    )

    IBM_RUNTIME_QAOA_VERIFIED_V1 = (
        "IBM_RUNTIME_QAOA_VERIFIED_V1"
    )


class SelectionCommitRejectionCode(str, Enum):
    WORLD_STATE_MISMATCH = (
        "WORLD_STATE_MISMATCH"
    )

    POPULATION_REVISION_MISMATCH = (
        "POPULATION_REVISION_MISMATCH"
    )

    STALE_POPULATION = (
        "STALE_POPULATION"
    )

    CANDIDATE_NOT_FOUND = (
        "CANDIDATE_NOT_FOUND"
    )

    STALE_CANDIDATE_BINDING = (
        "STALE_CANDIDATE_BINDING"
    )

    CANDIDATE_NOT_ELIGIBLE = (
        "CANDIDATE_NOT_ELIGIBLE"
    )

    OPTIMALITY_GAP_EXCEEDED = (
        "OPTIMALITY_GAP_EXCEEDED"
    )


@dataclass(frozen=True)
class SelectionCandidateBinding:
    organism_id: str
    organism_state_digest: str
    genotype_digest: str
    fitness_record_digest: str
    scalar_fitness: int
    novelty: int
    lifecycle: str
    schema: str = (
        SELECTION_CANDIDATE_BINDING_SCHEMA
    )

    def __post_init__(self) -> None:
        if (
            self.schema
            != SELECTION_CANDIDATE_BINDING_SCHEMA
        ):
            raise ValueError(
                "Unsupported selection-candidate "
                "binding schema."
            )

        for field_name, digest in (
            (
                "organism_id",
                self.organism_id,
            ),
            (
                "organism_state_digest",
                self.organism_state_digest,
            ),
            (
                "genotype_digest",
                self.genotype_digest,
            ),
            (
                "fitness_record_digest",
                self.fitness_record_digest,
            ),
        ):
            require_sha256(
                digest,
                field_name=field_name,
            )

        if isinstance(
            self.scalar_fitness,
            bool,
        ) or not isinstance(
            self.scalar_fitness,
            int,
        ):
            raise TypeError(
                "scalar_fitness must be an integer."
            )

        _require_nonnegative_integer(
            self.novelty,
            field_name="novelty",
        )

        if (
            not isinstance(
                self.lifecycle,
                str,
            )
            or not self.lifecycle
        ):
            raise ValueError(
                "lifecycle must be non-empty."
            )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "organism_id": self.organism_id,
            "organism_state_digest": (
                self.organism_state_digest
            ),
            "genotype_digest": (
                self.genotype_digest
            ),
            "fitness_record_digest": (
                self.fitness_record_digest
            ),
            "scalar_fitness": (
                self.scalar_fitness
            ),
            "novelty": self.novelty,
            "lifecycle": self.lifecycle,
        }


@dataclass(frozen=True)
class PopulationState:
    """Canonical population bound to one source world digest."""

    source_world_state_digest: str
    revision: int
    organisms: tuple[OrganismState, ...]
    schema: str = POPULATION_STATE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != POPULATION_STATE_SCHEMA:
            raise ValueError(
                "Unsupported population-state schema."
            )

        require_sha256(
            self.source_world_state_digest,
            field_name=(
                "source_world_state_digest"
            ),
        )

        _require_nonnegative_integer(
            self.revision,
            field_name="revision",
        )

        organisms = tuple(self.organisms)

        if not organisms:
            raise ValueError(
                "A population requires at least "
                "one organism."
            )

        if any(
            not isinstance(
                organism,
                OrganismState,
            )
            for organism in organisms
        ):
            raise TypeError(
                "organisms must contain "
                "OrganismState objects."
            )

        ordered = tuple(
            sorted(
                organisms,
                key=lambda organism: (
                    organism.organism_id
                ),
            )
        )

        identifiers = tuple(
            organism.organism_id
            for organism in ordered
        )

        if len(identifiers) != len(
            set(identifiers)
        ):
            raise ValueError(
                "Population organism identities "
                "must be unique."
            )

        object.__setattr__(
            self,
            "organisms",
            ordered,
        )

    @property
    def organism_ids(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            organism.organism_id
            for organism in self.organisms
        )

    def organism(
        self,
        organism_id: str,
    ) -> OrganismState:
        for organism in self.organisms:
            if organism.organism_id == organism_id:
                return organism

        raise KeyError(organism_id)

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_world_state_digest": (
                self.source_world_state_digest
            ),
            "revision": self.revision,
            "organisms": [
                organism.canonical_payload()
                for organism in self.organisms
            ],
        }

    def digest(self) -> str:
        return payload_digest(
            self.canonical_payload()
        )


def _verification_payload(
    *,
    source_world_state_digest: str,
    expected_population_digest: str,
    expected_population_revision: int,
    problem_digest: str,
    compilation_digest: str,
    qubo_digest: str,
    solver_kind: SelectionSolverKind,
    solver_artifact_digest: str,
    variable_order: tuple[str, ...],
    bits_variable_order: tuple[int, ...],
    candidate_bindings: tuple[
        SelectionCandidateBinding,
        ...,
    ],
    survivor_count: int,
    exact_energy: str,
    reference_optimum_energy: str,
) -> dict[str, object]:
    selected_ids = [
        organism_id
        for organism_id, bit in zip(
            variable_order,
            bits_variable_order,
        )
        if bit == 1
    ]

    exact = _parse_fraction(
        exact_energy,
        field_name="exact_energy",
    )

    optimum = _parse_fraction(
        reference_optimum_energy,
        field_name=(
            "reference_optimum_energy"
        ),
    )

    return {
        "schema": SELECTION_PROPOSAL_SCHEMA,
        "source_world_state_digest": (
            source_world_state_digest
        ),
        "expected_population_digest": (
            expected_population_digest
        ),
        "expected_population_revision": (
            expected_population_revision
        ),
        "problem_digest": problem_digest,
        "compilation_digest": (
            compilation_digest
        ),
        "qubo_digest": qubo_digest,
        "solver_kind": solver_kind.value,
        "solver_artifact_digest": (
            solver_artifact_digest
        ),
        "variable_order": list(
            variable_order
        ),
        "bits_variable_order": list(
            bits_variable_order
        ),
        "selected_ids": selected_ids,
        "survivor_count": survivor_count,
        "candidate_bindings": [
            binding.canonical_payload()
            for binding in candidate_bindings
        ],
        "exact_energy": _fraction_text(
            exact
        ),
        "reference_optimum_energy": (
            _fraction_text(optimum)
        ),
        "optimality_gap": _fraction_text(
            exact - optimum
        ),
        "authority": {
            "solver_output_authoritative": False,
            "classical_verifier_authoritative": True,
        },
        "verification_method": (
            "Q01_EXACT_QUBO_RECOMPUTATION_V1"
        ),
    }


@dataclass(frozen=True)
class SelectionProposal:
    """Immutable classically verified selection proposal."""

    source_world_state_digest: str
    expected_population_digest: str
    expected_population_revision: int
    problem_digest: str
    compilation_digest: str
    qubo_digest: str
    solver_kind: SelectionSolverKind
    solver_artifact_digest: str
    variable_order: tuple[str, ...]
    bits_variable_order: tuple[int, ...]
    candidate_bindings: tuple[
        SelectionCandidateBinding,
        ...,
    ]
    survivor_count: int
    exact_energy: str
    reference_optimum_energy: str
    verification_digest: str
    schema: str = SELECTION_PROPOSAL_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SELECTION_PROPOSAL_SCHEMA:
            raise ValueError(
                "Unsupported selection-proposal schema."
            )

        for field_name, digest in (
            (
                "source_world_state_digest",
                self.source_world_state_digest,
            ),
            (
                "expected_population_digest",
                self.expected_population_digest,
            ),
            (
                "problem_digest",
                self.problem_digest,
            ),
            (
                "compilation_digest",
                self.compilation_digest,
            ),
            (
                "qubo_digest",
                self.qubo_digest,
            ),
            (
                "solver_artifact_digest",
                self.solver_artifact_digest,
            ),
            (
                "verification_digest",
                self.verification_digest,
            ),
        ):
            require_sha256(
                digest,
                field_name=field_name,
            )

        _require_nonnegative_integer(
            self.expected_population_revision,
            field_name=(
                "expected_population_revision"
            ),
        )

        _require_nonnegative_integer(
            self.survivor_count,
            field_name="survivor_count",
        )

        if not isinstance(
            self.solver_kind,
            SelectionSolverKind,
        ):
            raise TypeError(
                "solver_kind must be a "
                "SelectionSolverKind."
            )

        variable_order = tuple(
            self.variable_order
        )

        if not variable_order:
            raise ValueError(
                "Selection proposal requires "
                "at least one variable."
            )

        if tuple(
            sorted(variable_order)
        ) != variable_order:
            raise ValueError(
                "variable_order must be canonical."
            )

        if len(variable_order) != len(
            set(variable_order)
        ):
            raise ValueError(
                "variable_order must be unique."
            )

        bits = tuple(
            self.bits_variable_order
        )

        if len(bits) != len(variable_order):
            raise ValueError(
                "Bit vector length does not match "
                "variable_order."
            )

        if any(
            bit not in (0, 1)
            for bit in bits
        ):
            raise ValueError(
                "Selection bits must be zero or one."
            )

        bindings = tuple(
            sorted(
                self.candidate_bindings,
                key=lambda binding: (
                    binding.organism_id
                ),
            )
        )

        if any(
            not isinstance(
                binding,
                SelectionCandidateBinding,
            )
            for binding in bindings
        ):
            raise TypeError(
                "candidate_bindings must contain "
                "SelectionCandidateBinding objects."
            )

        binding_ids = tuple(
            binding.organism_id
            for binding in bindings
        )

        if binding_ids != variable_order:
            raise ValueError(
                "Candidate bindings must exactly match "
                "the canonical variable order."
            )

        selected_count = sum(bits)

        if selected_count != self.survivor_count:
            raise ValueError(
                "Selected bit count does not match "
                "survivor_count."
            )

        exact = _parse_fraction(
            self.exact_energy,
            field_name="exact_energy",
        )

        optimum = _parse_fraction(
            self.reference_optimum_energy,
            field_name=(
                "reference_optimum_energy"
            ),
        )

        if exact < optimum:
            raise ValueError(
                "Proposal energy cannot be lower than "
                "the reference optimum."
            )

        object.__setattr__(
            self,
            "variable_order",
            variable_order,
        )

        object.__setattr__(
            self,
            "bits_variable_order",
            bits,
        )

        object.__setattr__(
            self,
            "candidate_bindings",
            bindings,
        )

        object.__setattr__(
            self,
            "exact_energy",
            _fraction_text(exact),
        )

        object.__setattr__(
            self,
            "reference_optimum_energy",
            _fraction_text(optimum),
        )

        expected_verification = payload_digest(
            self.verification_payload()
        )

        if (
            self.verification_digest
            != expected_verification
        ):
            raise ValueError(
                "Selection proposal verification "
                "digest mismatch."
            )

    @classmethod
    def create_verified(
        cls,
        *,
        population: PopulationState,
        problem_digest: str,
        compilation_digest: str,
        qubo_digest: str,
        solver_kind: SelectionSolverKind,
        solver_artifact_digest: str,
        variable_order: Sequence[str],
        bits_variable_order: Sequence[int],
        candidate_bindings: Sequence[
            SelectionCandidateBinding
        ],
        survivor_count: int,
        exact_energy: (
            Fraction | int | str
        ),
        reference_optimum_energy: (
            Fraction | int | str
        ),
    ) -> "SelectionProposal":
        if not isinstance(
            population,
            PopulationState,
        ):
            raise TypeError(
                "population must be a "
                "PopulationState."
            )

        variables = tuple(variable_order)
        bits = tuple(bits_variable_order)

        bindings = tuple(
            sorted(
                candidate_bindings,
                key=lambda binding: (
                    binding.organism_id
                ),
            )
        )

        exact_text = _fraction_text(
            _parse_fraction(
                exact_energy,
                field_name="exact_energy",
            )
        )

        optimum_text = _fraction_text(
            _parse_fraction(
                reference_optimum_energy,
                field_name=(
                    "reference_optimum_energy"
                ),
            )
        )

        core = _verification_payload(
            source_world_state_digest=(
                population
                .source_world_state_digest
            ),
            expected_population_digest=(
                population.digest()
            ),
            expected_population_revision=(
                population.revision
            ),
            problem_digest=problem_digest,
            compilation_digest=(
                compilation_digest
            ),
            qubo_digest=qubo_digest,
            solver_kind=solver_kind,
            solver_artifact_digest=(
                solver_artifact_digest
            ),
            variable_order=variables,
            bits_variable_order=bits,
            candidate_bindings=bindings,
            survivor_count=survivor_count,
            exact_energy=exact_text,
            reference_optimum_energy=(
                optimum_text
            ),
        )

        return cls(
            source_world_state_digest=(
                population
                .source_world_state_digest
            ),
            expected_population_digest=(
                population.digest()
            ),
            expected_population_revision=(
                population.revision
            ),
            problem_digest=problem_digest,
            compilation_digest=(
                compilation_digest
            ),
            qubo_digest=qubo_digest,
            solver_kind=solver_kind,
            solver_artifact_digest=(
                solver_artifact_digest
            ),
            variable_order=variables,
            bits_variable_order=bits,
            candidate_bindings=bindings,
            survivor_count=survivor_count,
            exact_energy=exact_text,
            reference_optimum_energy=(
                optimum_text
            ),
            verification_digest=(
                payload_digest(core)
            ),
        )

    @property
    def selected_ids(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            organism_id
            for organism_id, bit in zip(
                self.variable_order,
                self.bits_variable_order,
            )
            if bit == 1
        )

    @property
    def optimality_gap(
        self,
    ) -> Fraction:
        return (
            _parse_fraction(
                self.exact_energy,
                field_name="exact_energy",
            )
            - _parse_fraction(
                self.reference_optimum_energy,
                field_name=(
                    "reference_optimum_energy"
                ),
            )
        )

    def verification_payload(
        self,
    ) -> dict[str, object]:
        return _verification_payload(
            source_world_state_digest=(
                self.source_world_state_digest
            ),
            expected_population_digest=(
                self.expected_population_digest
            ),
            expected_population_revision=(
                self.expected_population_revision
            ),
            problem_digest=self.problem_digest,
            compilation_digest=(
                self.compilation_digest
            ),
            qubo_digest=self.qubo_digest,
            solver_kind=self.solver_kind,
            solver_artifact_digest=(
                self.solver_artifact_digest
            ),
            variable_order=(
                self.variable_order
            ),
            bits_variable_order=(
                self.bits_variable_order
            ),
            candidate_bindings=(
                self.candidate_bindings
            ),
            survivor_count=(
                self.survivor_count
            ),
            exact_energy=self.exact_energy,
            reference_optimum_energy=(
                self.reference_optimum_energy
            ),
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        payload = self.verification_payload()
        payload["verification_digest"] = (
            self.verification_digest
        )
        return payload

    def digest(self) -> str:
        return payload_digest(
            self.canonical_payload()
        )


@dataclass(frozen=True)
class SelectionCommitPolicyV1:
    maximum_optimality_gap: (
        Fraction | int | str
    ) = 0
    schema: str = (
        SELECTION_COMMIT_POLICY_SCHEMA
    )

    def __post_init__(self) -> None:
        if (
            self.schema
            != SELECTION_COMMIT_POLICY_SCHEMA
        ):
            raise ValueError(
                "Unsupported selection-commit "
                "policy schema."
            )

        gap = _parse_fraction(
            self.maximum_optimality_gap,
            field_name=(
                "maximum_optimality_gap"
            ),
        )

        if gap < 0:
            raise ValueError(
                "maximum_optimality_gap cannot "
                "be negative."
            )

        object.__setattr__(
            self,
            "maximum_optimality_gap",
            gap,
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "maximum_optimality_gap": (
                _fraction_text(
                    self.maximum_optimality_gap
                )
            ),
            "excluded_candidate_transition": (
                "DYING"
            ),
            "selected_candidate_transition": (
                "UNCHANGED"
            ),
            "noncandidate_transition": (
                "UNCHANGED"
            ),
            "atomic": True,
        }

    def digest(self) -> str:
        return payload_digest(
            self.canonical_payload()
        )


@dataclass(frozen=True)
class SelectionCommitResult:
    accepted: bool
    rejection_code: (
        SelectionCommitRejectionCode | None
    )
    proposal_digest: str
    policy_digest: str
    population_before: PopulationState
    population_after: PopulationState
    selected_ids: tuple[str, ...]
    transitioned_to_dying: tuple[str, ...]
    schema: str = (
        SELECTION_COMMIT_RESULT_SCHEMA
    )

    def __post_init__(self) -> None:
        if (
            self.schema
            != SELECTION_COMMIT_RESULT_SCHEMA
        ):
            raise ValueError(
                "Unsupported selection-commit "
                "result schema."
            )

        require_sha256(
            self.proposal_digest,
            field_name="proposal_digest",
        )

        require_sha256(
            self.policy_digest,
            field_name="policy_digest",
        )

        if not isinstance(
            self.population_before,
            PopulationState,
        ):
            raise TypeError(
                "population_before must be a "
                "PopulationState."
            )

        if not isinstance(
            self.population_after,
            PopulationState,
        ):
            raise TypeError(
                "population_after must be a "
                "PopulationState."
            )

        selected = tuple(
            sorted(self.selected_ids)
        )

        transitioned = tuple(
            sorted(
                self.transitioned_to_dying
            )
        )

        object.__setattr__(
            self,
            "selected_ids",
            selected,
        )

        object.__setattr__(
            self,
            "transitioned_to_dying",
            transitioned,
        )

        if self.accepted:
            if self.rejection_code is not None:
                raise ValueError(
                    "Accepted selection cannot carry "
                    "a rejection code."
                )

            if (
                self.population_after.revision
                != self.population_before.revision
                + 1
            ):
                raise ValueError(
                    "Accepted selection must increment "
                    "the population revision once."
                )

            if (
                self.population_after.digest()
                == self.population_before.digest()
            ):
                raise ValueError(
                    "Accepted selection must change "
                    "the population state."
                )

        else:
            if not isinstance(
                self.rejection_code,
                SelectionCommitRejectionCode,
            ):
                raise ValueError(
                    "Rejected selection requires "
                    "a rejection code."
                )

            if (
                self.population_after
                != self.population_before
            ):
                raise ValueError(
                    "Rejected selection must leave "
                    "the population unchanged."
                )

            if transitioned:
                raise ValueError(
                    "Rejected selection cannot "
                    "transition organisms."
                )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "accepted": self.accepted,
            "rejection_code": (
                None
                if self.rejection_code is None
                else self.rejection_code.value
            ),
            "proposal_digest": (
                self.proposal_digest
            ),
            "policy_digest": (
                self.policy_digest
            ),
            "population_before": (
                self.population_before
                .canonical_payload()
            ),
            "population_after": (
                self.population_after
                .canonical_payload()
            ),
            "selected_ids": list(
                self.selected_ids
            ),
            "transitioned_to_dying": list(
                self.transitioned_to_dying
            ),
        }

    def digest(self) -> str:
        return payload_digest(
            self.canonical_payload()
        )


def _rejected(
    *,
    code: SelectionCommitRejectionCode,
    population: PopulationState,
    proposal: SelectionProposal,
    policy: SelectionCommitPolicyV1,
) -> SelectionCommitResult:
    return SelectionCommitResult(
        accepted=False,
        rejection_code=code,
        proposal_digest=proposal.digest(),
        policy_digest=policy.digest(),
        population_before=population,
        population_after=population,
        selected_ids=proposal.selected_ids,
        transitioned_to_dying=(),
    )


def commit_selection(
    *,
    population: PopulationState,
    proposal: SelectionProposal,
    policy: SelectionCommitPolicyV1 = (
        SelectionCommitPolicyV1()
    ),
) -> SelectionCommitResult:
    """Atomically apply a verified selection proposal."""

    if not isinstance(
        population,
        PopulationState,
    ):
        raise TypeError(
            "population must be a PopulationState."
        )

    if not isinstance(
        proposal,
        SelectionProposal,
    ):
        raise TypeError(
            "proposal must be a SelectionProposal."
        )

    if not isinstance(
        policy,
        SelectionCommitPolicyV1,
    ):
        raise TypeError(
            "policy must be a "
            "SelectionCommitPolicyV1."
        )

    if (
        population.source_world_state_digest
        != proposal.source_world_state_digest
    ):
        return _rejected(
            code=(
                SelectionCommitRejectionCode
                .WORLD_STATE_MISMATCH
            ),
            population=population,
            proposal=proposal,
            policy=policy,
        )

    if (
        population.revision
        != proposal.expected_population_revision
    ):
        return _rejected(
            code=(
                SelectionCommitRejectionCode
                .POPULATION_REVISION_MISMATCH
            ),
            population=population,
            proposal=proposal,
            policy=policy,
        )

    if (
        population.digest()
        != proposal.expected_population_digest
    ):
        return _rejected(
            code=(
                SelectionCommitRejectionCode
                .STALE_POPULATION
            ),
            population=population,
            proposal=proposal,
            policy=policy,
        )

    if (
        proposal.optimality_gap
        > policy.maximum_optimality_gap
    ):
        return _rejected(
            code=(
                SelectionCommitRejectionCode
                .OPTIMALITY_GAP_EXCEEDED
            ),
            population=population,
            proposal=proposal,
            policy=policy,
        )

    population_ids = set(
        population.organism_ids
    )

    eligible_states = {
        LifecycleState.ALIVE,
        LifecycleState.REPRODUCTIVE,
    }

    for binding in proposal.candidate_bindings:
        if binding.organism_id not in population_ids:
            return _rejected(
                code=(
                    SelectionCommitRejectionCode
                    .CANDIDATE_NOT_FOUND
                ),
                population=population,
                proposal=proposal,
                policy=policy,
            )

        organism = population.organism(
            binding.organism_id
        )

        if (
            organism.digest()
            != binding.organism_state_digest
            or organism.genotype.digest()
            != binding.genotype_digest
            or organism.lifecycle.value
            != binding.lifecycle
        ):
            return _rejected(
                code=(
                    SelectionCommitRejectionCode
                    .STALE_CANDIDATE_BINDING
                ),
                population=population,
                proposal=proposal,
                policy=policy,
            )

        if organism.lifecycle not in eligible_states:
            return _rejected(
                code=(
                    SelectionCommitRejectionCode
                    .CANDIDATE_NOT_ELIGIBLE
                ),
                population=population,
                proposal=proposal,
                policy=policy,
            )

    candidate_ids = set(
        proposal.variable_order
    )

    selected_ids = set(
        proposal.selected_ids
    )

    transitioned = []
    organisms_after = []

    for organism in population.organisms:
        if (
            organism.organism_id
            in candidate_ids
            and organism.organism_id
            not in selected_ids
        ):
            organisms_after.append(
                transition_lifecycle(
                    organism,
                    LifecycleState.DYING,
                )
            )

            transitioned.append(
                organism.organism_id
            )
        else:
            organisms_after.append(
                organism
            )

    population_after = PopulationState(
        source_world_state_digest=(
            population
            .source_world_state_digest
        ),
        revision=population.revision + 1,
        organisms=tuple(
            organisms_after
        ),
    )

    return SelectionCommitResult(
        accepted=True,
        rejection_code=None,
        proposal_digest=proposal.digest(),
        policy_digest=policy.digest(),
        population_before=population,
        population_after=population_after,
        selected_ids=proposal.selected_ids,
        transitioned_to_dying=tuple(
            transitioned
        ),
    )


__all__ = (
    "PopulationState",
    "SelectionCandidateBinding",
    "SelectionCommitPolicyV1",
    "SelectionCommitRejectionCode",
    "SelectionCommitResult",
    "SelectionProposal",
    "SelectionSolverKind",
    "commit_selection",
)
