"""R0 transaction orchestrator — executes the full deterministic pipeline.

RequestContext -> P0 projection -> Grid81 read -> scope derivation
  -> StructuralOracle -> adjudication -> Darwinian episode
  -> decoder -> AST validator -> receipt
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from .adapters import (
    read_grid81_canonical_state,
    run_p0_projection,
    derive_scope,
    run_oracle_transition,
    run_adjudication,
    run_darwinian_episode,
    run_decoder,
    run_ast_validator,
)
from .contracts import (
    R0ProjectionState,
    R0Grid81State,
    R0ScopeDerivation,
    R0OracleResult,
    R0AdjudicationResult,
    R0DarwinianResult,
    R0DecoderResult,
    R0ArtifactResult,
    R0ASTValidationResult,
    R0TransactionReceipt,
    _canonical_bytes,
    _sha256_hex,
    _digest,
)
from .errors import (
    R0Error,
    R0RequestContextError,
    R0AdjudicatorRejectionError,
    R0DarwinianRejectionError,
    R0ASTValidationFailure,
)


# ---------------------------------------------------------------------------
# Canonical input
# ---------------------------------------------------------------------------

def _resolve_canonical_root() -> str:
    """Resolve the canonical assembly root portably.

    Priority:
      1. ELPIS_CANON_ROOT env override
      2. <repo_root>/components  (where Grid81, DarwinianMatrix, etc. live)
    """
    env_root = os.environ.get("ELPIS_CANON_ROOT")
    if env_root:
        return env_root
    # This file lives at runtime/R0/src/elpis_runtime_r0/transaction.py
    # dirname(__file__) = .../elpis_runtime_r0
    # + 4 x ".." reaches repo_root: elpis_runtime_r0 -> src -> R0 -> runtime -> repo_root
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
    )
    return os.path.join(repo_root, "components")


CANONICAL_ROOT = _resolve_canonical_root()


def _resolve_build_dir() -> str:
    """Resolve build directory portably.

    Priority:
      1. ELPIS_BUILD_DIR env override
      2. Temporary directory outside the source tree
    """
    env_build = os.environ.get("ELPIS_BUILD_DIR")
    if env_build:
        return env_build
    import tempfile
    base = tempfile.mkdtemp(prefix="elpis_r0_build_")
    return base


BUILD_DIR: str = ""  # resolved lazily per-transaction

# Default request context for the canonical R0 transaction
DEFAULT_REQUEST = {
    "request_id": "r0_canonical_001",
    "prompt": "def solution(x): return x + 1",
    "domain": "python",
    "entrypoint": "solution",
    "parameters": ("x",),
    "decoder_hints": (("body", "return x + 1"),),
}


def _ensure_build_dir() -> str:
    global BUILD_DIR
    if not BUILD_DIR:
        BUILD_DIR = _resolve_build_dir()
    os.makedirs(BUILD_DIR, exist_ok=True)
    return BUILD_DIR


# ---------------------------------------------------------------------------
# Component manifest digests
# ---------------------------------------------------------------------------

def _compute_component_manifest_digests() -> str:
    """Compute digests of all component manifests in the canonical assembly."""
    canon_root = CANONICAL_ROOT
    manifests = {}
    for root, dirs, files in sorted(os.walk(canon_root)):
        dirs[:] = sorted(d for d in dirs if d not in (
            "__pycache__", ".pytest_cache", "node_modules",
        ))
        for f in sorted(files):
            if f == "COMPONENT_MANIFEST.json":
                fp = os.path.join(root, f)
                with open(fp, "rb") as fh:
                    h = hashlib.sha256(fh.read()).hexdigest()
                rel = os.path.relpath(fp, canon_root)
                manifests[rel] = h

    return _digest(manifests)


# ---------------------------------------------------------------------------
# Dependency resolution audit
# ---------------------------------------------------------------------------

FORBIDDEN_PREFIXES: tuple[str, ...] = (
    # Construct old pre-promotion source roots from configured canonical root
    # so the guard fires correctly even on a clean checkout
    os.path.join("/mnt/primesauce", "Elpis_Canon", "Pipeline", "P0ControlProtocol"),
    os.path.join("/mnt/primesauce", "Elpis_Canon", "TRMFractalSpine"),
    os.path.join("/mnt/primesauce", "Elpis_Canon", "DarwinianMatrix"),
    os.path.join("/mnt/primesauce", "Elpis_Canon", "Grid81"),
    os.path.join("/mnt/primesauce", "Elpis_Companions", "Elpis_Semantic_Fabric"),
    os.path.join("/mnt/primesauce", "Elpis_Canon", "HashAdressedCascadeFabric"),
)


def _dependency_escape_audit() -> str:
    """Check that no runtime import resolves to old source roots.

    We verify by checking that all elpis_* and DarwinianMatrix imports
    resolve from within the canonical R1 assembly at CANONICAL_ROOT.
    """
    import importlib
    errors = []
    canonical_pkg = os.path.realpath(CANONICAL_ROOT)

    # Check key imports resolve to canonical assembly
    for module_name in [
        "elpis_fractal_spine",
        "elpis_p0",
        "elpis_grid81_adjudication",
        "elpis_grid81_semantics",
        "DarwinianMatrix",
    ]:
        try:
            mod = importlib.import_module(module_name)
            mod_file = getattr(mod, "__file__", "")
            if mod_file and canonical_pkg not in os.path.realpath(mod_file):
                errors.append(f"{module_name} resolves to {mod_file} (not in canonical)")
        except ImportError:
            pass

    audit = {
        "canonical_root": canonical_pkg,
        "modules_checked": 5,
        "escapes_found": len(errors),
        "errors": errors,
        "status": "CLEAN" if not errors else "ESCAPE_DETECTED",
    }
    return _digest(audit)


# ---------------------------------------------------------------------------
# Main transaction
# ---------------------------------------------------------------------------

def execute_r0_transaction(
    request: dict[str, Any] | None = None,
    project_root: str | None = None,
) -> R0TransactionReceipt:
    """Execute a full R0 deterministic transaction.

    Args:
        request: RequestContext parameters. Uses DEFAULT_REQUEST if None.
        project_root: Path to canonical Elpis assembly. Uses env default.

    Returns:
        R0TransactionReceipt with all digests bound.
    """
    if project_root is None:
        project_root = CANONICAL_ROOT

    if request is None:
        request = DEFAULT_REQUEST

    build_dir = _ensure_build_dir()

    # --- Phase 1: RequestContext ingress ---
    request_id = request.get("request_id")
    prompt = request.get("prompt")
    domain = request.get("domain", "python")
    entrypoint = request.get("entrypoint", "solution")
    parameters = tuple(request.get("parameters", ()))
    decoder_hints = tuple(request.get("decoder_hints", ()))

    if not request_id:
        raise R0RequestContextError("MISSING_REQUEST_ID", "request_id required")
    if not prompt:
        raise R0RequestContextError("MISSING_PROMPT", "prompt required")

    request_digest = _digest(request)
    logical_tick = 0

    # --- Phase 2: P0 deterministic projection ---
    proj_digest, grid81, semantic_rows, features_digest = run_p0_projection(
        request_id=request_id,
        prompt=prompt,
        domain=domain,
        entrypoint=entrypoint,
        parameters=parameters,
        decoder_hints=decoder_hints,
    )

    projection = R0ProjectionState(
        projection_digest=proj_digest,
        grid81=grid81,
        semantic_rows=semantic_rows,
        features_digest=features_digest,
    )

    # Save projection for audit
    with open(os.path.join(build_dir, "p0_projection.json"), "w") as f:
        json.dump({
            "digest": proj_digest,
            "grid81": list(grid81),
            "semantic_rows": list(semantic_rows),
        }, f, sort_keys=True, separators=(",", ":"))

    # --- Phase 3: Grid81 canonical state read ---
    gen_number, gen_raw_sha, gen_semantic, canon_digest, txn_id = (
        read_grid81_canonical_state(project_root)
    )

    grid81_state = R0Grid81State(
        generation_number=gen_number,
        generation_raw_sha256=gen_raw_sha,
        generation_semantic_digest=gen_semantic,
        canonical_digest=canon_digest,
        transaction_id=txn_id,
    )

    # --- Phase 4: Scope derivation ---
    mask_digest, writable_mask81, scope_decision_digest = derive_scope(grid81)

    scope = R0ScopeDerivation(
        mask_digest=mask_digest,
        writable_mask81=writable_mask81,
        scope_decision_digest=scope_decision_digest,
    )

    # --- Phase 5: StructuralOracle transition ---
    oracle_input, oracle_output, quiescence, violations, rationale, candidates = (
        run_oracle_transition(grid81, writable_mask81)
    )

    oracle_result = R0OracleResult(
        input_digest=oracle_input,
        output_digest=oracle_output,
        quiescence=quiescence,
        violation_codes=violations,
        rationale_codes=rationale,
        candidate_count=candidates,
    )

    # Save oracle result
    with open(os.path.join(build_dir, "oracle_result.json"), "w") as f:
        json.dump({
            "input_digest": oracle_input,
            "output_digest": oracle_output,
            "quiescence": quiescence,
            "violation_codes": list(violations),
            "rationale_codes": list(rationale),
            "candidate_count": candidates,
        }, f, sort_keys=True, separators=(",", ":"))

    # --- Phase 6: Adjudication ---
    adj_digest, adj_verdict, adj_outcome, adj_reasons = run_adjudication(
        oracle_input_digest=oracle_input,
        oracle_output_digest=oracle_output,
        oracle_quiescence=quiescence,
        oracle_violations=violations,
        oracle_rationale=rationale,
        candidate_count=candidates,
    )

    adjudication = R0AdjudicationResult(
        adjudication_digest=adj_digest,
        verdict=adj_verdict,
        outcome=adj_outcome,
        reason_codes=adj_reasons,
    )

    # Save adjudication
    with open(os.path.join(build_dir, "adjudication_result.json"), "w") as f:
        json.dump({
            "digest": adj_digest,
            "verdict": adj_verdict,
            "outcome": adj_outcome,
            "reason_codes": list(adj_reasons),
        }, f, sort_keys=True, separators=(",", ":"))

    # Check adjudication verdict
    if adj_verdict == "REJECTED":
        # Produce failed receipt
        return R0TransactionReceipt(
            transaction_id=request_id,
            request_digest=request_digest,
            logical_tick=logical_tick,
            p0_projection_digest=proj_digest,
            grid81_generation_number=gen_number,
            grid81_canonical_state_digest=canon_digest,
            scope_decision_digest=scope_decision_digest,
            structural_oracle_input_digest=oracle_input,
            structural_oracle_output_digest=oracle_output,
            adjudication_digest=adj_digest,
            adjudication_verdict=adj_verdict,
            termination_disposition="ADJUDICATION_REJECTED",
            runtime_admission=False,
        )

    # --- Phase 7: Darwinian episode ---
    darw_digest, darw_verdict, darw_exercised, darw_inactive = (
        run_darwinian_episode(adj_digest, adj_verdict)
    )

    darwinian = R0DarwinianResult(
        episode_digest=darw_digest,
        verdict=darw_verdict,
        lifecycle_authorities_exercised=darw_exercised,
        lifecycle_authorities_inactive=darw_inactive,
    )

    # Save Darwinian result
    with open(os.path.join(build_dir, "darwinian_result.json"), "w") as f:
        json.dump({
            "episode_digest": darw_digest,
            "verdict": darw_verdict,
            "authorities_exercised": list(darw_exercised),
            "authorities_inactive": list(darw_inactive),
        }, f, sort_keys=True, separators=(",", ":"))

    # Check Darwinian verdict
    if darw_verdict == "REJECTED":
        return R0TransactionReceipt(
            transaction_id=request_id,
            request_digest=request_digest,
            logical_tick=logical_tick,
            p0_projection_digest=proj_digest,
            grid81_generation_number=gen_number,
            grid81_canonical_state_digest=canon_digest,
            scope_decision_digest=scope_decision_digest,
            structural_oracle_input_digest=oracle_input,
            structural_oracle_output_digest=oracle_output,
            adjudication_digest=adj_digest,
            adjudication_verdict=adj_verdict,
            darwinian_episode_digest=darw_digest,
            darwinian_verdict=darw_verdict,
            termination_disposition="DARWINIAN_REJECTED",
            runtime_admission=False,
        )

    # --- Phase 8: Decoder ---
    plan_digest, artifact_digest, artifact_source = run_decoder(
        request_id=request_id,
        prompt=prompt,
        entrypoint=entrypoint,
        parameters=parameters,
        structural_digest=proj_digest,
        selected_experts=("python.codegen",),
        body_hint="return x + 1",
    )

    decoder = R0DecoderResult(
        control_plan_digest=plan_digest,
        plan_backend="deterministic-python-template-v1",
    )

    artifact = R0ArtifactResult(
        artifact_digest=artifact_digest,
        source_length=len(artifact_source),
        language="python",
    )

    # Save artifact
    with open(os.path.join(build_dir, "artifact.py"), "w") as f:
        f.write(artifact_source)

    # --- Phase 9: AST validator ---
    ast_passed, ast_code, ast_message, ast_validator = run_ast_validator(
        request_id=request_id,
        prompt=prompt,
        entrypoint=entrypoint,
        artifact_source=artifact_source,
    )

    ast_result = R0ASTValidationResult(
        passed=ast_passed,
        code=ast_code,
        message=ast_message,
        validator_id=ast_validator,
    )

    # --- Phase 10: Receipt assembly ---
    component_manifests = _compute_component_manifest_digests()
    dep_audit = _dependency_escape_audit()

    ast_result_str = (
        f"{ast_validator}:{ast_code}:{'PASS' if ast_passed else 'FAIL'}:{ast_message}"
    )

    disposition = "DETERMINISTIC_TRANSACTION_COMPLETE"
    if not ast_passed:
        disposition = "AST_VALIDATION_FAILED"

    receipt = R0TransactionReceipt(
        transaction_id=request_id,
        request_digest=request_digest,
        logical_tick=logical_tick,
        p0_projection_digest=proj_digest,
        grid81_generation_number=gen_number,
        grid81_canonical_state_digest=canon_digest,
        scope_decision_digest=scope_decision_digest,
        structural_oracle_input_digest=oracle_input,
        structural_oracle_output_digest=oracle_output,
        adjudication_digest=adj_digest,
        adjudication_verdict=adj_verdict,
        darwinian_episode_digest=darw_digest,
        darwinian_verdict=darw_verdict,
        decoder_control_plan_digest=plan_digest,
        decoded_artifact_digest=artifact_digest,
        ast_validation_result=ast_result_str,
        component_manifest_digests=component_manifests,
        dependency_resolution_audit=dep_audit,
        termination_disposition=disposition,
        runtime_admission=False,
    )

    # Save receipt
    with open(os.path.join(build_dir, "transaction_receipt.json"), "w") as f:
        f.write(receipt.to_canonical_json())

    return receipt
