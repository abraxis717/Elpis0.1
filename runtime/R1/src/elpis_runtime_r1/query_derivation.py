"""Deterministic retrieval-query derivation from RequestContext.

Contract:
  - Deterministic for identical input
  - Bounded output length
  - Explicit normalization
  - No wall-clock, process, random, or filesystem path data
  - No hidden model inference
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .contracts import RetrievalQuery, _digest
from .errors import R1QueryDerivationError


# Maximum derived query length
MAX_QUERY_BYTES = 4096

# Selected stable RequestContext fields for query derivation
SELECTED_FIELDS = ("request_id", "prompt", "domain", "entrypoint")

# Normalization schema identifier
NORMALIZATION_SCHEMA = "unicode_nfkc_lowercase_ascii_strip_v1"


def _normalize_query(text: str) -> str:
    """Deterministic normalization: NFKC + lowercase + strip non-ASCII + collapse whitespace."""
    # Unicode normalization
    text = unicodedata.normalize("NFKC", text)
    # Lowercase
    text = text.lower()
    # Strip non-ASCII
    text = text.encode("ascii", "ignore").decode("ascii")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def derive_query(
    request: dict[str, Any],
    budget_params: dict[str, Any] | None = None,
) -> RetrievalQuery:
    """Derive a canonical retrieval query from RequestContext fields.

    Args:
        request: RequestContext dict with stable fields.
        budget_params: Optional budget parameter dict for recording.

    Returns:
        RetrievalQuery with digests and normalization metadata.

    Raises:
        R1QueryDerivationError: on malformed input or overflow.
    """
    # Validate required fields
    for field in SELECTED_FIELDS:
        if field not in request:
            raise R1QueryDerivationError(
                "MISSING_FIELD",
                f"RequestContext missing required field: {field}",
            )

    # Extract selected fields
    request_digest = _digest(request)
    selected_values: list[str] = []
    for field in SELECTED_FIELDS:
        value = request[field]
        if isinstance(value, (tuple, list)):
            selected_values.append("|".join(str(v) for v in value))
        else:
            selected_values.append(str(value))

    # Build raw query from selected fields
    raw_query = " ".join(selected_values)

    # Normalize
    normalized = _normalize_query(raw_query)

    # Empty query check
    if not normalized:
        raise R1QueryDerivationError(
            "EMPTY_QUERY",
            "Derived query is empty after normalization — forbidden",
        )

    # Bounded length check
    query_bytes = normalized.encode("utf-8")
    if len(query_bytes) > MAX_QUERY_BYTES:
        raise R1QueryDerivationError(
            "QUERY_OVERFLOW",
            f"Derived query {len(query_bytes)} bytes exceeds max {MAX_QUERY_BYTES}",
        )

    # Compute digests
    query_digest = _digest(normalized)

    # Budget parameters serialization
    if budget_params is None:
        budget_params = {}
    budget_str = _digest(budget_params)

    return RetrievalQuery(
        query_text=normalized,
        query_digest=query_digest,
        source_request_digest=request_digest,
        selected_fields=SELECTED_FIELDS,
        normalization_schema=NORMALIZATION_SCHEMA,
        budget_parameters=budget_str,
    )


def verify_query(query: RetrievalQuery, request: dict[str, Any]) -> bool:
    """Verify that a RetrievalQuery matches the source request."""
    expected = derive_query(request)
    return expected.query_digest == query.query_digest
