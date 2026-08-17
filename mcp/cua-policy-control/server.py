from __future__ import annotations

import json
import os
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from core import APP_NAME, APP_VERSION, TOOL_MAP, call_tool, list_tools
from profiles import resolve_profile

SUPPORTED_PROTOCOLS = {"2025-06-18", "2025-11-25"}
TOKEN = os.environ.get("CUA_MCP_TOKEN", "")
ALLOWED_ORIGINS = {
    x.strip()
    for x in os.environ.get("CUA_MCP_ALLOWED_ORIGINS", "https://chatgpt.com,https://chat.openai.com").split(",")
    if x.strip()
}


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


def allowed_tools() -> set[str]:
    try:
        return resolve_profile(os.environ.get("CUA_MCP_PROFILE"))
    except Exception:
        return set(TOOL_MAP)


async def healthz(request: Request) -> Response:
    return JSONResponse({"ok": True, "name": APP_NAME, "version": APP_VERSION, "profile": os.environ.get("CUA_MCP_PROFILE", "default")})


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
                "instructions": "MCP and CLI share one tool registry. Browser tools are read-only. Preview policy merges before staging; policy.merge writes only to app-owned staging state.",
            },
        )

    if method in {"notifications/initialized", "notifications/cancelled"}:
        return Response(status_code=202)
    if method == "ping":
        return rpc_result(req_id, {})
    if method == "tools/list":
        return rpc_result(req_id, {"tools": list_tools(allowed_tools())})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if not isinstance(name, str):
            return rpc_error(req_id, -32602, "Tool name is required")
        if not isinstance(args, dict):
            return rpc_error(req_id, -32602, "Tool arguments must be an object")
        if name not in TOOL_MAP or name not in allowed_tools():
            return rpc_error(req_id, -32601, f"Unknown or disabled tool: {name}")
        try:
            data = call_tool(name, args)
            is_error = isinstance(data, dict) and data.get("reachable") is False and "error" in data
            return rpc_result(req_id, tool_result(data, is_error=is_error))
        except Exception as exc:
            return rpc_result(req_id, tool_result({"error": str(exc)}, is_error=True))

    return rpc_error(req_id, -32601, f"Method not found: {method}")


app = Starlette(
    routes=[
        Route("/healthz", healthz, methods=["GET"]),
        Route("/mcp", mcp_get, methods=["GET"]),
        Route("/mcp", mcp_post, methods=["POST"]),
    ]
)
