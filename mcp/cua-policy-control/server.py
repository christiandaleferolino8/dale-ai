from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

APP_NAME = "CUA Policy Control"
APP_VERSION = "0.1.0"
SUPPORTED_PROTOCOLS = {"2025-06-18", "2025-11-25"}
TOKEN = os.environ.get("CUA_MCP_TOKEN", "")
ALLOWED_ORIGINS = {
    x.strip()
    for x in os.environ.get(
        "CUA_MCP_ALLOWED_ORIGINS",
        "https://chatgpt.com,https://chat.openai.com",
    ).split(",")
    if x.strip()
}
POLICY_BRIDGE = os.path.join(os.path.dirname(__file__), "python", "policy_bridge.py")
CDP_BASE = os.environ.get("CUA_CDP_BASE", "http://127.0.0.1:9222")

TOOLS = [
    {
        "name": "cua.runtime_status",
        "title": "CUA Runtime Status",
        "description": "Read the local Chromium CDP version and report whether the CUA browser control plane is reachable.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "cua.browser_pages",
        "title": "List CUA Browser Pages",
        "description": "List the currently open Chromium pages from the loopback DevTools endpoint. This is read-only.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "policy.merge.preview",
        "title": "Preview Chromium Policy Merge",
        "description": "Preview the exact deep-merge semantics used by the deployed CUA policy_merge.py without writing files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fragments": {"type": "array", "minItems": 1, "items": {"type": "object"}},
                "merge_keys": {"type": "array", "items": {"type": "string"}, "default": []},
            },
            "required": ["fragments"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "policy.merge",
        "title": "Stage Chromium Policy Merge",
        "description": "Merge policy fragments using the deployed CUA policy_merge.py semantics and atomically stage the result in this app's isolated state directory. Existing staged output is revision-backed up. This does not modify /etc/chromium or restart Chromium.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile": {"type": "string", "pattern": "^[A-Za-z0-9_-]+$", "default": "default"},
                "fragments": {"type": "array", "minItems": 1, "items": {"type": "object"}},
                "merge_keys": {"type": "array", "items": {"type": "string"}, "default": []},
            },
            "required": ["fragments"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    },
    {
        "name": "policy.current",
        "title": "Read Staged Chromium Policy",
        "description": "Read the currently staged merged policy for an app-owned profile.",
        "inputSchema": {
            "type": "object",
            "properties": {"profile": {"type": "string", "pattern": "^[A-Za-z0-9_-]+$", "default": "default"}},
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
]


def rpc_result(req_id: Any, result: Any) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})


def rpc_error(req_id: Any, code: int, message: str, data: Any = None, status: int = 200) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": error}, status_code=status)


def tool_result(data: Any, *, is_error: bool = False) -> dict[str, Any]:
    text = json.dumps(data, indent=2, sort_keys=True) if not isinstance(data, str) else data
    result: dict[str, Any] = {"content": [{"type": "text", "text": text}], "isError": is_error}
    if isinstance(data, dict):
        result["structuredContent"] = data
    return result


def check_request_security(request: Request) -> Response | None:
    origin = request.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        return rpc_error(None, -32001, "Origin not allowed", status=403)
    if TOKEN:
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {TOKEN}":
            return JSONResponse(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32002, "message": "Unauthorized"}},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
    return None


def fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=3) as response:
        return json.load(response)


def policy_call(action: str, args: dict[str, Any]) -> Any:
    cmd = [sys.executable, POLICY_BRIDGE, action]
    if action in {"apply", "current"}:
        cmd += ["--profile", args.get("profile", "default")]
    payload = args if action != "current" else {}
    completed = subprocess.run(
        cmd,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
        env=os.environ.copy(),
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "policy helper failed").strip())
    return json.loads(completed.stdout)


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    try:
        if name == "cua.runtime_status":
            version = fetch_json(f"{CDP_BASE}/json/version")
            safe_version = {k: v for k, v in version.items() if k != "webSocketDebuggerUrl"}
            return tool_result({"reachable": True, "cdp": "loopback", "browser": safe_version})
        if name == "cua.browser_pages":
            pages = fetch_json(f"{CDP_BASE}/json/list")
            safe_pages = [
                {k: p.get(k) for k in ("id", "type", "title", "url")}
                for p in pages
                if isinstance(p, dict)
            ]
            return tool_result({"count": len(safe_pages), "pages": safe_pages})
        if name == "policy.merge.preview":
            merged = policy_call("preview", args)
            return tool_result({"merged": merged})
        if name == "policy.merge":
            return tool_result(policy_call("apply", args))
        if name == "policy.current":
            return tool_result(policy_call("current", args))
        raise KeyError(name)
    except KeyError:
        raise
    except (urllib.error.URLError, TimeoutError) as exc:
        return tool_result({"error": f"CDP unavailable: {exc}"}, is_error=True)
    except Exception as exc:
        return tool_result({"error": str(exc)}, is_error=True)


async def healthz(request: Request) -> Response:
    return JSONResponse({"ok": True, "name": APP_NAME, "version": APP_VERSION})


async def mcp_get(request: Request) -> Response:
    blocked = check_request_security(request)
    if blocked:
        return blocked
    return Response(status_code=405, headers={"Allow": "POST, GET"})


async def mcp_post(request: Request) -> Response:
    blocked = check_request_security(request)
    if blocked:
        return blocked
    try:
        msg = await request.json()
    except Exception:
        return rpc_error(None, -32700, "Parse error", status=400)

    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or "method" not in msg:
        return rpc_error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request", status=400)

    req_id = msg.get("id")
    method = msg["method"]
    params = msg.get("params") or {}

    if method == "initialize":
        requested = params.get("protocolVersion", "2025-11-25")
        protocol = requested if requested in SUPPORTED_PROTOCOLS else "2025-11-25"
        return rpc_result(
            req_id,
            {
                "protocolVersion": protocol,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": APP_NAME, "version": APP_VERSION, "description": "CUA browser inspection and safe Chromium policy staging"},
                "instructions": "Use read-only CUA tools for runtime inspection. Preview policy merges before staging them. policy.merge only writes into the app-owned staging directory and never activates system Chromium policy.",
            },
        )

    if method in {"notifications/initialized", "notifications/cancelled"}:
        return Response(status_code=202)

    if method == "ping":
        return rpc_result(req_id, {})

    if method == "tools/list":
        return rpc_result(req_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if not isinstance(name, str):
            return rpc_error(req_id, -32602, "Tool name is required")
        if not isinstance(args, dict):
            return rpc_error(req_id, -32602, "Tool arguments must be an object")
        if name not in {tool["name"] for tool in TOOLS}:
            return rpc_error(req_id, -32601, f"Unknown tool: {name}")
        return rpc_result(req_id, call_tool(name, args))

    return rpc_error(req_id, -32601, f"Method not found: {method}")


app = Starlette(
    routes=[
        Route("/healthz", healthz, methods=["GET"]),
        Route("/mcp", mcp_get, methods=["GET"]),
        Route("/mcp", mcp_post, methods=["POST"]),
    ]
)
