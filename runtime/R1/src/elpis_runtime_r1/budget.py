"""Retrieval budget — explicit immutable limits, versioned contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import _digest
from .errors import R1BudgetOverflowError


# Versioned budget contract
BUDGET_CONTRACT_VERSION = "elpis.retrieval_budget.v1"


@dataclass(frozen=True)
class RetrievalBudget:
    """Immutable retrieval budget with explicit limits."""
    contract_version: str = BUDGET_CONTRACT_VERSION

    # Candidate limits
    max_lexical_candidates: int = 100
    max_dense_candidates: int = 100

    # Fused result limits
    max_fused_results: int = 50

    # Context expansion limits
    max_context_neighbors_per_seed: int = 10
    max_context_seeds: int = 20

    # Total limits
    max_total_chunks: int = 200
    max_total_evidence_bytes: int = 256 * 1024  # 256 KB
    max_individual_chunk_bytes: int = 8 * 1024  # 8 KB

    # Time limit (seconds) — for qualification only
    max_wall_clock_seconds: float = 30.0

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "max_lexical_candidates": self.max_lexical_candidates,
            "max_dense_candidates": self.max_dense_candidates,
            "max_fused_results": self.max_fused_results,
            "max_context_neighbors_per_seed": self.max_context_neighbors_per_seed,
            "max_context_seeds": self.max_context_seeds,
            "max_total_chunks": self.max_total_chunks,
            "max_total_evidence_bytes": self.max_total_evidence_bytes,
            "max_individual_chunk_bytes": self.max_individual_chunk_bytes,
            "max_wall_clock_seconds": self.max_wall_clock_seconds,
        }

    def digest(self) -> str:
        return _digest(self.to_canonical_dict())


@dataclass(frozen=True)
class BudgetDecision:
    """Budget enforcement decision record."""
    budget_digest: str
    requested_count: int
    available_count: int
    admitted_count: int
    truncation_reason: str  # "NONE" if no truncation
    total_evidence_bytes: int
    exceeded: bool

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "budget_digest": self.budget_digest,
            "requested_count": self.requested_count,
            "available_count": self.available_count,
            "admitted_count": self.admitted_count,
            "truncation_reason": self.truncation_reason,
            "total_evidence_bytes": self.total_evidence_bytes,
            "exceeded": self.exceeded,
        }


def check_budget(
    budget: RetrievalBudget,
    actual_counts: dict[str, int],
    total_evidence_bytes: int,
) -> BudgetDecision:
    """Check actual retrieval counts against budget limits.

    Args:
        budget: The budget contract.
        actual_counts: Dict with keys like 'lexical', 'dense', 'fused', 'context', 'total'.
        total_evidence_bytes: Total bytes of all retrieved evidence text.

    Returns:
        BudgetDecision with admission counts and truncation info.

    Raises:
        R1BudgetOverflowError: if any hard limit is exceeded.
    """
    truncation_reasons: list[str] = []
    admitted = actual_counts.get("total", 0)
    available = actual_counts.get("total", 0)
    requested = actual_counts.get("fused", 0) + actual_counts.get("context", 0)

    # Check each limit
    if actual_counts.get("lexical", 0) > budget.max_lexical_candidates:
        truncation_reasons.append(
            f"lexical {actual_counts['lexical']} > {budget.max_lexical_candidates}"
        )

    if actual_counts.get("dense", 0) > budget.max_dense_candidates:
        truncation_reasons.append(
            f"dense {actual_counts['dense']} > {budget.max_dense_candidates}"
        )

    if actual_counts.get("fused", 0) > budget.max_fused_results:
        truncation_reasons.append(
            f"fused {actual_counts['fused']} > {budget.max_fused_results}"
        )

    if actual_counts.get("context", 0) > (
        budget.max_context_seeds * budget.max_context_neighbors_per_seed
    ):
        truncation_reasons.append(
            f"context {actual_counts['context']} > "
            f"{budget.max_context_seeds * budget.max_context_neighbors_per_seed}"
        )

    if actual_counts.get("total", 0) > budget.max_total_chunks:
        truncation_reasons.append(
            f"total {actual_counts['total']} > {budget.max_total_chunks}"
        )

    if total_evidence_bytes > budget.max_total_evidence_bytes:
        truncation_reasons.append(
            f"evidence_bytes {total_evidence_bytes} > {budget.max_total_evidence_bytes}"
        )

    if truncation_reasons:
        raise R1BudgetOverflowError(
            "BUDGET_EXCEEDED",
            "Budget limits exceeded: " + "; ".join(truncation_reasons),
        )

    return BudgetDecision(
        budget_digest=budget.digest(),
        requested_count=requested,
        available_count=available,
        admitted_count=admitted,
        truncation_reason="NONE",
        total_evidence_bytes=total_evidence_bytes,
        exceeded=False,
    )
