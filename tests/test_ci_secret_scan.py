#!/usr/bin/env python3
"""Tests for the CI secret scanner — positive and negative fixtures."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from tools.ci_secret_scan import scan_secrets, scan_private_paths, scan_binaries, run_scan


# ---------------------------------------------------------------------------
# Negative fixtures — these must NOT trigger any detector
# ---------------------------------------------------------------------------

NEGATIVE_PY = '''
def solve(task_id):
    # task-1 is a benign string, not a secret
    task_name = "task-1"
    token_count = 0
    token_record = {}
    tokenization = True
    sklearn_model = None
    # Variable names with 'secret' or 'password' in them are fine
    secret_module = "my_module"
    password_hash = "abc123"
    # Short values should not match
    password = "ab"
    secret = "xyz"
'''

NEGATIVE_JSON = '''
{
    "task": "task-1",
    "token": "some_token",
    "description": "This is a test task-1"
}
'''

# ---------------------------------------------------------------------------
# Positive fixtures — these MUST trigger detectors
# ---------------------------------------------------------------------------

POSITIVE_PRIVATE_KEY = '''
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA...
'''

POSITIVE_GITHUB_PAT = '''
token = "ghp_abcdefghijklmnopqrstuvwxyz0123456789AB"
'''

POSITIVE_GITHUB_FINE_PAT = '''
token = "github_pat_1234567890abcdefghijklmnopqrstuv"
'''

POSITIVE_OPENAI_KEY = '''
api_key = "sk-abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQR"
'''

POSITIVE_AWS_KEY = '''
aws_key = "AKIAIOSFODNN7EXAMPLE"
'''

POSITIVE_GOOGLE_KEY = '''
google_key = "AIzaSyA1234567890abcdefghijklmnopqrstuvwxyz"
'''

POSITIVE_BEARER = '''
headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkw"}
'''

POSITIVE_PASSWORD = '''
password = "super_secret_password_123"
'''

POSITIVE_SECRET = '''
secret_key = "a_long_secret_value_here_123"
'''

POSITIVE_PRIVATE_PATH_JSON = '''
{
    "canonical_root": "/mnt/primesauce/Elpis_Canon/Elpis",
    "build_dir": "/home/joe/projects/build"
}
'''

POSITIVE_PRIVATE_PATH_PY = '''
CANON = "/mnt/primesauce/Elpis_Canon/Elpis"
HOME = "/home/joe/some/path"
'''


def _write_fixture(tmp: Path, name: str, content: str) -> Path:
    f = tmp / name
    f.write_text(content, encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# Negative fixture tests — must produce zero findings
# ---------------------------------------------------------------------------

class TestNegativeFixtures:
    def test_benign_py_no_secrets(self, tmp_path):
        _write_fixture(tmp_path, "benign.py", NEGATIVE_PY)
        findings = scan_secrets(tmp_path)
        assert findings == [], f"False positive on benign .py: {findings}"

    def test_benign_json_no_secrets(self, tmp_path):
        _write_fixture(tmp_path, "benign.json", NEGATIVE_JSON)
        findings = scan_secrets(tmp_path)
        assert findings == [], f"False positive on benign .json: {findings}"

    def test_benign_py_no_private_paths(self, tmp_path):
        _write_fixture(tmp_path, "benign.py", NEGATIVE_PY)
        findings = scan_private_paths(tmp_path)
        assert findings == [], f"False positive on benign .py: {findings}"

    def test_task_string_does_not_match(self, tmp_path):
        content = 'task_id = "task-1"\n'
        _write_fixture(tmp_path, "task.py", content)
        findings = scan_secrets(tmp_path)
        assert len([f for f in findings if "OPENAI_KEY" in f]) == 0, \
            "'task-1' should not match OpenAI key pattern"


# ---------------------------------------------------------------------------
# Positive fixture tests — must each produce at least one finding
# ---------------------------------------------------------------------------

class TestPositiveFixtures:
    def test_private_key_detected(self, tmp_path):
        _write_fixture(tmp_path, "key.py", POSITIVE_PRIVATE_KEY)
        findings = scan_secrets(tmp_path)
        assert any("PRIVATE_KEY" in f for f in findings), f"No private key detection: {findings}"

    def test_github_pat_detected(self, tmp_path):
        _write_fixture(tmp_path, "pat.py", POSITIVE_GITHUB_PAT)
        findings = scan_secrets(tmp_path)
        assert any("GITHUB_PAT" in f for f in findings), f"No GitHub PAT detection: {findings}"

    def test_github_fine_pat_detected(self, tmp_path):
        _write_fixture(tmp_path, "fine_pat.py", POSITIVE_GITHUB_FINE_PAT)
        findings = scan_secrets(tmp_path)
        assert any("GITHUB_FINE_PAT" in f for f in findings), f"No fine-grained PAT detection: {findings}"

    def test_openai_key_detected(self, tmp_path):
        _write_fixture(tmp_path, "oa.py", POSITIVE_OPENAI_KEY)
        findings = scan_secrets(tmp_path)
        assert any("OPENAI_KEY" in f for f in findings), f"No OpenAI key detection: {findings}"

    def test_aws_key_detected(self, tmp_path):
        _write_fixture(tmp_path, "aws.py", POSITIVE_AWS_KEY)
        findings = scan_secrets(tmp_path)
        assert any("AWS_ACCESS_KEY" in f for f in findings), f"No AWS key detection: {findings}"

    def test_google_key_detected(self, tmp_path):
        _write_fixture(tmp_path, "google.py", POSITIVE_GOOGLE_KEY)
        findings = scan_secrets(tmp_path)
        assert any("GOOGLE_API_KEY" in f for f in findings), f"No Google key detection: {findings}"

    def test_bearer_token_detected(self, tmp_path):
        _write_fixture(tmp_path, "bearer.py", POSITIVE_BEARER)
        findings = scan_secrets(tmp_path)
        assert any("BEARER_TOKEN" in f for f in findings), f"No bearer token detection: {findings}"

    def test_password_detected(self, tmp_path):
        _write_fixture(tmp_path, "pass.py", POSITIVE_PASSWORD)
        findings = scan_secrets(tmp_path)
        assert any("PASSWORD" in f for f in findings), f"No password detection: {findings}"

    def test_secret_detected(self, tmp_path):
        _write_fixture(tmp_path, "sec.py", POSITIVE_SECRET)
        findings = scan_secrets(tmp_path)
        assert any("SECRET" in f for f in findings), f"No secret detection: {findings}"

    def test_private_path_mnt_detected(self, tmp_path):
        _write_fixture(tmp_path, "paths.json", POSITIVE_PRIVATE_PATH_JSON)
        findings = scan_private_paths(tmp_path)
        assert any("/mnt/primesauce" in f for f in findings), f"No /mnt/primesauce detection: {findings}"

    def test_private_path_home_detected(self, tmp_path):
        _write_fixture(tmp_path, "paths.py", POSITIVE_PRIVATE_PATH_PY)
        findings = scan_private_paths(tmp_path)
        assert any("/home/joe" in f for f in findings), f"No /home/joe detection: {findings}"


# ---------------------------------------------------------------------------
# Scanner self-test — scanner must not self-trigger
# ---------------------------------------------------------------------------

class TestScannerSelfCheck:
    def test_scanner_does_not_self_trigger(self):
        """The scanner file itself must not be flagged by the scanner."""
        scanner_path = Path(__file__).parent.parent / "tools" / "ci_secret_scan.py"
        if scanner_path.exists():
            # Create a temp dir with just the scanner file
            import shutil
            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td)
                dest = tmp / "ci_secret_scan.py"
                shutil.copy(str(scanner_path), str(dest))
                findings = scan_secrets(tmp)
                assert findings == [], \
                    f"Scanner self-triggers: {findings}"


# ---------------------------------------------------------------------------
# Binary artifact detection
# ---------------------------------------------------------------------------

class TestBinaryScan:
    def test_detects_so_file(self, tmp_path):
        (tmp_path / "lib.so").write_bytes(b"\x7fELF")
        findings = scan_binaries(tmp_path)
        assert any("BINARY" in f for f in findings), f"No binary detection: {findings}"

    def test_detects_pyc_file(self, tmp_path):
        (tmp_path / "mod.pyc").write_bytes(b"dummy")
        findings = scan_binaries(tmp_path)
        assert any("BINARY" in f for f in findings), f"No .pyc detection: {findings}"

    def test_clean_dir_no_binaries(self, tmp_path):
        (tmp_path / "mod.py").write_text("pass\n")
        findings = scan_binaries(tmp_path)
        assert findings == [], f"False positive on clean dir: {findings}"


# ---------------------------------------------------------------------------
# Full run_scan integration
# ---------------------------------------------------------------------------

class TestRunScan:
    def test_clean_repo(self, tmp_path):
        (tmp_path / "clean.py").write_text("x = 1\n")
        result = run_scan(str(tmp_path))
        assert result["clean"] is True
        assert result["total_findings"] == 0

    def test_dirty_repo(self, tmp_path):
        (tmp_path / "dirty.py").write_text(POSITIVE_GITHUB_PAT)
        result = run_scan(str(tmp_path))
        assert result["clean"] is False
        assert result["total_findings"] > 0
        assert len(result["secrets"]) > 0
