"""G5.3C Authority boundary verification.

Verifies artifacts cannot write to canonical or prohibited state through
artifact-controlled fields.
"""

FORBIDDEN_FIELDS = frozenset([
    "apply", "applied", "activation", "execute", "dispatch",
    "winner", "selected", "rank", "priority", "score", "weight",
    "confidence", "probability", "model_id", "model_name",
    "model_path", "adapter_id", "adapter_name", "adapter_path",
    "runtime_target", "device", "gpu", "port", "endpoint",
    "command", "process_id", "server", "ecs_entity", "token_commit",
    "canonical", "darwinian", "matrix", "checkpoint", "inference",
])


def check_forbidden_fields(obj, path: str = "") -> list[str]:
    """Recursively check for forbidden field names in artifact or receipt."""
    found = []
    if isinstance(obj, dict):
        for key in obj:
            current_path = f"{path}.{key}" if path else key
            if key.lower() in {f.lower() for f in FORBIDDEN_FIELDS}:
                found.append(f"forbidden_field:{current_path}")
            found.extend(check_forbidden_fields(obj[key], current_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(check_forbidden_fields(item, f"{path}[{i}]"))
    return found


def verify_authority_boundary(artifact: dict, receipt: dict | None = None) -> tuple[bool, list[str]]:
    """Verify no authority violations in artifact and receipt.

    Returns (ok, violations).
    """
    violations = []

    if artifact:
        violations.extend(check_forbidden_fields(artifact))

    if receipt:
        violations.extend(check_forbidden_fields(receipt))

    return len(violations) == 0, violations


def verify_no_canonical_write(artifact: dict) -> tuple[bool, list[str]]:
    """Verify artifact does not attempt to write canonical state.

    Checks for fields that reference canonical paths or external systems.
    """
    issues = []
    forbidden_keys = {
        "canonical_path", "canonical_digest_target", "canonical_state",
        "darwinian_matrix", "model_checkpoint", "inference_target",
        "activation_target", "routing_target",
    }
    if isinstance(artifact, dict):
        for key in artifact:
            if key in forbidden_keys:
                issues.append(f"canonical_write_field:{key}")

    return len(issues) == 0, issues
