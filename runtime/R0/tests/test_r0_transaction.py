"""R0 transaction tests — full pipeline and negative cases."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile

import pytest

# Ensure canonical packages are on path
CANON = "/mnt/primesauce/Elpis_Canon/Elpis"
_SRC = [
    os.path.join(CANON, "TRMFractalSpine", "src"),
    os.path.join(CANON, "Pipeline", "P0ControlProtocol", "src"),
    os.path.join(CANON, "Grid81DeterministicStructuralAdjudicator", "src"),
    os.path.join(CANON, "Grid81StructuralSemantics", "src"),
    CANON,
]
for _p in _SRC:
    if _p not in sys.path:
        sys.path.insert(0, _p)

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
        with pytest.raises(R0Grid81ReadError):
            execute_r0_transaction(project_root="/tmp/nonexistent_grid81")

    def test_invalid_project_root(self):
        with pytest.raises(R0Grid81ReadError):
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
        head_path = "/mnt/primesauce/Elpis_Canon/Elpis/Grid81/state/Canonical/Grid81/HEAD.json"
        with open(head_path, "rb") as f:
            before = hashlib.sha256(f.read()).hexdigest()

        execute_r0_transaction()

        with open(head_path, "rb") as f:
            after = hashlib.sha256(f.read()).hexdigest()

        assert before == after, "Grid81 HEAD was modified during transaction"

    def test_no_darwinian_canonical_mutation(self):
        """Verify Darwinian canonical state is not modified."""
        # The DarwinianMatrix directory should have no new files after transaction
        dm_dir = "/mnt/primesauce/Elpis_Canon/Elpis/DarwinianMatrix"

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
            "/mnt/primesauce/Elpis_Canon/Pipeline/P0ControlProtocol",
            "/mnt/primesauce/Elpis_Canon/TRMFractalSpine",
            "/mnt/primesauce/Elpis_Canon/DarwinianMatrix",
            "/mnt/primesauce/Elpis_Canon/Grid81",
            "/mnt/primesauce/Elpis_Companions/Elpis_Semantic_Fabric",
            "/mnt/primesauce/Elpis_Canon/HashAdressedCascadeFabric",
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
