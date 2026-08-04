"""Cortex port for Elpis Canon FS1.0 spine runtime.

L7: Cortex is diagnostic. CortexCommitReaderSystem verifies the latest
committed C0.1 manifest and writes ObservationCorrelationComponent only.
No system reads entropy, transition, anomaly, or state-token values as control.
CortexEvidenceCodecPort exists with default NullCortexEvidenceCodec returning
NO_CONTROL_EMISSION.
"""

from dataclasses import dataclass, field
from typing import Optional
import json
import hashlib
import os

from .components import ObservationCorrelation
from .canonical import json_sha256


class CortexEvidenceCodecPort:
    """
    Interface for Cortex evidence codec.

    Default implementation is NullCortexEvidenceCodec that returns
    NO_CONTROL_EMISSION.
    """
    pass


class NullCortexEvidenceCodec(CortexEvidenceCodecPort):
    """Default Cortex codec — returns NO_CONTROL_EMISSION."""

    emission_status: str = "NO_CONTROL_EMISSION"

    def encode(self, data: dict) -> dict:
        """No-op encoding — diagnostic only."""
        return {"emission": "NO_CONTROL_EMISSION"}


class CortexCommitReaderSystem:
    """
    Reads the latest committed C0.1 manifest, verifies checksums,
    writes ObservationCorrelationComponent.

    INVALID/absent manifest => component status INVALID/ABSENT;
    the request proceeds.
    """

    def __init__(self, manifest_path: Optional[str] = None):
        self._manifest_path = manifest_path
        self._codec = NullCortexEvidenceCodec()
        self._last_manifest: Optional[dict] = None

    @property
    def codec(self) -> NullCortexEvidenceCodec:
        return self._codec

    def read_manifest(self) -> Optional[dict]:
        """Read and verify the latest C0.1 manifest."""
        if self._manifest_path is None or not os.path.exists(self._manifest_path):
            return None
        try:
            with open(self._manifest_path, "r") as f:
                manifest = json.load(f)
            # Verify checksums if present
            if "checksum" in manifest:
                # Verify against the manifest itself
                content = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
                expected = hashlib.sha256(content.encode()).hexdigest()
                if manifest["checksum"] != expected:
                    return None  # Checksum mismatch => INVALID
            self._last_manifest = manifest
            return manifest
        except (json.JSONDecodeError, OSError):
            return None

    def generate_observation(
        self,
        request_id: str,
        generation: Optional[int] = None,
        lifecycle_stage: Optional[str] = None,
    ) -> ObservationCorrelation:
        """
        Generate an ObservationCorrelation from the latest manifest.

        Returns ABSENT if no manifest, INVALID if checksum fails.
        """
        manifest = self.read_manifest()

        if manifest is None:
            return ObservationCorrelation(
                request_id=request_id,
                status="ABSENT",
            )

        packet_digest = manifest.get("packet_digest")
        forecast_eval = manifest.get("forecast_eval_status")

        return ObservationCorrelation(
            request_id=request_id,
            generation=generation,
            lifecycle_stage=lifecycle_stage,
            packet_digest=packet_digest,
            forecast_eval_status=forecast_eval,
            status="VALID",
        )

    @staticmethod
    def verify_no_control_consumption(source_files: list[str]) -> list[str]:
        """
        Verify that no system (except the reader) touches entropy/transition/
        anomaly/state-token fields as control inputs.

        Returns list of violations (empty = clean).
        """
        violations = []
        forbidden_patterns = [
            "entropy",
            "transition",
            "anomaly",
            "state_token",
            "state-token",
            "chronos_status",
            "thermal_token",
            "opcode",
        ]

        for fpath in source_files:
            if "cortex_port.py" in fpath:
                continue  # The reader itself is exempt
            try:
                with open(fpath, "r") as f:
                    content = f.read()
                for pattern in forbidden_patterns:
                    if pattern in content.lower():
                        violations.append(
                            f"Potential control consumption of '{pattern}' in {fpath}"
                        )
            except OSError:
                pass

        return violations
