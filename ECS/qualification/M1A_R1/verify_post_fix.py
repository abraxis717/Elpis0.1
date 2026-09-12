"""M1A-R1 — post-fix verification of the repaired behavior.

Runs against the FIXED M1A-R1 implementation and demonstrates that the
equivalent checks from the pre-fix reproduction now FAIL or yield DIFFERENT
roots, as required by review item 16:

  D1. The entity-facing API has NO sender parameter: an arbitrary caller
      CANNOT select sender=B. (The old Kernel.propose is gone.)
  D2. Mutating next_founding_index CHANGES the state root.
  D3. Different mailbox capacities yield DIFFERENT state roots.
  D4. Mutating the logical clock CHANGES the state root.

Output is a deterministic JSON evidence record.
"""
from __future__ import annotations

import inspect
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
from elpis_ecs.port import EntityPort  # noqa: E402
from elpis_ecs.replay import KernelState  # noqa: E402
from elpis_ecs.persistence import genesis_descriptor_digest  # noqa: E402


def _genesis():
    return genesis_descriptor_digest("ecs-m1a-genesis")


def d1_sender_no_longer_selectable():
    """The entity-facing API has no sender parameter; the old propose is gone."""
    # The old defective API is removed.
    old_propose_gone = not hasattr(Kernel, "propose")
    # The entity-facing propose has no sender parameter.
    params = list(inspect.signature(EntityPort.propose).parameters)
    no_sender_param = not any("sender" in p for p in params)
    # Demonstrate: an A-bound port can only attribute A.
    with tempfile.TemporaryDirectory() as d:
        k = Kernel(d).open()
        a = k.found_entity("alpha")
        b = k.found_entity("beta")
        k.run_until_quiescent()
        pa = k.entity_port(a)
        pa.propose(b, b"from-a")
        ev = [e for e in k.events() if e["event_kind"] == "MESSAGE_ENQUEUED"][0]
        sender = ev["payload"]["envelope"]["sender_entity_id"]
        k.close()
    return {
        "defect": "D1_sender_attribution_now_kernel_owned",
        "old_kernel_propose_removed": old_propose_gone,
        "entity_facing_propose_params": params,
        "no_sender_parameter": no_sender_param,
        "a_bound_port_attributed_to": sender,
        "attributed_to_a": sender == a,
        "conclusion": (
            "The entity-facing API (EntityPort.propose) has NO sender "
            "parameter; the old Kernel.propose(sender, ...) is removed. An "
            "A-bound port can only attribute A. A caller cannot select "
            "sender=B."
        ),
    }


def d2_founding_index_now_in_root():
    g = _genesis()
    s = KernelState(genesis_digest=g)
    root_before = s.state_root_digest()
    s.next_founding_index = 99
    root_after = s.state_root_digest()
    return {
        "defect": "D2_next_founding_index_now_bound",
        "root_before": root_before,
        "root_after": root_after,
        "root_changed": root_before != root_after,
        "conclusion": (
            "Changing next_founding_index now CHANGES the state root "
            "(it is bound into the v2 root)."
        ),
    }


def d3_capacity_now_in_root():
    g = _genesis()
    s1 = KernelState(genesis_digest=g, mailbox_capacity=1)
    s2 = KernelState(genesis_digest=g, mailbox_capacity=64)
    r1 = s1.state_root_digest()
    r2 = s2.state_root_digest()
    return {
        "defect": "D3_mailbox_capacity_now_bound",
        "root_cap1": r1,
        "root_cap64": r2,
        "root_changed": r1 != r2,
        "conclusion": (
            "Two equivalent empty states with different mailbox_capacity "
            "(1 vs 64) now produce DIFFERENT state roots."
        ),
    }


def d4_clock_now_in_root():
    g = _genesis()
    s = KernelState(genesis_digest=g)
    root_before = s.state_root_digest()
    s.logical_clock = 42
    root_after = s.state_root_digest()
    return {
        "defect": "D4_logical_clock_now_bound",
        "root_before": root_before,
        "root_after": root_after,
        "root_changed": root_before != root_after,
        "conclusion": (
            "Changing the logical clock now CHANGES the state root (the "
            "clock is part of the v2 root)."
        ),
    }


def main():
    evidence = {
        "title": "M1A-R1 post-fix verification",
        "note": "Run against the FIXED M1A-R1. The equivalent pre-fix checks "
                "now fail or yield different roots.",
        "D1": d1_sender_no_longer_selectable(),
        "D2": d2_founding_index_now_in_root(),
        "D3": d3_capacity_now_in_root(),
        "D4": d4_clock_now_in_root(),
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
