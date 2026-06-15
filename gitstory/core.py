"""Core engine for GITSTORY.

Parses conventional commits and produces grouped changelog data plus
semantic-version bump recommendations. No external dependencies.

Conventional commit grammar handled:
    <type>[optional scope][!]: <description>
    [blank line]
    [body]
    [blank line]
    [footer(s) e.g. "BREAKING CHANGE: ..."]

A git log is consumed as records separated by a NUL-style record separator so
that multi-line bodies survive intact. We use the ASCII Record Separator
(\x1e) between commits and Unit Separator (\x1f) between fields, matching what
`git log --format="%H%x1f%s%x1f%b%x1e"` would emit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

RECORD_SEP = "\x1e"
FIELD_SEP = "\x1f"

# Ordered mapping of conventional types -> human headings.
TYPE_HEADINGS: Dict[str, str] = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "perf": "Performance",
    "refactor": "Refactoring",
    "docs": "Documentation",
    "test": "Tests",
    "build": "Build System",
    "ci": "Continuous Integration",
    "style": "Styles",
    "chore": "Chores",
    "revert": "Reverts",
}

# type(scope)!: description
_HEADER_RE = re.compile(
    r"^(?P<type>[a-zA-Z]+)"
    r"(?:\((?P<scope>[^()]+)\))?"
    r"(?P<bang>!)?"
    r":\s*(?P<desc>.+?)\s*$"
)
_BREAKING_FOOTER_RE = re.compile(r"^BREAKING[ -]CHANGE:\s*(?P<text>.+)$", re.MULTILINE)


@dataclass
class Commit:
    """A single parsed commit."""

    sha: str
    type: Optional[str]
    scope: Optional[str]
    description: str
    breaking: bool = False
    breaking_desc: Optional[str] = None
    body: str = ""
    conventional: bool = True

    @property
    def short_sha(self) -> str:
        return self.sha[:7] if self.sha else ""

    def to_dict(self) -> dict:
        return {
            "sha": self.sha,
            "short_sha": self.short_sha,
            "type": self.type,
            "scope": self.scope,
            "description": self.description,
            "breaking": self.breaking,
            "breaking_desc": self.breaking_desc,
            "conventional": self.conventional,
        }


@dataclass
class ReleaseSection:
    """A heading plus its commits in the changelog."""

    key: str
    heading: str
    commits: List[Commit] = field(default_factory=list)


def parse_commit(subject: str, body: str = "", sha: str = "") -> Commit:
    """Parse a single commit subject/body into a Commit."""
    subject = (subject or "").strip()
    body = body or ""
    m = _HEADER_RE.match(subject)
    if not m:
        # Non-conventional commit: keep it but flag it.
        return Commit(
            sha=sha,
            type=None,
            scope=None,
            description=subject,
            body=body.strip(),
            conventional=False,
        )

    ctype = m.group("type").lower()
    scope = m.group("scope")
    bang = bool(m.group("bang"))
    desc = m.group("desc").strip()

    breaking_desc = None
    fm = _BREAKING_FOOTER_RE.search(body)
    if fm:
        breaking_desc = fm.group("text").strip()
    breaking = bang or breaking_desc is not None
    if bang and breaking_desc is None:
        breaking_desc = desc

    return Commit(
        sha=sha,
        type=ctype,
        scope=scope,
        description=desc,
        breaking=breaking,
        breaking_desc=breaking_desc,
        body=body.strip(),
        conventional=True,
    )


def parse_log(text: str) -> List[Commit]:
    """Parse a raw git log string into Commit objects.

    Supports two formats:
      1. Structured: records separated by \\x1e, fields (sha, subject, body)
         separated by \\x1f -- i.e. `git log --format='%H%x1f%s%x1f%b%x1e'`.
      2. Plain: one commit subject per line (sha omitted). Useful for piping
         `git log --format='%s'` or hand-written changelog input.
    """
    text = text or ""
    commits: List[Commit] = []

    if RECORD_SEP in text or FIELD_SEP in text:
        for raw in text.split(RECORD_SEP):
            raw = raw.strip("\n")
            if not raw.strip():
                continue
            parts = raw.split(FIELD_SEP)
            sha = parts[0].strip() if len(parts) > 0 else ""
            subject = parts[1].strip() if len(parts) > 1 else ""
            body = parts[2] if len(parts) > 2 else ""
            if not subject and not sha:
                continue
            commits.append(parse_commit(subject, body, sha))
        return commits

    # Plain one-line-per-commit fallback.
    for line in text.splitlines():
        if not line.strip():
            continue
        commits.append(parse_commit(line.strip()))
    return commits


def group_commits(
    commits: List[Commit], include_unconventional: bool = False
) -> Tuple[List[ReleaseSection], List[Commit]]:
    """Group commits by type into ordered ReleaseSections.

    Returns (sections, breaking_commits). Breaking changes are surfaced both
    in their type section and in a dedicated breaking list.
    """
    buckets: Dict[str, List[Commit]] = {}
    other: List[Commit] = []
    breaking: List[Commit] = []

    for c in commits:
        if c.breaking:
            breaking.append(c)
        if c.type in TYPE_HEADINGS:
            buckets.setdefault(c.type, []).append(c)
        elif c.type is not None:
            # Known-shaped but unmapped type -> treat under "Other".
            other.append(c)
        elif include_unconventional:
            other.append(c)

    sections: List[ReleaseSection] = []
    for key, heading in TYPE_HEADINGS.items():
        if buckets.get(key):
            sections.append(ReleaseSection(key=key, heading=heading, commits=buckets[key]))
    if other:
        sections.append(ReleaseSection(key="other", heading="Other Changes", commits=other))
    return sections, breaking


def _parse_semver(version: str) -> Tuple[int, int, int, str]:
    """Parse a (possibly v-prefixed) semver into (major, minor, patch, prefix)."""
    prefix = ""
    v = version.strip()
    if v[:1].lower() == "v":
        prefix = v[0]
        v = v[1:]
    # Drop any pre-release / build metadata for bumping math.
    core = re.split(r"[-+]", v, 1)[0]
    nums = core.split(".")
    while len(nums) < 3:
        nums.append("0")
    try:
        major, minor, patch = (int(nums[0]), int(nums[1]), int(nums[2]))
    except ValueError:
        raise ValueError(f"invalid semantic version: {version!r}")
    return major, minor, patch, prefix


def bump_version(current: str, commits: List[Commit]) -> Tuple[str, str]:
    """Recommend the next version from commit contents.

    Rules (semver): any breaking change -> major; any feat -> minor;
    any fix/perf -> patch; otherwise no bump (still returns patch label).
    Returns (new_version, bump_level).
    """
    major, minor, patch, prefix = _parse_semver(current)

    has_breaking = any(c.breaking for c in commits)
    has_feat = any(c.type == "feat" for c in commits)
    has_patch = any(c.type in ("fix", "perf") for c in commits)

    if has_breaking and major > 0:
        major, minor, patch = major + 1, 0, 0
        level = "major"
    elif has_breaking and major == 0:
        # 0.x: breaking bumps minor per semver convention.
        minor, patch = minor + 1, 0
        level = "minor"
    elif has_feat:
        minor, patch = minor + 1, 0
        level = "minor"
    elif has_patch:
        patch += 1
        level = "patch"
    else:
        patch += 1
        level = "none"

    return f"{prefix}{major}.{minor}.{patch}", level


def _fmt_commit_line(c: Commit) -> str:
    scope = f"**{c.scope}:** " if c.scope else ""
    sha = f" ({c.short_sha})" if c.short_sha else ""
    return f"- {scope}{c.description}{sha}"


def render_markdown(
    version: str,
    sections: List[ReleaseSection],
    breaking: List[Commit],
    date: Optional[str] = None,
) -> str:
    """Render a markdown changelog block for a single release."""
    header = f"## {version}"
    if date:
        header += f" - {date}"
    lines: List[str] = [header, ""]

    if breaking:
        lines.append("### ⚠ BREAKING CHANGES")
        lines.append("")
        for c in breaking:
            text = c.breaking_desc or c.description
            scope = f"**{c.scope}:** " if c.scope else ""
            sha = f" ({c.short_sha})" if c.short_sha else ""
            lines.append(f"- {scope}{text}{sha}")
        lines.append("")

    for sec in sections:
        lines.append(f"### {sec.heading}")
        lines.append("")
        for c in sec.commits:
            lines.append(_fmt_commit_line(c))
        lines.append("")

    if not breaking and not sections:
        lines.append("_No notable changes._")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_changelog(
    log_text: str,
    version: str = "Unreleased",
    date: Optional[str] = None,
    include_unconventional: bool = False,
    current_version: Optional[str] = None,
) -> dict:
    """End-to-end: parse a log and return a structured result dict."""
    commits = parse_log(log_text)
    sections, breaking = group_commits(commits, include_unconventional)

    recommended = None
    bump_level = None
    if current_version:
        recommended, bump_level = bump_version(current_version, commits)

    markdown = render_markdown(version, sections, breaking, date)

    return {
        "version": version,
        "date": date,
        "total_commits": len(commits),
        "conventional_commits": sum(1 for c in commits if c.conventional),
        "breaking_changes": len(breaking),
        "recommended_version": recommended,
        "bump_level": bump_level,
        "sections": [
            {
                "key": s.key,
                "heading": s.heading,
                "commits": [c.to_dict() for c in s.commits],
            }
            for s in sections
        ],
        "breaking": [c.to_dict() for c in breaking],
        "markdown": markdown,
    }
