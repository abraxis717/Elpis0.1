"""R0 transaction tests — full pipeline and negative cases."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile

import pytest

# Resolve repository root portably and bootstrap all required packages.
# This test lives at runtime/R0/tests/
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Namespaced packages under components/*/src
_SRC = [
    os.path.join(_REPO_ROOT, "components", "TRMFractalSpine", "src"),
    os.path.join(_REPO_ROOT, "components", "Grid81DeterministicStructuralAdjudicator", "src"),
    os.path.join(_REPO_ROOT, "components", "Grid81StructuralSemantics", "src"),
    os.path.join(_REPO_ROOT, "components", "Pipeline", "P0ControlProtocol", "src"),
]
# Top-level packages directly under components/ (Grid81, DarwinianMatrix)
for _p in _SRC:
    if _p not in sys.path:
        sys.path.insert(0, _p)
if _REPO_ROOT + "/components" not in sys.path and os.path.join(_REPO_ROOT, "components") not in sys.path:
    sys.path.insert(0, os.path.join(_REPO_ROOT, "components"))

os.environ["CUDA_VISIBLE_DEVICES"] = ""

from elpis_runtime_r0.contracts import (
    R0TransactionReceipt,
    _canonical_bytes,
    _sha256_hex,
)
from elpis_runtime_r0.errors import (
    R0Error,
    R0RequestContextError,
    R0Grid81ReadError,
    R0ImportEscapeError,
    R0OracleError,
)
from elpis_runtime_r0.receipt import (
    verify_receipt_self_hash,
    receipts_identical,
)
from elpis_runtime_r0.transaction import (
    execute_r0_transaction,
    CANONICAL_ROOT,
    DEFAULT_REQUEST,
)


# ====================================================================
# Happy-path tests
# ====================================================================

class TestHappyPath:
    """Full transaction execution tests."""

    def test_transaction_produces_receipt(self):
        receipt = execute_r0_transaction()
        assert isinstance(receipt, R0TransactionReceipt)
        assert receipt.schema == "elpis.runtime.r0.receipt.v1"
        assert receipt.runtime_admission is False

    def test_transaction_has_non_empty_digests(self):
        receipt = execute_r0_transaction()
        assert receipt.transaction_id
        assert receipt.request_digest
        assert receipt.p0_projection_digest
        assert receipt.grid81_canonical_state_digest
        assert receipt.structural_oracle_input_digest
        assert receipt.structural_oracle_output_digest
        assert receipt.adjudication_digest
        assert receipt.darwinian_episode_digest
        assert receipt.decoder_control_plan_digest
        assert receipt.decoded_artifact_digest
        assert receipt.receipt_self_hash

    def test_receipt_self_hash_valid(self):
        receipt = execute_r0_transaction()
        assert verify_receipt_self_hash(receipt)

    def test_receipt_canonical_json_deterministic(self):
        receipt = execute_r0_transaction()
        j1 = receipt.to_canonical_json()
        j2 = receipt.to_canonical_json()
        assert j1 == j2
        # Verify it parses back
        data = json.loads(j1)
        assert data["schema"] == "elpis.runtime.r0.receipt.v1"

    def test_in_process_repeatability(self):
        r1 = execute_r0_transaction()
        r2 = execute_r0_transaction()
        assert receipts_identical(r1, r2)

    def test_grid81_generation_is_000001(self):
        receipt = execute_r0_transaction()
        assert receipt.grid81_generation_number == 1

    def test_adjudication_verdict_recorded(self):
        receipt = execute_r0_transaction()
        assert receipt.adjudication_verdict in ("ACCEPTED", "REJECTED")

    def test_darwinian_verdict_recorded(self):
        receipt = execute_r0_transaction()
        assert receipt.darwinian_verdict in ("ACCEPTED", "REJECTED")

    def test_runtime_admission_always_false(self):
        receipt = execute_r0_transaction()
        assert receipt.runtime_admission is False

    def test_receipt_bytes_stable(self):
        r1 = execute_r0_transaction()
        r2 = execute_r0_transaction()
        assert r1.receipt_bytes() == r2.receipt_bytes()

    def test_receipt_self_hash_matches(self):
        receipt = execute_r0_transaction()
        # Recompute self-hash
        payload = {
            "schema": receipt.schema,
            "transaction_id": receipt.transaction_id,
            "request_digest": receipt.request_digest,
            "logical_tick": receipt.logical_tick,
            "p0_projection_digest": receipt.p0_projection_digest,
            "grid81_generation_number": receipt.grid81_generation_number,
            "grid81_canonical_state_digest": receipt.grid81_canonical_state_digest,
            "scope_decision_digest": receipt.scope_decision_digest,
            "structural_oracle_input_digest": receipt.structural_oracle_input_digest,
            "structural_oracle_output_digest": receipt.structural_oracle_output_digest,
            "adjudication_digest": receipt.adjudication_digest,
            "adjudication_verdict": receipt.adjudication_verdict,
            "darwinian_episode_digest": receipt.darwinian_episode_digest,
            "darwinian_verdict": receipt.darwinian_verdict,
            "decoder_control_plan_digest": receipt.decoder_control_plan_digest,
            "decoded_artifact_digest": receipt.decoded_artifact_digest,
            "ast_validation_result": receipt.ast_validation_result,
            "component_manifest_digests": receipt.component_manifest_digests,
            "dependency_resolution_audit": receipt.dependency_resolution_audit,
            "termination_disposition": receipt.termination_disposition,
            "runtime_admission": receipt.runtime_admission,
        }
        expected = _sha256_hex(_canonical_bytes(payload))
        assert receipt.receipt_self_hash == expected


# ====================================================================
# Negative / fail-closed tests
# ====================================================================

class TestNegativeCases:
    """Failure tests — all must fail closed."""

    def test_malformed_request_context_missing_id(self):
        with pytest.raises(R0RequestContextError, match="MISSING_REQUEST_ID"):
            execute_r0_transaction(request={"request_id": "", "prompt": "test"})

    def test_malformed_request_context_missing_prompt(self):
        with pytest.raises(R0RequestContextError, match="MISSING_PROMPT"):
            execute_r0_transaction(request={"request_id": "x", "prompt": ""})

    def test_missing_grid81_head(self):
        with pytest.raises(R0ImportEscapeError, match="CANONICAL_ROOT_INVALID"):
            execute_r0_transaction(project_root="/tmp/nonexistent_grid81")

    def test_invalid_project_root(self):
        with pytest.raises(R0ImportEscapeError, match="CANONICAL_ROOT_INVALID"):
            execute_r0_transaction(project_root="/tmp")

    def test_malformed_oracle_input_bad_grid_size(self):
        from elpis_runtime_r0.adapters import run_oracle_transition
        with pytest.raises(R0OracleError, match="INVALID_GRID81"):
            run_oracle_transition(grid81=tuple(range(10)), writable_mask81=tuple(range(10)))

    def test_malformed_oracle_input_bad_mask_size(self):
        from elpis_runtime_r0.adapters import run_oracle_transition
        with pytest.raises(R0OracleError, match="INVALID_MASK81"):
            run_oracle_transition(grid81=tuple(range(81)), writable_mask81=tuple(range(10)))

    def test_oracle_with_all_locked_cells(self):
        # All cells locked — oracle should handle gracefully
        from elpis_runtime_r0.adapters import run_oracle_transition
        # This should not crash — it's valid input with no writable cells
        result = run_oracle_transition(
            grid81=tuple(1 for _ in range(81)),
            writable_mask81=tuple(0 for _ in range(81)),
        )
        assert isinstance(result, tuple)
        assert len(result) == 6

    def test_transaction_with_custom_request(self):
        custom = {
            "request_id": "custom_test_001",
            "prompt": "def solve(a, b): return a * b",
            "domain": "python",
            "entrypoint": "solve",
            "parameters": ("a", "b"),
            "decoder_hints": (("body", "return a * b"),),
        }
        receipt = execute_r0_transaction(request=custom)
        assert receipt.transaction_id == "custom_test_001"
        assert receipt.runtime_admission is False

    def test_no_canonical_mutation(self):
        """Verify canonical assembly is not modified by running transaction."""
        from elpis_runtime_r0.transaction import CANONICAL_ROOT
        head_path = os.path.join(
            CANONICAL_ROOT, "Grid81", "state", "Canonical", "Grid81", "HEAD.json"
        )
        if not os.path.exists(head_path):
            pytest.skip(f"Grid81 HEAD not found at {head_path} (clean clone)")
        with open(head_path, "rb") as f:
            before = hashlib.sha256(f.read()).hexdigest()

        execute_r0_transaction()

        with open(head_path, "rb") as f:
            after = hashlib.sha256(f.read()).hexdigest()

        assert before == after, "Grid81 HEAD was modified during transaction"

    def test_no_darwinian_canonical_mutation(self):
        """Verify Darwinian canonical state is not modified."""
        from elpis_runtime_r0.transaction import CANONICAL_ROOT
        dm_dir = os.path.join(CANONICAL_ROOT, "DarwinianMatrix")
        if not os.path.isdir(dm_dir):
            pytest.skip(f"DarwinianMatrix not found at {dm_dir} (clean clone)")

        def count_files(d):
            count = 0
            for root, dirs, files in os.walk(d):
                dirs[:] = [x for x in dirs if x not in ("__pycache__", ".pytest_cache")]
                count += len(files)
            return count

        before = count_files(dm_dir)
        execute_r0_transaction()
        after = count_files(dm_dir)

        assert before == after, "DarwinianMatrix files changed during transaction"


# ====================================================================
# Determinism tests
# ====================================================================

class TestDeterminism:
    """Cross-process determinism verification."""

    def test_temp_build_dir_determinism(self):
        """Same result with different build directories."""
        r1 = execute_r0_transaction()
        h1 = hashlib.sha256(r1.receipt_bytes()).hexdigest()

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["ELPIS_BUILD_DIR"] = tmp
            try:
                r2 = execute_r0_transaction()
                h2 = hashlib.sha256(r2.receipt_bytes()).hexdigest()
            finally:
                del os.environ["ELPIS_BUILD_DIR"]

        assert h1 == h2, f"Build dir changed receipt: {h1} vs {h2}"


# ====================================================================
# Authority boundary tests
# ====================================================================

class TestAuthorityBoundaries:
    """Verify authority rules are preserved."""

    def test_composition_authority_integrity(self):
        from elpis_runtime_r0.composition import verify_authority_integrity
        assert verify_authority_integrity()

    def test_authority_integrity_rejects_forbidden_claim(
        self, monkeypatch
    ):
        import elpis_runtime_r0.composition as composition

        monkeypatch.setattr(
            composition,
            "P0_PROJECTOR_AUTHORITY",
            "semantic_truth",
        )

        assert composition.verify_authority_integrity() is False

    def test_authority_integrity_rejects_unapproved_drift(
        self, monkeypatch
    ):
        import elpis_runtime_r0.composition as composition

        monkeypatch.setattr(
            composition,
            "P0_PROJECTOR_AUTHORITY",
            "structural_description_and_execution",
        )

        assert composition.verify_authority_integrity() is False

    def test_authority_integrity_rejects_runtime_admission(
        self, monkeypatch
    ):
        import elpis_runtime_r0.composition as composition

        monkeypatch.setattr(
            composition,
            "RUNTIME_ADMISSION",
            True,
        )

        assert composition.verify_authority_integrity() is False

    def test_runtime_admission_never_true(self):
        from elpis_runtime_r0.composition import RUNTIME_ADMISSION
        assert RUNTIME_ADMISSION is False

    def test_transaction_pipeline_complete(self):
        from elpis_runtime_r0.composition import get_transaction_pipeline
        pipeline = get_transaction_pipeline()
        assert len(pipeline) == 11
        assert "RequestContext_ingress" in pipeline
        assert "immutable_transaction_receipt" in pipeline

    def test_no_old_source_root_escapes(self):
        """R0 package must not import from old pre-promotion source roots.

        Forbidden paths are the old locations outside the canonical R1 assembly.
        Canonical R1 imports (elpis_p0, elpis_fractal_spine, DarwinianMatrix,
        Grid81) are required and allowed.
        """
        pkg_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "src", "elpis_runtime_r0",
        )
        # These are the OLD pre-promotion paths that must NOT be used
        forbidden_paths = [
            os.path.join(os.path.sep, "mnt", "primesauce", "Elpis_Canon", "Pipeline", "P0ControlProtocol"),
            os.path.join(os.path.sep, "mnt", "primesauce", "Elpis_Canon", "TRMFractalSpine"),
            os.path.join(os.path.sep, "mnt", "primesauce", "Elpis_Canon", "DarwinianMatrix"),
            os.path.join(os.path.sep, "mnt", "primesauce", "Elpis_Canon", "Grid81"),
            os.path.join(os.path.sep, "mnt", "primesauce", "Elpis_Companions", "Elpis_Semantic_Fabric"),
            os.path.join(os.path.sep, "mnt", "primesauce", "Elpis_Canon", "HashAdressedCascadeFabric"),
        ]
        for root, dirs, files in os.walk(pkg_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fname in files:
                if fname.endswith(".py"):
                    with open(os.path.join(root, fname)) as f:
                        content = f.read()
                    for forbidden in forbidden_paths:
                        assert forbidden not in content, (
                            f"{fname} references old source root: {forbidden}"
                        )


def test_canonical_root_rejects_filesystem_root():
    from elpis_runtime_r0.transaction import _validate_canonical_root
    from elpis_runtime_r0.errors import R0ImportEscapeError
    with pytest.raises(R0ImportEscapeError, match="CANONICAL_ROOT_INVALID"):
        _validate_canonical_root(os.path.sep)


def test_canonical_root_rejects_noncanonical_directory(tmp_path):
    from elpis_runtime_r0.transaction import _validate_canonical_root
    from elpis_runtime_r0.errors import R0ImportEscapeError
    with pytest.raises(R0ImportEscapeError, match="CANONICAL_ROOT_INVALID"):
        _validate_canonical_root(str(tmp_path))


def test_canonical_root_accepts_current_components():
    from elpis_runtime_r0.transaction import _validate_canonical_root, CANONICAL_ROOT
    assert _validate_canonical_root(CANONICAL_ROOT) == os.path.realpath(CANONICAL_ROOT)


# Exact canonical manifest authority; all fixtures copy only these three files.
_CANONICAL_MANIFEST_PATHS = (
    "Grid81/COMPONENT_MANIFEST.json",
    "DarwinianMatrix/COMPONENT_MANIFEST.json",
    "Pipeline/P0ControlProtocol/COMPONENT_MANIFEST.json",
)


@pytest.fixture
def canonical_root_fixture(tmp_path):
    from pathlib import Path

    components = Path(__file__).resolve().parents[3] / "components"
    candidate = tmp_path / "candidate"
    for relative in _CANONICAL_MANIFEST_PATHS:
        destination = candidate / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((components / relative).read_bytes())
    return candidate


def _assert_canonical_root_rejected(root, reason):
    from elpis_runtime_r0.transaction import _validate_canonical_root
    from elpis_runtime_r0.errors import R0ImportEscapeError

    with pytest.raises(R0ImportEscapeError, match="CANONICAL_ROOT_INVALID") as caught:
        _validate_canonical_root(root)
    assert reason in str(caught.value)


def test_canonical_root_exact_copies_accepted(canonical_root_fixture):
    from elpis_runtime_r0.transaction import _validate_canonical_root

    assert _validate_canonical_root(str(canonical_root_fixture)) == str(canonical_root_fixture.resolve())


def test_canonical_root_pins_match_repository_bytes():
    from pathlib import Path
    from elpis_runtime_r0.transaction import EXPECTED_CANONICAL_MANIFESTS, _validate_canonical_root

    components = Path(__file__).resolve().parents[3] / "components"
    assert set(EXPECTED_CANONICAL_MANIFESTS) == set(_CANONICAL_MANIFEST_PATHS)
    for relative, expected in EXPECTED_CANONICAL_MANIFESTS.items():
        raw = (components / relative).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected["sha256"]
        manifest = json.loads(raw)
        for field in ("component_id", "canonical_destination", "manifest_self_hash"):
            assert manifest[field] == expected[field]
    assert _validate_canonical_root(str(components)) == str(components.resolve())


def test_canonical_root_pins_are_immutable():
    from elpis_runtime_r0.transaction import EXPECTED_CANONICAL_MANIFESTS

    with pytest.raises(TypeError):
        EXPECTED_CANONICAL_MANIFESTS["extra"] = {}
    with pytest.raises(TypeError):
        EXPECTED_CANONICAL_MANIFESTS[_CANONICAL_MANIFEST_PATHS[0]]["sha256"] = "0" * 64


def test_canonical_root_json_stubs_rejected(canonical_root_fixture):
    for relative in _CANONICAL_MANIFEST_PATHS:
        path = canonical_root_fixture / relative
        legitimate = json.loads(path.read_bytes())
        path.write_text(json.dumps({
            field: legitimate[field]
            for field in ("component_id", "canonical_destination", "manifest_self_hash")
        }), encoding="utf-8")
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_digest_mismatch")


@pytest.mark.parametrize("relative", _CANONICAL_MANIFEST_PATHS)
@pytest.mark.parametrize("rewrite", ["single_byte", "content", "self_consistent"])
def test_canonical_root_manifest_rewrites_rejected(canonical_root_fixture, relative, rewrite):
    path = canonical_root_fixture / relative
    raw = path.read_bytes()
    if rewrite == "single_byte":
        # Even one added whitespace byte must fail exact-byte authentication.
        changed = raw + b"\n"
    else:
        manifest = json.loads(raw)
        manifest["display_name"] = "rewritten"
        if rewrite == "self_consistent":
            manifest.pop("manifest_self_hash")
            payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
            manifest["manifest_self_hash"] = hashlib.sha256(payload).hexdigest()
            assert len(manifest["manifest_self_hash"]) == 64
            assert manifest["manifest_self_hash"] != json.loads(raw)["manifest_self_hash"]
        changed = json.dumps(manifest, sort_keys=True).encode("utf-8")
    path.write_bytes(changed)
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_digest_mismatch")


@pytest.mark.parametrize("field", ["component_id", "canonical_destination", "manifest_self_hash"])
def test_canonical_root_wrong_identity_rejected(canonical_root_fixture, field):
    path = canonical_root_fixture / _CANONICAL_MANIFEST_PATHS[0]
    manifest = json.loads(path.read_bytes())
    manifest[field] = "0" * 64 if field == "manifest_self_hash" else "wrong"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_digest_mismatch")


@pytest.mark.parametrize("other", _CANONICAL_MANIFEST_PATHS[1:])
def test_canonical_root_swapped_manifests_rejected(canonical_root_fixture, other):
    first = canonical_root_fixture / _CANONICAL_MANIFEST_PATHS[0]
    second = canonical_root_fixture / other
    first_bytes, second_bytes = first.read_bytes(), second.read_bytes()
    first.write_bytes(second_bytes)
    second.write_bytes(first_bytes)
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_digest_mismatch")


@pytest.mark.parametrize("raw", [b'{"malformed":', b"[]", b"null", b"\xff"])
def test_canonical_root_malformed_or_nonobject_json_rejected(canonical_root_fixture, raw):
    (canonical_root_fixture / _CANONICAL_MANIFEST_PATHS[0]).write_bytes(raw)
    # The external byte pin rejects malformed replacements before JSON parsing.
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_digest_mismatch")


@pytest.mark.parametrize("relative", _CANONICAL_MANIFEST_PATHS)
def test_canonical_root_missing_manifest_rejected(canonical_root_fixture, relative):
    (canonical_root_fixture / relative).unlink()
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_missing")


@pytest.mark.parametrize("relative", [
    "", "Grid81", "DarwinianMatrix", "Pipeline", "Pipeline/P0ControlProtocol",
    *_CANONICAL_MANIFEST_PATHS,
])
def test_canonical_root_symlink_rejected(canonical_root_fixture, tmp_path, relative):
    path = canonical_root_fixture / relative
    is_directory = path.is_dir()
    authentic = tmp_path / "authentic"
    path.rename(authentic)
    path.symlink_to(authentic, target_is_directory=is_directory)
    reason = "manifest_symlink" if relative else "symlink root"
    _assert_canonical_root_rejected(str(canonical_root_fixture), reason)


@pytest.mark.parametrize("kind", ["directory", "fifo"])
def test_canonical_root_nonregular_manifest_rejected(canonical_root_fixture, kind):
    path = canonical_root_fixture / _CANONICAL_MANIFEST_PATHS[0]
    path.unlink()
    if kind == "directory":
        path.mkdir()
    else:
        os.mkfifo(path)
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_not_regular")


@pytest.mark.parametrize("root", ["", None, 42, "\x00"])
def test_canonical_root_invalid_input_rejected(root):
    reason = "root_malformed" if root == "\x00" else "empty/non-string root"
    _assert_canonical_root_rejected(root, reason)


def test_canonical_root_environment_override_authenticated(canonical_root_fixture, monkeypatch):
    from elpis_runtime_r0 import transaction

    monkeypatch.setenv("ELPIS_CANON_ROOT", str(canonical_root_fixture))
    assert transaction._resolve_canonical_root() == str(canonical_root_fixture.resolve())
    (canonical_root_fixture / _CANONICAL_MANIFEST_PATHS[0]).write_bytes(b"{}")
    with pytest.raises(transaction.R0ImportEscapeError, match="manifest_digest_mismatch"):
        transaction._resolve_canonical_root()


def test_canonical_root_default_resolution_remains_lazy(tmp_path, monkeypatch):
    from elpis_runtime_r0 import transaction

    monkeypatch.delenv("ELPIS_CANON_ROOT", raising=False)
    monkeypatch.setattr(transaction, "__file__", str(tmp_path / "installed" / "transaction.py"))

    def unexpected_authentication(root):
        pytest.fail("Default-root resolution must not require a source checkout at import")

    monkeypatch.setattr(transaction, "_validate_canonical_root", unexpected_authentication)
    expected = os.path.join(os.path.abspath(os.path.join(
        os.path.dirname(transaction.__file__), "..", "..", "..", ".."
    )), "components")
    assert transaction._resolve_canonical_root() == expected


@pytest.mark.parametrize("use_default", [True, False])
def test_canonical_root_dependency_audit_authenticates(canonical_root_fixture, monkeypatch, use_default):
    from elpis_runtime_r0 import transaction

    (canonical_root_fixture / _CANONICAL_MANIFEST_PATHS[0]).write_bytes(b"{}")
    monkeypatch.setattr(transaction, "CANONICAL_ROOT", str(canonical_root_fixture))
    with pytest.raises(transaction.R0ImportEscapeError, match="manifest_digest_mismatch"):
        if use_default:
            transaction._dependency_escape_audit()
        else:
            transaction._dependency_escape_audit(str(canonical_root_fixture))


@pytest.mark.parametrize("field", ["component_id", "canonical_destination", "manifest_self_hash"])
def test_canonical_root_parsed_identity_defense(canonical_root_fixture, monkeypatch, field):
    from elpis_runtime_r0 import transaction

    manifest = json.loads((canonical_root_fixture / _CANONICAL_MANIFEST_PATHS[0]).read_bytes())
    manifest[field] = "wrong"
    # Fault injection after authentic bytes: identity checks independently reject.
    monkeypatch.setattr(transaction.json, "loads", lambda raw: manifest)
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_identity_mismatch")


@pytest.mark.parametrize("parsed", [None, []])
def test_canonical_root_parsed_object_required(canonical_root_fixture, monkeypatch, parsed):
    from elpis_runtime_r0 import transaction

    monkeypatch.setattr(transaction.json, "loads", lambda raw: parsed)
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_malformed")


def test_canonical_root_parser_error_is_bounded(canonical_root_fixture, monkeypatch):
    from elpis_runtime_r0 import transaction

    def malformed(raw):
        raise json.JSONDecodeError("arbitrary parser detail", "", 0)

    monkeypatch.setattr(transaction.json, "loads", malformed)
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_malformed")


def test_canonical_root_filesystem_error_is_bounded(canonical_root_fixture, monkeypatch):
    from elpis_runtime_r0 import transaction

    def unreadable(*args, **kwargs):
        raise PermissionError("arbitrary filesystem detail")

    monkeypatch.setattr(transaction.os, "open", unreadable)
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_unreadable")
