"""Non-model executor authority and patch transaction policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import Literal

from .digest import canonical_digest
from .errors import ExecutorPolicyViolation, PatchTransactionViolation
from .schemas import ActionKind, CodingAction, CommandPayload, PatchPayload


class PatchTransactionState(str, Enum):
    PROPOSED = "proposed"
    STAGED = "staged"
    VERIFIED = "verified"
    RENAMED = "renamed"
    RECEIPTED = "receipted"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True, slots=True)
class ExecutorPolicy:
    schema: Literal["elpis.nanbeige42.executor-policy.v1"]
    allowed_command_ids: tuple[str, ...]
    allowed_repo_roots: tuple[str, ...]
    forbidden_path_prefixes: tuple[str, ...]
    network_allowed: bool
    allowed_physical_gpus: tuple[int, ...]
    git_push_allowed: bool
    symlink_write_allowed: bool
    shell_interpolation_allowed: bool
    patch_transaction_sequence: tuple[str, ...]
    policy_digest: str = ""

    def with_digest(self) -> "ExecutorPolicy":
        digest = canonical_digest(self, digest_field="policy_digest")
        return ExecutorPolicy(
            schema=self.schema,
            allowed_command_ids=self.allowed_command_ids,
            allowed_repo_roots=self.allowed_repo_roots,
            forbidden_path_prefixes=self.forbidden_path_prefixes,
            network_allowed=self.network_allowed,
            allowed_physical_gpus=self.allowed_physical_gpus,
            git_push_allowed=self.git_push_allowed,
            symlink_write_allowed=self.symlink_write_allowed,
            shell_interpolation_allowed=self.shell_interpolation_allowed,
            patch_transaction_sequence=self.patch_transaction_sequence,
            policy_digest=digest,
        )

    def validate_action(self, action: CodingAction) -> None:
        if action.kind in (ActionKind.RUN_COMMAND, ActionKind.RUN_TEST):
            payload = action.payload
            if not isinstance(payload, CommandPayload):
                raise ExecutorPolicyViolation("command action missing typed payload")
            if payload.command_id not in self.allowed_command_ids:
                raise ExecutorPolicyViolation("command id not allowlisted")
            if any(token in arg for arg in payload.argv for token in (";", "&&", "||", "`", "$(")):
                raise ExecutorPolicyViolation("shell interpolation or chaining forbidden")
        if action.kind is ActionKind.PATCH:
            payload = action.payload
            if not isinstance(payload, PatchPayload):
                raise ExecutorPolicyViolation("patch action missing typed payload")
            for operation in payload.operations:
                self.validate_write_path(operation.target_path)
            for command_id in payload.verification_command_ids:
                if command_id not in self.allowed_command_ids:
                    raise ExecutorPolicyViolation("verification command not allowlisted")

    def validate_write_path(self, value: str) -> None:
        path = PurePosixPath(value)
        if not path.is_absolute():
            raise ExecutorPolicyViolation("write path must be absolute")
        text = str(path)
        if any(text == prefix or text.startswith(prefix.rstrip("/") + "/") for prefix in self.forbidden_path_prefixes):
            raise ExecutorPolicyViolation("write path is forbidden")
        if not any(text == root or text.startswith(root.rstrip("/") + "/") for root in self.allowed_repo_roots):
            raise ExecutorPolicyViolation("write path outside allowed repository roots")

    def validate_patch_transition(self, before: PatchTransactionState, after: PatchTransactionState) -> None:
        allowed = {
            PatchTransactionState.PROPOSED: {PatchTransactionState.STAGED},
            PatchTransactionState.STAGED: {PatchTransactionState.VERIFIED, PatchTransactionState.ROLLED_BACK},
            PatchTransactionState.VERIFIED: {PatchTransactionState.RENAMED, PatchTransactionState.ROLLED_BACK},
            PatchTransactionState.RENAMED: {PatchTransactionState.RECEIPTED, PatchTransactionState.ROLLED_BACK},
            PatchTransactionState.RECEIPTED: set(),
            PatchTransactionState.ROLLED_BACK: set(),
        }
        if after not in allowed[before]:
            raise PatchTransactionViolation(f"invalid patch transition {before.value}->{after.value}")


def default_policy() -> ExecutorPolicy:
    return ExecutorPolicy(
        schema="elpis.nanbeige42.executor-policy.v1",
        allowed_command_ids=(
            "python_py_compile", "pytest_focused", "pytest_registry",
            "git_diff_readonly", "git_status_readonly", "grep_readonly",
            "find_readonly", "cat_readonly",
        ),
        allowed_repo_roots=("$ELPIS_CANON_ROOT/Elpis_Canon",),
        forbidden_path_prefixes=(
            "$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric",
            "$HOME/Downloads",
            "/sys", "/proc", "/dev",
        ),
        network_allowed=False,
        allowed_physical_gpus=(1,),
        git_push_allowed=False,
        symlink_write_allowed=False,
        shell_interpolation_allowed=False,
        patch_transaction_sequence=(
            "stage", "verify", "atomic_rename", "receipt", "rollback_on_failure"
        ),
    ).with_digest()
