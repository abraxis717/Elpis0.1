from __future__ import annotations

from .controller import P0Controller
from .decoder import (
    DeterministicPythonDecoder,
)
from .experts import (
    DeterministicExpertProposer,
)
from .initial_void_scope_provider import (
    InitialVoidScopeProvider,
)
from .semantic_binding import (
    SemanticSidecarPythonProjector,
)
from .refinement_proposer import (
    DeterministicShadowRefinementProposer,
)
from .trm import ShadowTRMProposer
from .validators import (
    PythonASTValidator,
)


def build_default_controller(
) -> P0Controller:
    return P0Controller(
        projector=(
            SemanticSidecarPythonProjector()
        ),
        trm=ShadowTRMProposer(),
        expert_proposer=(
            DeterministicExpertProposer()
        ),
        decoder=(
            DeterministicPythonDecoder()
        ),
        validators=(
            PythonASTValidator(),
        ),
        refinement_proposer=(
            DeterministicShadowRefinementProposer()
        ),
        scope_provider=InitialVoidScopeProvider(),
    )
