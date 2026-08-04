"""G4.0B.1 Typed Projection Compiler with D4 Orbit Implementation."""

__version__ = "0.1.0"
__spec_version__ = "g4.0b.1.v1"

from elpis_grid81_typed.canonical import canonicalize, domain_digest
from elpis_grid81_typed.source_identity import SourceRowIdentityV1
from elpis_grid81_typed.transition import T00TransitionViewV1
from elpis_grid81_typed.expansion import T00ExpansionLocusViewV1
from elpis_grid81_typed.quiescence import T00QuiescenceViewV1
from elpis_grid81_typed.rationale import T00RationaleViewV1
from elpis_grid81_typed.d4 import D4, D4_TRANSFORMS
from elpis_grid81_typed.typed_orbits import (
    TransitionOrbitV1,
    ExpansionOrbitV1,
    QuiescenceOrbitV1,
    RationaleOrbitV1,
)
from elpis_grid81_typed.compiler import compile_corpus
from elpis_grid81_typed.errors import (
    ElpisGridError,
    CanonicalizationError,
    SourceIdentityError,
    TransitionCompilerError,
    ExpansionCompilerError,
    QuiescenceCompilerError,
    RationaleCompilerError,
    D4Error,
    OrbitError,
)

__all__ = [
    "canonicalize",
    "domain_digest",
    "SourceRowIdentityV1",
    "T00TransitionViewV1",
    "T00ExpansionLocusViewV1",
    "T00QuiescenceViewV1",
    "T00RationaleViewV1",
    "D4",
    "D4_TRANSFORMS",
    "TransitionOrbitV1",
    "ExpansionOrbitV1",
    "QuiescenceOrbitV1",
    "RationaleOrbitV1",
    "compile_corpus",
    "ElpisGridError",
    "CanonicalizationError",
    "SourceIdentityError",
    "TransitionCompilerError",
    "ExpansionCompilerError",
    "QuiescenceCompilerError",
    "RationaleCompilerError",
    "D4Error",
    "OrbitError",
]
