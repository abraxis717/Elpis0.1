"""Admission failures preserve integrity classifications across loader boundaries."""


class AdmissionIntegrityViolation(RuntimeError):
    """A required identity or authority invariant did not hold."""


class AdmissionUnavailable(RuntimeError):
    """An explicitly optional admission dependency is unavailable."""

    _DETAILS = {
        'TORCH_UNAVAILABLE': 'Optional torch runtime is unavailable.',
    }

    def __init__(self, error_code: str):
        self.error_code = error_code
        self.error_class = 'AdmissionUnavailable'
        self.detail = self._DETAILS[error_code]
        super().__init__(self.detail)
