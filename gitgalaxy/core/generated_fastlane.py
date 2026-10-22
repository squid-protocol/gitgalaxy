"""Generated-file fast lane (#3188).

A machine-generated preprocessor table (darwin-xnu's `AvailabilityInternal.h`: 2.6 MB, 23k near-identical
`#define` / `#if` lines) spent ~2 s in the Security Lens, which cannot find anything in it. The Security Lens
scans the whole text; its hits come from line content, so a file whose lines repeat the same few shapes needs
each shape scanned once. `clean_directive_table_scan` recognises that file with a bounded, linear,
ReDoS-proof gate, runs the REAL lens over one line per distinct shape, and returns that scan only when it is
clean. The worker then uses it in place of the whole-file scan (same zero-count keys, no snippets), so the
output is identical and a file that does carry a finding (a `#if 0`, a call to `system`) stays on the full lane.
The detector is not skipped: its signals feed the risk scores and the file's place in the graph.
"""

import re
from typing import Any

# Only the C preprocessor dialects: `#if`-style lines are comments in shell / python / ruby.
FASTLANE_LANGS = frozenset({"c", "cpp", "objective-c"})

# Below this size the full lane is cheap and the gate is not worth the risk.
MIN_BYTES = 256 * 1024

# Share of non-blank lines that must be bare directives (slack for banner comments and `#include "x"`).
MIN_DIRECTIVE_RATIO = 0.95

# One directive per line, no quote / brace / semicolon / line-continuation in it. Possessive `*+` keeps a
# failing line linear.
_DIRECTIVE_LINE = re.compile(
    r"^[ \t]*#[ \t]*(?:define|undef|if|ifdef|ifndef|elif|else|endif|include|error|pragma)\b[^\"'{};\\\n]*+$",
    re.MULTILINE,
)
_NON_BLANK_LINE = re.compile(r"^[ \t]*\S", re.MULTILINE)


# Digit runs are what differs between rows of a generated table (`MAC_10_4` / `MAC_10_5`).
_DIGITS = re.compile(r"\d+")

# More distinct shapes than this share of the lines means the file is not repetitive.
MAX_SHAPE_RATIO = 0.25


def clean_directive_table_scan(content: str, lang_id: str, size_bytes: int, security: Any) -> dict[str, Any] | None:
    """The Security Lens result for `content` when it is a large, repetitive, bare-directive table and the
    lens finds nothing in any of its line shapes; None when the full lane must run."""
    if lang_id not in FASTLANE_LANGS or size_bytes < MIN_BYTES or not content.isascii():
        return None
    non_blank = sum(1 for _ in _NON_BLANK_LINE.finditer(content))
    if not non_blank:
        return None
    directives = sum(1 for _ in _DIRECTIVE_LINE.finditer(content))
    if directives < non_blank * MIN_DIRECTIVE_RATIO:
        return None
    shapes = {_DIGITS.sub("0", line) for line in content.splitlines() if line.strip()}
    if len(shapes) > non_blank * MAX_SHAPE_RATIO:
        return None
    sample = "\n".join(sorted(shapes)) + "\n"
    scan: dict[str, Any] = security.scan_content(sample, code_stream=sample, prose=False)
    if any(scan["counts"].values()):
        return None
    return scan
