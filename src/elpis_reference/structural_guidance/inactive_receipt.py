"""Successor receipts omit measurements that were never made.

V1 remains historical and is still used for fully observed admitted results.
The v2 inactive payload cannot claim a checkpoint, envelope or search result.
"""
from dataclasses import dataclass, field
import hashlib
import json

from .errors import AdmissionUnavailable

SCHEMA = 'elpis.structural-guidance.inactive-receipt.v2'


@dataclass(frozen=True)
class UnavailableDetail:
    error_code: str
    error_class: str
    detail: str

    @classmethod
    def from_error(cls, error: AdmissionUnavailable):
        # Reconstruct from the closed taxonomy; never bind exception text.
        stable = AdmissionUnavailable(error.error_code)
        return cls(stable.error_code, stable.error_class, stable.detail)


@dataclass(frozen=True)
class InactiveGuidanceReceiptV2:
    outcome: str
    projection_digest: str
    input_refinement_fingerprint: str
    errors: tuple[UnavailableDetail, ...]
    receipt_digest: str = field(init=False)

    def __post_init__(self):
        if self.outcome not in ('BYPASSED', 'FALLBACK_REQUIRED'):
            raise ValueError('invalid inactive admission outcome')
        if len(self.errors) != (1 if self.outcome == 'FALLBACK_REQUIRED' else 0):
            raise ValueError('inactive admission error/outcome mismatch')
        for error in self.errors:
            if error != UnavailableDetail.from_error(AdmissionUnavailable(error.error_code)):
                raise ValueError('unrecognized public admission error')
        object.__setattr__(self, 'receipt_digest', self._computed_digest())

    @property
    def enabled(self):
        return self.outcome == 'FALLBACK_REQUIRED'

    @property
    def authority_granted(self):
        return 0  # Explicit policy: an inactive admission grants no authority.

    @property
    def error_code(self):
        return self.errors[0].error_code

    def payload(self):
        from dataclasses import asdict
        return {
            'schema': SCHEMA,
            'outcome': self.outcome,
            'projection_digest': self.projection_digest,
            'input_refinement_fingerprint': self.input_refinement_fingerprint,
            'errors': [asdict(error) for error in self.errors],
        }

    def _computed_digest(self):
        return hashlib.sha256(json.dumps(
            self.payload(), sort_keys=True, separators=(',', ':'),
            ensure_ascii=False, allow_nan=False,
        ).encode('utf-8')).hexdigest()

    def validate_digest(self):
        return self.receipt_digest == self._computed_digest()
