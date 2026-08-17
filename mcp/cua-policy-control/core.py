from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

APP_NAME = "CUA Policy Control"
APP_VERSION = "0.2.0"
POLICY_BRIDGE = os.path.join(os.path.dirname(__file__), "python", "policy_bridge.py")
CDP_BASE = os.environ.get("CUA_CDP_BASE", "http://127.0.0.1:9222")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]
    read_only: bool = True
    destructive: bool = False
    idempotent: bool = True
    open_world: bool = False

    def as_mcp(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": {
                "readOnlyHint": self.read_only,
                "destructiveHint": self.destructive,
                "idempotentHint": self.idempotent,
                "openWorldHint": self.open_world,
            },
        }


def _fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=3) as response:
        return json.load(response)


def _policy_call(action: str, args: dict[str, Any]) -> Any:
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


def runtime_status(_: dict[str, Any]) -> dict[str, Any]:
    try:
        version = _fetch_json(f"{CDP_BASE}/json/version")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"reachable": False, "cdp": "loopback", "error": str(exc)}
    safe_version = {k: v for k, v in version.items() if k != "webSocketDebuggerUrl"}
    return {"reachable": True, "cdp": "loopback", "browser": safe_version}


def browser_pages(_: dict[str, Any]) -> dict[str, Any]:
    try:
        pages = _fetch_json(f"{CDP_BASE}/json/list")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"reachable": False, "count": 0, "pages": [], "error": str(exc)}
    safe_pages = [
        {k: p.get(k) for k in ("id", "type", "title", "url")}
        for p in pages
        if isinstance(p, dict)
    ]
    return {"reachable": True, "count": len(safe_pages), "pages": safe_pages}


def policy_preview(args: dict[str, Any]) -> dict[str, Any]:
    return {"merged": _policy_call("preview", args)}


def policy_stage(args: dict[str, Any]) -> dict[str, Any]:
    return _policy_call("apply", args)


def policy_current(args: dict[str, Any]) -> dict[str, Any]:
    return _policy_call("current", args)


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "cua.runtime_status",
        "CUA Runtime Status",
        "Read the local Chromium CDP version and report whether the CUA browser control plane is reachable.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        runtime_status,
    ),
    ToolSpec(
        "cua.browser_pages",
        "List CUA Browser Pages",
        "List currently open Chromium pages from the loopback DevTools endpoint without exposing debugger URLs.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        browser_pages,
    ),
    ToolSpec(
        "policy.merge.preview",
        "Preview Chromium Policy Merge",
        "Preview the deployed CUA policy_merge.py deep-merge behavior without writing files.",
        {
            "type": "object",
            "properties": {
                "fragments": {"type": "array", "minItems": 1, "items": {"type": "object"}},
                "merge_keys": {"type": "array", "items": {"type": "string"}, "default": []},
            },
            "required": ["fragments"],
            "additionalProperties": False,
        },
        policy_preview,
    ),
    ToolSpec(
        "policy.merge",
        "Stage Chromium Policy Merge",
        "Merge policy fragments and atomically stage the result in the app-owned state directory. Existing staged output is revision-backed up; system Chromium policy is never activated.",
        {
            "type": "object",
            "properties": {
                "profile": {"type": "string", "pattern": "^[A-Za-z0-9_-]+$", "default": "default"},
                "fragments": {"type": "array", "minItems": 1, "items": {"type": "object"}},
                "merge_keys": {"type": "array", "items": {"type": "string"}, "default": []},
            },
            "required": ["fragments"],
            "additionalProperties": False,
        },
        policy_stage,
        read_only=False,
        idempotent=False,
    ),
    ToolSpec(
        "policy.current",
        "Read Staged Chromium Policy",
        "Read the currently staged merged policy for an app-owned profile.",
        {
            "type": "object",
            "properties": {"profile": {"type": "string", "pattern": "^[A-Za-z0-9_-]+$", "default": "default"}},
            "additionalProperties": False,
        },
        policy_current,
    ),
)

TOOL_MAP = {tool.name: tool for tool in TOOLS}


def list_tools(names: set[str] | None = None) -> list[dict[str, Any]]:
    selected = TOOLS if names is None else tuple(t for t in TOOLS if t.name in names)
    return [tool.as_mcp() for tool in selected]


def call_tool(name: str, args: dict[str, Any] | None = None) -> Any:
    try:
        tool = TOOL_MAP[name]
    except KeyError as exc:
        raise KeyError(f"unknown tool: {name}") from exc
    if not isinstance(args or {}, dict):
        raise ValueError("tool arguments must be an object")
    return tool.handler(args or {})


def describe() -> dict[str, Any]:
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "cdp_base": CDP_BASE,
        "tools": list_tools(),
        "safety": {
            "browser_control": "read-only",
            "policy_write_scope": "app-owned staging only",
            "system_policy_activation": False,
        },
    }
