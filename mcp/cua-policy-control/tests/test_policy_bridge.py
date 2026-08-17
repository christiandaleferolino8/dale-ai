import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

BRIDGE = Path(__file__).parents[1] / "python" / "policy_bridge.py"


def load_bridge(state_root: Path):
    os.environ["CUA_MCP_STATE_ROOT"] = str(state_root)
    spec = importlib.util.spec_from_file_location("policy_bridge_test", BRIDGE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PolicyBridgeTests(unittest.TestCase):
    def test_preview_matches_recursive_merge_contract(self):
        with tempfile.TemporaryDirectory() as td:
            bridge = load_bridge(Path(td))
            merged = bridge.preview(
                [
                    {"ExtensionSettings": {"a": {"installation_mode": "blocked"}}, "List": [1, 2]},
                    {"ExtensionSettings": {"b": {"installation_mode": "allowed"}}, "List": [2, 3]},
                ],
                ["ExtensionSettings", "List"],
            )
            self.assertEqual(set(merged["ExtensionSettings"]), {"a", "b"})
            self.assertEqual(merged["List"], [1, 2, 3])

    def test_unlisted_nested_dict_is_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            bridge = load_bridge(Path(td))
            merged = bridge.preview([{"Prefs": {"a": 1}}, {"Prefs": {"b": 2}}], [])
            self.assertEqual(merged, {"Prefs": {"b": 2}})

    def test_apply_isolated_and_revision_backed_up(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bridge = load_bridge(root)
            first = bridge.apply("demo", [{"A": 1}], [])
            second = bridge.apply("demo", [{"A": 2}], [])
            self.assertEqual(first["merged"], {"A": 1})
            self.assertEqual(second["merged"], {"A": 2})
            current = root / "demo" / "000_policy_merge.json"
            backup = root / "demo" / ".policy_merge" / "000_policy_merge.0001.json"
            self.assertTrue(current.is_file())
            self.assertTrue(backup.is_file())
            self.assertEqual(bridge.current("demo")["merged"], {"A": 2})

    def test_profile_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            bridge = load_bridge(Path(td))
            with self.assertRaises(ValueError):
                bridge.apply("../escape", [{"A": 1}], [])


if __name__ == "__main__":
    unittest.main()
