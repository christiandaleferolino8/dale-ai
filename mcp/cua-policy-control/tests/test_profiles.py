from __future__ import annotations

import importlib
import os
import tempfile
import unittest


class ProfileTests(unittest.TestCase):
    def load(self, root: str):
        os.environ["CUA_MCP_PROFILE_ROOT"] = root
        import profiles
        return importlib.reload(profiles)

    def test_default_contains_all_tools(self):
        with tempfile.TemporaryDirectory() as td:
            profiles = self.load(td)
            self.assertEqual(set(profiles.show_profile("default")["tools"]), set(profiles.TOOL_MAP))

    def test_unknown_tool_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            profiles = self.load(td)
            with self.assertRaises(ValueError):
                profiles.set_profile("bad", ["missing.tool"])

    def test_invalid_profile_name_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            profiles = self.load(td)
            with self.assertRaises(ValueError):
                profiles.set_profile("../bad", ["cua.runtime_status"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
