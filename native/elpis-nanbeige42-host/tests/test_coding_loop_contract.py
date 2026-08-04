from pathlib import Path
import json

import pytest

from elpis_nanbeige42_host.coding_loop_contract import (
    ACTION_SCHEMA,
    ActionKind,
    CodingLoopContractError,
    assert_canary_only,
    balanced_mode_orders,
    contract_payload,
    execute_action_atomic,
    parse_exact_action,
    relocate_acceptance_argv,
    render_prompt,
    sha256_text,
)


def replace_payload(content: str = "x = 2\n", digest: str | None = None) -> str:
    return json.dumps(
        {
            "schema": ACTION_SCHEMA,
            "action": "replace_file",
            "path": "solution.py",
            "preimage_sha256": digest or sha256_text("x = 1\n"),
            "content": content,
        },
        separators=(",", ":"),
    )


def test_parse_replace_file_exact():
    action = parse_exact_action(replace_payload(), maximum_patch_bytes=1024)
    assert action.action is ActionKind.REPLACE_FILE
    assert action.path == "solution.py"
    assert action.action_digest.startswith("sha256:")


def test_parse_blocker_exact():
    action = parse_exact_action(
        '{"schema":"elpis.nanbeige42.coding-action.v1","action":"report_blocker","reason":"insufficient contract"}',
        maximum_patch_bytes=1024,
    )
    assert action.action is ActionKind.REPORT_BLOCKER


def test_parser_rejects_fence_and_trailing_value():
    with pytest.raises(CodingLoopContractError):
        parse_exact_action("```json\n{}\n```", maximum_patch_bytes=100)
    with pytest.raises(CodingLoopContractError):
        parse_exact_action(replace_payload() + " {}", maximum_patch_bytes=100)


def test_parser_rejects_extra_key_and_wrong_path():
    value = json.loads(replace_payload())
    value["comment"] = "no"
    with pytest.raises(CodingLoopContractError, match="key set"):
        parse_exact_action(json.dumps(value), maximum_patch_bytes=100)
    value.pop("comment")
    value["path"] = "../solution.py"
    with pytest.raises(CodingLoopContractError, match="solution.py"):
        parse_exact_action(json.dumps(value), maximum_patch_bytes=100)


def test_parser_rejects_bad_digest_and_oversize():
    value = json.loads(replace_payload())
    value["preimage_sha256"] = "sha256:BAD"
    with pytest.raises(CodingLoopContractError, match="sha256"):
        parse_exact_action(json.dumps(value), maximum_patch_bytes=100)
    with pytest.raises(CodingLoopContractError, match="maximum_patch_bytes"):
        parse_exact_action(replace_payload("x" * 101), maximum_patch_bytes=100)


def test_prompt_is_deterministic_and_mode_free():
    first = render_prompt(
        objective="Fix the arithmetic.",
        constraints=("modify only solution.py", "no network"),
        solution="x = 1\n",
        feedback="NONE",
    )
    second = render_prompt(
        objective="Fix the arithmetic.",
        constraints=("modify only solution.py", "no network"),
        solution="x = 1\n",
        feedback="NONE",
    )
    assert first == second
    assert "dock" not in first[0].lower()
    assert "observe" not in first[0].lower()


def test_atomic_executor_commits_on_acceptance(tmp_path: Path):
    target = tmp_path / "solution.py"
    target.write_text("x = 1\n")
    action = parse_exact_action(replace_payload(), maximum_patch_bytes=1024)
    receipt = execute_action_atomic(
        task_id="task",
        run_id="run",
        tick_index=0,
        workspace_root=tmp_path,
        action=action,
        maximum_patch_bytes=1024,
        acceptance_runner=lambda: (0, "PASS"),
    )
    assert receipt.accepted is True
    assert receipt.rollback_performed is False
    assert target.read_text() == "x = 2\n"


def test_atomic_executor_rolls_back_on_rejection(tmp_path: Path):
    target = tmp_path / "solution.py"
    target.write_text("x = 1\n")
    action = parse_exact_action(replace_payload(), maximum_patch_bytes=1024)
    receipt = execute_action_atomic(
        task_id="task",
        run_id="run",
        tick_index=0,
        workspace_root=tmp_path,
        action=action,
        maximum_patch_bytes=1024,
        acceptance_runner=lambda: (1, "FAIL"),
    )
    assert receipt.accepted is False
    assert receipt.rollback_performed is True
    assert target.read_text() == "x = 1\n"


def test_atomic_executor_rejects_stale_preimage(tmp_path: Path):
    (tmp_path / "solution.py").write_text("changed\n")
    action = parse_exact_action(replace_payload(), maximum_patch_bytes=1024)
    with pytest.raises(CodingLoopContractError, match="stale"):
        execute_action_atomic(
            task_id="task",
            run_id="run",
            tick_index=0,
            workspace_root=tmp_path,
            action=action,
            maximum_patch_bytes=1024,
            acceptance_runner=lambda: (0, "PASS"),
        )


def test_atomic_executor_rejects_symlink(tmp_path: Path):
    real = tmp_path / "real.py"
    real.write_text("x = 1\n")
    (tmp_path / "solution.py").symlink_to(real)
    action = parse_exact_action(replace_payload(), maximum_patch_bytes=1024)
    with pytest.raises(CodingLoopContractError, match="non-symlink"):
        execute_action_atomic(
            task_id="task",
            run_id="run",
            tick_index=0,
            workspace_root=tmp_path,
            action=action,
            maximum_patch_bytes=1024,
            acceptance_runner=lambda: (0, "PASS"),
        )


def test_blocker_receipt_never_executes_acceptance(tmp_path: Path):
    (tmp_path / "solution.py").write_text("x = 1\n")
    action = parse_exact_action(
        '{"schema":"elpis.nanbeige42.coding-action.v1","action":"report_blocker","reason":"blocked"}',
        maximum_patch_bytes=1024,
    )
    called = False
    def runner():
        nonlocal called
        called = True
        return 0, "PASS"
    receipt = execute_action_atomic(
        task_id="task", run_id="run", tick_index=0, workspace_root=tmp_path,
        action=action, maximum_patch_bytes=1024, acceptance_runner=runner,
    )
    assert receipt.blocker_reported is True
    assert called is False


def test_acceptance_relocation_translates_exactly_one_path(tmp_path: Path):
    canonical = tmp_path / "canonical"
    shadow = tmp_path / "shadow"
    argv = ("-q", str(canonical / "acceptance" / "task" / "test_acceptance.py"))
    relocated = relocate_acceptance_argv(
        canonical_argv=argv,
        canonical_task_root=canonical,
        shadow_task_root=shadow,
    )
    assert relocated == ("-q", str(shadow / "acceptance" / "task" / "test_acceptance.py"))
    with pytest.raises(CodingLoopContractError, match="exactly one"):
        relocate_acceptance_argv(
            canonical_argv=("-q", "relative.py"),
            canonical_task_root=canonical,
            shadow_task_root=shadow,
        )


def test_canary_guard_rejects_pilot():
    assert_canary_only("canary", ("canary",))
    with pytest.raises(CodingLoopContractError, match="pilot"):
        assert_canary_only("pilot", ("canary",))


def test_balanced_mode_orders():
    tasks = tuple(f"task-{index}" for index in range(6))
    orders = balanced_mode_orders(tasks, ("none", "observe", "dock"))
    assert len(orders) == 6
    for position in range(3):
        values = [order[position] for _, order in orders]
        assert values.count("none") == 2
        assert values.count("observe") == 2
        assert values.count("dock") == 2


def test_contract_payload_is_frozen_and_mode_blind():
    payload = contract_payload()
    assert payload["generation"]["do_sample"] is False
    assert payload["generation"]["num_beams"] == 1
    assert payload["prompt"]["mode_visible_to_prompt"] is False
    assert payload["action_schema"]["writable_relative_paths"] == ["solution.py"]
