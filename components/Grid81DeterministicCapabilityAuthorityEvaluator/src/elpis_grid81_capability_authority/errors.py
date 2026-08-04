"""G5.2B Error types and failure codes."""


class AuthorityError(Exception):
    """Base authority evaluation error."""


class UpstreamSealError(AuthorityError):
    """Upstream seal verification failure."""
    def __init__(self, code, details=""):
        self.code = code
        super().__init__(f"{code}: {details}")


class SourceJoinError(AuthorityError):
    """Source-domain join failure."""
    def __init__(self, code, details=""):
        self.code = code
        super().__init__(f"{code}: {details}")


class PolicyError(AuthorityError):
    """Authority policy error."""
    def __init__(self, code, details=""):
        self.code = code
        super().__init__(f"{code}: {details}")


class ContextError(AuthorityError):
    """Authority context error."""
    def __init__(self, code, details=""):
        self.code = code
        super().__init__(f"{code}: {details}")


class ScopeError(AuthorityError):
    """Capability scope error."""
    def __init__(self, code, details=""):
        self.code = code
        super().__init__(f"{code}: {details}")


class LimitError(AuthorityError):
    """Capability limit error."""
    def __init__(self, code, details=""):
        self.code = code
        super().__init__(f"{code}: {details}")


class NonceError(AuthorityError):
    """Nonce generation/verification error."""
    def __init__(self, code, details=""):
        self.code = code
        super().__init__(f"{code}: {details}")


class CapabilityError(AuthorityError):
    """Capability compilation error."""
    def __init__(self, code, details=""):
        self.code = code
        super().__init__(f"{code}: {details}")


class LifecycleError(AuthorityError):
    """Lifecycle state error."""
    def __init__(self, code, details=""):
        self.code = code
        super().__init__(f"{code}: {details}")


class BoundaryError(AuthorityError):
    """Authority boundary violation."""
    def __init__(self, code, details=""):
        self.code = code
        super().__init__(f"{code}: {details}")


class DeterminismError(AuthorityError):
    """Determinism verification failure."""
    def __init__(self, code, details=""):
        self.code = code
        super().__init__(f"{code}: {details}")


class MutationError(AuthorityError):
    """Mutation qualification failure."""
    def __init__(self, code, details=""):
        self.code = code
        super().__init__(f"{code}: {details}")
