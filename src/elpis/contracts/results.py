# elpis/contracts/results.py — §XII fail-closed stage results.
# Law (T-failopen): a REQUIRED stage with status FAILED cannot fold into a
# successful ExecutionResult; constructing OK-with-error raises.
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Sequence, TypeVar

P = TypeVar("P")


class StageStatus(str, Enum):
    OK = "ok"; FAILED = "failed"; SKIPPED = "skipped"
    FALLBACK = "fallback"; STANDIN = "standin"


class StageClass(str, Enum):
    REQUIRED = "required"; OPTIONAL_FALLBACK = "optional_fallback"
    OPTIONAL_TELEMETRY = "optional_telemetry"; EXPERIMENTAL = "experimental"


class RunStatus(str, Enum):
    VERIFIED = "verified"; UNVERIFIED = "unverified"
    FAILED = "failed"; ABORTED = "aborted"


@dataclass(frozen=True, slots=True)
class StageError:
    kind: str; message: str; stage: str


@dataclass(frozen=True, slots=True)
class StageEvidence:
    items: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class StageResult(Generic[P]):
    stage: str
    stage_class: StageClass
    status: StageStatus
    output: P | None
    evidence: StageEvidence = StageEvidence()
    error: StageError | None = None
    reason_code: str = ""

    def __post_init__(self):
        if self.status is StageStatus.OK and self.error is not None:
            raise ValueError("OK result cannot carry an error")
        if self.status is StageStatus.FAILED and self.error is None:
            raise ValueError("FAILED result must carry a typed error")
        if self.stage_class is StageClass.REQUIRED \
                and self.status is StageStatus.STANDIN:
            raise ValueError("REQUIRED stage may never run a stand-in")


@dataclass(frozen=True, slots=True)
class ExecutionResult(Generic[P]):
    status: RunStatus
    final: P | None
    stages: tuple[StageResult, ...] = ()
    reason: str = ""


def fold_stages(stages: Sequence[StageResult], final=None) -> ExecutionResult:
    for s in stages:
        if s.stage_class is StageClass.REQUIRED and s.status in (
                StageStatus.FAILED, StageStatus.SKIPPED):
            return ExecutionResult(RunStatus.FAILED, None, tuple(stages),
                                   reason=f"required stage {s.stage}: {s.status.value}")
    return ExecutionResult(RunStatus.VERIFIED if final is not None
                           else RunStatus.UNVERIFIED, final, tuple(stages))
