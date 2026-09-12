"""Run repository tests and independent deterministic process qualification.

Generated evidence is written only to the explicitly supplied output directory.
It is descriptive evidence, never semantic authority.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = Path(__file__).with_name("scenario.py")


def determinism(work, interpreter=sys.executable):
    results = []
    cases = []
    for seed in ["0", "1", "42", "123456789", "random"]:
        for restart in [0, 1, 3, 7]:
            directory = work / f"history-{seed}-{restart}"
            env = dict(os.environ, PYTHONHASHSEED=seed)
            build = subprocess.run([interpreter, str(SCENARIO), str(directory),
                                    "--restart-every", str(restart)],
                                   capture_output=True, text=True, env=env, check=True, timeout=60)
            live = json.loads(build.stdout)
            fresh = subprocess.run([interpreter, str(SCENARIO), str(directory), "--replay"],
                                   capture_output=True, text=True, env=env, check=True, timeout=60)
            assert json.loads(fresh.stdout) == live
            results.append(live)
            cases.append({"hash_seed": seed, "restart_every_operations": restart,
                          "fresh_process_equal": True})
    assert all(value == results[0] for value in results)
    return {"cases": cases, "all_canonical_outputs_equal": True,
            "independent_histories": len(results), "fresh_replays": len(results),
            "event_count": results[0]["snapshot"]["event_count"],
            "state_root": results[0]["snapshot"]["state_root_digest"],
            "event_bytes_sha256": results[0]["event_bytes_sha256"],
            "full_projection_digest": results[0]["full_projection_digest"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--python", action="append", default=[], help="Additional Python executable for cross-version qualification")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    junit = out / "m1a-tests.xml"
    command = [sys.executable, "-m", "pytest", "ECS/tests", "-o", "addopts=", "-q",
               "--tb=short", f"--junitxml={junit}"]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    (out / "m1a-tests.txt").write_text(run.stdout + run.stderr)
    if run.returncode:
        print(run.stdout)
        raise SystemExit(run.returncode)
    suites = ET.parse(junit).getroot().findall("testsuite")
    counts = {field: sum(int(s.get(field, 0)) for s in suites)
              for field in ["tests", "failures", "errors", "skipped"]}
    versions = []
    for interpreter in [sys.executable, *args.python]:
        version = subprocess.check_output([interpreter, "--version"], text=True).strip()
        with tempfile.TemporaryDirectory(dir=out) as temporary:
            deterministic = determinism(Path(temporary), interpreter)
        versions.append({"python": version, **deterministic})
    assert all(v["state_root"] == versions[0]["state_root"] and
               v["event_bytes_sha256"] == versions[0]["event_bytes_sha256"] and
               v["full_projection_digest"] == versions[0]["full_projection_digest"]
               for v in versions)
    evidence = {"schema": "ecs.integration.evidence.v1", "authority": False,
                "python": sys.version.split()[0], "tests": counts,
                "determinism": versions, "cross_version_equal": True}
    (out / "qualification.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
