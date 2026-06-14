"""Tests for hardened error paths and edge cases in GITSTORY."""
from __future__ import annotations

import io
import json
import sys
import unittest

import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gitstory.core import (
    TOOL_NAME,
    TOOL_VERSION,
    parse_log,
    group_commits,
    bump_version,
    build_changelog,
    render_markdown,
    scan,
    to_json,
)
from gitstory.cli import main


class TestEdgeCaseParsing(unittest.TestCase):
    def test_empty_string_input(self):
        """Empty log produces zero commits, not an error."""
        result = build_changelog("")
        self.assertEqual(result["total_commits"], 0)
        self.assertEqual(result["breaking_changes"], 0)
        self.assertIn("No notable changes", result["markdown"])

    def test_whitespace_only_input(self):
        """Whitespace-only log produces zero commits gracefully."""
        commits = parse_log("   \n  \n  ")
        self.assertEqual(commits, [])

    def test_group_commits_none_safe(self):
        """group_commits does not crash when passed None."""
        sections, breaking = group_commits(None)
        self.assertEqual(sections, [])
        self.assertEqual(breaking, [])

    def test_bump_version_none_commits_safe(self):
        """bump_version treats None commits as an empty list."""
        v, level = bump_version("v1.0.0", None)
        self.assertEqual(v, "v1.0.1")
        self.assertEqual(level, "none")

    def test_render_markdown_none_version(self):
        """render_markdown falls back to 'Unreleased' when version is None."""
        md = render_markdown(None, [], [])
        self.assertIn("## Unreleased", md)

    def test_render_markdown_none_sections_breaking(self):
        """render_markdown handles None sections/breaking without crashing."""
        md = render_markdown("v1.0.0", None, None)
        self.assertIn("## v1.0.0", md)
        self.assertIn("No notable changes", md)

    def test_parse_semver_empty_raises(self):
        """_parse_semver raises ValueError for empty/None version strings."""
        with self.assertRaises(ValueError):
            bump_version("", [])

    def test_scan_alias(self):
        """scan() is a stable alias for build_changelog."""
        result = scan("feat: add thing\nfix: fix bug")
        self.assertEqual(result["total_commits"], 2)
        self.assertIn("markdown", result)

    def test_scan_empty_input(self):
        """scan(None) and scan('') both return a valid empty result."""
        r1 = scan(None)
        r2 = scan("")
        self.assertEqual(r1["total_commits"], 0)
        self.assertEqual(r2["total_commits"], 0)

    def test_to_json_roundtrip(self):
        """to_json produces valid JSON that round-trips."""
        result = scan("feat: x")
        j = to_json(result)
        parsed = json.loads(j)
        self.assertEqual(parsed["total_commits"], 1)

    def test_tool_name_version_exported(self):
        """TOOL_NAME and TOOL_VERSION are accessible from core directly."""
        self.assertEqual(TOOL_NAME, "gitstory")
        self.assertTrue(TOOL_VERSION)


class TestMcpServerImport(unittest.TestCase):
    def test_mcp_server_imports_cleanly(self):
        """mcp_server module imports without ImportError (mcp package not needed)."""
        import importlib
        import sys
        # Remove cached module if present.
        sys.modules.pop("gitstory.mcp_server", None)
        try:
            mod = importlib.import_module("gitstory.mcp_server")
            self.assertTrue(hasattr(mod, "serve"))
        except ImportError as exc:
            self.fail(f"mcp_server import raised ImportError: {exc}")


class TestCliEdgeCases(unittest.TestCase):
    def test_cli_missing_file_returns_1_with_message(self):
        """Missing --input file returns exit code 1 and prints to stderr."""
        buf = io.StringIO()
        old_err = sys.stderr
        sys.stderr = buf
        try:
            rc = main(["changelog", "--input", "/no/such/file/does-not-exist.log"])
        finally:
            sys.stderr = old_err
        self.assertEqual(rc, 1)
        self.assertIn("error", buf.getvalue().lower())

    def test_cli_empty_stdin_changelog(self):
        """Empty stdin produces a valid zero-commit changelog, not a crash."""
        buf = io.StringIO()
        old_stdin, old_stdout = sys.stdin, sys.stdout
        sys.stdin = io.StringIO("")
        sys.stdout = buf
        try:
            rc = main(["--format", "json", "changelog"])
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["total_commits"], 0)

    def test_cli_empty_stdin_bump_bad_version(self):
        """bump with invalid version string returns 1, not a traceback."""
        old_stdin = sys.stdin
        sys.stdin = io.StringIO("feat: thing")
        try:
            rc = main(["bump", "not-a-semver"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
