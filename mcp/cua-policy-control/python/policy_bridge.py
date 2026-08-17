from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

POLICY_MERGE_PATH = Path(
    os.environ.get(
        "CUA_POLICY_MERGE_PY",
        "/openai/project/cua/cua_chrome/cua_chrome/core/policy_merge.py",
    )
)
STATE_ROOT = Path(
    os.environ.get(
        "CUA_MCP_STATE_ROOT",
        "/openai/project/cua/custom_app/state/policies",
    )
).resolve()


def _load_policy_merge():
    if not POLICY_MERGE_PATH.is_file():
        raise RuntimeError(f"policy_merge.py not found: {POLICY_MERGE_PATH}")
    spec = importlib.util.spec_from_file_location("cua_policy_merge", POLICY_MERGE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load policy_merge.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy_merge = _load_policy_merge()


def _validate_fragments(fragments: list[dict[str, Any]]) -> None:
    if not isinstance(fragments, list) or not fragments:
        raise ValueError("fragments must be a non-empty list")
    for index, fragment in enumerate(fragments):
        if not isinstance(fragment, dict):
            raise ValueError(f"fragments[{index}] must be an object")


def preview(fragments: list[dict[str, Any]], merge_keys: list[str]) -> dict[str, Any]:
    _validate_fragments(fragments)
    if not isinstance(merge_keys, list) or any(not isinstance(k, str) or not k for k in merge_keys):
        raise ValueError("merge_keys must be a list of non-empty strings")

    merged: dict[str, Any] = {}
    merge_key_set = set(merge_keys)
    for fragment in fragments:
        merged = policy_merge.deep_merge(merged, fragment, merge_keys_set=merge_key_set)
    return merged


def _safe_profile(profile: str) -> str:
    if not profile or profile in {".", ".."}:
        raise ValueError("profile must be non-empty")
    if not all(ch.isalnum() or ch in "-_" for ch in profile):
        raise ValueError("profile may contain only letters, digits, '-' and '_'")
    return profile


def apply(profile: str, fragments: list[dict[str, Any]], merge_keys: list[str]) -> dict[str, Any]:
    profile = _safe_profile(profile)
    merged = preview(fragments, merge_keys)

    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    profile_dir = (STATE_ROOT / profile).resolve()
    if STATE_ROOT not in profile_dir.parents:
        raise ValueError("profile escaped state root")
    profile_dir.mkdir(parents=True, exist_ok=True)

    current = profile_dir / "000_policy_merge.json"
    backup = profile_dir / ".policy_merge"
    backup.mkdir(exist_ok=True)

    if current.exists():
        revisions = sorted(backup.glob("000_policy_merge.*.json"))
        next_index = len(revisions) + 1
        current.replace(backup / f"000_policy_merge.{next_index:04d}.json")

    tmp = profile_dir / ".000_policy_merge.json.tmp"
    tmp.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(current)

    return {
        "profile": profile,
        "path": str(current),
        "merge_keys": merge_keys,
        "fragment_count": len(fragments),
        "merged": merged,
    }


def current(profile: str) -> dict[str, Any]:
    profile = _safe_profile(profile)
    path = (STATE_ROOT / profile / "000_policy_merge.json").resolve()
    if STATE_ROOT not in path.parents:
        raise ValueError("profile escaped state root")
    if not path.is_file():
        return {"profile": profile, "exists": False, "path": str(path), "merged": None}
    return {
        "profile": profile,
        "exists": True,
        "path": str(path),
        "merged": json.loads(path.read_text(encoding="utf-8")),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["preview", "apply", "current"])
    parser.add_argument("--profile", default="default")
    args = parser.parse_args()
    payload = json.load(sys.stdin)

    if args.action == "preview":
        result = preview(payload["fragments"], payload.get("merge_keys", []))
    elif args.action == "apply":
        result = apply(args.profile, payload["fragments"], payload.get("merge_keys", []))
    else:
        result = current(args.profile)

    json.dump(result, sys.stdout)
