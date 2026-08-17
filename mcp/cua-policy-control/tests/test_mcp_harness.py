from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from starlette.testclient import TestClient

APP_ROOT = Path(__file__).parents[1]


def load_server(*, token: str = "", state_root: str | None = None):
    os.environ["CUA_MCP_TOKEN"] = token
    if state_root is not None:
        os.environ["CUA_MCP_STATE_ROOT"] = state_root
    import server
    return importlib.reload(server)


class McpHarnessTests(unittest.TestCase):
    def rpc(self, client: TestClient, method: str, params: dict | None = None, *, req_id: int = 1, headers: dict | None = None):
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        response = client.post("/mcp", json=payload, headers=headers or {})
        return response, response.json()

    def test_initialize_and_tool_discovery(self):
        with tempfile.TemporaryDirectory() as td:
            server = load_server(state_root=td)
            with TestClient(server.app) as client:
                response, body = self.rpc(
                    client,
                    "initialize",
                    {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "harness", "version": "1"}},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(body["result"]["serverInfo"]["name"], "CUA Policy Control")

                response, body = self.rpc(client, "tools/list", req_id=2)
                self.assertEqual(response.status_code, 200)
                names = {tool["name"] for tool in body["result"]["tools"]}
                self.assertEqual(
                    names,
                    {"cua.runtime_status", "cua.browser_pages", "policy.merge.preview", "policy.merge", "policy.current"},
                )

    def test_unknown_tool_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            server = load_server(state_root=td)
            with TestClient(server.app) as client:
                response, body = self.rpc(client, "tools/call", {"name": "missing.tool", "arguments": {}})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(body["error"]["code"], -32601)

    def test_origin_guard_rejects_untrusted_origin(self):
        with tempfile.TemporaryDirectory() as td:
            server = load_server(state_root=td)
            with TestClient(server.app) as client:
                response, body = self.rpc(client, "ping", headers={"Origin": "https://evil.invalid"})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(body["error"]["message"], "Origin not allowed")

    def test_bearer_guard_when_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            server = load_server(token="test-secret", state_root=td)
            with TestClient(server.app) as client:
                response, _ = self.rpc(client, "ping")
                self.assertEqual(response.status_code, 401)
                response, body = self.rpc(client, "ping", headers={"Authorization": "Bearer test-secret"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(body["result"], {})

    def test_live_runtime_status_and_policy_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            server = load_server(state_root=td)
            with TestClient(server.app) as client:
                response, body = self.rpc(
                    client,
                    "tools/call",
                    {"name": "cua.runtime_status", "arguments": {}},
                )
                self.assertEqual(response.status_code, 200)
                result = body["result"]
                self.assertFalse(result["isError"], result)
                self.assertTrue(result["structuredContent"]["reachable"])
                self.assertNotIn("webSocketDebuggerUrl", json.dumps(result))

                fragments = [
                    {"ExtensionSettings": {"alpha": {"installation_mode": "blocked"}}, "List": [1, 2]},
                    {"ExtensionSettings": {"beta": {"installation_mode": "allowed"}}, "List": [2, 3]},
                ]
                args = {"fragments": fragments, "merge_keys": ["ExtensionSettings", "List"]}
                response, body = self.rpc(
                    client,
                    "tools/call",
                    {"name": "policy.merge.preview", "arguments": args},
                    req_id=2,
                )
                self.assertFalse(body["result"]["isError"], body)
                merged = body["result"]["structuredContent"]["merged"]
                self.assertEqual(set(merged["ExtensionSettings"]), {"alpha", "beta"})
                self.assertEqual(merged["List"], [1, 2, 3])

                apply_args = {"profile": "harness", **args}
                response, body = self.rpc(
                    client,
                    "tools/call",
                    {"name": "policy.merge", "arguments": apply_args},
                    req_id=3,
                )
                self.assertFalse(body["result"]["isError"], body)
                staged = Path(body["result"]["structuredContent"]["path"])
                self.assertTrue(staged.is_file())
                self.assertTrue(str(staged).startswith(td))

                response, body = self.rpc(
                    client,
                    "tools/call",
                    {"name": "policy.current", "arguments": {"profile": "harness"}},
                    req_id=4,
                )
                self.assertFalse(body["result"]["isError"], body)
                current = body["result"]["structuredContent"]
                self.assertTrue(current["exists"])
                self.assertEqual(current["merged"], merged)


if __name__ == "__main__":
    unittest.main(verbosity=2)
