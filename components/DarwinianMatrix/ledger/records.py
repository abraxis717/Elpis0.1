"""Deterministic ledger records for ecological transaction frames."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

import torch
from torch import Tensor

from ..ecology.engine import EcologyState
from ..ecology.transaction import (
    EcologyStepTelemetry,
    EcologyTransactionConfig,
)
from ..geometry import LatticeClimateView
from ..runtime import RUNTIME_POLICY


GENESIS_RECORD_DIGEST = "0" * 64


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def domain_digest(
    domain: str,
    payload: Any,
) -> str:
    return hashlib.sha256(
        domain.encode("utf-8")
        + b"\x00"
        + canonical_json_bytes(payload)
    ).hexdigest()


def tensor_digest(
    domain: str,
    tensor: Tensor,
) -> str:
    value = tensor.detach().cpu().contiguous()

    digest = hashlib.sha256()
    digest.update(domain.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(str(value.dtype).encode("ascii"))
    digest.update(b"\x00")
    digest.update(
        canonical_json_bytes(
            list(value.shape)
        )
    )
    digest.update(b"\x00")
    digest.update(value.numpy().tobytes())

    return digest.hexdigest()


def climate_digest(
    climate: LatticeClimateView,
) -> str:
    payload = {
        "changed": tensor_digest(
            "darwinian.climate.changed.v1",
            climate.changed,
        ),
        "current": tensor_digest(
            "darwinian.climate.current.v1",
            climate.current,
        ),
        "previous": tensor_digest(
            "darwinian.climate.previous.v1",
            climate.previous,
        ),
        "transition_ids": tensor_digest(
            "darwinian.climate.transitions.v1",
            climate.transition_ids,
        ),
    }

    return domain_digest(
        "darwinian.lattice-climate-view.v1",
        payload,
    )


def config_payload(
    config: EcologyTransactionConfig,
) -> dict[str, object]:
    return {
        "adaptation_rate": config.adaptation_rate,
        "bounds": {
            "max_abs_energy": (
                config.bounds.max_abs_energy
            ),
            "max_population": (
                config.bounds.max_population
            ),
            "max_resource": (
                config.bounds.max_resource
            ),
        },
        "consumer_cost": config.consumer_cost,
        "consumer_demand": config.consumer_demand,
        "consumer_energy_efficiency": (
            config.consumer_energy_efficiency
        ),
        "death_threshold": config.death_threshold,
        "diffusion_rate": config.diffusion_rate,
        "gradient_alpha": config.gradient_alpha,
        "max_effective_capacity": (
            config.max_effective_capacity
        ),
        "producer_cost": config.producer_cost,
        "producer_energy_efficiency": (
            config.producer_energy_efficiency
        ),
        "producer_rate": config.producer_rate,
        "shock_energy_scale": (
            config.shock_energy_scale
        ),
        "shock_resource_scale": (
            config.shock_resource_scale
        ),
        "shock_tau": config.shock_tau,
        "structure_capacity_bonus": (
            config.structure_capacity_bonus
        ),
        "structure_cost": config.structure_cost,
        "structure_shock_scale": (
            config.structure_shock_scale
        ),
    }


def config_digest(
    config: EcologyTransactionConfig,
) -> str:
    return domain_digest(
        "darwinian.ecology-transaction-config.v1",
        config_payload(config),
    )


@dataclass(frozen=True)
class EcologyFrameRecord:
    schema_version: str

    episode_id: str
    frame_index: int
    random_seed: int

    state_before_digest: str
    state_after_digest: str

    climate_digest: str
    transition_age_digest: str
    neighbor_table_digest: str
    config_digest: str
    runtime_policy_digest: str
    telemetry_digest: str

    previous_record_digest: str
    record_digest: str

    def __post_init__(self) -> None:
        if self.schema_version != "darwinian.frame-record.v1":
            raise ValueError(
                "Unsupported frame-record schema."
            )

        if not self.episode_id:
            raise ValueError("episode_id cannot be empty.")

        if self.frame_index < 0:
            raise ValueError(
                "frame_index cannot be negative."
            )

        if self.random_seed < 0:
            raise ValueError(
                "random_seed cannot be negative."
            )

        for name in (
            "state_before_digest",
            "state_after_digest",
            "climate_digest",
            "transition_age_digest",
            "neighbor_table_digest",
            "config_digest",
            "runtime_policy_digest",
            "telemetry_digest",
            "previous_record_digest",
            "record_digest",
        ):
            value = getattr(self, name)

            if len(value) != 64:
                raise ValueError(
                    f"{name} must be a SHA-256 digest."
                )

    def semantic_payload(self) -> dict[str, object]:
        return {
            "climate_digest": self.climate_digest,
            "config_digest": self.config_digest,
            "episode_id": self.episode_id,
            "frame_index": self.frame_index,
            "neighbor_table_digest": (
                self.neighbor_table_digest
            ),
            "previous_record_digest": (
                self.previous_record_digest
            ),
            "random_seed": self.random_seed,
            "runtime_policy_digest": (
                self.runtime_policy_digest
            ),
            "schema_version": self.schema_version,
            "state_after_digest": (
                self.state_after_digest
            ),
            "state_before_digest": (
                self.state_before_digest
            ),
            "telemetry_digest": (
                self.telemetry_digest
            ),
            "transition_age_digest": (
                self.transition_age_digest
            ),
        }

    def recompute_digest(self) -> str:
        return domain_digest(
            "darwinian.frame-record.v1",
            self.semantic_payload(),
        )

    def validate_digest(self) -> bool:
        return self.record_digest == self.recompute_digest()

    def to_dict(self) -> dict[str, object]:
        payload = self.semantic_payload()
        payload["record_digest"] = self.record_digest
        return payload

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, object],
    ) -> "EcologyFrameRecord":
        return cls(
            schema_version=str(
                payload["schema_version"]
            ),
            episode_id=str(payload["episode_id"]),
            frame_index=int(payload["frame_index"]),
            random_seed=int(payload["random_seed"]),
            state_before_digest=str(
                payload["state_before_digest"]
            ),
            state_after_digest=str(
                payload["state_after_digest"]
            ),
            climate_digest=str(
                payload["climate_digest"]
            ),
            transition_age_digest=str(
                payload["transition_age_digest"]
            ),
            neighbor_table_digest=str(
                payload["neighbor_table_digest"]
            ),
            config_digest=str(
                payload["config_digest"]
            ),
            runtime_policy_digest=str(
                payload["runtime_policy_digest"]
            ),
            telemetry_digest=str(
                payload["telemetry_digest"]
            ),
            previous_record_digest=str(
                payload["previous_record_digest"]
            ),
            record_digest=str(
                payload["record_digest"]
            ),
        )


def build_frame_record(
    *,
    episode_id: str,
    frame_index: int,
    random_seed: int,
    state_before: EcologyState,
    state_after: EcologyState,
    climate: LatticeClimateView,
    transition_age: Tensor,
    neighbors: Tensor,
    config: EcologyTransactionConfig,
    telemetry: EcologyStepTelemetry,
    previous_record_digest: str = GENESIS_RECORD_DIGEST,
) -> EcologyFrameRecord:
    partial = EcologyFrameRecord(
        schema_version="darwinian.frame-record.v1",
        episode_id=episode_id,
        frame_index=frame_index,
        random_seed=random_seed,
        state_before_digest=state_before.digest(),
        state_after_digest=state_after.digest(),
        climate_digest=climate_digest(climate),
        transition_age_digest=tensor_digest(
            "darwinian.transition-age.v1",
            transition_age,
        ),
        neighbor_table_digest=tensor_digest(
            "darwinian.neighbor-table.v1",
            neighbors,
        ),
        config_digest=config_digest(config),
        runtime_policy_digest=RUNTIME_POLICY.digest(),
        telemetry_digest=telemetry.digest(),
        previous_record_digest=previous_record_digest,
        record_digest=GENESIS_RECORD_DIGEST,
    )

    return EcologyFrameRecord(
        **{
            **partial.to_dict(),
            "record_digest": partial.recompute_digest(),
        }
    )


def write_jsonl_record(
    path: str,
    record: EcologyFrameRecord,
) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(
            canonical_json_bytes(
                record.to_dict()
            ).decode("utf-8")
        )
        handle.write("\n")


def read_jsonl_records(
    path: str,
) -> tuple[EcologyFrameRecord, ...]:
    records = []

    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue

            records.append(
                EcologyFrameRecord.from_dict(
                    json.loads(line)
                )
            )

    return tuple(records)


def verify_record_chain(
    records: tuple[EcologyFrameRecord, ...],
) -> bool:
    previous = GENESIS_RECORD_DIGEST

    for expected_index, record in enumerate(records):
        if record.frame_index != expected_index:
            return False

        if record.previous_record_digest != previous:
            return False

        if not record.validate_digest():
            return False

        previous = record.record_digest

    return True
