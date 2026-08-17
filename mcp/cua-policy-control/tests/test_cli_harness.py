from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
CLI = ROOT / "scripts" / "cua-policy-control"


class CliHarnessTests(unittest.TestCase):
    def run_cli(self, *args: str, env: dict[str, str] | None = None):
        merged = os.environ.copy()
        merged["CUA_MCP_TOKEN"] = ""
        if env:
            merged.update(env)
        completed = subprocess.run([str(CLI), *args], cwd=ROOT, text=True, capture_output=True, env=merged, timeout=15)
        return completed, json.loads(completed.stdout) if completed.stdout.strip() else None

    def test_tools_and_dynamic_call_share_registry(self):
        completed, tools = self.run_cli("tools", "--names-only")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(set(tools), {"cua.runtime_status", "cua.browser_pages", "policy.merge.preview", "policy.merge", "policy.current"})
        completed, status = self.run_cli("call", "cua.runtime_status")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(status["reachable"], status)

    def test_inspect_and_smoke(self):
        with tempfile.TemporaryDirectory() as td:
            env = {"CUA_MCP_PROFILE_ROOT": td}
            completed, inspected = self.run_cli("inspect", "--live", env=env)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(inspected["name"], "CUA Policy Control")
            self.assertTrue(inspected["live"]["runtime"]["reachable"])
            completed, smoke = self.run_cli("smoke", env=env)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(smoke["ok"], smoke)

    def test_profile_allowlist_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            env = {"CUA_MCP_PROFILE_ROOT": td}
            completed, profile = self.run_cli("profile", "set", "readonly", "cua.runtime_status", "cua.browser_pages", env=env)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(profile["tools"], ["cua.browser_pages", "cua.runtime_status"])
            completed, shown = self.run_cli("profile", "show", "readonly", env=env)
            self.assertEqual(shown["tools"], profile["tools"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
