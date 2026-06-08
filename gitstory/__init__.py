"""GITSTORY - Changelog and release notes from conventional commits.

A zero-install, standard-library-only tool that parses conventional commit
messages (https://www.conventionalcommits.org) and renders grouped changelogs
or release notes, in the spirit of git-cliff.
"""
from .core import (
    Commit,
    ReleaseSection,
    parse_commit,
    parse_log,
    group_commits,
    bump_version,
    render_markdown,
    build_changelog,
    TYPE_HEADINGS,
)

TOOL_NAME = "gitstory"
TOOL_VERSION = "1.0.0"

__all__ = [
    "Commit",
    "ReleaseSection",
    "parse_commit",
    "parse_log",
    "group_commits",
    "bump_version",
    "render_markdown",
    "build_changelog",
    "TYPE_HEADINGS",
    "TOOL_NAME",
    "TOOL_VERSION",
]
