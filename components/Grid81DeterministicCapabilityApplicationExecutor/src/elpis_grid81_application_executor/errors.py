"""G5.3C Error classes for capability application."""


class ApplicationError(Exception):
    """Base class for application errors."""
    pass


class ApplicationRejected(ApplicationError):
    """Application was deterministically rejected."""
    def __init__(self, reason: str, details: list[str] | None = None):
        self.reason = reason
        self.details = details or []
        super().__init__(f"{reason}: {'; '.join(details)}")


class AuthorityViolation(ApplicationError):
    """Artifact attempts to write to canonical or prohibited state."""
    def __init__(self, field: str, context: str = ""):
        self.field = field
        self.context = context
        super().__init__(f"Authority violation: {field} {context}")


class ReplayRejected(ApplicationRejected):
    """Deterministic replay rejection."""
    def __init__(self, reason: str):
        super().__init__(reason)


class AtomicityError(ApplicationError):
    """Atomicity guarantee was violated — should never happen in correct code."""
    pass
