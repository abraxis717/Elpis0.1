"""Tests for CLI interface."""

import json
import os
import sys
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CONFIG = os.path.join(ROOT, "fixtures", "source_config.json")
CLI_ENTRYPOINT = os.path.join(ROOT, "src", "elpis_grid81_promotion_planner", "cli.py")


def _cli_command(args):
    cmd = [sys.executable, "-m", "elpis_grid81_promotion_planner.cli"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, env={
        **os.environ,
        "PYTHONPATH": os.path.join(ROOT, "src"),
    })
    return result


def test_cli_help():
    r = _cli_command(["--help"])
    assert r.returncode == 0
    assert "g53e-plan" in r.stdout.lower() or "usage" in r.stdout.lower()


def test_cli_unknown_command():
    r = _cli_command(["nonexistent-command"])
    assert r.returncode != 0


def test_cli_census():
    r = _cli_command(["census", "--source-config", CONFIG])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "g53b1" in data
    assert "g53c" in data
    assert "g53d" in data
    assert "chain_digest" in data


def test_cli_gates():
    r = _cli_command(["gates", "--source-config", CONFIG])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert len(data) == 20
    for gate in data:
        assert "gate_id" in gate
        assert "passed" in gate
        assert "gate_digest" in gate


def test_cli_decide():
    r = _cli_command(["decide", "--source-config", CONFIG])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["decision"] in (
        "READY_FOR_CANONICAL_REVIEW",
        "NOT_READY_FOR_CANONICAL_REVIEW",
    )
    assert "decision_digest" in data


def test_cli_render_plan():
    r = _cli_command(["render-plan", "--source-config", CONFIG])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    if data.get("plan"):
        assert data["plan"]["executable"] is False
        assert data["plan"]["self_applying"] is False
        assert data["plan"]["authoritative"] is False
        assert data["plan"]["canonical_write_permitted"] is False


def test_cli_authority():
    r = _cli_command(["authority", "--source-config", CONFIG])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["planner_authoritative_for_application"] is False
    assert data["canonical_write_permitted"] is False
    assert data["qubo_touched"] is False


def test_cli_deterministic_output():
    r1 = _cli_command(["decide", "--source-config", CONFIG])
    r2 = _cli_command(["decide", "--source-config", CONFIG])
    assert r1.stdout == r2.stdout


def test_cli_verify_chain():
    r = _cli_command(["verify-chain", "--source-config", CONFIG])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "chain_digest" in data
    assert "chain_version" in data
