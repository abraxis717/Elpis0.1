from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

import numpy as np

from .contracts import (
    EntropyState,
    ForecastResult,
    GridPacket,
)


class GridPacketSink:
    """Atomic ABI boundary for TRMFractalSpine.

    The NPZ contains:

    tokens81:
        uint8 shape [81], values 0..9.

    digits:
        uint8 shape [9, 9].

    bits:
        uint8 shape [4, 9, 9].

    valid_mask:
        uint8 shape [9, 9].

    recursive_signature:
        deterministic multi-scale float features.

    A Grid81 TinyRecursiveModel should consume tokens81 reshaped
    to [1, 81], with num_tokens=10.
    """

    def __init__(
        self,
        npz_path: str,
        json_path: str,
    ):
        self.npz_path = Path(npz_path)
        self.json_path = Path(json_path)

        self.npz_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.json_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def write(
        self,
        packet: GridPacket,
        entropy: EntropyState,
        forecast: ForecastResult | None,
    ) -> None:
        packet.validate()

        self._write_npz(packet)

        self._write_json(
            packet,
            entropy,
            forecast,
        )

    def _write_npz(
        self,
        packet: GridPacket,
    ) -> None:
        file_descriptor, temporary_name = (
            tempfile.mkstemp(
                prefix="grid81_",
                suffix=".npz",
                dir=self.npz_path.parent,
            )
        )

        os.close(file_descriptor)

        try:
            np.savez_compressed(
                temporary_name,
                wall_time_ns=np.asarray(
                    [packet.wall_time_ns],
                    dtype=np.int64,
                ),
                tokens81=packet.tokens81,
                digits=packet.digits,
                bits=packet.bits,
                valid_mask=packet.valid_mask,
                channel_names=np.asarray(
                    packet.channel_names,
                    dtype="U128",
                ),
                recursive_signature=(
                    packet.recursive_signature
                ),
            )

            os.replace(
                temporary_name,
                self.npz_path,
            )

        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def _write_json(
        self,
        packet: GridPacket,
        entropy: EntropyState,
        forecast: ForecastResult | None,
    ) -> None:
        payload = {
            "abi_version": (
                "cnumpycortex.grid81.v1"
            ),
            "wall_time_ns": packet.wall_time_ns,
            "semantic_space": (
                "thermal_grid81"
            ),
            "shape": [1, 81],
            "dtype": "uint8",
            "vocabulary": {
                "0": "missing",
                "1-9": (
                    "robust telemetry bins"
                ),
            },
            "channel_names": list(
                packet.channel_names
            ),
            "entropy": {
                "bit_entropy": (
                    entropy.bit_entropy
                ),
                "digit_entropy": (
                    entropy.digit_entropy
                ),
                "transition_rate": (
                    entropy.transition_rate
                ),
                "temporal_gradient": (
                    entropy.temporal_gradient
                ),
                "event_score": (
                    entropy.event_score
                ),
            },
            "forecast": (
                None
                if forecast is None
                else {
                    "generated_at_ns": (
                        forecast.generated_at_ns
                    ),
                    "prediction_length": (
                        forecast.prediction_length
                    ),
                    "anomaly_score": (
                        forecast.anomaly_score
                    ),
                    "summary": forecast.summary,
                    "error": forecast.error,
                }
            ),
        }

        temporary = self.json_path.with_suffix(
            self.json_path.suffix + ".tmp"
        )

        temporary.write_text(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
        )

        os.replace(
            temporary,
            self.json_path,
        )


def tokens_to_torch(
    packet: GridPacket,
    device: str = "cpu",
):
    """Convert a packet into TinyRecursiveModel input form."""
    import torch

    return (
        torch
        .from_numpy(
            packet.tokens81.copy()
        )
        .long()
        .reshape(1, 81)
        .to(device)
    )
