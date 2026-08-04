"""G5.3C Deterministic Capability Application Executor.

Applies UNAPPLIED G5.3B consumption artifacts against shadow capability records
with deterministic guards, atomicity, replay protection, and mutation qualification.

No canonical G5.2B mutation. No DarwinianMatrix access. No model activation.
"""
from .canonical import canonical_json, canonical_digest, check_hex64
from .errors import ApplicationError, ApplicationRejected, AuthorityViolation
from .shadow_state import ShadowCapabilityState
from .application import apply_artifact
from .ledger import ApplicationLedger, ledger_head_digest
