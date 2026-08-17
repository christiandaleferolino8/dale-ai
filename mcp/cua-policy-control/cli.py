from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from core import TOOL_MAP, call_tool, describe, list_tools
from profiles import list_profiles, set_profile, show_profile


def emit(data: Any, compact: bool = False) -> None:
    print(json.dumps(data, indent=None if compact else 2, sort_keys=True))


def parse_json_arg(value: str | None) -> dict[str, Any]:
    if value is None:
        return {}
    if value == "-":
        value = sys.stdin.read()
    path = Path(value)
    if path.is_file():
        value = path.read_text(encoding="utf-8")
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("arguments JSON must be an object")
    return data


def cmd_tools(args: argparse.Namespace) -> int:
    tools = list_tools()
    if args.search:
        q = args.search.lower()
        tools = [t for t in tools if q in t["name"].lower() or q in t["description"].lower()]
    if args.names_only:
        emit([t["name"] for t in tools], args.compact)
    else:
        emit(tools, args.compact)
    return 0


def cmd_call(args: argparse.Namespace) -> int:
    if args.name not in TOOL_MAP:
        print(f"unknown tool: {args.name}", file=sys.stderr)
        return 2
    payload = parse_json_arg(args.args)
    emit(call_tool(args.name, payload), args.compact)
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    data = describe()
    data["profiles"] = list_profiles()
    if args.live:
        data["live"] = {
            "runtime": call_tool("cua.runtime_status", {}),
            "pages": call_tool("cua.browser_pages", {}),
        }
    emit(data, args.compact)
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    runtime = call_tool("cua.runtime_status", {})
    pages = call_tool("cua.browser_pages", {})
    checks = {
        "tool_registry": len(TOOL_MAP) >= 5,
        "profile_default": set(show_profile("default")["tools"]) == set(TOOL_MAP),
        "cdp_reachable": bool(runtime.get("reachable")),
        "page_listing": bool(pages.get("reachable")),
    }
    result = {"ok": all(checks.values()), "checks": checks, "runtime": runtime, "page_count": pages.get("count", 0)}
    emit(result, args.compact)
    return 0 if result["ok"] else 1


def cmd_profile(args: argparse.Namespace) -> int:
    if args.profile_command == "list":
        emit(list_profiles(), args.compact)
    elif args.profile_command == "show":
        emit(show_profile(args.name), args.compact)
    elif args.profile_command == "set":
        emit(set_profile(args.name, args.tools), args.compact)
    else:
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cua-policy-control", description="Shared CLI for the CUA Policy Control MCP tool registry")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("tools", help="list available tools")
    p.add_argument("--search")
    p.add_argument("--names-only", action="store_true")
    p.set_defaults(func=cmd_tools)

    p = sub.add_parser("call", help="call a tool from the shared registry")
    p.add_argument("name")
    p.add_argument("--args", help="JSON object, file path, or '-' for stdin")
    p.set_defaults(func=cmd_call)

    p = sub.add_parser("inspect", help="describe registry/profile/runtime configuration")
    p.add_argument("--live", action="store_true")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("smoke", help="run a fast live smoke probe")
    p.set_defaults(func=cmd_smoke)

    p = sub.add_parser("profile", help="manage app-owned tool allowlist profiles")
    sp = p.add_subparsers(dest="profile_command", required=True)
    q = sp.add_parser("list")
    q.set_defaults(func=cmd_profile)
    q = sp.add_parser("show")
    q.add_argument("name")
    q.set_defaults(func=cmd_profile)
    q = sp.add_parser("set")
    q.add_argument("name")
    q.add_argument("tools", nargs="+")
    q.set_defaults(func=cmd_profile)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
