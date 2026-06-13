"""Smoke tests for GITSTORY. Standard library only, no network."""
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gitstory import (  # noqa: E402
    TOOL_NAME,
    TOOL_VERSION,
    parse_commit,
    parse_log,
    group_commits,
    bump_version,
    build_changelog,
)
from gitstory.cli import main  # noqa: E402
from gitstory.core import RECORD_SEP, FIELD_SEP  # noqa: E402


class TestParsing(unittest.TestCase):
    def test_metadata(self):
        self.assertEqual(TOOL_NAME, "gitstory")
        self.assertTrue(TOOL_VERSION)

    def test_parse_basic_commit(self):
        c = parse_commit("feat(auth): add login", sha="abc1234def")
        self.assertEqual(c.type, "feat")
        self.assertEqual(c.scope, "auth")
        self.assertEqual(c.description, "add login")
        self.assertFalse(c.breaking)
        self.assertEqual(c.short_sha, "abc1234")
        self.assertTrue(c.conventional)

    def test_parse_breaking_bang(self):
        c = parse_commit("feat!: drop py2")
        self.assertTrue(c.breaking)
        self.assertEqual(c.breaking_desc, "drop py2")

    def test_parse_breaking_footer(self):
        c = parse_commit("feat: x", body="body\n\nBREAKING CHANGE: removed old API")
        self.assertTrue(c.breaking)
        self.assertEqual(c.breaking_desc, "removed old API")

    def test_non_conventional(self):
        c = parse_commit("random commit message")
        self.assertFalse(c.conventional)
        self.assertIsNone(c.type)
        self.assertEqual(c.description, "random commit message")

    def test_parse_structured_log(self):
        log = (
            f"sha1{FIELD_SEP}feat: a{FIELD_SEP}{RECORD_SEP}\n"
            f"sha2{FIELD_SEP}fix: b{FIELD_SEP}BREAKING CHANGE: boom{RECORD_SEP}"
        )
        commits = parse_log(log)
        self.assertEqual(len(commits), 2)
        self.assertEqual(commits[0].type, "feat")
        self.assertTrue(commits[1].breaking)

    def test_parse_plain_log(self):
        commits = parse_log("feat: a\nfix: b\nchore: c")
        self.assertEqual(len(commits), 3)


class TestGroupingAndBump(unittest.TestCase):
    def test_grouping(self):
        commits = parse_log("feat: a\nfix: b\nfeat: c\ndocs: d")
        sections, breaking = group_commits(commits)
        keys = [s.key for s in sections]
        self.assertEqual(keys[0], "feat")
        self.assertIn("fix", keys)
        self.assertIn("docs", keys)
        self.assertEqual(breaking, [])
        feat_sec = next(s for s in sections if s.key == "feat")
        self.assertEqual(len(feat_sec.commits), 2)

    def test_bump_major(self):
        commits = parse_log("feat!: big change")
        v, level = bump_version("v1.2.3", commits)
        self.assertEqual(v, "v2.0.0")
        self.assertEqual(level, "major")

    def test_bump_minor(self):
        commits = parse_log("feat: new")
        v, level = bump_version("1.2.3", commits)
        self.assertEqual(v, "1.3.0")
        self.assertEqual(level, "minor")

    def test_bump_patch(self):
        commits = parse_log("fix: bug")
        v, level = bump_version("v1.2.3", commits)
        self.assertEqual(v, "v1.2.4")
        self.assertEqual(level, "patch")

    def test_bump_zerover_breaking_is_minor(self):
        commits = parse_log("feat!: big")
        v, level = bump_version("0.4.1", commits)
        self.assertEqual(v, "0.5.0")
        self.assertEqual(level, "minor")

    def test_bump_invalid_version_raises(self):
        with self.assertRaises(ValueError):
            bump_version("not-a-version", [])


class TestBuildAndCli(unittest.TestCase):
    def test_build_changelog(self):
        log = "feat(api): add x\nfix: y\nfeat!: drop z"
        result = build_changelog(log, version="v2.0.0", current_version="v1.0.0")
        self.assertEqual(result["total_commits"], 3)
        self.assertEqual(result["breaking_changes"], 1)
        self.assertEqual(result["recommended_version"], "v2.0.0")
        self.assertIn("## v2.0.0", result["markdown"])
        self.assertIn("BREAKING CHANGES", result["markdown"])
        self.assertIn("Features", result["markdown"])

    def test_cli_version(self):
        with self.assertRaises(SystemExit) as cm:
            main(["--version"])
        self.assertEqual(cm.exception.code, 0)

    def test_cli_changelog_json(self):
        buf = io.StringIO()
        stdin = sys.stdin
        stdout = sys.stdout
        sys.stdin = io.StringIO("feat: a\nfix: b")
        sys.stdout = buf
        try:
            rc = main(["--format", "json", "changelog", "--current", "v1.0.0"])
        finally:
            sys.stdin = stdin
            sys.stdout = stdout
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["total_commits"], 2)
        self.assertEqual(data["recommended_version"], "v1.1.0")

    def test_cli_bump_json(self):
        buf = io.StringIO()
        stdin = sys.stdin
        stdout = sys.stdout
        sys.stdin = io.StringIO("fix: a")
        sys.stdout = buf
        try:
            rc = main(["--format", "json", "bump", "v1.0.0"])
        finally:
            sys.stdin = stdin
            sys.stdout = stdout
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["recommended_version"], "v1.0.1")

    def test_cli_bad_input_file_returns_nonzero(self):
        rc = main(["changelog", "--input", "/no/such/file/xyz.log"])
        self.assertEqual(rc, 1)

    def test_cli_bad_version_returns_nonzero(self):
        stdin = sys.stdin
        sys.stdin = io.StringIO("feat: a")
        try:
            rc = main(["bump", "garbage"])
        finally:
            sys.stdin = stdin
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
