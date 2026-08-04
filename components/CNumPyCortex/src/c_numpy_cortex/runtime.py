from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import json
import threading
import time

from .airgap import instrument_airgap, uninstrument_airgap
from .cache import WorkerCache
from .chronos2 import ChronosWorker, Chronos2Forecaster
from .config import (
    CortexConfig,
    HEALTH_ENDPOINTS,
    PSUTIL_RATE_HZ,
    RETENTION_COUNT,
)
from .contracts import (
    ChannelSchema,
    EntropyState,
    ForecastResult,
    GridPacket,
    ObservedValue,
    ObservationPacketV2,
    ObservationValidity,
    PacketLifecycle,
    TensorSpaceIdentity,
)
from .diagnostic_log import format_diagnostic_line
from .encoding import (
    QUANTIZER_VERSION,
    Grid81Compiler,
    compile_thermal_frame,
    compute_normalizer_digest,
    compute_quantizer_state,
)
from .entropy import (
    entropy_event_score,
    masked_bit_entropy,
    masked_digit_entropy,
    masked_transition_rate,
)
from .lifecycle import classify_lifecycle
from .packets import (
    AtomicPacketWriter,
    crash_recovery,
    read_manifest,
    retention_cleanup,
)
from .ring import ChronologicalRing
from .schema import load_channel_schema
from .sensors import SensorHub
from .trm_bridge import GridPacketSink
from .vintages import SyntheticForecastPort, VintageStore


@dataclass(slots=True)
class RuntimeState:
    schema: ChannelSchema
    hub: SensorHub
    ring: ChronologicalRing
    compiler: Grid81Compiler
    sink: GridPacketSink
    writer: AtomicPacketWriter
    vintage_store: VintageStore
    chronos_worker: ChronosWorker | None

    # Generation tracking
    generation: int = 0
    monotonic_ns: int = 0

    # Quantizer state
    quantizer_states: dict = None  # type: ignore

    # Previous frame data for transition
    previous_tokens: object = None
    previous_mask: object = None
    previous_schema_digest: str = ""
    previous_normalizer_digest: str = ""

    # Latest state
    latest_packet_v2: ObservationPacketV2 | None = None
    previous_grid: GridPacket | None = None
    latest_grid: GridPacket | None = None
    entropy: EntropyState | None = None
    forecast: ForecastResult | None = None

    # Diagnostic
    diagnostic_lines: list = None  # type: ignore

    # Lifecycle
    _compile_lock: threading.Lock = None  # type: ignore


def build_runtime(
    config: CortexConfig,
) -> tuple["World", "Scheduler"]:
    """Build the CNumPyCortex runtime.

    Multi-rate orchestration:
    - Fast path (20 Hz): psutil synchronous reads
    - hwmon worker (10 Hz): dedicated cache worker
    - NVIDIA worker (2 Hz): dedicated cache worker
    - Llama health worker (1 Hz): dedicated cache worker
    - Chronos worker (0.2 Hz): exactly one per runtime
    """
    import os

    # Load channel schema
    schema = load_channel_schema(config.channel_schema_path)

    # Initialize sensor hub
    hub = SensorHub(
        config.sensors,
        config.llama_endpoints,
    )
    hub.start_workers()

    # Initialize ring
    ring = ChronologicalRing(
        schema,
        capacity=config.loop.ring_capacity,
    )

    # Initialize legacy compiler
    legacy_channels = tuple(r.channel_id for r in schema.rows)
    compiler = Grid81Compiler(
        channel_names=legacy_channels,
        preferred_channels=config.compiler.channels,
        normalization_window=config.compiler.normalization_window,
        clip_z=config.compiler.clip_z,
    )

    # Initialize packet writer
    output_dir = os.path.dirname(config.output.grid_npz)
    if not output_dir:
        output_dir = "runtime"

    writer = AtomicPacketWriter(output_dir)

    # Crash recovery
    crash_recovery(output_dir)
    retention_cleanup(output_dir, config.retention_count)

    # Initialize vintage store
    vintage_store = VintageStore()

    # Initialize Chronos worker (at most one)
    chronos_worker: ChronosWorker | None = None

    if config.chronos.enabled:
        chronos_cache = WorkerCache()
        chronos_worker = ChronosWorker(
            config.chronos,
            vintage_store,
            chronos_cache,
        )
        chronos_worker.start()

    # Initialize sink
    sink = GridPacketSink(
        config.output.grid_npz,
        config.output.state_json,
    )

    # Quantizer states
    quantizer_states: dict[str, object] = {}

    runtime_state = RuntimeState(
        schema=schema,
        hub=hub,
        ring=ring,
        compiler=compiler,
        sink=sink,
        writer=writer,
        vintage_store=vintage_store,
        chronos_worker=chronos_worker,
        quantizer_states=quantizer_states,
        diagnostic_lines=[],
        _compile_lock=threading.Lock(),
    )

    world = World()
    entity = world.create_entity()
    world.set(entity, runtime_state)

    def acquire(world: World) -> None:
        state = world.get(entity, RuntimeState)
        sample = state.hub.fast_acquire()

        for ch_id, value in sample.values.items():
            # Find matching schema row
            for row in state.schema.rows:
                if row.channel_id == ch_id:
                    state.ring.append_for(
                        ch_id,
                        ObservedValue(
                            value=value,
                            observed_monotonic_ns=sample.monotonic_ns,
                            source_sequence=state.generation,
                            validity=ObservationValidity.FRESH,
                            error_code=None,
                        ),
                    )
                    break

    def compile_grid(world: World) -> None:
        state = world.get(entity, RuntimeState)

        with state._compile_lock:
            state.generation += 1
            state.monotonic_ns = time.monotonic_ns()
            wall_ns = time.time_ns()

            gen = state.generation

            # Update quantizer states
            for row in state.schema.rows:
                history = state.ring.get_valid_history(
                    row.channel_id,
                    max_count=config.compiler.normalization_window,
                )
                state.quantizer_states[
                    row.channel_id
                ] = compute_quantizer_state(history)

            # Compute normalizer digest
            normalizer_digest = compute_normalizer_digest(
                state.schema,
                state.quantizer_states,
            )

            # Compile thermal frame
            ring_data = {}

            for row in state.schema.rows:
                samples = state.ring.get_chronological(
                    row.channel_id,
                    count=9,
                )
                ring_data[row.channel_id] = samples

            tokens, valid_mask, bitplanes, cell_meta = (
                compile_thermal_frame(
                    state.schema,
                    ring_data,
                    state.quantizer_states,
                    gen,
                    wall_ns,
                    state.monotonic_ns,
                    PacketLifecycle.WARMING,
                    (),
                )
            )

            # Compute masked entropy
            digit_entropy = masked_digit_entropy(
                tokens, valid_mask
            )
            bit_entropy = masked_bit_entropy(bitplanes, valid_mask)

            # Transition rate
            transition_rate = None

            if state.previous_tokens is not None:
                transition_rate = masked_transition_rate(
                    tokens,
                    valid_mask,
                    state.previous_tokens,
                    state.previous_mask,
                    state.schema.digest,
                    state.previous_schema_digest,
                    normalizer_digest,
                    state.previous_normalizer_digest,
                )

            # Event score
            event_score = entropy_event_score(
                digit_entropy, transition_rate
            )

            # Valid cell count
            valid_count = int(np.sum(valid_mask > 0))

            # Classify lifecycle
            channel_values: dict[str, ObservedValue] = {}

            for row in state.schema.rows:
                samples = state.ring.get_chronological(
                    row.channel_id, count=1
                )

                if samples:
                    channel_values[row.channel_id] = samples[-1]

            lifecycle, reasons = classify_lifecycle(
                state.schema,
                channel_values,
                state.monotonic_ns,
                None,
            )

            # Check warming condition
            for row in state.schema.rows:
                if row.required:
                    count = state.ring.sample_count(row.channel_id)

                    if count < 9:
                        lifecycle = PacketLifecycle.WARMING
                        reasons = reasons + (
                            f"WARMING:{row.channel_id}",
                        )
                        break

            # Compute token and bit SHA-256
            import hashlib

            tokens_sha = hashlib.sha256(
                tokens.tobytes()
            ).hexdigest()
            bits_sha = hashlib.sha256(
                bitplanes.tobytes()
            ).hexdigest()

            # TensorSpaceIdentity
            space = TensorSpaceIdentity.thermal(
                layout_digest=state.schema.digest,
                basis_digest=normalizer_digest,
            )

            # ObservationPacketV2
            packet_v2 = ObservationPacketV2(
                generation=gen,
                wall_time_ns=wall_ns,
                monotonic_ns=state.monotonic_ns,
                lifecycle=lifecycle,
                lifecycle_reasons=reasons,
                space=space,
                channel_schema_digest=state.schema.digest,
                normalizer_state_digest=normalizer_digest,
                tokens_sha256=tokens_sha,
                bits_sha256=bits_sha,
                digit_entropy=digit_entropy,
                bit_entropy=bit_entropy,
                entropy_event_score=event_score,
                transition_rate=transition_rate,
                valid_cell_count=valid_count,
            )

            state.latest_packet_v2 = packet_v2
            state.previous_tokens = tokens.copy()
            state.previous_mask = valid_mask.copy()
            state.previous_schema_digest = state.schema.digest
            state.previous_normalizer_digest = normalizer_digest

            # Legacy compatibility
            from .contracts import GridPacket
            import numpy as np

            legacy_packet = GridPacket(
                wall_time_ns=wall_ns,
                digits=tokens,
                bits=bitplanes,
                valid_mask=valid_mask,
                channel_names=tuple(
                    r.channel_id for r in state.schema.rows
                ),
                recursive_signature=np.zeros(144, dtype=np.float32),
            )
            legacy_packet.validate()
            state.latest_grid = legacy_packet

            # Legacy entropy
            from .entropy import measure_entropy
            state.entropy = measure_entropy(
                legacy_packet, state.previous_grid
            )
            state.previous_grid = state.latest_grid

            # Write generation atomically
            metadata = {
                "packet_v2": {
                    "generation": packet_v2.generation,
                    "wall_time_ns": packet_v2.wall_time_ns,
                    "monotonic_ns": packet_v2.monotonic_ns,
                    "lifecycle": packet_v2.lifecycle.value,
                    "lifecycle_reasons": list(packet_v2.lifecycle_reasons),
                    "valid_cell_count": packet_v2.valid_cell_count,
                    "digit_entropy": packet_v2.digit_entropy,
                    "transition_rate": packet_v2.transition_rate,
                },
                "cell_provenance": {},
                "channel_descriptors": [
                    {
                        "channel_id": r.channel_id,
                        "source_kind": r.source_kind,
                        "required": r.required,
                    }
                    for r in state.schema.rows
                ],
                "normalizer_digest": normalizer_digest,
                "tokens_sha256": tokens_sha,
                "bits_sha256": bits_sha,
            }

            # Cell provenance
            for (row, col), meta in cell_meta.items():
                metadata["cell_provenance"][
                    f"{row}_{col}"
                ] = meta

            manifest = state.writer.write_generation(
                generation=gen,
                digits=tokens,
                valid_mask=valid_mask,
                bitplanes=bitplanes,
                metadata=metadata,
                channel_schema_digest=state.schema.digest,
                created_monotonic_ns=state.monotonic_ns,
                fresh_until_monotonic_ns=state.monotonic_ns + 2_000_000_000,
            )

            # Retention
            retention_cleanup(
                output_dir, config.retention_count
            )

            # Write legacy sink
            state.sink.write(
                legacy_packet,
                state.entropy,
                state.forecast,
            )

            # Diagnostic line
            line = format_diagnostic_line(
                generation=gen,
                monotonic_ns=state.monotonic_ns,
                wall_time_ns=wall_ns,
                component="compile",
                event="grid81_commit",
                status=lifecycle.value,
                extra={
                    "valid_cells": valid_count,
                    "lifecycle_reasons": "|".join(reasons),
                },
            )
            state.diagnostic_lines.append(line)
            print(line, flush=True)

    def emit(world: World) -> None:
        state = world.get(entity, RuntimeState)

        if state.latest_grid is None or state.entropy is None:
            return

        from .entropy import state_token as _state_token

        anomaly = (
            state.forecast.anomaly_score
            if state.forecast
            else 0.0
        )

        token = _state_token(state.entropy, anomaly)

        line = format_diagnostic_line(
            generation=state.generation,
            monotonic_ns=state.monotonic_ns,
            wall_time_ns=time.time_ns(),
            component="emit",
            event="diagnostic",
            status="READY",
            extra={
                "token": token,
                "event_score": round(state.entropy.event_score, 5),
                "transition": round(
                    state.entropy.transition_rate, 5
                ),
            },
        )
        state.diagnostic_lines.append(line)

    systems = [
        System(
            "sensor_acquisition",
            1.0 / config.loop.sample_hz,
            acquire,
        ),
        System(
            "grid81_compile",
            1.0 / config.loop.compile_hz,
            compile_grid,
        ),
        System(
            "telemetry_emit",
            1.0 / config.loop.print_hz,
            emit,
        ),
    ]

    return world, Scheduler(systems), runtime_state


# Re-export ECS for backward compatibility
from .ecs import Scheduler, System, World

__all__ = [
    "build_runtime",
    "RuntimeState",
]
