"""P14.2b bounded coding-loop contract.

The contract is deliberately narrower than a general coding agent. A model may
return exactly one JSON action: replace the complete ``solution.py`` file or
report a blocker. Verification commands and writable paths come only from the
frozen P14.2a registry. Mode is not represented in the prompt.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any, Callable, Literal, Mapping, Sequence

from .digest import canonical_digest


ACTION_SCHEMA = "elpis.nanbeige42.coding-action.v1"
RECEIPT_SCHEMA = "elpis.nanbeige42.patch-receipt.v1"
SYSTEM_PROMPT = """You are Nanbeige operating under the Elpis bounded coding ABI.
Return exactly one JSON object and no other text.
You may either replace solution.py with complete UTF-8 source, or report a blocker.
Do not emit Markdown, shell commands, diffs, explanations, additional files, or network requests.
For replacement use exactly: {\"schema\":\"elpis.nanbeige42.coding-action.v1\",\"action\":\"replace_file\",\"path\":\"solution.py\",\"preimage_sha256\":\"sha256:<64 lowercase hex>\",\"content\":\"<complete file>\"}.
For a blocker use exactly: {\"schema\":\"elpis.nanbeige42.coding-action.v1\",\"action\":\"report_blocker\",\"reason\":\"<bounded reason>\"}.
"""
USER_TEMPLATE = """TASK\n{objective}\n\nCONSTRAINTS\n{constraints}\n\nCURRENT solution.py SHA-256\n{preimage_sha256}\n\nCURRENT solution.py\n<solution.py>\n{solution}\n</solution.py>\n\nVERIFICATION FEEDBACK\n{feedback}\n"""


class CodingLoopContractError(RuntimeError):
    """Raised when a bounded coding-loop invariant is violated."""


class ActionKind(str, Enum):
    REPLACE_FILE = "replace_file"
    REPORT_BLOCKER = "report_blocker"


@dataclass(frozen=True, slots=True)
class GenerationContract:
    schema: Literal["elpis.nanbeige42.generation-contract.v1"]
    do_sample: bool
    num_beams: int
    max_input_tokens: int
    max_new_tokens: int
    use_cache: bool
    truncation_rule: Literal["hard_fail_no_truncation"]
    stop_sequences: tuple[str, ...]
    generation_contract_digest: str = ""

    def __post_init__(self) -> None:
        if self.do_sample:
            raise CodingLoopContractError("sampling is forbidden")
        if self.num_beams != 1:
            raise CodingLoopContractError("num_beams must equal one")
        if not 256 <= self.max_input_tokens <= 32768:
            raise CodingLoopContractError("max_input_tokens outside bounds")
        if not 64 <= self.max_new_tokens <= 8192:
            raise CodingLoopContractError("max_new_tokens outside bounds")
        if not self.use_cache:
            raise CodingLoopContractError("use_cache must remain enabled")

    def with_digest(self) -> "GenerationContract":
        return GenerationContract(
            schema=self.schema,
            do_sample=self.do_sample,
            num_beams=self.num_beams,
            max_input_tokens=self.max_input_tokens,
            max_new_tokens=self.max_new_tokens,
            use_cache=self.use_cache,
            truncation_rule=self.truncation_rule,
            stop_sequences=self.stop_sequences,
            generation_contract_digest=canonical_digest(
                self, digest_field="generation_contract_digest"
            ),
        )


@dataclass(frozen=True, slots=True)
class CodingAction:
    schema: Literal["elpis.nanbeige42.coding-action.v1"]
    action: ActionKind
    path: str | None = None
    preimage_sha256: str | None = None
    content: str | None = None
    reason: str | None = None
    action_digest: str = ""

    def __post_init__(self) -> None:
        if self.schema != ACTION_SCHEMA:
            raise CodingLoopContractError("action schema mismatch")
        if self.action is ActionKind.REPLACE_FILE:
            if self.path != "solution.py":
                raise CodingLoopContractError("replace_file path must equal solution.py")
            _validate_sha256(self.preimage_sha256, "preimage_sha256")
            if self.content is None:
                raise CodingLoopContractError("replace_file content absent")
            if self.reason is not None:
                raise CodingLoopContractError("replace_file cannot include reason")
        elif self.action is ActionKind.REPORT_BLOCKER:
            if any(value is not None for value in (self.path, self.preimage_sha256, self.content)):
                raise CodingLoopContractError("report_blocker cannot include patch fields")
            if self.reason is None or not self.reason.strip():
                raise CodingLoopContractError("blocker reason absent")
            if len(self.reason.encode("utf-8")) > 1024:
                raise CodingLoopContractError("blocker reason exceeds 1024 bytes")
        else:  # pragma: no cover - Enum prevents this
            raise CodingLoopContractError("unsupported action")

    def with_digest(self) -> "CodingAction":
        return CodingAction(
            schema=self.schema,
            action=self.action,
            path=self.path,
            preimage_sha256=self.preimage_sha256,
            content=self.content,
            reason=self.reason,
            action_digest=canonical_digest(self, digest_field="action_digest"),
        )


@dataclass(frozen=True, slots=True)
class PatchReceipt:
    schema: Literal["elpis.nanbeige42.patch-receipt.v1"]
    task_id: str
    run_id: str
    tick_index: int
    action_digest: str
    target_relative_path: str | None
    preimage_sha256: str | None
    proposed_sha256: str | None
    acceptance_exit_code: int | None
    accepted: bool
    rollback_performed: bool
    blocker_reported: bool
    acceptance_output_digest: str | None
    receipt_digest: str = ""

    def with_digest(self) -> "PatchReceipt":
        return PatchReceipt(
            schema=self.schema,
            task_id=self.task_id,
            run_id=self.run_id,
            tick_index=self.tick_index,
            action_digest=self.action_digest,
            target_relative_path=self.target_relative_path,
            preimage_sha256=self.preimage_sha256,
            proposed_sha256=self.proposed_sha256,
            acceptance_exit_code=self.acceptance_exit_code,
            accepted=self.accepted,
            rollback_performed=self.rollback_performed,
            blocker_reported=self.blocker_reported,
            acceptance_output_digest=self.acceptance_output_digest,
            receipt_digest=canonical_digest(self, digest_field="receipt_digest"),
        )


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def _validate_sha256(value: str | None, field: str) -> None:
    if value is None or len(value) != 71 or not value.startswith("sha256:"):
        raise CodingLoopContractError(f"{field} must be sha256-prefixed")
    suffix = value[7:]
    if suffix.lower() != suffix or any(c not in "0123456789abcdef" for c in suffix):
        raise CodingLoopContractError(f"{field} must use lowercase hexadecimal")


def parse_exact_action(text: str, *, maximum_patch_bytes: int) -> CodingAction:
    """Parse exactly one JSON object with an exact key set.

    Markdown fences, leading prose, trailing prose, and a second JSON value are
    rejected. ``maximum_patch_bytes`` is applied to UTF-8 bytes, not characters.
    """
    if not isinstance(text, str):
        raise CodingLoopContractError("model output must be text")
    stripped = text.strip()
    if not stripped or stripped.startswith("```"):
        raise CodingLoopContractError("model output must be one bare JSON object")
    decoder = json.JSONDecoder()
    try:
        value, end = decoder.raw_decode(stripped)
    except json.JSONDecodeError as exc:
        raise CodingLoopContractError(f"invalid action JSON: {exc.msg}") from exc
    if stripped[end:].strip():
        raise CodingLoopContractError("trailing content after action JSON")
    if not isinstance(value, dict):
        raise CodingLoopContractError("action JSON must be an object")
    if any(not isinstance(key, str) for key in value):
        raise CodingLoopContractError("action keys must be strings")
    if value.get("schema") != ACTION_SCHEMA:
        raise CodingLoopContractError("action schema mismatch")
    try:
        kind = ActionKind(value.get("action"))
    except (TypeError, ValueError) as exc:
        raise CodingLoopContractError("unsupported action kind") from exc

    if kind is ActionKind.REPLACE_FILE:
        expected = {"schema", "action", "path", "preimage_sha256", "content"}
        if set(value) != expected:
            raise CodingLoopContractError("replace_file key set mismatch")
        content = value["content"]
        if not isinstance(content, str):
            raise CodingLoopContractError("replace_file content must be text")
        if len(content.encode("utf-8")) > maximum_patch_bytes:
            raise CodingLoopContractError("replacement exceeds maximum_patch_bytes")
        action = CodingAction(
            schema=ACTION_SCHEMA,
            action=kind,
            path=value["path"],
            preimage_sha256=value["preimage_sha256"],
            content=content,
        )
    else:
        expected = {"schema", "action", "reason"}
        if set(value) != expected:
            raise CodingLoopContractError("report_blocker key set mismatch")
        if not isinstance(value["reason"], str):
            raise CodingLoopContractError("blocker reason must be text")
        action = CodingAction(
            schema=ACTION_SCHEMA,
            action=kind,
            reason=value["reason"],
        )
    return action.with_digest()


def render_prompt(
    *, objective: str, constraints: Sequence[str], solution: str, feedback: str
) -> tuple[str, str]:
    """Render the mode-independent prompt and return prompt plus digest."""
    if not objective.strip():
        raise CodingLoopContractError("objective absent")
    if not constraints:
        raise CodingLoopContractError("constraints absent")
    normalized_feedback = feedback if feedback.strip() else "NONE"
    prompt = SYSTEM_PROMPT + "\n" + USER_TEMPLATE.format(
        objective=objective.strip(),
        constraints="\n".join(f"- {item}" for item in constraints),
        preimage_sha256=sha256_text(solution),
        solution=solution,
        feedback=normalized_feedback,
    )
    return prompt, sha256_text(prompt)


def validate_relative_target(path: str) -> None:
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or str(candidate) != "solution.py":
        raise CodingLoopContractError("only relative solution.py is writable")
    if ".." in candidate.parts:
        raise CodingLoopContractError("parent traversal forbidden")


def assert_regular_non_symlink(path: Path) -> None:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise CodingLoopContractError("target must be a regular non-symlink file")
    parent = path.parent
    while True:
        pinfo = parent.lstat()
        if stat.S_ISLNK(pinfo.st_mode) or not stat.S_ISDIR(pinfo.st_mode):
            raise CodingLoopContractError("workspace ancestry must be non-symlink directories")
        if parent == parent.parent:
            break
        parent = parent.parent


def execute_action_atomic(
    *,
    task_id: str,
    run_id: str,
    tick_index: int,
    workspace_root: Path,
    action: CodingAction,
    maximum_patch_bytes: int,
    acceptance_runner: Callable[[], tuple[int, str]],
) -> PatchReceipt:
    """Apply a bounded action and commit only after frozen verification passes."""
    if action.action is ActionKind.REPORT_BLOCKER:
        return PatchReceipt(
            schema=RECEIPT_SCHEMA,
            task_id=task_id,
            run_id=run_id,
            tick_index=tick_index,
            action_digest=action.action_digest,
            target_relative_path=None,
            preimage_sha256=None,
            proposed_sha256=None,
            acceptance_exit_code=None,
            accepted=False,
            rollback_performed=False,
            blocker_reported=True,
            acceptance_output_digest=None,
        ).with_digest()

    assert action.content is not None
    assert action.preimage_sha256 is not None
    validate_relative_target(action.path or "")
    proposed = action.content.encode("utf-8")
    if len(proposed) > maximum_patch_bytes:
        raise CodingLoopContractError("replacement exceeds maximum_patch_bytes")

    root = workspace_root.resolve(strict=True)
    target = root / "solution.py"
    assert_regular_non_symlink(target)
    before = target.read_bytes()
    before_digest = sha256_bytes(before)
    if before_digest != action.preimage_sha256:
        raise CodingLoopContractError("stale workspace preimage")

    stage = root / ".elpis_solution.py.stage"
    backup = root / ".elpis_solution.py.rollback"
    for ephemeral in (stage, backup):
        if ephemeral.exists() or ephemeral.is_symlink():
            raise CodingLoopContractError("executor ephemeral path already exists")

    proposed_digest = sha256_bytes(proposed)
    accepted = False
    rollback = False
    exit_code: int | None = None
    output = ""
    try:
        with stage.open("xb") as handle:
            handle.write(proposed)
            handle.flush()
            os.fsync(handle.fileno())
        with backup.open("xb") as handle:
            handle.write(before)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(stage, target)
        exit_code, output = acceptance_runner()
        if exit_code == 0:
            accepted = True
            backup.unlink()
        else:
            os.replace(backup, target)
            rollback = True
    except Exception:
        if backup.exists():
            os.replace(backup, target)
            rollback = True
        if stage.exists():
            stage.unlink()
        raise
    finally:
        if stage.exists():
            stage.unlink()
        if backup.exists():
            backup.unlink()

    return PatchReceipt(
        schema=RECEIPT_SCHEMA,
        task_id=task_id,
        run_id=run_id,
        tick_index=tick_index,
        action_digest=action.action_digest,
        target_relative_path="solution.py",
        preimage_sha256=before_digest,
        proposed_sha256=proposed_digest,
        acceptance_exit_code=exit_code,
        accepted=accepted,
        rollback_performed=rollback,
        blocker_reported=False,
        acceptance_output_digest=sha256_text(output),
    ).with_digest()


def relocate_acceptance_argv(
    *,
    canonical_argv: Sequence[str],
    canonical_task_root: Path,
    shadow_task_root: Path,
) -> tuple[str, ...]:
    """Translate exactly one frozen acceptance path into an isolated shadow root."""
    canonical_prefix = canonical_task_root.resolve(strict=False)
    shadow_prefix = shadow_task_root.resolve(strict=False)
    relocated: list[str] = []
    translated = 0
    for argument in canonical_argv:
        candidate = Path(argument)
        if candidate.is_absolute():
            try:
                relative = candidate.relative_to(canonical_prefix)
            except ValueError:
                relocated.append(argument)
                continue
            relocated.append(str(shadow_prefix / relative))
            translated += 1
        else:
            relocated.append(argument)
    if translated != 1:
        raise CodingLoopContractError("acceptance relocation must translate exactly one path")
    return tuple(relocated)


def assert_canary_only(task_id: str, canary_ids: Sequence[str]) -> None:
    if task_id not in set(canary_ids):
        raise CodingLoopContractError("pilot or unregistered task access forbidden")


def balanced_mode_orders(
    task_ids: Sequence[str], modes: Sequence[str]
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if len(modes) != 3 or len(set(modes)) != 3:
        raise CodingLoopContractError("exactly three distinct modes required")
    result = []
    for index, task_id in enumerate(task_ids):
        offset = index % len(modes)
        order = tuple(modes[(offset + j) % len(modes)] for j in range(len(modes)))
        result.append((task_id, order))
    return tuple(result)


def contract_payload() -> Mapping[str, Any]:
    generation = GenerationContract(
        schema="elpis.nanbeige42.generation-contract.v1",
        do_sample=False,
        num_beams=1,
        max_input_tokens=4096,
        max_new_tokens=2048,
        use_cache=True,
        truncation_rule="hard_fail_no_truncation",
        stop_sequences=(),
    ).with_digest()
    action_schema = {
        "schema": "elpis.nanbeige42.action-schema-manifest.v1",
        "output_container": "one_bare_json_object",
        "allowed_actions": [ActionKind.REPLACE_FILE.value, ActionKind.REPORT_BLOCKER.value],
        "replace_file_exact_keys": [
            "schema", "action", "path", "preimage_sha256", "content"
        ],
        "report_blocker_exact_keys": ["schema", "action", "reason"],
        "writable_relative_paths": ["solution.py"],
        "markdown_allowed": False,
        "multiple_actions_allowed": False,
        "action_schema_digest": "",
    }
    action_schema["action_schema_digest"] = canonical_digest(
        action_schema, digest_field="action_schema_digest"
    )
    prompt = {
        "schema": "elpis.nanbeige42.prompt-contract.v1",
        "system_prompt": SYSTEM_PROMPT,
        "user_template": USER_TEMPLATE,
        "mode_visible_to_prompt": False,
        "feedback_source": "exact_bounded_acceptance_output",
        "system_prompt_digest": sha256_text(SYSTEM_PROMPT),
        "user_template_digest": sha256_text(USER_TEMPLATE),
        "prompt_contract_digest": "",
    }
    prompt["prompt_contract_digest"] = canonical_digest(
        prompt, digest_field="prompt_contract_digest"
    )
    return {
        "generation": asdict(generation),
        "action_schema": action_schema,
        "prompt": prompt,
    }
