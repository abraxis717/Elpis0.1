"""Frozen PacketDerivation contract for P14.0b.

P14.0b does not claim a semantic map from arbitrary coding tasks to the 22-D
collapse coordinates. It freezes four derivation methods with strict scope:

- NONE: no packet; valid only for NONE/OBSERVE.
- NEUTRAL_STUB: deterministic all-zero packet with gain 0; plumbing only.
- EXPLICIT_SEALED_VECTOR: externally produced, digest-bound diagnostic vector.
- REGISTRY_LOOKUP: reserved for a future task registry sealed before P14.2.
- GRID81: explicitly forbidden in host v0.1 unless separately qualified.

Only a future registry-bound method may become coding-utility eligible. The two
implemented packet-producing methods in P14.0b are diagnostic only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from .digest import canonical_digest, validate_digest
from .errors import (
    ExplicitControlVectorInvalid,
    Grid81DerivationForbidden,
    PacketDerivationInputMismatch,
    PacketDerivationMethodUnsupported,
    RegistryDerivationUnavailable,
)
from .schemas import (
    CollapseControlPacket,
    ControlMode,
    ElpisCodingTick,
    GenerationShape,
    CodingTask,
    ToolEvidence,
    WorkspaceState,
)


class PacketDerivationMethod(str, Enum):
    NONE = "none"
    NEUTRAL_STUB = "neutral_stub"
    EXPLICIT_SEALED_VECTOR = "explicit_sealed_vector"
    REGISTRY_LOOKUP = "registry_lookup"
    GRID81 = "grid81"


@dataclass(frozen=True, slots=True)
class CodingTickSeed:
    """All coding-tick fields that exist before a control packet is derived."""

    schema: Literal["elpis.nanbeige42.coding-tick-seed.v1"]
    tick_id: str
    parent_tick_id: str | None
    logical_time: int
    task: CodingTask
    workspace: WorkspaceState
    evidence: tuple[ToolEvidence, ...]
    control_mode: ControlMode
    generation_shape: GenerationShape
    seed_digest: str = ""

    def with_digest(self) -> "CodingTickSeed":
        digest = canonical_digest(self, digest_field="seed_digest")
        return CodingTickSeed(
            schema=self.schema,
            tick_id=self.tick_id,
            parent_tick_id=self.parent_tick_id,
            logical_time=self.logical_time,
            task=self.task,
            workspace=self.workspace,
            evidence=self.evidence,
            control_mode=self.control_mode,
            generation_shape=self.generation_shape,
            seed_digest=digest,
        )


@dataclass(frozen=True, slots=True)
class ExplicitControlVector:
    """Externally supplied diagnostic vector.

    This is not a semantic task-to-packet mapper. `purpose` is frozen to runtime
    qualification diagnostics so the vector cannot silently become P14.2 coding
    utility evidence.
    """

    schema: Literal["elpis.explicit-control-vector.v1"]
    common: float
    structural: tuple[float, ...]
    gain: float
    producer_id: str
    producer_state_digest: str
    purpose: Literal["runtime_qualification_diagnostic"]
    vector_digest: str = ""

    def __post_init__(self) -> None:
        if len(self.structural) != 21:
            raise ExplicitControlVectorInvalid(
                "explicit structural vector must contain exactly 21 coordinates"
            )
        if not (0.0 <= self.gain <= 8.0):
            raise ExplicitControlVectorInvalid("explicit gain must be within [0, 8]")
        if not self.producer_id:
            raise ExplicitControlVectorInvalid("producer_id must be non-empty")
        if not self.producer_state_digest.startswith("sha256:"):
            raise ExplicitControlVectorInvalid(
                "producer_state_digest must be a bound sha256 digest"
            )

    def with_digest(self) -> "ExplicitControlVector":
        digest = canonical_digest(self, digest_field="vector_digest")
        return ExplicitControlVector(
            schema=self.schema,
            common=self.common,
            structural=self.structural,
            gain=self.gain,
            producer_id=self.producer_id,
            producer_state_digest=self.producer_state_digest,
            purpose=self.purpose,
            vector_digest=digest,
        )


@dataclass(frozen=True, slots=True)
class PacketDerivationRequest:
    schema: Literal["elpis.packet-derivation-request.v1"]
    method: PacketDerivationMethod
    explicit_vector: ExplicitControlVector | None = None
    registry_key: str | None = None
    request_digest: str = ""

    def __post_init__(self) -> None:
        if self.method is PacketDerivationMethod.EXPLICIT_SEALED_VECTOR:
            if self.explicit_vector is None or self.registry_key is not None:
                raise PacketDerivationInputMismatch(
                    "explicit method requires explicit_vector and forbids registry_key"
                )
        elif self.method is PacketDerivationMethod.REGISTRY_LOOKUP:
            if not self.registry_key or self.explicit_vector is not None:
                raise PacketDerivationInputMismatch(
                    "registry method requires registry_key and forbids explicit_vector"
                )
        elif self.explicit_vector is not None or self.registry_key is not None:
            raise PacketDerivationInputMismatch(
                f"{self.method.value} method accepts no vector or registry key"
            )

    def with_digest(self) -> "PacketDerivationRequest":
        digest = canonical_digest(self, digest_field="request_digest")
        return PacketDerivationRequest(
            schema=self.schema,
            method=self.method,
            explicit_vector=self.explicit_vector,
            registry_key=self.registry_key,
            request_digest=digest,
        )


@dataclass(frozen=True, slots=True)
class PacketDerivationReceipt:
    schema: Literal["elpis.packet-derivation-receipt.v1"]
    method: PacketDerivationMethod
    seed_digest: str
    request_digest: str
    packet_digest: str | None
    producer_id: str | None
    producer_state_digest: str | None
    registry_digest: str | None
    grid81_used: bool
    semantic_mapper_qualified: bool
    coding_utility_eligible: bool
    receipt_digest: str = ""

    def with_digest(self) -> "PacketDerivationReceipt":
        digest = canonical_digest(self, digest_field="receipt_digest")
        return PacketDerivationReceipt(
            schema=self.schema,
            method=self.method,
            seed_digest=self.seed_digest,
            request_digest=self.request_digest,
            packet_digest=self.packet_digest,
            producer_id=self.producer_id,
            producer_state_digest=self.producer_state_digest,
            registry_digest=self.registry_digest,
            grid81_used=self.grid81_used,
            semantic_mapper_qualified=self.semantic_mapper_qualified,
            coding_utility_eligible=self.coding_utility_eligible,
            receipt_digest=digest,
        )


@dataclass(frozen=True, slots=True)
class PacketDerivationResult:
    packet: CollapseControlPacket | None
    receipt: PacketDerivationReceipt


@dataclass(frozen=True, slots=True)
class PacketDerivationPolicy:
    schema: Literal["elpis.packet-derivation-policy.v1"]
    implemented_methods: tuple[PacketDerivationMethod, ...]
    coding_utility_eligible_methods: tuple[PacketDerivationMethod, ...]
    grid81_allowed: bool
    registry_lookup_available: bool
    explicit_vector_purpose: Literal["runtime_qualification_diagnostic"]
    policy_digest: str = ""

    def with_digest(self) -> "PacketDerivationPolicy":
        digest = canonical_digest(self, digest_field="policy_digest")
        return PacketDerivationPolicy(
            schema=self.schema,
            implemented_methods=self.implemented_methods,
            coding_utility_eligible_methods=self.coding_utility_eligible_methods,
            grid81_allowed=self.grid81_allowed,
            registry_lookup_available=self.registry_lookup_available,
            explicit_vector_purpose=self.explicit_vector_purpose,
            policy_digest=digest,
        )


def default_packet_derivation_policy() -> PacketDerivationPolicy:
    return PacketDerivationPolicy(
        schema="elpis.packet-derivation-policy.v1",
        implemented_methods=(
            PacketDerivationMethod.NONE,
            PacketDerivationMethod.NEUTRAL_STUB,
            PacketDerivationMethod.EXPLICIT_SEALED_VECTOR,
        ),
        coding_utility_eligible_methods=(),
        grid81_allowed=False,
        registry_lookup_available=False,
        explicit_vector_purpose="runtime_qualification_diagnostic",
    ).with_digest()


class PacketDerivation(ABC):
    policy: PacketDerivationPolicy

    @abstractmethod
    def derive(
        self,
        seed: CodingTickSeed,
        request: PacketDerivationRequest,
    ) -> PacketDerivationResult:
        raise NotImplementedError


class FrozenV01PacketDerivation(PacketDerivation):
    """P14.0b implementation: no semantic task mapper is claimed."""

    def __init__(self, policy: PacketDerivationPolicy | None = None) -> None:
        self.policy = policy or default_packet_derivation_policy()

    @staticmethod
    def _validate_inputs(
        seed: CodingTickSeed,
        request: PacketDerivationRequest,
    ) -> None:
        if not validate_digest(seed, digest_field="seed_digest"):
            raise PacketDerivationInputMismatch("coding tick seed digest invalid")
        if not validate_digest(request, digest_field="request_digest"):
            raise PacketDerivationInputMismatch("derivation request digest invalid")
        if request.explicit_vector is not None and not validate_digest(
            request.explicit_vector, digest_field="vector_digest"
        ):
            raise PacketDerivationInputMismatch("explicit vector digest invalid")

    def derive(
        self,
        seed: CodingTickSeed,
        request: PacketDerivationRequest,
    ) -> PacketDerivationResult:
        self._validate_inputs(seed, request)

        if request.method is PacketDerivationMethod.GRID81:
            raise Grid81DerivationForbidden(
                "Grid81 is not part of Nanbeige host v0.1 packet derivation; "
                "any coding-task-to-Grid81 projector requires a separate qualification"
            )
        if request.method is PacketDerivationMethod.REGISTRY_LOOKUP:
            raise RegistryDerivationUnavailable(
                "registry derivation is reserved for a task registry sealed before P14.2"
            )
        if request.method not in self.policy.implemented_methods:
            raise PacketDerivationMethodUnsupported(request.method.value)

        if request.method is PacketDerivationMethod.NONE:
            if seed.control_mode not in (ControlMode.NONE, ControlMode.OBSERVE):
                raise PacketDerivationInputMismatch(
                    "actuating mode requires a packet-producing derivation method"
                )
            receipt = PacketDerivationReceipt(
                schema="elpis.packet-derivation-receipt.v1",
                method=request.method,
                seed_digest=seed.seed_digest,
                request_digest=request.request_digest,
                packet_digest=None,
                producer_id=None,
                producer_state_digest=None,
                registry_digest=None,
                grid81_used=False,
                semantic_mapper_qualified=False,
                coding_utility_eligible=False,
            ).with_digest()
            return PacketDerivationResult(packet=None, receipt=receipt)

        if seed.control_mode not in (
            ControlMode.DOCK,
            ControlMode.POST_LOGIT,
            ControlMode.HYBRID,
        ):
            raise PacketDerivationInputMismatch(
                "packet-producing method requires an actuating control mode"
            )

        if request.method is PacketDerivationMethod.NEUTRAL_STUB:
            packet = CollapseControlPacket(
                schema="elpis.collapse-control.v1",
                common=0.0,
                structural=(0.0,) * 21,
                source_state_digest=seed.seed_digest,
                gain=0.0,
            ).with_digest()
            producer_id = "elpis.nanbeige42.neutral-stub.v1"
            producer_state_digest = seed.seed_digest
        elif request.method is PacketDerivationMethod.EXPLICIT_SEALED_VECTOR:
            vector = request.explicit_vector
            if vector is None:  # protected by request validation; explicit for type checkers
                raise PacketDerivationInputMismatch("explicit vector absent")
            if vector.purpose != self.policy.explicit_vector_purpose:
                raise ExplicitControlVectorInvalid("explicit vector purpose drift")
            packet = CollapseControlPacket(
                schema="elpis.collapse-control.v1",
                common=vector.common,
                structural=vector.structural,
                source_state_digest=vector.producer_state_digest,
                gain=vector.gain,
            ).with_digest()
            producer_id = vector.producer_id
            producer_state_digest = vector.producer_state_digest
        else:  # pragma: no cover - guarded above
            raise PacketDerivationMethodUnsupported(request.method.value)

        receipt = PacketDerivationReceipt(
            schema="elpis.packet-derivation-receipt.v1",
            method=request.method,
            seed_digest=seed.seed_digest,
            request_digest=request.request_digest,
            packet_digest=packet.packet_digest,
            producer_id=producer_id,
            producer_state_digest=producer_state_digest,
            registry_digest=None,
            grid81_used=False,
            semantic_mapper_qualified=False,
            coding_utility_eligible=False,
        ).with_digest()
        return PacketDerivationResult(packet=packet, receipt=receipt)


def finalize_tick(
    seed: CodingTickSeed,
    result: PacketDerivationResult,
) -> ElpisCodingTick:
    """Construct a coding tick only after derivation has produced a receipt."""

    if not validate_digest(seed, digest_field="seed_digest"):
        raise PacketDerivationInputMismatch("coding tick seed digest invalid")
    if not validate_digest(result.receipt, digest_field="receipt_digest"):
        raise PacketDerivationInputMismatch("packet derivation receipt digest invalid")
    if result.receipt.seed_digest != seed.seed_digest:
        raise PacketDerivationInputMismatch("receipt is bound to another coding tick seed")
    packet_digest = result.packet.packet_digest if result.packet is not None else None
    if result.receipt.packet_digest != packet_digest:
        raise PacketDerivationInputMismatch("receipt packet digest mismatch")

    if seed.control_mode in (ControlMode.NONE, ControlMode.OBSERVE):
        if result.packet is not None:
            raise PacketDerivationInputMismatch("non-actuating mode must not carry a packet")
    elif result.packet is None:
        raise PacketDerivationInputMismatch("actuating mode requires a derived packet")

    return ElpisCodingTick(
        schema="elpis.nanbeige42.coding-tick.v2",
        tick_id=seed.tick_id,
        parent_tick_id=seed.parent_tick_id,
        logical_time=seed.logical_time,
        task=seed.task,
        workspace=seed.workspace,
        evidence=seed.evidence,
        control_mode=seed.control_mode,
        control=result.packet,
        generation_shape=seed.generation_shape,
        packet_derivation_receipt_digest=result.receipt.receipt_digest,
    ).with_digest()
