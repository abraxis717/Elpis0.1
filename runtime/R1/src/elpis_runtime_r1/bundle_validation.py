"""RetrievalBundle validation — gate before P0 projection.

Validates schema identity, query binding, epoch consistency, rank ordering,
chunk identity, text presence, dedup, budget bounds, and provenance fields.
Fails closed on any violation.
"""

from __future__ import annotations

from .budget import BudgetDecision, RetrievalBudget
from .contracts import RetrievalBundle, RetrievalItem, _sha256_hex
from .errors import R1BundleValidationError


def validate_bundle(
    bundle: RetrievalBundle,
    expected_query_digest: str,
    corpus_manifest_digest: str,
    budget: RetrievalBudget | None = None,
) -> BudgetDecision | None:
    """Validate a RetrievalBundle against canonical constraints.

    Args:
        bundle: The bundle to validate.
        expected_query_digest: Digest the bundle must be bound to.
        corpus_manifest_digest: Corpus manifest the bundle must reference.
        budget: Optional budget for size checks.

    Returns:
        BudgetDecision if budget was provided and passed, else None.

    Raises:
        R1BundleValidationError: on any validation failure.
    """
    # 1. Schema identity
    if bundle.schema != "elpis.retrieval_bundle.v1":
        raise R1BundleValidationError(
            "UNKNOWN_SCHEMA",
            f"Bundle schema '{bundle.schema}' != expected 'elpis.retrieval_bundle.v1'",
        )

    # 2. Query digest binding
    if bundle.query_digest != expected_query_digest:
        raise R1BundleValidationError(
            "QUERY_DIGEST_MISMATCH",
            f"Bundle query_digest '{bundle.query_digest}' != "
            f"expected '{expected_query_digest}'",
        )

    # 3. Corpus manifest binding
    if bundle.corpus_manifest_digest != corpus_manifest_digest:
        raise R1BundleValidationError(
            "CORPUS_DIGEST_MISMATCH",
            f"Bundle corpus_manifest '{bundle.corpus_manifest_digest}' != "
            f"expected '{corpus_manifest_digest}'",
        )

    # 4. Epoch consistency — corpus and vector_index epochs must be non-negative
    if bundle.corpus_epoch < 0:
        raise R1BundleValidationError(
            "EPOCH_DRIFT",
            f"Negative corpus_epoch: {bundle.corpus_epoch}",
        )
    if bundle.vector_index_epoch < 0:
        raise R1BundleValidationError(
            "EPOCH_DRIFT",
            f"Negative vector_index_epoch: {bundle.vector_index_epoch}",
        )

    # 5. Rank ordering and item validation
    seen_chunk_digests: set[str] = set()
    total_bytes = 0

    for rank, item in enumerate(bundle.items):
        # Final rank must match position
        if item.final_rank != rank:
            raise R1BundleValidationError(
                "RANK_ORDER",
                f"Item at position {rank} has final_rank={item.final_rank}",
            )

        # Chunk digest must be non-empty
        if not item.chunk_digest:
            raise R1BundleValidationError(
                "MISSING_CHUNK_DIGEST",
                f"Item {rank} has empty chunk_digest",
            )

        # Duplicate chunk rejection
        if item.chunk_digest in seen_chunk_digests:
            raise R1BundleValidationError(
                "DUPLICATE_CHUNK",
                f"Duplicate chunk_digest at rank {rank}: {item.chunk_digest}",
            )
        seen_chunk_digests.add(item.chunk_digest)

        # Frozen text must be present
        if not item.text:
            raise R1BundleValidationError(
                "MISSING_FROZEN_TEXT",
                f"Item {rank} has empty text",
            )

        # Verify text digest matches
        actual_text_digest = _sha256_hex(item.text.encode("utf-8"))
        if item.text_digest and item.text_digest != actual_text_digest:
            raise R1BundleValidationError(
                "TEXT_DIGEST_MISMATCH",
                f"Item {rank}: declared text_digest '{item.text_digest}' "
                f"!= computed '{actual_text_digest}'",
            )

        # Text bytes field consistency
        if item.text_bytes != len(item.text.encode("utf-8")):
            raise R1BundleValidationError(
                "TEXT_BYTES_MISMATCH",
                f"Item {rank}: text_bytes={item.text_bytes} != "
                f"actual {len(item.text.encode('utf-8'))}",
            )

        # Individual chunk byte bound
        if budget and item.text_bytes > budget.max_individual_chunk_bytes:
            raise R1BundleValidationError(
                "CHUNK_BYTE_OVERFLOW",
                f"Item {rank}: {item.text_bytes} > "
                f"{budget.max_individual_chunk_bytes}",
            )

        # Context expansion: one-hop only
        if item.graph_hop > 1:
            raise R1BundleValidationError(
                "CONTEXT_Beyond_ONE_HOP",
                f"Item {rank}: graph_hop={item.graph_hop} > 1",
            )

        # Provenance: UNAVAILABLE for primary items without graph
        if item.graph_hop == 0:
            # Primary evidence — graph_parent should be all-zero hex
            if item.graph_parent_digest != "0" * 64:
                # Allow empty as alternative sentinel
                if item.graph_parent_digest and item.graph_parent_digest != "0" * 64:
                    raise R1BundleValidationError(
                        "INVENTED_PROVENANCE",
                        f"Primary item {rank} has non-zero graph_parent_digest",
                    )

        total_bytes += item.text_bytes

    # 6. Budget enforcement
    if budget:
        counts = {
            "lexical": sum(
                1 for i in bundle.items if i.lexical_rank > 0
            ),
            "dense": sum(
                1 for i in bundle.items if i.dense_rank > 0
            ),
            "fused": len(bundle.items),
            "context": sum(
                1 for i in bundle.items if i.item_kind == 2
            ),
            "total": len(bundle.items),
        }
        if len(bundle.items) > budget.max_total_chunks:
            raise R1BundleValidationError(
                "BUDGET_OVERFLOW",
                f"Bundle has {len(bundle.items)} items > "
                f"budget max_total_chunks={budget.max_total_chunks}",
            )
        if total_bytes > budget.max_total_evidence_bytes:
            raise R1BundleValidationError(
                "EVIDENCE_BYTE_OVERFLOW",
                f"Total evidence bytes {total_bytes} > "
                f"{budget.max_total_evidence_bytes}",
            )
        return _make_budget_decision(budget, counts, total_bytes)

    return None


def _make_budget_decision(
    budget: RetrievalBudget,
    counts: dict[str, int],
    total_bytes: int,
) -> BudgetDecision:
    from .budget import BudgetDecision
    return BudgetDecision(
        budget_digest=budget.digest(),
        requested_count=counts.get("fused", 0),
        available_count=counts.get("total", 0),
        admitted_count=counts.get("total", 0),
        truncation_reason="NONE",
        total_evidence_bytes=total_bytes,
        exceeded=False,
    )


def validate_bundle_schema(schema: str) -> None:
    """Validate schema string alone (pre-validation check)."""
    if schema not in ("elpis.retrieval_bundle.v1",):
        raise R1BundleValidationError(
            "UNKNOWN_SCHEMA",
            f"Unknown RetrievalBundle schema: {schema}",
        )
