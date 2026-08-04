"""G5.3B Error classes for capability consumption."""


class ConsumptionError(Exception):
    """Base class for capability consumption errors."""
    pass


class ValidationFailed(ConsumptionError):
    """Transaction input failed validation."""
    pass


class SchemaMismatch(ConsumptionError):
    """Schema version or structure mismatch."""
    pass


class ForbiddenFieldError(ConsumptionError):
    """Forbidden runtime/activation field detected in artifact."""
    pass
