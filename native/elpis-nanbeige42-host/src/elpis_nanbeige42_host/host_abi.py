"""Abstract host ABI. No model implementation is supplied by P14.0b."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .errors import RuntimeQualificationRequired, UnsupportedControlMode
from .manifest import HostAbiManifest
from .packet_derivation import (
    CodingTickSeed,
    PacketDerivation,
    PacketDerivationRequest,
    PacketDerivationResult,
)
from .schemas import CodingAction, ControlMode, ElpisCodingTick, TickEvidence


@dataclass(frozen=True, slots=True)
class RuntimeQualification:
    qualified: bool
    qualification_digest: str | None
    failures: tuple[str, ...]


class ElpisNanbeige42HostABI(ABC):
    """Public API boundary; implementations must not import phase scripts."""

    manifest: HostAbiManifest
    packet_derivation: PacketDerivation

    def assert_mode_enabled(self, mode: ControlMode) -> None:
        if mode not in self.manifest.enabled_control_modes:
            if mode in (ControlMode.DOCK, ControlMode.POST_LOGIT, ControlMode.HYBRID):
                raise RuntimeQualificationRequired(
                    "packet construction is defined, but actuating modes remain disabled "
                    "until P14.1 runtime qualification"
                )
            raise UnsupportedControlMode(mode.value)

    def derive_packet(
        self,
        seed: CodingTickSeed,
        request: PacketDerivationRequest,
    ) -> PacketDerivationResult:
        return self.packet_derivation.derive(seed, request)

    @abstractmethod
    def load(self) -> None: ...

    @abstractmethod
    def validate_runtime(self) -> RuntimeQualification: ...

    @abstractmethod
    def prepare_tick(self, tick: ElpisCodingTick) -> Any: ...

    @abstractmethod
    def run_tick(self, prepared_tick: Any) -> Any: ...

    @abstractmethod
    def parse_action(self, generated_output: Any) -> CodingAction: ...

    @abstractmethod
    def emit_evidence(self, execution: Any) -> TickEvidence: ...

    @abstractmethod
    def close(self) -> None: ...
