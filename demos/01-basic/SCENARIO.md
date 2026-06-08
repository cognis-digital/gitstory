# Demo 01 - Basic changelog from a release range

This demo shows GITSTORY turning a range of conventional commits into release
notes and a recommended version bump.

## The input

`commits.log` is the structured form GITSTORY consumes natively. In a real
repo you produce it with:

```sh
git log --format='%H%x1f%s%x1f%b%x1e' v1.4.0..HEAD > commits.log
```

Each record is one commit: full SHA, subject, and body, separated by ASCII
unit separators, records ended by an ASCII record separator. This preserves
multi-line bodies (including `BREAKING CHANGE:` footers) that a plain
line-per-commit dump would mangle.

## Run it

Markdown release notes (table view) with a bump recommendation:

```sh
python -m gitstory changelog --input demos/01-basic/commits.log \
    --tag v1.5.0 --date 2026-06-08 --current v1.4.0
```

Machine-readable JSON for CI:

```sh
python -m gitstory --format json changelog \
    --input demos/01-basic/commits.log --current v1.4.0
```

Just the version recommendation:

```sh
python -m gitstory bump v1.4.0 --input demos/01-basic/commits.log
```

## What to expect

- A `feat` commit and a `feat!` (breaking) are present, so the recommended
  bump from `v1.4.0` is **major -> v2.0.0**.
- Commits are grouped under Features, Bug Fixes, Performance, Documentation.
- The breaking change is surfaced in a dedicated `BREAKING CHANGES` block
  using its `BREAKING CHANGE:` footer text.
- Scopes (e.g. `auth`, `api`) are bolded inline.
