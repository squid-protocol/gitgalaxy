#!/usr/bin/env python3
"""
Content-keyed baseline keys shared by tests/ruff_audit.py and tests/mypy_audit.py (#3384).

WHY
Both audits used to key baseline entries as `{file}:{line}: {code}`. Line numbers
are not stable: an unrelated insertion earlier in a file shifts every finding below
it, so the baseline changed (and conflicted on rebase) even though nothing
lint-relevant changed. Rebases repeatedly had to hand-fix moved entries.

KEY SCHEME
    "{file}: {code} @{hash}#{occurrence}"

  - `file`       repo-relative POSIX path (always first, so `key.split(":", 1)[0]`
                 is still the file -- rebase_rebless.py relies on that).
  - `code`       the rule code (ruff) / error code (mypy).
  - `hash`       first 12 hex chars of sha256 over the flagged source line with ALL
                 whitespace removed (see normalize_line), so reindenting or
                 re-spacing the line doesn't change it either.
  - occurrence   0-based index among findings sharing the same (file, code, hash),
                 in source order (line, then column). Two identical violating lines
                 in one file get #0 and #1, so a NEW duplicate of a baselined line
                 produces an unbaselined #1 and is still caught; it also means two
                 findings of the same code on the same line no longer collapse into
                 one entry the way the old line-number key did.

The line number is deliberately NOT part of the key; it's carried alongside each
current finding (Finding.line) purely so human-readable output can still point at
where the finding is now.
"""

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Callable, NamedTuple

HASH_LEN = 12


class Finding(NamedTuple):
    file: str  # repo-relative POSIX path
    line: int  # 1-based; 0 if the tool gave no location
    column: int  # 1-based; 0 if unknown
    code: str
    message: str


def normalize_line(text: str) -> str:
    """Strips ALL whitespace, so indentation/spacing-only edits don't change a key."""
    return "".join(text.split())


def line_hash(text: str) -> str:
    return hashlib.sha256(normalize_line(text).encode("utf-8")).hexdigest()[:HASH_LEN]


def format_key(file: str, code: str, digest: str, occurrence: int) -> str:
    return f"{file}: {code} @{digest}#{occurrence}"


def parse_key(key: str) -> tuple[str, str, str, int]:
    """Inverse of format_key: returns (file, code, hash, occurrence)."""
    file_part, _, rest = key.partition(": ")
    code_part, _, tail = rest.rpartition(" @")
    digest, _, occurrence = tail.partition("#")
    return file_part, code_part, digest, int(occurrence or 0)


def source_reader(repo_root: Path) -> Callable[[str, int], str]:
    """Returns read(file, line) -> that source line's text ("" if unavailable), caching each file."""
    cache: dict[str, list[str]] = {}

    def read(rel_path: str, line: int) -> str:
        if rel_path not in cache:
            try:
                cache[rel_path] = (repo_root / rel_path).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                cache[rel_path] = []
        lines = cache[rel_path]
        return lines[line - 1] if 1 <= line <= len(lines) else ""

    return read


def key_findings(findings: Iterable[Finding], read_line: Callable[[str, int], str]) -> dict[str, Finding]:
    """Assigns each finding its content key. Deterministic: occurrence indexes follow source order."""
    ordered = sorted(findings, key=lambda f: (f.file, f.line, f.column, f.code, f.message))
    seen: dict[tuple[str, str, str], int] = {}
    keyed: dict[str, Finding] = {}
    for finding in ordered:
        digest = line_hash(read_line(finding.file, finding.line))
        triple = (finding.file, finding.code, digest)
        occurrence = seen.get(triple, 0)
        seen[triple] = occurrence + 1
        keyed[format_key(finding.file, finding.code, digest, occurrence)] = finding
    return keyed


def to_baseline(keyed: dict[str, Finding]) -> dict[str, str]:
    """The committed baseline shape: {key: message} -- no line numbers, so line shifts don't touch it."""
    return {key: finding.message for key, finding in keyed.items()}


def dump_baseline(baseline: dict[str, str]) -> str:
    """Canonical serialization (sorted, 2-space indent, trailing newline) -- byte-identical on regenerate."""
    return json.dumps(baseline, indent=2, sort_keys=True) + "\n"


def write_baseline(path: Path, baseline: dict[str, str]) -> None:
    path.write_text(dump_baseline(baseline), encoding="utf-8")


def load_baseline(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def describe(key: str, finding: Finding) -> str:
    """Human-readable line for a CURRENT finding: current location first, stable key after."""
    return f"{finding.file}:{finding.line}: {finding.code}  -- {finding.message}  [{key}]"
