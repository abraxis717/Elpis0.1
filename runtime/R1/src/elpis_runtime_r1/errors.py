"""R1 transaction errors — fail-closed, typed, deterministic."""

from __future__ import annotations


class R1Error(Exception):
    """Base error for R1 transaction failures."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"[{code}] {detail}")


class R1QueryDerivationError(R1Error):
    """Raised when query derivation fails or overflows."""

    pass


class R1HacfImportError(R1Error):
    """Raised when HACF library cannot be loaded."""

    pass


class R1HacfRetrievalError(R1Error):
    """Raised when HACF retrieval call fails."""

    pass


class R1BundleValidationError(R1Error):
    """Raised when RetrievalBundle validation fails."""

    pass


class R1BudgetOverflowError(R1Error):
    """Raised when retrieval budget is exceeded."""

    pass


class R1EvidenceAdapterError(R1Error):
    """Raised when evidence envelope construction fails."""

    pass


class R1DownstreamR0Error(R1Error):
    """Raised when downstream R0 transaction rejects or fails."""

    pass


class R1DeterminismError(R1Error):
    """Raised when determinism verification fails."""

    pass


class R1DependencyEscapeError(R1Error):
    """Raised when import escapes to forbidden roots."""

    pass


class R1CanonicalMutationError(R1Error):
    """Raised when canonical assembly is detected as modified."""

    pass
