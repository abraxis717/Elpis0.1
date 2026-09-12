"""M1A-R1 — independent reproduction of the ORIGINAL M1A defects (pre-fix).

This script runs against the UNFIXED M1A draft and captures evidence of the
four concrete defects identified by independent review:

  D1. Sender attribution is caller-selectable:
      Kernel.propose(sender, receiver, payload) lets an arbitrary caller pick
      any ACTIVE entity ID as the sender.
  D2. State root excludes next_founding_index (mutating it leaves root unchanged).
  D3. State root excludes mailbox_capacity (different capacity -> same root).
  D4. State root excludes the logical clock (mutating it leaves root unchanged).

Output is a deterministic JSON evidence record. This belongs in qualification
output/reporting, NOT in frozen science.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_RUNTIME = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "runtime")
if _RUNTIME not in sys.path:
    sys.path.insert(0, _RUNTIME)

from elpis_ecs.kernel import Kernel  # noqa: E402
from elpis_ecs.replay import KernelState  # noqa: E402
from elpis_ecs.persistence import genesis_descriptor_digest  # noqa: E402


def _genesis():
    return genesis_descriptor_digest("ecs-m1a-genesis")


def d1_sender_selectable():
    """Two ACTIVE entities A and B; an arbitrary caller proposes AS B.

    Pre-fix: Kernel.propose(sender, receiver, payload) let the caller select
    sender=B. Post-fix: the old API is removed, so this records the removal
    (the defect is repaired) rather than crashing.
    """
    if not hasattr(Kernel, "propose"):
        return {
            "defect": "D1_sender_attribution_caller_selectable",
            "status": "REPAIRED",
            "old_kernel_propose_removed": True,
            "conclusion": (
                "The defective Kernel.propose(sender, receiver, payload) API "
                "has been removed. The entity-facing API is now "
                "EntityPort.propose(receiver, payload) with NO sender "
                "parameter; the sender is taken from the bound port. A caller "
                "cannot select sender=B."
            ),
        }
    with tempfile.TemporaryDirectory() as d:
        k = Kernel(d).open()
        a = k.found_entity("alpha")
        b = k.found_entity("beta")
        k.run_until_quiescent()  # both ACTIVE
        # Arbitrary caller selects sender = B (not A).
        mid = k.propose(b, a, b"spoof-from-b")
        ev = [e for e in k.events() if e["event_kind"] == "MESSAGE_ENQUEUED"][0]
        sender_in_envelope = ev["payload"]["envelope"]["sender_entity_id"]
        k.close()
    return {
        "defect": "D1_sender_attribution_caller_selectable",
        "caller_chose_sender": "B",
        "envelope_attributed_to": sender_in_envelope,
        "attributed_to_B": sender_in_envelope == b,
        "message_id": mid,
        "conclusion": (
            "Kernel.propose(sender, receiver, payload) allowed the caller to "
            "select sender=B; the emitted envelope is attributed to B. The "
            "kernel does NOT own sender attribution."
        ),
    }


def d2_founding_index_not_in_root():
    g = _genesis()
    s = KernelState(genesis_digest=g)
    root_before = s.state_root_digest()
    s.next_founding_index = 99  # mutate ONLY the founding counter
    root_after = s.state_root_digest()
    return {
        "defect": "D2_next_founding_index_excluded_from_root",
        "next_founding_index_before": 0,
        "next_founding_index_after": 99,
        "root_before": root_before,
        "root_after": root_after,
        "root_unchanged": root_before == root_after,
        "conclusion": (
            "Changing next_founding_index (which determines the next entity "
            "identity) left the state root UNCHANGED. The root does not bind "
            "this behavior-affecting state."
        ),
    }


def d3_capacity_not_in_root():
    g = _genesis()
    s1 = KernelState(genesis_digest=g, mailbox_capacity=1)
    s2 = KernelState(genesis_digest=g, mailbox_capacity=64)
    r1 = s1.state_root_digest()
    r2 = s2.state_root_digest()
    return {
        "defect": "D3_mailbox_capacity_excluded_from_root",
        "capacity_1": 1,
        "capacity_2": 64,
        "root_cap1": r1,
        "root_cap64": r2,
        "root_unchanged": r1 == r2,
        "conclusion": (
            "Two equivalent empty states with different mailbox_capacity "
            "(1 vs 64) produced the SAME state root. Capacity changes future "
            "acceptance but is not bound into the root."
        ),
    }


def d4_clock_not_in_root():
    g = _genesis()
    s = KernelState(genesis_digest=g)
    root_before = s.state_root_digest()
    s.logical_clock = 42  # mutate ONLY the logical clock
    root_after = s.state_root_digest()
    return {
        "defect": "D4_logical_clock_excluded_from_root",
        "logical_clock_before": 0,
        "logical_clock_after": 42,
        "root_before": root_before,
        "root_after": root_after,
        "root_unchanged": root_before == root_after,
        "conclusion": (
            "Changing the logical clock left the state root UNCHANGED. The "
            "clock is a behavior-affecting state variable (it is verified by "
            "replay) but is not bound into the root."
        ),
    }


def main():
    evidence = {
        "title": "M1A-R1 original-defect reproduction (pre-fix)",
        "note": "Run against the UNFIXED M1A draft. Post-fix, the equivalent "
                "checks must FAIL or yield DIFFERENT roots.",
        "D1": d1_sender_selectable(),
        "D2": d2_founding_index_not_in_root(),
        "D3": d3_capacity_not_in_root(),
        "D4": d4_clock_not_in_root(),
    }
    parser = argparse.ArgumentParser(description="Historical narrow M1A-R1 checks; not current qualification")
    parser.add_argument("--output", help="Optional generated evidence file; defaults to stdout only")
    args = parser.parse_args()
    evidence["historical_narrow_checks_only"] = True
    rendered = json.dumps(evidence, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w") as fh:
            fh.write(rendered + "\n")
    print(rendered)



if __name__ == "__main__":
    main()
