"""G5.0B compiler error types."""


class G50BError(Exception):
    """Base error for G5.0B compiler."""
    pass


class UpstreamSealError(G50BError):
    """Upstream seal verification failed."""
    pass


class SourceJoinError(G50BError):
    """Source inventory join failed."""
    pass


class DerivationError(G50BError):
    """Evidence derivation law violated."""
    pass


class OrbitError(G50BError):
    """D4 orbit computation error."""
    pass


class ProposalError(G50BError):
    """Proposal compilation error."""
    pass


class OrderingError(G50BError):
    """Proposal ordering error."""
    pass


class ConflictError(G50BError):
    """Conflict evidence error."""
    pass


class VerificationError(G50BError):
    """Verifier found inconsistency."""
    pass
