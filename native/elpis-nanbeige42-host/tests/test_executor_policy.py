import pytest

from elpis_nanbeige42_host.errors import ExecutorPolicyViolation, PatchTransactionViolation
from elpis_nanbeige42_host.executor_policy import PatchTransactionState, default_policy
from elpis_nanbeige42_host.schemas import (
    ActionKind, CodingAction, CommandPayload, PatchOperation, PatchPayload,
)

def test_raw_command_is_not_an_authority():
    policy = default_policy()
    action = CodingAction(
        schema="elpis.nanbeige42.coding-action.v1", action_id="a", tick_id="t",
        kind=ActionKind.RUN_COMMAND,
        payload=CommandPayload(command_id="curl", argv=("https://example.com",)),
        rationale_summary="", expected_result="",
    )
    with pytest.raises(ExecutorPolicyViolation):
        policy.validate_action(action)

def test_shell_chaining_forbidden_even_for_allowed_command():
    policy = default_policy()
    action = CodingAction(
        schema="elpis.nanbeige42.coding-action.v1", action_id="a", tick_id="t",
        kind=ActionKind.RUN_TEST,
        payload=CommandPayload(command_id="pytest_focused", argv=("x", "&&", "rm")),
        rationale_summary="", expected_result="",
    )
    with pytest.raises(ExecutorPolicyViolation):
        policy.validate_action(action)

def test_patch_path_and_transaction_are_enforced():
    policy = default_policy()
    payload = PatchPayload(
        operations=(PatchOperation(
            target_path="$ELPIS_CANON_ROOT/Elpis_Canon/a.py",
            expected_preimage_digest="sha256:x", unified_diff="@@",
        ),),
        verification_command_ids=("python_py_compile",),
    )
    action = CodingAction(
        schema="elpis.nanbeige42.coding-action.v1", action_id="a", tick_id="t",
        kind=ActionKind.PATCH, payload=payload,
        rationale_summary="", expected_result="",
    )
    policy.validate_action(action)
    policy.validate_patch_transition(PatchTransactionState.PROPOSED, PatchTransactionState.STAGED)
    with pytest.raises(PatchTransactionViolation):
        policy.validate_patch_transition(PatchTransactionState.PROPOSED, PatchTransactionState.RENAMED)
