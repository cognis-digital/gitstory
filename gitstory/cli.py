"""Command-line interface for GITSTORY.

Subcommands:
    changelog   Build a changelog/release notes from a git log.
    bump        Recommend the next semantic version from commits.

Input is read from a file (--input), or stdin if omitted. The log may be the
structured `git log --format='%H%x1f%s%x1f%b%x1e'` form, or plain one-subject-
per-line. Example end-to-end:

    git log --format='%H%x1f%s%x1f%b%x1e' v1.2.0..HEAD | gitstory changelog
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import TOOL_NAME, TOOL_VERSION
from .core import build_changelog, parse_log, bump_version


def _read_input(path: Optional[str]) -> str:
    if path and path != "-":
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    data = sys.stdin.read()
    return data


def _print_table(result: dict, stream) -> None:
    """Human-readable table view (markdown + summary)."""
    print(result["markdown"], file=stream)
    summary = (
        f"summary: {result['total_commits']} commits "
        f"({result['conventional_commits']} conventional), "
        f"{result['breaking_changes']} breaking"
    )
    if result.get("recommended_version"):
        summary += (
            f" | next: {result['recommended_version']} "
            f"({result['bump_level']})"
        )
    print(summary, file=stream)


def _cmd_changelog(args: argparse.Namespace) -> int:
    text = _read_input(args.input)
    result = build_changelog(
        text,
        version=args.tag,
        date=args.date,
        include_unconventional=args.include_all,
        current_version=args.current,
    )
    if args.format == "json":
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        _print_table(result, sys.stdout)
    return 0


def _cmd_bump(args: argparse.Namespace) -> int:
    text = _read_input(args.input)
    commits = parse_log(text)
    new_version, level = bump_version(args.current, commits)
    if args.format == "json":
        json.dump(
            {
                "current_version": args.current,
                "recommended_version": new_version,
                "bump_level": level,
                "analyzed_commits": len(commits),
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        print(f"{args.current} -> {new_version} ({level})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Changelog and release notes from conventional commits.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{TOOL_NAME} {TOOL_VERSION}",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="output format (default: table)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_cl = sub.add_parser("changelog", help="build a changelog from a git log")
    p_cl.add_argument("-i", "--input", help="log file (default: stdin)")
    p_cl.add_argument("-t", "--tag", default="Unreleased", help="release tag/version header")
    p_cl.add_argument("-d", "--date", default=None, help="release date string")
    p_cl.add_argument(
        "-c", "--current", default=None, help="current version, to recommend a bump"
    )
    p_cl.add_argument(
        "--include-all",
        action="store_true",
        help="include non-conventional commits under 'Other Changes'",
    )
    p_cl.set_defaults(func=_cmd_changelog)

    p_bump = sub.add_parser("bump", help="recommend the next semantic version")
    p_bump.add_argument("current", help="current version, e.g. v1.2.3")
    p_bump.add_argument("-i", "--input", help="log file (default: stdin)")
    p_bump.set_defaults(func=_cmd_bump)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError) as exc:
        print(f"{TOOL_NAME}: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
