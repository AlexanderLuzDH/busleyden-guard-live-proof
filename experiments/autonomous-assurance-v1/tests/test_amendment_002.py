from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The correction wrappers import their base modules by normal module name.
sys.path.insert(0, str(ROOT))
static = load("run_corrected_static_test", "run_corrected_static.py")
executable = load("run_corrected_pysnooper_test", "run_corrected_pysnooper.py")


class Amendment002Tests(unittest.TestCase):
    def test_github_repository_trailing_slash(self):
        expected = "jakubroztocil/httpie"
        self.assertEqual(static.github_repo("https://github.com/jakubroztocil/httpie/"), expected)
        self.assertEqual(static.github_repo("https://github.com/jakubroztocil/httpie"), expected)
        self.assertEqual(static.github_repo("https://github.com/jakubroztocil/httpie.git"), expected)

    def test_string_path_oracle_matches_declared_property(self):
        code = executable.base.CASES[2].test_code
        self.assertIn('assert path.is_file()', code)
        self.assertIn('assert "x = 7" in text', code)
        self.assertNotIn('assert "15" in', code)


if __name__ == "__main__":
    unittest.main()
