"""Deterministic Torch execution policy for Darwinian Matrix transactions.

Hash-seed-independent evidence requires deterministic state evolution and
deterministic intermediate telemetry tensors. Canonicalizing only the final
scalar reduction is insufficient if parallel kernels produced different
low-order bits beforehand.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import threading

import torch


_RUNTIME_LOCK = threading.Lock()


@dataclass(frozen=True)
class DeterministicRuntimePolicy:
    schema_version: str = "darwinian.runtime-policy.v1"
    intraop_threads: int = 1
    deterministic_algorithms: bool = True
    mkldnn_enabled: bool = False

    def canonical_payload(self) -> dict[str, object]:
        return {
            "deterministic_algorithms": (
                self.deterministic_algorithms
            ),
            "intraop_threads": self.intraop_threads,
            "mkldnn_enabled": self.mkldnn_enabled,
            "schema_version": self.schema_version,
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

        return hashlib.sha256(
            b"darwinian.runtime-policy.v1\x00"
            + encoded
        ).hexdigest()


RUNTIME_POLICY = DeterministicRuntimePolicy()


def enforce_deterministic_runtime() -> DeterministicRuntimePolicy:
    """Enforce and verify the process-wide deterministic execution policy.

    Torch thread configuration is process-global. The Darwinian Matrix makes
    that dependency explicit rather than silently inheriting host defaults.
    """
    with _RUNTIME_LOCK:
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ["MKL_NUM_THREADS"] = "1"
        os.environ["OPENBLAS_NUM_THREADS"] = "1"
        os.environ["NUMEXPR_NUM_THREADS"] = "1"

        torch.set_num_threads(
            RUNTIME_POLICY.intraop_threads
        )
        torch.use_deterministic_algorithms(
            RUNTIME_POLICY.deterministic_algorithms,
            warn_only=False,
        )
        torch.backends.mkldnn.enabled = (
            RUNTIME_POLICY.mkldnn_enabled
        )

        assert_deterministic_runtime()

    return RUNTIME_POLICY


def assert_deterministic_runtime() -> None:
    """Fail closed when the active Torch policy violates the contract."""
    observed_threads = torch.get_num_threads()

    if observed_threads != RUNTIME_POLICY.intraop_threads:
        raise RuntimeError(
            "Deterministic runtime violation: "
            f"expected {RUNTIME_POLICY.intraop_threads} "
            f"Torch intra-op thread, observed "
            f"{observed_threads}."
        )

    if (
        torch.are_deterministic_algorithms_enabled()
        != RUNTIME_POLICY.deterministic_algorithms
    ):
        raise RuntimeError(
            "Deterministic runtime violation: deterministic "
            "algorithms are not enabled."
        )

    if (
        bool(torch.backends.mkldnn.enabled)
        != RUNTIME_POLICY.mkldnn_enabled
    ):
        raise RuntimeError(
            "Deterministic runtime violation: unexpected "
            "MKLDNN state."
        )
