from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

from .identity import require_hex


class ConvergenceContractError(ValueError):
    pass


class ContractionMethod(str, Enum):
    TIME_UNIFORM_CONFIDENCE_SEQUENCE = (
        "time_uniform_confidence_sequence"
    )
    DETERMINISTIC_BOUND = "deterministic_bound"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ContractionEvidence:
    """
    Statistical evidence contract only.

    Y0/C1 does not implement or certify a particular empirical-Bernstein
    theorem. `method_id` and `assumptions` must identify the exact estimator
    admitted in a later convergence phase.
    """

    method: ContractionMethod
    method_id: str
    estimator_version: str
    alpha: float
    sample_count: int
    upper_bound: float
    valid_through_iteration: int
    assumptions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.method_id or not self.estimator_version:
            raise ConvergenceContractError(
                "contraction estimator identity is required"
            )
        if not 0.0 < self.alpha < 1.0:
            raise ConvergenceContractError("alpha must be in (0, 1)")
        if self.sample_count < 1:
            raise ConvergenceContractError(
                "sample_count must be positive"
            )
        if self.valid_through_iteration < 0:
            raise ConvergenceContractError(
                "valid_through_iteration must be non-negative"
            )
        if not math.isfinite(self.upper_bound):
            raise ConvergenceContractError(
                "upper_bound must be finite"
            )
        if not self.assumptions:
            raise ConvergenceContractError(
                "estimator assumptions must be explicit"
            )


@dataclass(frozen=True, slots=True)
class StopCertificate:
    """
    Evidence that a scheduler may propose termination.

    This certificate does not grant emission, memory-write or governance
    authority.
    """

    request_id: str
    anchor_iteration: int
    terminal_iteration: int
    grid_signature_chi: str
    maximum_step_delta: float
    maximum_anchor_displacement: float
    maximum_residual: float
    contraction_evidence: ContractionEvidence
    validator_evidence_ref: str
    obligation_certificate_ref: str

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ConvergenceContractError("request_id is required")
        if self.anchor_iteration < 0:
            raise ConvergenceContractError(
                "anchor_iteration must be non-negative"
            )
        if self.terminal_iteration < self.anchor_iteration:
            raise ConvergenceContractError(
                "terminal_iteration precedes anchor_iteration"
            )
        require_hex(
            self.grid_signature_chi,
            field_name="grid_signature_chi",
        )
        for field_name, value in (
            ("maximum_step_delta", self.maximum_step_delta),
            (
                "maximum_anchor_displacement",
                self.maximum_anchor_displacement,
            ),
            ("maximum_residual", self.maximum_residual),
        ):
            if not math.isfinite(value) or value < 0:
                raise ConvergenceContractError(
                    f"{field_name} must be finite and non-negative"
                )
        if not self.validator_evidence_ref:
            raise ConvergenceContractError(
                "validator evidence reference is required"
            )
        if not self.obligation_certificate_ref:
            raise ConvergenceContractError(
                "obligation certificate reference is required"
            )
