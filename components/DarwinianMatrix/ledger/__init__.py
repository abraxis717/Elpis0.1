"""Deterministic records and lazily loaded episode archives.

The archive layer imports controller.episode. Importing it eagerly here would
create this cycle:

controller.episode
→ ledger.records
→ ledger package initializer
→ ledger.episode_archive
→ controller.episode

Record primitives remain eager. Archive interfaces are loaded only when they
are explicitly requested.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from .records import (
    GENESIS_RECORD_DIGEST,
    EcologyFrameRecord,
    build_frame_record,
    read_jsonl_records,
    verify_record_chain,
    write_jsonl_record,
)


_ARCHIVE_EXPORTS = frozenset(
    {
        "ArchivedEpisodeAttempt",
        "EpisodeArchive",
        "EpisodeArchiveReplayResult",
        "EpisodeAttemptCapture",
        "build_episode_archive",
        "load_episode_archive",
        "replay_episode_archive",
        "write_episode_archive",
    }
)


if TYPE_CHECKING:
    from .episode_archive import (
        ArchivedEpisodeAttempt,
        EpisodeArchive,
        EpisodeArchiveReplayResult,
        EpisodeAttemptCapture,
        build_episode_archive,
        load_episode_archive,
        replay_episode_archive,
        write_episode_archive,
    )


def __getattr__(name: str):
    if name in _ARCHIVE_EXPORTS:
        module = import_module(
            ".episode_archive",
            __name__,
        )
        value = getattr(module, name)
        globals()[name] = value
        return value

    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


def __dir__() -> list[str]:
    return sorted(
        set(globals())
        | set(__all__)
    )


__all__ = (
    "GENESIS_RECORD_DIGEST",
    "ArchivedEpisodeAttempt",
    "EcologyFrameRecord",
    "EpisodeArchive",
    "EpisodeArchiveReplayResult",
    "EpisodeAttemptCapture",
    "build_episode_archive",
    "build_frame_record",
    "load_episode_archive",
    "read_jsonl_records",
    "replay_episode_archive",
    "verify_record_chain",
    "write_episode_archive",
    "write_jsonl_record",
)
