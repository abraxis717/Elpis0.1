"""Error hierarchy for the Typed Projection Compiler."""


class ElpisGridError(Exception):
    """Base exception for all Grid81 typed projection errors."""
    pass


class CanonicalizationError(ElpisGridError):
    """Error in canonical serialization or domain-separated digest."""
    pass


class SourceIdentityError(ElpisGridError):
    """Error in source row identity derivation or validation."""
    pass


class TransitionCompilerError(ElpisGridError):
    """Error in transition view compilation."""
    pass


class ExpansionCompilerError(ElpisGridError):
    """Error in expansion locus view compilation."""
    pass


class QuiescenceCompilerError(ElpisGridError):
    """Error in quiescence view compilation."""
    pass


class RationaleCompilerError(ElpisGridError):
    """Error in rationale view compilation."""
    pass


class D4Error(ElpisGridError):
    """Error in D4 group operations."""
    pass


class OrbitError(ElpisGridError):
    """Error in typed orbit identity computation."""
    pass
