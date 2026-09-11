"""Executable public Structural R0; no Projector or scientific execution.

Input is canonical little-endian binary64 C-order (6, N) bytes. Endianness
conversion is deliberately outside this API. Signed zeros and subnormals are
retained verbatim; NaN and infinities are rejected by the finite-value contract.
Slots are operational gauge addresses, never intrinsic entities.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import struct

ONTOLOGY = "MICROSCOPIC_COLUMN_PARTICIPATION_MASK_R0"
VERSION = "R0"
PRIMITIVE = "745fe2d762568dced27b9ff55e373ea40943f5104d24d995c30847052044ec90"
GAUGE = "BOUND_ARRAY_COLUMN_ORDER_G0"
WIDTHS = (36, 48, 72)
DEFAULT_ROOT = Path(__file__).absolute().parents[2]
AUTHORITY_DIR = "ECS/ECS_AUTHORITY/STRUCTURAL_R0"
AUTHORITY_ROOT_ENV = "ELPIS_ECS_AUTHORITY_ROOT"
# Public release pins also reject a self-consistently rewritten manifest.
EXPECTED = {
    "EDIT_IDENTITY_CONTRACT.json": "080582ee20d228af4351f923559d3e0fe0b563dd7a25db58a3dc68c6026367d9",
    "EQUIVALENCE_AND_GAUGE_ANALYSIS.json": "f6e4526b91904de77f9e51c0e6484d2547e9623089a88d081334822503f08f25",
    "FROZEN_WRITABLE_BOUNDARY.json": "fca454fa84c6da890fc60994f4beb42b7078258b08872842db077cd991c31240",
    "MATERIALIZATION_CONTRACT.json": "fce6ce9c1df090eb749ce8eb18328e449c6da6534052cbeb968f822fb18b270c",
    "MUTATION_GRAMMAR.json": "b6bc30c4a686e4273393cba36dba170678c69d7eb903803b0d91326a7d90df4c",
    "README.md": "edaf184158934a8653037b90e5f88b238e3f5e96cd827686ff0915efe8bfa743",
    "SELECTED_ONTOLOGY_SPEC.json": "f69ee197d5bff6641b3538d19a04dc27cb3aee3d4f29c3d0085c0e592423ed21",
}
HEADER_SHA256 = "5ea67cfabb46155e18cfae0e4f351c4650bf2082219741374fcec6b6a63f365d"
MANIFEST_SHA256 = "78dcc7ab307145450fd9155e0183f4cbdbae54a478a71ab16a2be17fc33f5af5"


class R0Error(ValueError):
    """Deterministic closed-contract rejection, with a stable machine code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise R0Error(code)


def _json_digest(domain: str, payload: object) -> str:
    # Same domain + NUL + canonical JSON convention as c2r6p0.domain_digest.
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(domain.encode("utf-8") + b"\0" + encoded).hexdigest()


def _framed(domain: str, parts: tuple[bytes, ...]) -> bytes:
    """Domain + NUL, followed by uint64 LE lengths and exact byte payloads."""
    return domain.encode("ascii") + b"\0" + b"".join(
        struct.pack("<Q", len(part)) + part for part in parts)


def _resolve_authority_root(root: Path | str | None = None) -> Path:
    """Resolve authority explicitly; installed packages never invent a root."""
    if root is not None:
        candidate = Path(root).absolute()
    else:
        env_root = os.environ.get(AUTHORITY_ROOT_ENV)
        if env_root:
            candidate = Path(env_root).absolute()
        elif (DEFAULT_ROOT / AUTHORITY_DIR / "SHA256SUMS").is_file():
            candidate = DEFAULT_ROOT
        else:
            raise R0Error("AUTHORITY_ROOT_REQUIRED")
    return candidate


def verify_authority(root: Path | str | None = None) -> str:
    """Check the exact seven manifest entries, pins, and all file bytes.

    No symlinks are followed, including ancestors of the supplied root.
    There is no verification cache or caller-supplied trust receipt.
    """
    root = _resolve_authority_root(root)
    directory = root / AUTHORITY_DIR
    # Inspect ancestors first so even metadata checks never traverse a symlink.
    for path in reversed((directory, *directory.parents)):
        _require(not path.is_symlink(), "AUTHORITY_SYMLINK")
    manifest = directory / "SHA256SUMS"
    _require(not manifest.is_symlink(), "AUTHORITY_SYMLINK")
    try:
        _require(manifest.is_file(), "AUTHORITY_UNREADABLE")
        raw = manifest.read_bytes()
        entries = {}
        for line in raw.decode("ascii").splitlines():
            match = re.fullmatch(r"([0-9a-f]{64})  ([A-Z][A-Z0-9_]*\.(?:json|md))", line)
            _require(match is not None, "AUTHORITY_MANIFEST_MALFORMED")
            digest, name = match.groups()
            _require(name not in entries, "AUTHORITY_MANIFEST_DUPLICATE")
            entries[name] = digest
        _require(entries == EXPECTED, "AUTHORITY_MANIFEST_ENTRIES")
        _require(hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256,
                 "AUTHORITY_MANIFEST_DIGEST")
        header = root / "ECS/ECS_AUTHORITY_HEADER.md"
        _require(not header.is_symlink(), "AUTHORITY_SYMLINK")
        _require(header.is_file(), "AUTHORITY_UNREADABLE")
        _require(hashlib.sha256(header.read_bytes()).hexdigest() == HEADER_SHA256,
                 "AUTHORITY_HEADER_DIGEST")
        for name, digest in sorted(entries.items()):
            path = directory / name
            _require(not path.is_symlink(), "AUTHORITY_SYMLINK")
            _require(path.is_file(), "AUTHORITY_UNREADABLE")
            _require(hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                     "AUTHORITY_DIGEST_MISMATCH")
    except (OSError, UnicodeError) as exc:
        raise R0Error("AUTHORITY_UNREADABLE") from exc
    return _json_digest("elpis.ecs.r0.authority.v1", {
        "entries": entries, "manifest": MANIFEST_SHA256, "header": HEADER_SHA256})


class Status(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    FROZEN_ZERO = "FROZEN_ZERO"


class Opcode(str, Enum):
    ABSTAIN = "ABSTAIN"
    DISABLE_COLUMN = "DISABLE_COLUMN"
    RESTORE_COLUMN = "RESTORE_COLUMN"


_CODES = {Status.ACTIVE: 1, Status.DISABLED: 0, Status.FROZEN_ZERO: 2}


def _prefix(width: int) -> tuple[bytes, ...]:
    return (ONTOLOGY.encode(), VERSION.encode(), bytes.fromhex(PRIMITIVE),
            struct.pack("<Q", 6), struct.pack("<Q", width))


@dataclass(frozen=True, slots=True)
class FrozenTheta:
    width: int
    data: bytes
    authority_root: Path | str | None = None
    encoding: str = "binary64-le-c-order"

    def __post_init__(self) -> None:
        _require(type(self.width) is int and self.width in WIDTHS, "WIDTH_SCOPE")
        _require(self.encoding == "binary64-le-c-order", "THETA_ENCODING")
        _require(type(self.data) in (bytes, bytearray, memoryview), "THETA_BYTES")
        object.__setattr__(self, "data", bytes(self.data))
        object.__setattr__(self, "authority_root", _resolve_authority_root(self.authority_root))
        _require(len(self.data) == 6 * self.width * 8, "THETA_SHAPE")
        verify_authority(self.authority_root)
        # Inspect exponent bits, never parse/repack a float.
        for (bits,) in struct.iter_unpack("<Q", self.data):
            _require((bits >> 52) & 0x7ff != 0x7ff, "THETA_NONFINITE")

    def column(self, slot: int) -> bytes:
        _require(type(slot) is int and 0 <= slot < self.width, "SLOT_BOUNDS")
        return b"".join(self.data[(row * self.width + slot) * 8:
                                  (row * self.width + slot + 1) * 8]
                        for row in range(6))

    def is_zero(self, slot: int) -> bool:
        return all(bits & 0x7fffffffffffffff == 0
                   for (bits,) in struct.iter_unpack("<Q", self.column(slot)))

    @property
    def digest(self) -> str:
        return hashlib.sha256(_framed("elpis.ecs.r0.theta.v1",
                                     _prefix(self.width) + (self.data,))).hexdigest()


@dataclass(frozen=True, slots=True, init=False)
class Candidate:
    theta: FrozenTheta
    mask: tuple[Status, ...]

    @classmethod
    def _from_validated_state(
        cls, theta: FrozenTheta, mask: tuple[Status, ...] | list[Status]
    ) -> Candidate:
        """Internal state constructor used only by bind/mutate/permute."""
        _require(type(theta) is FrozenTheta, "THETA_TYPE")
        verify_authority(theta.authority_root)
        _require(type(mask) in (tuple, list), "MASK_TYPE")
        normalized = tuple(mask)
        _require(len(normalized) == theta.width, "MASK_LENGTH")
        for slot, status in enumerate(normalized):
            _require(type(status) is Status, "MASK_STATUS")
            _require((status is Status.FROZEN_ZERO) == theta.is_zero(slot),
                     "FROZEN_ZERO_STATUS")
        self = object.__new__(cls)
        object.__setattr__(self, "theta", theta)
        object.__setattr__(self, "mask", normalized)
        return self

    @classmethod
    def bind(cls, theta: FrozenTheta) -> Candidate:
        _require(type(theta) is FrozenTheta, "THETA_TYPE")
        return cls._from_validated_state(
            theta, tuple(Status.FROZEN_ZERO if theta.is_zero(i)
                         else Status.ACTIVE for i in range(theta.width))
        )

    @property
    def width(self) -> int:
        return self.theta.width

    @property
    def canonical_state(self) -> bytes:
        records = tuple(sorted(self.theta.column(i) + bytes([_CODES[s]])
                               for i, s in enumerate(self.mask)))
        return _framed("elpis.ecs.r0.equivalence.v1", _prefix(self.width) + records)

    @property
    def equivalence_digest(self) -> str:
        return hashlib.sha256(self.canonical_state).hexdigest()

    @property
    def digest(self) -> str:
        return _json_digest("elpis.ecs.r0.candidate.v1", {
            "ontology_id": ONTOLOGY, "ontology_version": VERSION,
            "primitive_contract_digest": PRIMITIVE, "d": 6, "N": self.width,
            "ordered_frozen_sidecar_digest": self.theta.digest,
            "operational_gauge_id": GAUGE,
            "authority_digest": verify_authority(self.theta.authority_root),
            "mask": [s.value for s in self.mask],
            "state_equivalence_digest": self.equivalence_digest,
        })

    def materialize(self) -> bytes:
        verify_authority(self.theta.authority_root)
        return b"".join(
            b"\0" * 8 if self.mask[slot] is Status.DISABLED else
            self.theta.data[(row * self.width + slot) * 8:
                            (row * self.width + slot + 1) * 8]
            for row in range(6) for slot in range(self.width))

    def address(self, slot: int) -> EditAddress:
        self.theta.column(slot)  # strict int/bounds check, including bool rejection
        return EditAddress(ONTOLOGY, VERSION, PRIMITIVE, 6, self.width,
                           self.theta.digest, GAUGE, slot, self.mask[slot].value,
                           self.equivalence_digest)


@dataclass(frozen=True, slots=True)
class EditAddress:
    ontology_id: str
    ontology_version: str
    primitive_contract_digest: str
    d: int
    N: int
    ordered_frozen_sidecar_digest: str
    operational_gauge_id: str
    slot_index: int
    expected_pre_status: str
    pre_state_equivalence_digest: str


@dataclass(frozen=True, slots=True)
class MutationRequest:
    op: Opcode
    expected_candidate_digest: str
    address: EditAddress | None = None

    def __post_init__(self) -> None:
        _require(type(self.op) is Opcode, "OPCODE")
        _require(type(self.expected_candidate_digest) is str and
                 re.fullmatch("[0-9a-f]{64}", self.expected_candidate_digest) is not None,
                 "CANDIDATE_DIGEST_FORMAT")
        _require((self.address is None) if self.op is Opcode.ABSTAIN else
                 type(self.address) is EditAddress, "EDIT_ADDRESS")

    @classmethod
    def from_packet(cls, packet: dict) -> MutationRequest:
        _require(type(packet) is dict and set(packet) ==
                 {"op", "expected_candidate_digest", "address"}, "PACKET_FIELDS")
        try:
            _require(type(packet["op"]) is str, "OPCODE")
            op = Opcode(packet["op"])
        except ValueError as exc:
            raise R0Error("OPCODE") from exc
        address = packet["address"]
        if address is not None:
            _require(type(address) is dict and set(address) ==
                     set(EditAddress.__dataclass_fields__), "ADDRESS_FIELDS")
            address = EditAddress(**address)
        return cls(op, packet["expected_candidate_digest"], address)


@dataclass(frozen=True, slots=True)
class MutationResult:
    candidate: Candidate
    op: Opcode
    before_digest: str
    after_digest: str
    changed: bool


def mutate(candidate: Candidate, request: MutationRequest) -> MutationResult:
    _require(type(candidate) is Candidate, "CANDIDATE_TYPE")
    _require(type(request) is MutationRequest, "REQUEST_TYPE")
    before = candidate.digest
    _require(request.expected_candidate_digest == before, "STALE_CANDIDATE")
    if request.op is Opcode.ABSTAIN:
        return MutationResult(candidate, request.op, before, before, False)
    address = request.address
    _require(type(address) is EditAddress, "EDIT_ADDRESS")
    _require(type(address.d) is int and type(address.N) is int, "ADDRESS_DIMENSIONS")
    for name in EditAddress.__dataclass_fields__:
        if name not in ("d", "N", "slot_index"):
            _require(type(getattr(address, name)) is str, "ADDRESS_FIELD_TYPE")
    expected = candidate.address(address.slot_index)
    _require(address == expected, "STALE_ADDRESS")
    pre = Status.ACTIVE if request.op is Opcode.DISABLE_COLUMN else Status.DISABLED
    _require(candidate.mask[address.slot_index] is pre, "MUTATION_PRECONDITION")
    mask = list(candidate.mask)
    mask[address.slot_index] = Status.DISABLED if pre is Status.ACTIVE else Status.ACTIVE
    after = Candidate._from_validated_state(candidate.theta, tuple(mask))
    return MutationResult(after, request.op, before, after.digest, True)


def equivalent(left: Candidate, right: Candidate) -> bool:
    """Full canonical bytes, not hash equality, decide the R0 gauge relation."""
    return left.canonical_state == right.canonical_state


def permute(candidate: Candidate, order: tuple[int, ...]) -> tuple[Candidate, tuple[int, ...]]:
    """Return a rebound gauge plus old-slot -> new-slot operational addresses.

    No ordinary materialization or mutation ever sorts or rebinds slots.
    """
    _require(type(order) in (tuple, list) and len(order) == candidate.width and
             all(type(i) is int for i in order) and
             set(order) == set(range(candidate.width)), "PERMUTATION")
    data = b"".join(candidate.theta.data[(row * candidate.width + i) * 8:
                                         (row * candidate.width + i + 1) * 8]
                    for row in range(6) for i in order)
    theta = FrozenTheta(candidate.width, data, candidate.theta.authority_root)
    rebound = Candidate._from_validated_state(theta, tuple(candidate.mask[i] for i in order))
    inverse = tuple(order.index(i) for i in range(candidate.width))
    return rebound, inverse
