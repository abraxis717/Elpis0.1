"""Byte-level contract tests; fixtures are synthetic software data only."""
from dataclasses import FrozenInstanceError, asdict, replace
import hashlib
import itertools
from pathlib import Path
import os
import struct
import subprocess
import sys

import pytest

from elpis_reference.ecs_r0 import (
    AUTHORITY_DIR, EXPECTED, Candidate, EditAddress, FrozenTheta,
    MutationRequest, Opcode, R0Error, Status, equivalent, mutate, permute,
    verify_authority,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _bind_repository_ecs_authority(monkeypatch):
    monkeypatch.setenv("ELPIS_ECS_AUTHORITY_ROOT", str(REPO_ROOT))


def theta_bytes(n=36):
    # Unique columns; signed zero, subnormal and extreme finite values survive.
    values = [struct.pack("<d", float(row * n + i + 1))
              for row in range(6) for i in range(n)]
    values[n] = bytes.fromhex("0000000000000080")
    values[2 * n] = bytes.fromhex("0100000000000000")
    values[3 * n] = bytes.fromhex("ffffffffffffef7f")
    return b"".join(values)


@pytest.fixture
def candidate():
    return Candidate.bind(FrozenTheta(36, theta_bytes()))


@pytest.fixture
def authority_copy(tmp_path):
    target = tmp_path / AUTHORITY_DIR
    target.mkdir(parents=True)
    for name in (*EXPECTED, "SHA256SUMS"):
        (target / name).write_bytes((REPO_ROOT / AUTHORITY_DIR / name).read_bytes())
    (tmp_path / "ECS_AUTHORITY_HEADER.md").write_bytes(
        (REPO_ROOT / "ECS_AUTHORITY_HEADER.md").read_bytes())
    return tmp_path


def edit(candidate, opcode, slot=0):
    return mutate(candidate, MutationRequest(opcode, candidate.digest,
                  None if opcode is Opcode.ABSTAIN else candidate.address(slot)))


def test_manifest_pass(authority_copy):
    assert verify_authority() == verify_authority(authority_copy)


@pytest.mark.parametrize("target", ["header", "manifest", "entry", "directory", "root"])
def test_authority_symlinks_fail_closed_inside_fixture(authority_copy, target):
    # Both endpoints are inside pytest's workspace-local fixture; never inspect
    # an external symlink target to exercise this policy.
    if target == "root":
        link = authority_copy / "alias"
        link.symlink_to(authority_copy, target_is_directory=True)
        root = link
    else:
        paths = {
            "header": authority_copy / "ECS_AUTHORITY_HEADER.md",
            "manifest": authority_copy / AUTHORITY_DIR / "SHA256SUMS",
            "entry": authority_copy / AUTHORITY_DIR / "README.md",
            "directory": authority_copy / AUTHORITY_DIR,
        }
        path = paths[target]
        saved = path.with_name(path.name + ".saved")
        path.rename(saved)
        path.symlink_to(saved, target_is_directory=(target == "directory"))
        root = authority_copy
    with pytest.raises(R0Error, match="AUTHORITY_SYMLINK"): verify_authority(root)


def test_header_tamper_and_manifest_byte_pin(authority_copy):
    header = authority_copy / "ECS_AUTHORITY_HEADER.md"
    original = header.read_bytes()
    header.write_bytes(original + b"\n")
    with pytest.raises(R0Error, match="AUTHORITY_HEADER_DIGEST"):
        verify_authority(authority_copy)
    header.write_bytes(original)
    manifest = authority_copy / AUTHORITY_DIR / "SHA256SUMS"
    manifest.write_bytes(manifest.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(R0Error, match="AUTHORITY_MANIFEST_DIGEST"):
        verify_authority(authority_copy)


@pytest.mark.parametrize("fault", ["tamper", "missing", "manifest_missing", "duplicate",
    "bad_digest", "malformed", "traversal", "extra", "omitted", "non_ascii", "self_consistent"])
def test_manifest_fails_closed(authority_copy, fault):
    directory = authority_copy / AUTHORITY_DIR
    manifest = directory / "SHA256SUMS"
    lines = manifest.read_text().splitlines()
    name = "MUTATION_GRAMMAR.json"
    if fault in ("tamper", "self_consistent"):
        (directory / name).write_bytes(b"{}")
        if fault == "self_consistent":
            lines = [hashlib.sha256(b"{}").hexdigest() + "  " + name
                     if line.endswith(name) else line for line in lines]
            manifest.write_text("\n".join(lines) + "\n")
    elif fault == "missing":
        (directory / name).unlink()
    elif fault == "manifest_missing":
        manifest.unlink()
    elif fault == "non_ascii":
        manifest.write_bytes(b"\xff")
    else:
        if fault == "duplicate": lines.append(lines[0])
        if fault == "bad_digest": lines[0] = "g" + lines[0][1:]
        if fault == "malformed": lines[0] = lines[0].replace("  ", " ")
        if fault == "traversal": lines[0] = "0" * 64 + "  ../README.md"
        if fault == "extra": lines.append("0" * 64 + "  EXTRA.json")
        if fault == "omitted": lines.pop()
        manifest.write_text("\n".join(lines) + "\n")
    with pytest.raises(R0Error): verify_authority(authority_copy)
    with pytest.raises(R0Error): FrozenTheta(36, theta_bytes(), authority_copy)


def test_no_cached_authority_bypass(authority_copy):
    theta = FrozenTheta(36, theta_bytes(), authority_copy)
    bound = Candidate.bind(theta)
    (authority_copy / AUTHORITY_DIR / "README.md").write_bytes(b"tamper")
    for operation in (lambda: Candidate.bind(theta), bound.materialize,
                      lambda: bound.digest):
        with pytest.raises(R0Error): operation()


@pytest.mark.parametrize("n", [36, 48, 72])
def test_active_disabled_restore_width_determinism(n):
    theta = FrozenTheta(n, theta_bytes(n))
    bound = Candidate.bind(theta)
    assert bound.materialize() == theta.data
    disabled = edit(bound, Opcode.DISABLE_COLUMN).candidate
    expected = bytearray(theta.data)
    for row in range(6): expected[row * n * 8:row * n * 8 + 8] = b"\0" * 8
    assert disabled.materialize() == bytes(expected) == disabled.materialize()
    restored = edit(disabled, Opcode.RESTORE_COLUMN).candidate
    assert restored.materialize() == theta.data
    assert restored.digest == bound.digest
    assert restored.width == disabled.width == n
    assert restored.theta is disabled.theta is bound.theta


def test_initial_zero_columns_nonwritable():
    raw = bytearray(theta_bytes())
    for row in range(6):
        raw[row * 36 * 8:row * 36 * 8 + 8] = struct.pack("<d", -0.0)
    bound = Candidate.bind(FrozenTheta(36, raw))
    assert bound.mask[0] is Status.FROZEN_ZERO
    assert bound.materialize() == raw
    for op in (Opcode.DISABLE_COLUMN, Opcode.RESTORE_COLUMN):
        with pytest.raises(R0Error, match="MUTATION_PRECONDITION"): edit(bound, op)
    with pytest.raises(TypeError):
        replace(bound, mask=(Status.ACTIVE,) + bound.mask[1:])


@pytest.mark.parametrize("bits", [0x7ff0000000000000, 0xfff0000000000000,
    0x7ff8000000000123, 0x7ff0000000000001, 0xfff8000000000042])
def test_reject_nonfinite_without_normalizing(bits):
    raw = struct.pack("<Q", bits) + theta_bytes()[8:]
    with pytest.raises(R0Error, match="THETA_NONFINITE"): FrozenTheta(36, raw)


@pytest.mark.parametrize("n", [True, 0, 1, 35, 37, 81, 36.0])
def test_width_scope(n):
    with pytest.raises(R0Error, match="WIDTH_SCOPE"): FrozenTheta(n, theta_bytes())


def test_theta_shape_and_encoding():
    with pytest.raises(R0Error, match="THETA_SHAPE"): FrozenTheta(36, theta_bytes()[:-8])
    with pytest.raises(R0Error, match="THETA_ENCODING"):
        FrozenTheta(36, theta_bytes(), encoding="binary64-be-c-order")


@pytest.mark.parametrize("mask", [(), [Status.ACTIVE] * 35, [Status.ACTIVE] * 37,
    [True] * 36, [1] * 36, ["ACTIVE"] * 36, [Status.FROZEN_ZERO] * 36])
def test_public_candidate_construction_is_closed(candidate, mask):
    with pytest.raises(TypeError):
        Candidate(candidate.theta, mask)
    with pytest.raises(TypeError):
        replace(candidate, mask=mask)


@pytest.mark.parametrize("slot", [-1, 36, 100, True, 1.0, "0", None])
def test_invalid_slot(candidate, slot):
    with pytest.raises(R0Error, match="SLOT_BOUNDS"): candidate.address(slot)
    request = MutationRequest(Opcode.DISABLE_COLUMN, candidate.digest,
                             replace(candidate.address(0), slot_index=slot))
    with pytest.raises(R0Error, match="SLOT_BOUNDS"): mutate(candidate, request)


@pytest.mark.parametrize("opcode", ["OPTIMIZE", "DISABLE", "", 0, None])
def test_invalid_opcode(candidate, opcode):
    with pytest.raises(R0Error, match="OPCODE"):
        MutationRequest.from_packet(dict(op=opcode, address=None,
                                        expected_candidate_digest=candidate.digest))


@pytest.mark.parametrize("field", ["values", "theta", "N", "width", "primitive", "d",
    "adjacency", "graph", "modules", "S3", "optimizer", "learning_rate", "operations"])
def test_injection_closed_surface(candidate, field):
    packet = dict(op="DISABLE_COLUMN", address=asdict(candidate.address(0)),
                  expected_candidate_digest=candidate.digest)
    with pytest.raises(R0Error, match="PACKET_FIELDS"):
        MutationRequest.from_packet({**packet, field: [0.5]})
    packet["address"][field] = [0.5]
    # d and N are legitimate address fields, but incorrect values reject later.
    with pytest.raises(R0Error): mutate(candidate, MutationRequest.from_packet(packet))


def test_identity_and_stale_bindings(candidate):
    same = Candidate.bind(FrozenTheta(36, theta_bytes()))
    assert candidate.digest == same.digest
    other = Candidate.bind(FrozenTheta(36, struct.pack("<d", 9.0) + theta_bytes()[8:]))
    assert candidate.theta.digest != other.theta.digest
    req = MutationRequest(Opcode.DISABLE_COLUMN, candidate.digest, candidate.address(0))
    with pytest.raises(R0Error, match="STALE_CANDIDATE"): mutate(other, req)
    with pytest.raises(R0Error, match="STALE_ADDRESS"):
        mutate(other, replace(req, expected_candidate_digest=other.digest))
    disabled = mutate(candidate, req).candidate
    with pytest.raises(R0Error, match="STALE_CANDIDATE"): mutate(disabled, req)


@pytest.mark.parametrize("field,value", [
    ("ontology_id", "other"), ("ontology_version", "R1"),
    ("primitive_contract_digest", "0" * 64), ("d", 5), ("d", 6.0),
    ("N", 48), ("N", 36.0), ("operational_gauge_id", "other"),
    ("ordered_frozen_sidecar_digest", "0" * 64),
    ("expected_pre_status", "DISABLED"), ("pre_state_equivalence_digest", "0" * 64)])
def test_every_address_binding(candidate, field, value):
    req = MutationRequest(Opcode.DISABLE_COLUMN, candidate.digest,
                          replace(candidate.address(0), **{field: value}))
    with pytest.raises(R0Error): mutate(candidate, req)


def test_idempotence_is_only_abstain(candidate):
    abstain = edit(candidate, Opcode.ABSTAIN)
    assert not abstain.changed and abstain.candidate is candidate
    assert edit(abstain.candidate, Opcode.ABSTAIN) == abstain
    with pytest.raises(R0Error, match="MUTATION_PRECONDITION"):
        edit(candidate, Opcode.RESTORE_COLUMN)
    disabled = edit(candidate, Opcode.DISABLE_COLUMN).candidate
    with pytest.raises(R0Error, match="MUTATION_PRECONDITION"):
        edit(disabled, Opcode.DISABLE_COLUMN)


def test_immutable_public_interfaces():
    data = bytearray(theta_bytes())
    theta = FrozenTheta(36, memoryview(data))
    candidate = Candidate.bind(theta)
    original = candidate.materialize()
    data[:] = b"\0" * len(data)
    with pytest.raises(TypeError):
        Candidate(theta, [Status.ACTIVE] * 36)
    for obj, name, value in ((theta, "data", b""), (theta, "width", 72),
                             (candidate, "mask", ()), (candidate, "theta", None)):
        with pytest.raises((FrozenInstanceError, AttributeError)): setattr(obj, name, value)
    with pytest.raises(TypeError): theta.data[0] = 0
    with pytest.raises(TypeError): candidate.mask[0] = Status.DISABLED
    materialized = bytearray(candidate.materialize())
    materialized[:] = b"\0" * len(materialized)
    assert theta.data == candidate.materialize() == original


def test_permutation_preserves_bytes_status_and_reverse_addresses(candidate):
    candidate = edit(candidate, Opcode.DISABLE_COLUMN, 2).candidate
    moved, addresses = permute(candidate, tuple(reversed(range(36))))
    assert equivalent(candidate, moved)
    assert candidate.equivalence_digest == moved.equivalence_digest
    assert candidate.digest != moved.digest
    for old, new in enumerate(addresses):
        assert candidate.theta.column(old) == moved.theta.column(new)
        assert candidate.mask[old] is moved.mask[new]
    with pytest.raises(R0Error, match="STALE_ADDRESS"):
        mutate(moved, MutationRequest(Opcode.DISABLE_COLUMN, moved.digest, candidate.address(0)))


@pytest.mark.parametrize("order", [tuple([0] * 36), tuple(range(35)),
    tuple(range(35)) + (True,), tuple(range(35)) + (36,)])
def test_duplicate_missing_malformed_addresses(candidate, order):
    with pytest.raises(R0Error, match="PERMUTATION"): permute(candidate, order)


def test_duplicate_column_multiplicity_and_signed_zero():
    raw = b"".join(struct.pack("<d", float(row + 1)) * 36 for row in range(6))
    candidate = Candidate.bind(FrozenTheta(36, raw))
    left = edit(candidate, Opcode.DISABLE_COLUMN, 0).candidate
    right = edit(candidate, Opcode.DISABLE_COLUMN, 1).candidate
    assert equivalent(left, right)
    assert not equivalent(left, candidate)
    changed = Candidate.bind(FrozenTheta(36, b"\0" * 8 + raw[8:]))
    negative = Candidate.bind(FrozenTheta(36, struct.pack("<d", -0.0) + raw[8:]))
    assert not equivalent(changed, negative)


def test_non_equivalent_masks_never_alias_in_bounded_exhaustive_space(candidate):
    canonical, identities = set(), set()
    for bits in itertools.product((Status.ACTIVE, Status.DISABLED), repeat=6):
        state = candidate
        for slot, status in enumerate(bits):
            if status is Status.DISABLED:
                state = edit(state, Opcode.DISABLE_COLUMN, slot).candidate
        canonical.add(state.canonical_state)
        identities.add(state.digest)
    assert len(canonical) == len(identities) == 64


def test_no_observation_or_optimization_identity_surface(candidate):
    assert set(Candidate.__dataclass_fields__) == {"theta", "mask"}
    assert set(MutationRequest.__dataclass_fields__) == {"op", "address", "expected_candidate_digest"}
    assert {op.value for op in Opcode} == {"ABSTAIN", "DISABLE_COLUMN", "RESTORE_COLUMN"}
    observation = {"S3": [0] * 83}
    digest = candidate.digest
    observation["S3"][0] = 10
    assert candidate.digest == digest
    disabled = edit(candidate, Opcode.DISABLE_COLUMN, 4).candidate
    assert disabled.theta is candidate.theta
    assert all(disabled.mask[i] is candidate.mask[i] for i in range(36) if i != 4)


def test_packet_positive_and_abstain_address_negative(candidate):
    packet = dict(op="DISABLE_COLUMN", address=asdict(candidate.address(0)),
                  expected_candidate_digest=candidate.digest)
    assert mutate(candidate, MutationRequest.from_packet(packet)).changed
    with pytest.raises(R0Error, match="EDIT_ADDRESS"):
        MutationRequest.from_packet({**packet, "op": "ABSTAIN"})


def test_fresh_process_digests_and_materialization(candidate):
    code = (
        "import hashlib; from test_ecs_r0 import theta_bytes; "
        "from elpis_reference.ecs_r0 import Candidate,FrozenTheta; "
        "c=Candidate.bind(FrozenTheta(36,theta_bytes())); "
        "print(c.digest,c.equivalence_digest,hashlib.sha256(c.materialize()).hexdigest())"
    )
    expected = " ".join((candidate.digest, candidate.equivalence_digest,
                         hashlib.sha256(candidate.materialize()).hexdigest()))
    for seed in ("1", "77"):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED=seed,
                   PYTHONPATH=os.pathsep.join((str(REPO_ROOT / "src"),
                                              str(REPO_ROOT / "tests"))))
        assert subprocess.check_output([sys.executable, "-B", "-c", code],
                                       cwd=REPO_ROOT, env=env, text=True).strip() == expected


@pytest.mark.parametrize("field", ["ontology_id", "ontology_version",
    "primitive_contract_digest", "ordered_frozen_sidecar_digest",
    "operational_gauge_id", "expected_pre_status", "pre_state_equivalence_digest"])
def test_address_string_fields_are_strictly_typed(candidate, field):
    class EqualToAnything:
        def __eq__(self, other): return True
    address = replace(candidate.address(0), **{field: EqualToAnything()})
    with pytest.raises(R0Error, match="ADDRESS_FIELD_TYPE"):
        mutate(candidate, MutationRequest(Opcode.DISABLE_COLUMN, candidate.digest, address))


# Explicit bounded decoder census at the largest supported width.
#
# Address domain = {None} U {0, ..., 71}
# Opcode domain  = {ABSTAIN, DISABLE_COLUMN, RESTORE_COLUMN}
#
# Therefore the complete structural decode surface is 3 * 73 = 219 rows.
_DECODE_TOTALITY_ROWS_72 = tuple(
    (opcode, slot)
    for opcode in tuple(Opcode)
    for slot in (None, *range(72))
)


@pytest.fixture(scope="module")
def decode_candidate72():
    return Candidate.bind(
        FrozenTheta(72, theta_bytes(72), authority_root=REPO_ROOT)
    )


@pytest.mark.parametrize(
    ("opcode", "slot"),
    _DECODE_TOTALITY_ROWS_72,
    ids=[
        f"{opcode.value}-{'none' if slot is None else slot}"
        for opcode, slot in _DECODE_TOTALITY_ROWS_72
    ],
)
def test_mutation_packet_decode_totality_72(
    decode_candidate72, opcode, slot
):
    """Every bounded opcode/address pair has one deterministic decode result."""
    candidate = decode_candidate72

    packet = {
        "op": opcode.value,
        "expected_candidate_digest": candidate.digest,
        "address": (
            None
            if slot is None
            else asdict(candidate.address(slot))
        ),
    }

    should_decode = (
        (opcode is Opcode.ABSTAIN and slot is None)
        or
        (opcode is not Opcode.ABSTAIN and slot is not None)
    )

    if not should_decode:
        with pytest.raises(R0Error, match="EDIT_ADDRESS"):
            MutationRequest.from_packet(packet)
        return

    request = MutationRequest.from_packet(packet)

    assert request.op is opcode
    assert request.expected_candidate_digest == candidate.digest

    if slot is None:
        assert request.address is None
    else:
        assert request.address == candidate.address(slot)
