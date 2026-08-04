"""R0 transaction errors — fail-closed, typed, deterministic."""

from __future__ import annotations


class R0Error(Exception):
    """Base error for R0 transaction failures."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"[{code}] {detail}")


class R0ImportEscapeError(R0Error):
    """Raised when a runtime import escapes to old source roots."""

    def __init__(self, escaped_path: str):
        super().__init__(
            "IMPORT_ESCAPE",
            f"Import resolved to forbidden path: {escaped_path}",
        )
        self.escaped_path = escaped_path


class R0CanonicalMutationError(R0Error):
    """Raised when canonical assembly is detected as modified."""

    def __init__(self, detail: str):
        super().__init__("CANONICAL_MUTATION", detail)


class R0RequestContextError(R0Error):
    """Raised when RequestContext is malformed."""

    pass


class R0Grid81ReadError(R0Error):
    """Raised when Grid81 canonical read fails."""

    pass


class R0OracleError(R0Error):
    """Raised when StructuralOracle integration fails."""

    pass


class R0OracleRejectionError(R0Error):
    """Oracle returned rejection — transaction must fail closed."""

    pass


class R0AdjudicatorError(R0Error):
    """Raised when adjudicator integration fails."""

    pass


class R0AdjudicatorRejectionError(R0Error):
    """Adjudicator rejected — transaction must fail closed."""

    pass


class R0DarwinianError(R0Error):
    """Raised when Darwinian integration fails."""

    pass


class R0DarwinianRejectionError(R0Error):
    """Darwinian evaluation rejected — transaction must fail closed."""

    pass


class R0DecoderError(R0Error):
    """Raised when decoder integration fails."""

    pass


class R0ASTValidationFailure(R0Error):
    """AST validator rejected the decoded artifact."""

    pass


class R0ReceiptError(R0Error):
    """Raised when receipt construction fails."""

    pass
