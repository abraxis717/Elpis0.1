from __future__ import annotations

import queue
import threading
import time
from typing import Any

import numpy as np
import pandas as pd

from .cache import WorkerCache
from .config import ChronosConfig
from .contracts import (
    ForecastResult,
    ObservedValue,
    ObservationValidity,
)
from .vintages import (
    ForecastPort,
    VintageStore,
)


class ChronosWorker:
    """Exactly one Chronos worker per CNumPyCortex runtime.

    Manages model loading, forecast queue, and vintage creation.
    Loads model with local_files_only=True.
    """

    def __init__(
        self,
        config: ChronosConfig,
        vintage_store: VintageStore,
        cache: WorkerCache,
    ):
        self.config = config
        self.vintage_store = vintage_store
        self.cache = cache
        self._pipeline = None
        self._pipeline_lock = threading.Lock()
        self._queue: queue.Queue = queue.Queue(maxsize=10)
        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._model_digest = ""
        self._loaded = False

    @property
    def model_digest(self) -> str:
        return self._model_digest

    def start(self) -> None:
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._run_loop,
            name="chronos_worker",
            daemon=True,
        )
        self._worker_thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)

    def submit_forecast(
        self,
        base_generation: int,
        context_data: dict[str, Any],
        channels: tuple[str, ...],
        target_monotonic_ns: tuple[int, ...],
    ) -> None:
        if self._queue.full():
            return

        self._queue.put(
            (
                base_generation,
                context_data,
                channels,
                target_monotonic_ns,
            )
        )

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(
                    timeout=0.5
                )
            except queue.Empty:
                continue

            base_gen, context, channels, targets = item

            try:
                self._process_forecast(
                    base_gen,
                    context,
                    channels,
                    targets,
                )
            except Exception:
                pass

            self._queue.task_done()

    def _process_forecast(
        self,
        base_generation: int,
        context_data: dict[str, Any],
        channels: tuple[str, ...],
        target_monotonic_ns: tuple[int, ...],
    ) -> None:
        pipeline = self._load()

        if pipeline is None:
            return

        prediction = pipeline.predict_df(
            context_data,
            prediction_length=self.config.prediction_length,
            quantile_levels=[0.1, 0.5, 0.9],
            id_column="item_id",
            timestamp_column="timestamp",
            target="target",
        )

        summary = self._summarize(prediction)

        # Cache forecast result
        result = ForecastResult(
            generated_at_ns=time.time_ns(),
            prediction_length=self.config.prediction_length,
            anomaly_score=0.0,
            summary=summary,
        )

        self.cache.publish({
            f"chronos.gen.{base_generation}": ObservedValue(
                value=0.0,
                observed_monotonic_ns=time.monotonic_ns(),
                source_sequence=base_generation,
                validity=ObservationValidity.FRESH,
                error_code=None,
            )
        })

    def _load(self):
        """Lazy load with local_files_only=True."""
        with self._pipeline_lock:
            if self._pipeline is not None:
                return self._pipeline

            try:
                from chronos import Chronos2Pipeline

                self._pipeline = Chronos2Pipeline.from_pretrained(
                    self.config.model_path,
                    device_map=self.config.device,
                    local_files_only=True,
                )

                self._loaded = True
                import hashlib
                import json

                self._model_digest = hashlib.sha256(
                    json.dumps(
                        {
                            "path": self.config.model_path,
                            "device": self.config.device,
                            "local_only": True,
                        },
                        sort_keys=True,
                    ).encode()
                ).hexdigest()

            except Exception:
                self._loaded = False
                self._model_digest = ""
                return None

            return self._pipeline

    @staticmethod
    def _summarize(
        prediction: pd.DataFrame,
    ) -> dict[str, Any]:
        numeric = prediction.select_dtypes(
            include=[np.number]
        )

        summary: dict[str, Any] = {
            "rows": int(len(prediction)),
            "columns": [
                str(c) for c in prediction.columns
            ],
        }

        if not numeric.empty:
            last = numeric.tail(1).iloc[0]
            summary["numeric_last"] = {
                str(k): float(v)
                for k, v in last.items()
                if np.isfinite(v)
            }

        return summary


# ─── Legacy compatibility ───────────────────────────────────────────────

class Chronos2Forecaster:
    """Legacy forecaster for backward compatibility."""

    def __init__(
        self,
        config: ChronosConfig,
    ):
        self.config = config
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            from chronos import Chronos2Pipeline

            self._pipeline = Chronos2Pipeline.from_pretrained(
                self.config.model_path,
                device_map=self.config.device,
                local_files_only=True,
            )

        return self._pipeline

    def forecast(
        self,
        wall_time_ns: np.ndarray,
        values: np.ndarray,
        channel_names: tuple[str, ...],
    ) -> ForecastResult:
        generated_at = time.time_ns()

        try:
            context = self._build_context(
                wall_time_ns,
                values,
                channel_names,
            )

            if context.empty:
                raise ValueError(
                    "insufficient finite telemetry for Chronos-2"
                )

            pipeline = self._load()

            prediction = pipeline.predict_df(
                context,
                prediction_length=self.config.prediction_length,
                quantile_levels=[0.1, 0.5, 0.9],
                id_column="item_id",
                timestamp_column="timestamp",
                target="target",
            )

            anomaly = self._estimate_anomaly(
                context,
                prediction,
            )

            summary = self._summarize_prediction(prediction)

            return ForecastResult(
                generated_at_ns=generated_at,
                prediction_length=self.config.prediction_length,
                anomaly_score=anomaly,
                summary=summary,
            )

        except Exception as exc:
            return ForecastResult(
                generated_at_ns=generated_at,
                prediction_length=self.config.prediction_length,
                anomaly_score=0.0,
                summary={},
                error=f"{type(exc).__name__}: {exc}",
            )

    def _build_context(
        self,
        wall_time_ns: np.ndarray,
        values: np.ndarray,
        channel_names: tuple[str, ...],
    ) -> pd.DataFrame:
        if len(values) < self.config.min_points:
            return pd.DataFrame(
                columns=("item_id", "timestamp", "target")
            )

        keep = min(len(values), self.config.context_points)

        timestamps = pd.to_datetime(
            wall_time_ns[-keep:],
            unit="ns",
            utc=True,
        )

        wide = pd.DataFrame(
            values[-keep:],
            index=timestamps,
            columns=channel_names,
        )

        wide = wide.replace([np.inf, -np.inf], np.nan)
        wide = wide.resample(self.config.resample_rule).mean()
        wide = wide.interpolate(limit_direction="both")

        valid_columns = [
            n for n in wide
            if wide[n].notna().sum() >= self.config.min_points
        ]

        if not valid_columns:
            return pd.DataFrame(
                columns=("item_id", "timestamp", "target")
            )

        long = (
            wide[valid_columns]
            .rename_axis("timestamp")
            .reset_index()
            .melt(
                id_vars="timestamp",
                var_name="item_id",
                value_name="target",
            )
            .dropna(subset=["target"])
        )

        return long.sort_values(
            ("item_id", "timestamp")
        ).reset_index(drop=True)

    @staticmethod
    def _quantile_column(
        prediction: pd.DataFrame,
        target: float,
    ) -> str | float | None:
        for col in prediction.columns:
            try:
                if abs(float(col) - target) < 1e-9:
                    return col
            except (TypeError, ValueError):
                continue

        aliases = {
            0.1: ("q0.1", "p10"),
            0.5: ("median", "q0.5", "p50"),
            0.9: ("q0.9", "p90"),
        }

        for alias in aliases[target]:
            if alias in prediction.columns:
                return alias

        return None

    def _estimate_anomaly(
        self,
        context: pd.DataFrame,
        prediction: pd.DataFrame,
    ) -> float:
        q10 = self._quantile_column(prediction, 0.1)
        q90 = self._quantile_column(prediction, 0.9)

        if q10 is None or q90 is None or "item_id" not in prediction:
            return 0.0

        current = (
            context.groupby("item_id", sort=False)
            .tail(1)
            .set_index("item_id")["target"]
        )

        first = (
            prediction.groupby("item_id", sort=False)
            .head(1)
            .set_index("item_id")
        )

        common = current.index.intersection(first.index)

        if len(common) == 0:
            return 0.0

        low = first.loc[common, q10].astype(float)
        high = first.loc[common, q90].astype(float)
        observed = current.loc[common].astype(float)

        width = (high - low).abs().clip(lower=1e-6)
        distance = np.maximum(low - observed, 0.0) + np.maximum(
            observed - high, 0.0
        )

        return float(np.clip((distance / width).mean(), 0.0, 1.0))

    @staticmethod
    def _summarize_prediction(
        prediction: pd.DataFrame,
    ) -> dict[str, Any]:
        numeric = prediction.select_dtypes(include=[np.number])

        summary: dict[str, Any] = {
            "rows": int(len(prediction)),
            "columns": [str(c) for c in prediction.columns],
        }

        if not numeric.empty:
            last = numeric.tail(1).iloc[0]
            summary["numeric_last"] = {
                str(k): float(v)
                for k, v in last.items()
                if np.isfinite(v)
            }

        return summary
