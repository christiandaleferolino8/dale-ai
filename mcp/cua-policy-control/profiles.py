from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from core import TOOL_MAP

PROFILE_ROOT = Path(os.environ.get("CUA_MCP_PROFILE_ROOT", "/openai/project/cua/custom_app/state")).resolve()
PROFILE_FILE = PROFILE_ROOT / "profiles.json"


def _safe_name(name: str) -> str:
    if not name or not all(ch.isalnum() or ch in "-_" for ch in name):
        raise ValueError("profile name may contain only letters, digits, '-' and '_'")
    return name


def _load() -> dict[str, Any]:
    if not PROFILE_FILE.is_file():
        return {"default": {"tools": sorted(TOOL_MAP)}}
    raw = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("profiles file must contain an object")
    return raw


def _save(data: dict[str, Any]) -> None:
    PROFILE_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = PROFILE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(PROFILE_FILE)


def list_profiles() -> dict[str, Any]:
    profiles = _load()
    return {"count": len(profiles), "profiles": sorted(profiles)}


def show_profile(name: str) -> dict[str, Any]:
    name = _safe_name(name)
    profiles = _load()
    if name not in profiles:
        raise KeyError(name)
    tools = profiles[name].get("tools", [])
    return {"name": name, "tools": tools, "unknown_tools": sorted(set(tools) - set(TOOL_MAP))}


def set_profile(name: str, tools: list[str]) -> dict[str, Any]:
    name = _safe_name(name)
    if not isinstance(tools, list) or any(not isinstance(t, str) for t in tools):
        raise ValueError("tools must be a list of strings")
    unknown = sorted(set(tools) - set(TOOL_MAP))
    if unknown:
        raise ValueError(f"unknown tools: {', '.join(unknown)}")
    profiles = _load()
    profiles[name] = {"tools": sorted(set(tools))}
    _save(profiles)
    return show_profile(name)


def resolve_profile(name: str | None) -> set[str]:
    target = name or os.environ.get("CUA_MCP_PROFILE", "default")
    return set(show_profile(target)["tools"])
