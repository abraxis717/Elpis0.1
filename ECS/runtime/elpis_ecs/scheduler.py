"""Elpis ECS M1A — deterministic scheduler over a finite ready set.

The scheduler has NO semantic admission authority. It only orders a finite
ready set deterministically. No unspecified iteration / dictionary / set order
may affect execution: the ordering tuple is fully specified below.

Ordering tuple (total, deterministic)
-------------------------------------
A ready item is a tuple:
    (ready_rank, entity_id, mailbox_index, message_id)

  * ready_rank    — 0 for ENQUEUE-ready (message available to process),
                    1 for ACTIVATE-ready (entity may advance lifecycle).
                    Lower rank runs first.
  * entity_id     — lexicographic (byte) order of the entity ID string.
  * mailbox_index — 0-based FIFO position within the receiver mailbox.
  * message_id    — lexicographic tie-break (deterministic; the envelope is
                    already uniquely identified by (sender, sequence)).

The scheduler sorts the ready set by this tuple and returns it in that order.
For M1A this is simple deterministic fairness (FIFO per mailbox, entity-ID
order across mailboxes). No WFQ, no Resource Accounting, no Health behavior —
those subsystems are deferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .errors import SchedulerError

# Ready ranks (lower runs first).
RANK_ENQUEUE = 0
RANK_ACTIVATE = 1


@dataclass(frozen=True)
class ReadyItem:
    """One schedulable unit of work."""

    rank: int
    entity_id: str
    mailbox_index: int
    message_id: str
    kind: str  # "PROCESS_MESSAGE" | "LIFECYCLE"
    ref: Any  # opaque reference resolved by the kernel

    def ordering_key(self) -> tuple:
        return (self.rank, self.entity_id, self.mailbox_index, self.message_id)


def order_ready(items: Iterable[ReadyItem]) -> list[ReadyItem]:
    """Return the ready set sorted by the fully-specified ordering tuple.

    Deterministic: no reliance on dict/set iteration order. Ties are broken
    completely by the ordering tuple, so the result is a total order.
    """
    items = list(items)
    # Stable sort on the total ordering key; the key is a total order so the
    # result is unique regardless of input order.
    keys = [item.ordering_key() for item in items]
    if len(set(keys)) != len(keys):
        raise SchedulerError("AMBIGUOUS_READY_ORDER")
    return sorted(items, key=lambda it: it.ordering_key())


def run_deterministic(
    ready: Iterable[ReadyItem],
    step: Callable[[ReadyItem], None],
    max_steps: int | None = None,
) -> int:
    """Execute the ready set in deterministic order.

    ``step`` is invoked for each item in ordering-tuple order. ``max_steps`` is
    a static kernel bound (M1A allows static bounds). Returns the number of
    steps executed. No semantic admission: every provided ready item runs.
    """
    ordered = order_ready(ready)
    count = 0
    for item in ordered:
        if max_steps is not None and count >= max_steps:
            break
        step(item)
        count += 1
    return count
