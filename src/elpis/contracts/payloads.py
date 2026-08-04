# elpis/contracts/payloads.py — §II Design B payload types. Storage differs;
# the ExecutionEnvelope control law is shared. Payloads expose canonical_bytes()
# for chi_p; live tensors are carried, referenced across process boundaries.
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import torch

from .codecs.grid_numpy_torch import CELLS, bytes_from_np, np_from_bytes
from .identity import chi_payload
from .masks import ValidityMask


class PayloadError(ValueError): ...


@dataclass(frozen=True, slots=True)
class GridPayload:
    TYPE_TAG = "grid81"
    data: bytes                       # canonical storage: B*81 uint8 bytes
    batch: int
    validity: ValidityMask
    decoder_hints_ref: str | None = None   # side-channel key, never in-band

    def __post_init__(self):
        if not isinstance(self.validity, ValidityMask):
            raise PayloadError(f"GridPayload requires ValidityMask, got {type(self.validity).__name__}")
        if len(self.data) != self.batch * CELLS:
            raise PayloadError("data length != batch*81")
        np_from_bytes(self.data, batch=self.batch)  # range validation

    @classmethod
    def from_numpy(cls, g: np.ndarray, validity: ValidityMask,
                   hints_ref: str | None = None) -> "GridPayload":
        b = bytes_from_np(g)
        return cls(b, len(b) // CELLS, validity, hints_ref)

    def to_numpy(self) -> np.ndarray:
        return np_from_bytes(self.data, batch=self.batch)

    def canonical_bytes(self) -> bytes:
        return self.data + self.validity.to_bytes()

    def chi_p(self) -> str:
        return chi_payload(self.TYPE_TAG, self.canonical_bytes())


@dataclass(frozen=True, slots=True)
class TensorPayload:
    TYPE_TAG = "tensor"
    tensor: torch.Tensor              # Torch owns learned continuous state
    space: str                        # semantic space id, e.g. "trm_carry"

    def __post_init__(self):
        if self.tensor.requires_grad:
            raise PayloadError("envelope tensors must be detached (no request-path grads)")

    def canonical_bytes(self) -> bytes:
        t = self.tensor.detach().to("cpu").contiguous()
        head = f"{self.space}|{t.dtype}|{tuple(t.shape)}".encode()
        return head + b"\x00" + t.numpy().tobytes()

    def chi_p(self) -> str:
        return chi_payload(self.TYPE_TAG, self.canonical_bytes())


@dataclass(frozen=True, slots=True)
class EvidenceRefPayload:
    TYPE_TAG = "evidence_ref"
    checksums: tuple[str, ...]        # C0 record chi_r values — refs, never rows
    store_uri: str

    def canonical_bytes(self) -> bytes:
        return ("|".join(sorted(self.checksums)) + "@" + self.store_uri).encode()

    def chi_p(self) -> str:
        return chi_payload(self.TYPE_TAG, self.canonical_bytes())


@dataclass(frozen=True, slots=True)
class ArtifactPayload:
    TYPE_TAG = "artifact"
    kind: str                         # "python_function", "sql", ...
    content: bytes
    contract_id: str | None = None

    def canonical_bytes(self) -> bytes:
        return self.kind.encode() + b"\x00" + self.content

    def chi_p(self) -> str:
        return chi_payload(self.TYPE_TAG, self.canonical_bytes())
