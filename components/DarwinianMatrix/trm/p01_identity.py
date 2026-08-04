"""Content identity for the frozen external P0.1 structural refiner.

This module hashes artifacts as opaque byte streams. It does not import the
legacy implementation, deserialize the checkpoint, instantiate a model, or
perform inference.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


P01_IDENTITY_SCHEMA = (
    "darwinian.p01-artifact-identity.v1"
)

P01_CHECKPOINT_FILENAME = (
    "trm_hermes_best.pt"
)

P01_LEGACY_ADAPTER_FILENAME = (
    "grid_refiner.py"
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def _canonical_json_bytes(
    payload: dict[str, object],
) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _valid_digest(value: str) -> bool:
    return (
        len(value) == 64
        and all(
            character in "0123456789abcdef"
            for character in value
        )
    )


@dataclass(frozen=True)
class P01ArtifactIdentity:
    """Portable content identity for checkpoint plus adapter source."""

    checkpoint_filename: str
    checkpoint_size: int
    checkpoint_sha256: str
    adapter_filename: str
    adapter_size: int
    adapter_sha256: str

    schema: str = P01_IDENTITY_SCHEMA
    model_class: str = (
        "TinyRecursiveReasoningModel_ACTV1_Inner"
    )
    input_space: str = (
        "grid81.sudoku.p01.input.v1"
    )
    output_space: str = (
        "grid81.sudoku.p01.argmax.v1"
    )
    checkpoint_format: str = (
        "PYTORCH_ZIP_OPAQUE"
    )
    fallback_allowed: bool = False

    def __post_init__(self) -> None:
        if self.schema != P01_IDENTITY_SCHEMA:
            raise ValueError(
                "Unsupported P0.1 identity schema."
            )

        if self.checkpoint_size <= 0:
            raise ValueError(
                "checkpoint_size must be positive."
            )

        if self.adapter_size <= 0:
            raise ValueError(
                "adapter_size must be positive."
            )

        if not _valid_digest(
            self.checkpoint_sha256
        ):
            raise ValueError(
                "checkpoint_sha256 must be a lowercase "
                "SHA-256 digest."
            )

        if not _valid_digest(
            self.adapter_sha256
        ):
            raise ValueError(
                "adapter_sha256 must be a lowercase "
                "SHA-256 digest."
            )

        if self.fallback_allowed:
            raise ValueError(
                "The sealed P0.1 identity cannot permit "
                "fallback execution."
            )

    @classmethod
    def from_files(
        cls,
        *,
        checkpoint_path: str | Path,
        adapter_path: str | Path,
    ) -> "P01ArtifactIdentity":
        checkpoint = Path(
            checkpoint_path
        ).expanduser().resolve()

        adapter = Path(
            adapter_path
        ).expanduser().resolve()

        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)

        if not adapter.is_file():
            raise FileNotFoundError(adapter)

        return cls(
            checkpoint_filename=checkpoint.name,
            checkpoint_size=(
                checkpoint.stat().st_size
            ),
            checkpoint_sha256=_sha256_file(
                checkpoint
            ),
            adapter_filename=adapter.name,
            adapter_size=adapter.stat().st_size,
            adapter_sha256=_sha256_file(
                adapter
            ),
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        """Return portable identity; filesystem locations are excluded."""

        return {
            "schema": self.schema,
            "checkpoint": {
                "filename": self.checkpoint_filename,
                "size": self.checkpoint_size,
                "sha256": self.checkpoint_sha256,
                "format": self.checkpoint_format,
            },
            "adapter": {
                "filename": self.adapter_filename,
                "size": self.adapter_size,
                "sha256": self.adapter_sha256,
            },
            "model_class": self.model_class,
            "input_space": self.input_space,
            "output_space": self.output_space,
            "fallback_allowed": (
                self.fallback_allowed
            ),
        }

    def digest(self) -> str:
        return hashlib.sha256(
            _canonical_json_bytes(
                self.canonical_payload()
            )
        ).hexdigest()


__all__ = (
    "P01ArtifactIdentity",
    "P01_CHECKPOINT_FILENAME",
    "P01_IDENTITY_SCHEMA",
    "P01_LEGACY_ADAPTER_FILENAME",
)
