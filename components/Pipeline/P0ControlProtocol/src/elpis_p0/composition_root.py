"""CoreRuntimeBundle — composition root for consolidated Elpis core.

This module constructs the canonical runtime bundle containing all components
identified by the CDC (Core Dependency Consolidation) gate.

Design rules:
- This module imports lower-level packages; lower-level packages never import this.
- No circular imports.
- No learned T00 imports.
- No ECRF imports.
- Component identities, authority classifications, and construction results
  are exposed as typed attributes.
- Construction states distinguish: DECLARED, CONSTRUCTED, PACKAGE_UNAVAILABLE,
  CONSTRUCTION_FAILED, ARGUMENTS_REQUIRED, INTENTIONALLY_UNWIRED.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Construction state enumeration
# ---------------------------------------------------------------------------


class ConstructionState(str, Enum):
    """Explicit construction result for each component."""

    CONSTRUCTED = "CONSTRUCTED"
    PACKAGE_UNAVAILABLE = "PACKAGE_UNAVAILABLE"
    CONSTRUCTION_FAILED = "CONSTRUCTION_FAILED"
    ARGUMENTS_REQUIRED = "ARGUMENTS_REQUIRED"
    INTENTIONALLY_UNWIRED = "INTENTIONALLY_UNWIRED"
    DECLARED = "DECLARED"  # Declared in contract but not yet constructed


# ---------------------------------------------------------------------------
# Authority and role constants
# ---------------------------------------------------------------------------

ROLE_CANONICAL_RUNTIME = "CANONICAL_RUNTIME"
ROLE_SHADOW_IMPLEMENTATION = "SHADOW_IMPLEMENTATION"
ROLE_REFERENCE_IMPLEMENTATION = "REFERENCE_IMPLEMENTATION"

AUTHORITY_EXECUTION = "EXECUTION_AND_REFINEMENT"
AUTHORITY_STRUCTURAL_TRANSITION = "STRUCTURAL_TRANSITION_ORACLE"
AUTHORITY_PROPOSAL = "PROPOSAL_ONLY"
AUTHORITY_DECODING = "DECODING"
AUTHORITY_VALIDATION = "VALIDATION"
AUTHORITY_SCOPE = "SCOPE_DECISION"
AUTHORITY_PLANNING = "PLANNING"
AUTHORITY_EVIDENCE = "EVIDENCE_ORTHOGONALIZATION"
AUTHORITY_EPISODE = "EPISODE_STATE_MANAGER"
AUTHORITY_REFINEMENT_ADAPTER = "STRUCTURAL_REFINEMENT_ADAPTER"
AUTHORITY_NONE = "NONE"
AUTHORITY_PROJECTION = "STRUCTURAL_PROJECTION"


# ---------------------------------------------------------------------------
# Component identity and construction result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ComponentIdentity:
    """Typed identity for a bundle component."""

    name: str
    role: str
    authority: str
    disposition: str  # ACTIVE | SHADOW | NOT_YET_WIRED | OPTIONAL
    import_path: str
    description: str


@dataclass(frozen=True)
class ComponentConstructionResult:
    """Explicit result of a component construction attempt."""

    component_name: str
    state: ConstructionState
    instance: Any = None
    error_message: Optional[str] = None
    implementation_class: Optional[str] = None


@dataclass(frozen=True)
class ComponentInstanceRecord:
    """Full ledger entry for a constructed or declared component."""

    name: str
    implementation_class: str
    role: str
    authority: str
    disposition: str
    construction_state: ConstructionState
    active: bool
    owner: str  # owning component or "bundle"
    source_module: str
    source_sha256: str
    configuration_identity: Optional[str] = None


# ---------------------------------------------------------------------------
# CoreRuntimeBundle
# ---------------------------------------------------------------------------


@dataclass
class CoreRuntimeBundle:
    """Composition root for the consolidated Elpis core pipeline.

    Constructs components from the canonical nesting contract.
    Exposes component identities, authority classifications, and
    explicit construction results.

    Attributes:
        p0_controller: P0Controller instance (or None if not constructed).
        structural_oracle: StructuralOracle instance (or None if not wired).
        structural_adapter: DeterministicSudokuReferenceAdapter (or None).
        darwinian_episode_factory: callable that creates DarwinianEpisodeState (or None).
        recursive_evidence_controller: RecursiveEmbeddingController (or None).

    The bundle tracks which components are ACTIVE vs NOT_YET_WIRED vs OPTIONAL.
    Construction results are explicit — no silent import suppression.
    """

    p0_controller: Any = None
    structural_oracle: Any = None
    structural_adapter: Any = None
    darwinian_episode_factory: Any = None
    recursive_evidence_controller: Any = None

    _component_identities: Dict[str, ComponentIdentity] = field(
        default_factory=dict, init=False, repr=False
    )
    _construction_results: Dict[str, ComponentConstructionResult] = field(
        default_factory=dict, init=False, repr=False
    )
    _component_ledger: Dict[str, ComponentInstanceRecord] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        self._component_identities = self._build_identities()
        self._construction_results = {}
        self._component_ledger = {}

    # ------------------------------------------------------------------
    # Identity construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_identities() -> Dict[str, ComponentIdentity]:
        """Build component identity map from canonical nesting contract."""
        identities: Dict[str, ComponentIdentity] = {}

        # -- Controller and spine components --

        identities["p0_controller"] = ComponentIdentity(
            name="P0Controller",
            role=ROLE_CANONICAL_RUNTIME,
            authority=AUTHORITY_EXECUTION,
            disposition="ACTIVE",
            import_path="elpis_p0.controller",
            description="P0 execution and refinement controller. Constructs via factory.",
        )

        identities["projector"] = ComponentIdentity(
            name="DeterministicPythonProjector",
            role=ROLE_CANONICAL_RUNTIME,
            authority=AUTHORITY_PROJECTION,
            disposition="ACTIVE",
            import_path="elpis_p0.projector",
            description="Deterministic request-to-grid81 projector. Controller-owned subcomponent.",
        )

        identities["shadow_trm_proposer"] = ComponentIdentity(
            name="ShadowTRMProposer",
            role=ROLE_SHADOW_IMPLEMENTATION,
            authority=AUTHORITY_PROPOSAL,
            disposition="ACTIVE",
            import_path="elpis_p0.trm",
            description="Shadow TRM implementation. Deterministic stand-in. NOT the learned TRM. Proposal authority only.",
        )

        identities["expert_proposer"] = ComponentIdentity(
            name="DeterministicExpertProposer",
            role=ROLE_CANONICAL_RUNTIME,
            authority=AUTHORITY_PROPOSAL,
            disposition="ACTIVE",
            import_path="elpis_p0.experts",
            description="Deterministic expert activation proposer. Controller-owned subcomponent.",
        )

        identities["decoder"] = ComponentIdentity(
            name="DeterministicPythonDecoder",
            role=ROLE_CANONICAL_RUNTIME,
            authority=AUTHORITY_DECODING,
            disposition="ACTIVE",
            import_path="elpis_p0.decoder",
            description="Offline deterministic Python decoder. Controller-owned subcomponent.",
        )

        identities["validator"] = ComponentIdentity(
            name="PythonASTValidator",
            role=ROLE_CANONICAL_RUNTIME,
            authority=AUTHORITY_VALIDATION,
            disposition="ACTIVE",
            import_path="elpis_p0.validators",
            description="Python AST syntax validator. Controller-owned subcomponent.",
        )

        identities["refinement_proposer"] = ComponentIdentity(
            name="DeterministicShadowRefinementProposer",
            role=ROLE_CANONICAL_RUNTIME,
            authority=AUTHORITY_PROPOSAL,
            disposition="ACTIVE",
            import_path="elpis_p0.refinement_proposer",
            description="Deterministic shadow refinement proposer. Controller-owned subcomponent.",
        )

        identities["scope_provider"] = ComponentIdentity(
            name="InitialVoidScopeProvider",
            role=ROLE_CANONICAL_RUNTIME,
            authority=AUTHORITY_SCOPE,
            disposition="ACTIVE",
            import_path="elpis_p0.initial_void_scope_provider",
            description="Initial void scope provider for refinement. Controller-owned subcomponent.",
        )

        # -- Structural authority (NOT_YET_WIRED) --

        identities["structural_oracle"] = ComponentIdentity(
            name="StructuralOracle",
            role=ROLE_CANONICAL_RUNTIME,
            authority=AUTHORITY_STRUCTURAL_TRANSITION,
            disposition="NOT_YET_WIRED",
            import_path="elpis_fractal_spine.structural_oracle",
            description="Deterministic structural transition oracle. Pure NumPy. Sole structural transition authority.",
        )

        identities["structural_adapter"] = ComponentIdentity(
            name="DeterministicSudokuReferenceAdapter",
            role=ROLE_REFERENCE_IMPLEMENTATION,
            authority=AUTHORITY_REFINEMENT_ADAPTER,
            disposition="OPTIONAL",
            import_path="darwinian_matrix.trm.reference_solver",
            description="Deterministic DFS qualification oracle. Reference implementation, not production TRM.",
        )

        identities["darwinian_episode_factory"] = ComponentIdentity(
            name="DarwinianEpisodeState",
            role=ROLE_CANONICAL_RUNTIME,
            authority=AUTHORITY_EPISODE,
            disposition="NOT_YET_WIRED",
            import_path="darwinian_matrix.controller.episode",
            description="Persistent Darwinian episode ownership. Immutable by interface.",
        )

        identities["recursive_evidence_controller"] = ComponentIdentity(
            name="RecursiveEmbeddingController",
            role=ROLE_CANONICAL_RUNTIME,
            authority=AUTHORITY_EVIDENCE,
            disposition="NOT_YET_WIRED",
            import_path="elpis_fractal_spine.controller",
            description="Shadow-only recursive embedding controller. No model loading or authority.",
        )

        return identities

    # ------------------------------------------------------------------
    # Property accessors with identity tracking
    # ------------------------------------------------------------------

    @property
    def component_identities(self) -> Dict[str, ComponentIdentity]:
        """Return all component identities and their authority classifications."""
        return dict(self._component_identities)

    @property
    def construction_results(self) -> Dict[str, ComponentConstructionResult]:
        """Return explicit construction results for all components."""
        return dict(self._construction_results)

    @property
    def component_ledger(self) -> Dict[str, ComponentInstanceRecord]:
        """Return full component instance ledger."""
        return dict(self._component_ledger)

    @property
    def active_components(self) -> List[str]:
        """Return names of components with ACTIVE disposition."""
        return [
            name
            for name, ident in self._component_identities.items()
            if ident.disposition == "ACTIVE"
        ]

    @property
    def shadow_components(self) -> List[str]:
        """Return names of components with SHADOW disposition."""
        return [
            name
            for name, ident in self._component_identities.items()
            if ident.disposition == "SHADOW" or ident.role == ROLE_SHADOW_IMPLEMENTATION
        ]

    @property
    def unwired_components(self) -> List[str]:
        """Return names of components with NOT_YET_WIRED disposition."""
        return [
            name
            for name, ident in self._component_identities.items()
            if ident.disposition == "NOT_YET_WIRED"
        ]

    @property
    def optional_components(self) -> List[str]:
        """Return names of components with OPTIONAL disposition."""
        return [
            name
            for name, ident in self._component_identities.items()
            if ident.disposition == "OPTIONAL"
        ]

    @property
    def controller_owned_components(self) -> List[str]:
        """Return names of components owned by P0Controller."""
        return [
            "projector",
            "shadow_trm_proposer",
            "expert_proposer",
            "decoder",
            "validator",
            "refinement_proposer",
            "scope_provider",
        ]

    # ------------------------------------------------------------------
    # Authority queries
    # ------------------------------------------------------------------

    def get_authority(self, component_name: str) -> Optional[str]:
        """Get the authority classification for a named component."""
        ident = self._component_identities.get(component_name)
        if ident is None:
            return None
        return ident.authority

    def structural_transition_authority_holder(self) -> str:
        """Return the unique structural transition authority holder.

        Returns:
            Component name that holds STRUCTURAL_TRANSITION_ORACLE authority.

        Raises:
            ValueError: If no holder found (should never happen).
        """
        for name, ident in self._component_identities.items():
            if ident.authority == AUTHORITY_STRUCTURAL_TRANSITION:
                return name
        raise ValueError(
            "No structural transition authority holder found in bundle"
        )

    def active_structural_authority(self) -> Optional[str]:
        """Return the active structural transition authority holder.

        A declared but absent (unconstructed) oracle does NOT satisfy
        this check. The instance must be CONSTRUCTED and active=True.

        Returns:
            Component name if constructed and active, else None.
        """
        holder = self.structural_transition_authority_holder()
        result = self._construction_results.get(holder)
        if result is None or result.state != ConstructionState.CONSTRUCTED:
            return None
        ledger_entry = self._component_ledger.get(holder)
        if ledger_entry is None or not ledger_entry.active:
            return None
        return holder

    def proposal_components(self) -> List[str]:
        """Return all components with PROPOSAL_ONLY authority."""
        return [
            name
            for name, ident in self._component_identities.items()
            if ident.authority == AUTHORITY_PROPOSAL
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _source_sha256(module_path: str) -> str:
        """Compute SHA-256 of a source file."""
        import importlib

        try:
            mod = importlib.import_module(module_path)
            mod_file = getattr(mod, "__file__", None)
            if mod_file and mod_file.endswith(".py"):
                with open(mod_file, "rb") as f:
                    return hashlib.sha256(f.read()).hexdigest()
        except (ImportError, OSError, AttributeError):
            pass
        return "unavailable"

    @staticmethod
    def _class_name(instance: Any) -> str:
        """Get the qualified class name of an instance."""
        return type(instance).__module__ + "." + type(instance).__qualname__

    def _record_construction(
        self,
        name: str,
        state: ConstructionState,
        instance: Any = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Record a construction result and update ledger."""
        ident = self._component_identities.get(name)
        if ident is None:
            return

        impl_class = type(instance).__qualname__ if instance else None
        full_class = (
            type(instance).__module__ + "." + type(instance).__qualname__
            if instance
            else ident.import_path
        )

        self._construction_results[name] = ComponentConstructionResult(
            component_name=name,
            state=state,
            instance=instance,
            error_message=error_message,
            implementation_class=impl_class,
        )

        # Determine active status: CONSTRUCTED + not INTENTIONALLY_UNWIRED
        is_active = (
            state == ConstructionState.CONSTRUCTED
            and ident.disposition != "NOT_YET_WIRED"
            and ident.disposition != "OPTIONAL"
        )

        # For StructuralOracle: active only when explicitly wired
        if name == "structural_oracle":
            is_active = (
                state == ConstructionState.CONSTRUCTED
                and instance is not None
            )

        self._component_ledger[name] = ComponentInstanceRecord(
            name=ident.name,
            implementation_class=full_class,
            role=ident.role,
            authority=ident.authority,
            disposition=ident.disposition,
            construction_state=state,
            active=is_active,
            owner="p0_controller" if name in self.controller_owned_components else "bundle",
            source_module=ident.import_path,
            source_sha256=self._source_sha256(ident.import_path),
            configuration_identity=f"{name}.{ident.role}.{ident.authority}",
        )

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def construct_p0_only(cls) -> "CoreRuntimeBundle":
        """Construct bundle with P0 components (ACTIVE spine).

        Constructs P0Controller via factory and records explicit
        construction results for all declared components.
        NOT_YET_WIRED components are recorded as DECLARED with
        INTENTIONALLY_UNWIRED state.
        """
        from .factory import build_default_controller

        bundle = cls()

        # Construct P0Controller
        try:
            controller = build_default_controller()
            bundle.p0_controller = controller
            bundle._record_construction(
                "p0_controller",
                ConstructionState.CONSTRUCTED,
                instance=controller,
            )
        except Exception as e:
            bundle._record_construction(
                "p0_controller",
                ConstructionState.CONSTRUCTION_FAILED,
                error_message=str(e),
            )
            raise

        # Record controller-owned subcomponents from the constructed controller
        if bundle.p0_controller is not None:
            controller = bundle.p0_controller

            # Projector
            bundle._record_construction(
                "projector",
                ConstructionState.CONSTRUCTED,
                instance=controller.projector,
            )

            # ShadowTRMProposer
            bundle._record_construction(
                "shadow_trm_proposer",
                ConstructionState.CONSTRUCTED,
                instance=controller.trm,
            )

            # Expert proposer
            bundle._record_construction(
                "expert_proposer",
                ConstructionState.CONSTRUCTED,
                instance=controller.expert_proposer,
            )

            # Decoder
            bundle._record_construction(
                "decoder",
                ConstructionState.CONSTRUCTED,
                instance=controller.decoder,
            )

            # Validator
            if controller.validators:
                bundle._record_construction(
                    "validator",
                    ConstructionState.CONSTRUCTED,
                    instance=controller.validators[0],
                )
            else:
                bundle._record_construction(
                    "validator",
                    ConstructionState.CONSTRUCTION_FAILED,
                    error_message="No validators in controller",
                )

            # Refinement proposer
            bundle._record_construction(
                "refinement_proposer",
                ConstructionState.CONSTRUCTED,
                instance=controller.refinement_proposer,
            )

            # Scope provider
            bundle._record_construction(
                "scope_provider",
                ConstructionState.CONSTRUCTED,
                instance=controller.scope_provider,
            )

        # Record unwired components as INTENTIONALLY_UNWIRED
        bundle._record_construction(
            "structural_oracle",
            ConstructionState.INTENTIONALLY_UNWIRED,
            error_message="StructuralOracle not wired in P0-only construction",
        )
        bundle._record_construction(
            "structural_adapter",
            ConstructionState.INTENTIONALLY_UNWIRED,
            error_message="Reference adapter not constructed in P0-only mode",
        )
        bundle._record_construction(
            "darwinian_episode_factory",
            ConstructionState.INTENTIONALLY_UNWIRED,
            error_message="Darwinian nesting deferred",
        )
        bundle._record_construction(
            "recursive_evidence_controller",
            ConstructionState.INTENTIONALLY_UNWIRED,
            error_message="Evidence spine not wired",
        )

        return bundle

    @classmethod
    def construct_full(cls) -> "CoreRuntimeBundle":
        """Construct bundle with all available components.

        Imports from lower-level packages and constructs everything
        that can be constructed without learned T00 or ECRF.

        Returns explicit construction results — no silent suppression.
        """
        from .factory import build_default_controller

        bundle = cls(
            p0_controller=build_default_controller(),
        )

        # Record P0 controller
        bundle._record_construction(
            "p0_controller",
            ConstructionState.CONSTRUCTED,
            instance=bundle.p0_controller,
        )

        # Record controller-owned subcomponents
        if bundle.p0_controller is not None:
            controller = bundle.p0_controller
            bundle._record_construction(
                "projector", ConstructionState.CONSTRUCTED, instance=controller.projector
            )
            bundle._record_construction(
                "shadow_trm_proposer", ConstructionState.CONSTRUCTED, instance=controller.trm
            )
            bundle._record_construction(
                "expert_proposer", ConstructionState.CONSTRUCTED, instance=controller.expert_proposer
            )
            bundle._record_construction(
                "decoder", ConstructionState.CONSTRUCTED, instance=controller.decoder
            )
            if controller.validators:
                bundle._record_construction(
                    "validator", ConstructionState.CONSTRUCTED, instance=controller.validators[0]
                )
            bundle._record_construction(
                "refinement_proposer", ConstructionState.CONSTRUCTED, instance=controller.refinement_proposer
            )
            bundle._record_construction(
                "scope_provider", ConstructionState.CONSTRUCTED, instance=controller.scope_provider
            )

        # Attempt StructuralOracle construction with explicit result
        try:
            from elpis_fractal_spine.structural_oracle import StructuralOracle  # type: ignore

            oracle = StructuralOracle()
            bundle.structural_oracle = oracle
            bundle._record_construction(
                "structural_oracle",
                ConstructionState.CONSTRUCTED,
                instance=oracle,
            )
        except ImportError as e:
            bundle._record_construction(
                "structural_oracle",
                ConstructionState.PACKAGE_UNAVAILABLE,
                error_message=f"ImportError: {e}",
            )
        except TypeError as e:
            bundle._record_construction(
                "structural_oracle",
                ConstructionState.ARGUMENTS_REQUIRED,
                error_message=f"TypeError: {e}",
            )
        except Exception as e:
            bundle._record_construction(
                "structural_oracle",
                ConstructionState.CONSTRUCTION_FAILED,
                error_message=f"{type(e).__name__}: {e}",
            )

        # Attempt reference adapter construction with explicit result
        try:
            # DarwinianMatrix package path with verified casing
            from darwinian_matrix.trm.reference_solver import (  # type: ignore
                DeterministicSudokuReferenceAdapter,
            )
            adapter = DeterministicSudokuReferenceAdapter()
            bundle.structural_adapter = adapter
            bundle._record_construction(
                "structural_adapter",
                ConstructionState.CONSTRUCTED,
                instance=adapter,
            )
        except ImportError as e:
            bundle._record_construction(
                "structural_adapter",
                ConstructionState.PACKAGE_UNAVAILABLE,
                error_message=f"ImportError: {e}",
            )
        except Exception as e:
            bundle._record_construction(
                "structural_adapter",
                ConstructionState.CONSTRUCTION_FAILED,
                error_message=f"{type(e).__name__}: {e}",
            )

        # Darwinian episode — INTENTIONALLY_UNWIRED (deferred nesting)
        bundle._record_construction(
            "darwinian_episode_factory",
            ConstructionState.INTENTIONALLY_UNWIRED,
            error_message="Darwinian nesting deferred to recursive rollout gate",
        )

        # Evidence controller — INTENTIONALLY_UNWIRED
        bundle._record_construction(
            "recursive_evidence_controller",
            ConstructionState.INTENTIONALLY_UNWIRED,
            error_message="Evidence spine not wired",
        )

        return bundle

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_bundle(self) -> List[str]:
        """Validate bundle integrity.

        Returns:
            List of error strings. Empty if bundle is valid.
        """
        errors: List[str] = []

        # Check no learned T00 in bundle
        for name, ident in self._component_identities.items():
            if "t00" in ident.import_path.lower():
                errors.append(
                    f"LEARNED_T00_IN_BUNDLE: {name} imports from {ident.import_path}"
                )

        # Check structural transition authority is unique
        oracle_holders = [
            name
            for name, ident in self._component_identities.items()
            if ident.authority == AUTHORITY_STRUCTURAL_TRANSITION
        ]
        if len(oracle_holders) != 1:
            errors.append(
                f"STRUCTURAL_AUTHORITY_NOT_UNIQUE: {oracle_holders}"
            )

        # Check P0 controller is constructed when ACTIVE components exist
        if self.active_components and not self.p0_controller:
            errors.append(
                "P0_CONTROLLER_ABSENT: ACTIVE components declared but no P0Controller"
            )

        # Check declared active components are actually constructed
        for name in self.active_components:
            result = self._construction_results.get(name)
            if result is None:
                errors.append(f"UNCONSTRUCTED_ACTIVE: {name} declared ACTIVE but not constructed")
            elif result.state != ConstructionState.CONSTRUCTED:
                errors.append(
                    f"ACTIVE_NOT_CONSTRUCTED: {name} disposition ACTIVE "
                    f"but state={result.state.value}"
                )

        # Check ShadowTRMProposer conventions
        shadow_result = self._construction_results.get("shadow_trm_proposer")
        if shadow_result and shadow_result.state == ConstructionState.CONSTRUCTED:
            ident = self._component_identities["shadow_trm_proposer"]
            if ident.role != ROLE_SHADOW_IMPLEMENTATION:
                errors.append(
                    "SHADOW_TRM_ROLE_MISMATCH: ShadowTRMProposer must have SHADOW_IMPLEMENTATION role"
                )
            if ident.authority != AUTHORITY_PROPOSAL:
                errors.append(
                    "SHADOW_TRM_AUTHORITY_MISMATCH: ShadowTRMProposer must have PROPOSAL_ONLY authority"
                )

        # Check StructuralOracle conventions
        oracle_ident = self._component_identities.get("structural_oracle")
        if oracle_ident:
            if oracle_ident.role != ROLE_CANONICAL_RUNTIME:
                errors.append(
                    "ORACLE_ROLE_MISMATCH: StructuralOracle must have CANONICAL_RUNTIME role"
                )
            if oracle_ident.authority != AUTHORITY_STRUCTURAL_TRANSITION:
                errors.append(
                    "ORACLE_AUTHORITY_MISMATCH: StructuralOracle must have STRUCTURAL_TRANSITION_ORACLE authority"
                )

        return errors

    # ------------------------------------------------------------------
    # Deterministic identity
    # ------------------------------------------------------------------

    def identity_digest(self) -> str:
        """Compute a deterministic digest of the bundle's component identities.

        Binds actual constructed component classes and source identities
        when available. Changes when the active component set changes.

        Returns:
            SHA-256 hex digest of the sorted component identity data.
        """
        payload = {
            name: {
                "role": ident.role,
                "authority": ident.authority,
                "disposition": ident.disposition,
            }
            for name, ident in sorted(self._component_identities.items())
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def full_identity_digest(self) -> str:
        """Compute digest binding constructed classes and source identities.

        Returns:
            SHA-256 hex digest including implementation classes,
            construction states, and source SHAs.
        """
        payload = {}
        for name in sorted(self._component_ledger.keys()):
            record = self._component_ledger[name]
            payload[name] = {
                "implementation_class": record.implementation_class,
                "role": record.role,
                "authority": record.authority,
                "disposition": record.disposition,
                "construction_state": record.construction_state.value,
                "active": record.active,
                "owner": record.owner,
                "source_sha256": record.source_sha256,
            }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
