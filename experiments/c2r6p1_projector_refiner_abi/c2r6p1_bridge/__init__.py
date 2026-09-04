"""C2R6-P1 projector -> structural-refiner ABI bridge (experimental).

Public surface:
  * adapt_projection_to_refiner_input   (adapter)
  * build_envelope                       (semantic binding sidecar)
  * legal_candidates / apply_candidate   (candidate + transition)
  * NullRefiner / FirstLegalMoveRefiner  (deterministic test refiners)
  * run_refiner_bounded / empty_trace
  * replay_transition_chain              (mission 16)
  * pack_529 / roundtrip_529 / one_hot   (D0.1 packer compatibility)

Import order contract: the C2R6-P0 authority overlay (elpis_p0 -> frozen
C2R7-C structural_residual + canonical elpis_p0, plus the C2R7-C probe
dir on sys.path for structural_trm_features) must be installed BEFORE
importing this package. ``c2r6p0`` does that in its ``__init__``; tests
install it via the shared conftest.
"""
from .contracts import (  # noqa: F401
    BridgeRejection,
    BridgeRejectionCode,
    BridgeRejectionError,
    CandidateMoveV1,
    RefinerEnvelopeV1,
    RefinerInputV1,
    RefinerTransitionEvent,
    RefinerTransitionTraceV1,
    TransitionResultV1,
    digest_refiner_input,
    refinement_state_fingerprint,
    residual_state_digest,
    signed_envelope,
    signed_refiner_input,
    signed_trace,
    signed_transition,
)
from .adapter import (  # noqa: F401
    adapt_projection_to_refiner_input,
    build_envelope,
    validate_projection_for_bridge,
)
from .refiners import (  # noqa: F401
    FirstLegalMoveRefiner,
    NullRefiner,
    apply_candidate,
    empty_trace,
    legal_candidates,
    replay_grid_after,
    replay_transition_chain,
    run_refiner_bounded,
)
from .packer import one_hot, pack_529, roundtrip_529  # noqa: F401
from .ambient_guard import AmbientViolation, ambient_guard  # noqa: F401

__all__ = [
    "BridgeRejection",
    "BridgeRejectionCode",
    "BridgeRejectionError",
    "CandidateMoveV1",
    "RefinerEnvelopeV1",
    "RefinerInputV1",
    "RefinerTransitionEvent",
    "RefinerTransitionTraceV1",
    "TransitionResultV1",
    "digest_refiner_input",
    "refinement_state_fingerprint",
    "residual_state_digest",
    "signed_envelope",
    "signed_refiner_input",
    "signed_trace",
    "signed_transition",
    "adapt_projection_to_refiner_input",
    "build_envelope",
    "validate_projection_for_bridge",
    "FirstLegalMoveRefiner",
    "NullRefiner",
    "apply_candidate",
    "empty_trace",
    "legal_candidates",
    "replay_grid_after",
    "replay_transition_chain",
    "run_refiner_bounded",
    "one_hot",
    "pack_529",
    "roundtrip_529",
    "AmbientViolation",
    "ambient_guard",
]
