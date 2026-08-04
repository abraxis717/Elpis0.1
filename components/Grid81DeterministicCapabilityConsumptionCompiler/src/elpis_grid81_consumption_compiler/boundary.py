"""G5.3B Authority boundary verification.

Ensures G5.3B stays within its authority: no activation, no application,
no model/adapter/expert selection, no DarwinianMatrix interaction.
"""
from .validation import FORBIDDEN_FIELDS, check_forbidden_fields
from .canonical import canonical_digest


def verify_authority_boundary(artifact: dict, result: dict) -> tuple[bool, list[str]]:
    """Verify that the transaction result stays within authority boundaries."""
    violations = []

    # 1. Artifact must be UNAPPLIED
    if artifact and artifact.get("application_state") != "UNAPPLIED":
        violations.append("artifact_not_unapplied")

    # 2. No forbidden fields in artifact
    if artifact:
        forbidden = check_forbidden_fields(artifact)
        if forbidden:
            violations.extend(forbidden)

    # 3. No forbidden fields in full result
    forbidden_in_result = check_forbidden_fields(result)
    if forbidden_in_result:
        violations.extend(forbidden_in_result)

    # 4. Acceptance must produce exactly one artifact
    if result.get("transaction_outcome") == "CONSUMPTION_ACCEPTED":
        if result.get("structural_influence_artifact") is None:
            violations.append("accepted_no_artifact")
        if result.get("consumption_receipt") is None:
            violations.append("accepted_no_receipt")

    # 5. Rejection must produce no artifact
    if result.get("transaction_outcome") != "CONSUMPTION_ACCEPTED":
        if result.get("structural_influence_artifact") is not None:
            violations.append("rejected_has_artifact")
        if result.get("rejection_record") is None:
            violations.append("rejected_no_rejection_record")

    # 6. Lifecycle state preservation on rejection
    lifecycle = result.get("lifecycle_transition", {})
    if result.get("transaction_outcome") != "CONSUMPTION_ACCEPTED":
        if lifecycle.get("previous_lifecycle_state") != lifecycle.get("resulting_lifecycle_state"):
            violations.append("rejected_lifecycle_changed")
        if lifecycle.get("previous_consumption_count") != lifecycle.get("resulting_consumption_count"):
            violations.append("rejected_count_changed")

    # 7. Single-use law: consumption count increments by exactly 1 on acceptance
    if result.get("transaction_outcome") == "CONSUMPTION_ACCEPTED":
        prev_count = lifecycle.get("previous_consumption_count", -1)
        new_count = lifecycle.get("resulting_consumption_count", -1)
        if new_count != prev_count + 1:
            violations.append("single_use_violation")

    return len(violations) == 0, violations


def create_authority_boundary_record(artifacts: list, results: list) -> dict:
    """Create an authority boundary audit record."""
    all_violations = []
    for artifact, result in zip(artifacts, results):
        ok, violations = verify_authority_boundary(artifact, result)
        if not ok:
            all_violations.extend(violations)

    return {
        "schema_version": "g53a-authority-boundary.v1",
        "authorized_modules": [
            "elpis_grid81_consumption_compiler.canonical",
            "elpis_grid81_consumption_compiler.errors",
            "elpis_grid81_consumption_compiler.policy",
            "elpis_grid81_consumption_compiler.input",
            "elpis_grid81_consumption_compiler.validation",
            "elpis_grid81_consumption_compiler.transaction",
            "elpis_grid81_consumption_compiler.artifact",
            "elpis_grid81_consumption_compiler.receipt",
            "elpis_grid81_consumption_compiler.lifecycle",
            "elpis_grid81_consumption_compiler.replay",
            "elpis_grid81_consumption_compiler.boundary",
        ],
        "unauthorized_modules": [
            "DarwinianMatrix",
            "torch",
            "transformers",
            "socket",
            "random",
            "uuid",
        ],
        "forbidden_fields": sorted(list(FORBIDDEN_FIELDS)),
        "evidence_only": True,
        "violation_count": len(all_violations),
        "violations": all_violations,
        "boundary_digest": "",
    }
