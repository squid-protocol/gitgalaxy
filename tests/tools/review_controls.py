#!/usr/bin/env python3
"""Review-layer controls (#7155, part 3): realistic diffs that hide one defect no mechanical gate catches.

`canary_control.py` plants defects a gate must turn red. Gates catch rules; a reviewer catches judgement, and the
defects below are the judgement kind: a swallowed exception, a test that cannot fail, a check that is green by skipping.
Each one passes lint, format and the suite, so only a reader can object. Every defect has a clean twin of the same shape
(a feature plus its test, new files only) to measure false alarms.

    python tests/tools/review_controls.py list                 # keys and classes
    python tests/tools/review_controls.py packet KEY           # what a reviewer sees: title, body, diff, nothing else
    python tests/tools/review_controls.py key KEY              # the answer key (never shown to a reviewer)

The reviewer must not know a diff is a control, so a packet carries no key, class or marker, and `problems()` fails a
catalog whose visible text names the experiment. This module only authors and proves the set; running a Sonnet or Opus
review over it is the next checklist item (experiment lane, owner OK). Inert: new files, no network, no subprocess,
no secret, nothing under `.github/` or a release path. Stdlib only.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

FORBIDDEN_PREFIXES = (".github/", "release/", "dist/", ".claude/")
FORBIDDEN_NAMES = ("pyproject.toml", ".env", "publish.yml")
# Words a reviewer must never see: they would tell it this diff is part of an experiment.
LEAKY = re.compile(r"canary|planted|control|defect|experiment|7155|\bbait\b|\btrap\b|on purpose", re.IGNORECASE)
# Code the catalog never ships: a control is inert.
UNSAFE = re.compile(
    r"\b(?:subprocess|socket|urllib|requests|http\.client|os\.system|eval|exec|secret|token|password)\b"
)


@dataclass(frozen=True)
class Control:
    key: str
    cls: str  # the defect class a reviewer should name
    twin: str  # key of the clean twin ("" for a twin itself)
    title: str
    body: str
    module: str  # path of the feature module
    test: str  # path of its test file
    module_src: str
    test_src: str
    where: str  # the line (a substring of a changed line) the defect lives on; "" for a twin
    what: str  # what a good review says
    mutation: tuple[str, str] = ("", "")  # (old, new) applied to the module: tests that cannot fail stay green

    @property
    def files(self) -> dict[str, str]:
        return {self.module: self.module_src, self.test: self.test_src}


_BUDGET = '''"""Parse the retry budget a job file declares."""


def parse_budget(text: str) -> int:
    """Return the number of retries a job may spend; a negative value means none."""
    try:
        value = int(text.strip())
    except Exception:
        return 0
    return max(value, 0)
'''
_BUDGET_TWIN = '''"""Parse the retry budget a job file declares."""


def parse_budget(text: str) -> int:
    """Return the number of retries a job may spend; a negative value means none."""
    try:
        value = int(text.strip())
    except ValueError as exc:
        raise ValueError(f"retry budget is not a whole number: {text!r}") from exc
    return max(value, 0)
'''
_BUDGET_TEST = """import pytest

from {mod} import parse_budget


@pytest.mark.parametrize("text, expected", [("3", 3), (" 7 ", 7), ("-2", 0), ("0", 0)])
def test_parse_budget_reads_whole_numbers(text, expected):
    assert parse_budget(text) == expected
"""
_BUDGET_TEST_TWIN = (
    _BUDGET_TEST
    + """

def test_parse_budget_refuses_text_that_is_not_a_number():
    with pytest.raises(ValueError, match="not a whole number"):
        parse_budget("three")
"""
)

_SLUG = '''"""Turn a display name into a file-name slug."""

import re


def slugify(name: str) -> str:
    """Lowercase the name and join its words with single dashes."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
'''
_SLUG_TEST = """from {mod} import slugify


def _expected(name: str) -> str:
    return slugify(name)


def test_slugify_lowercases_and_joins_words():
    result = slugify("Hello  World")
    assert result == _expected("Hello  World")


def test_slugify_trims_the_ends():
    result = slugify("--Edge--")
    assert result == _expected("--Edge--")
"""
_SLUG_TEST_TWIN = """from {mod} import slugify


def test_slugify_lowercases_and_joins_words():
    assert slugify("Hello  World") == "hello-world"


def test_slugify_trims_the_ends():
    assert slugify("--Edge--") == "edge"
"""

_LINES = '''"""Count the non-blank lines of a text."""


def count_lines(text: str) -> int:
    """Return how many lines of the text hold something besides whitespace."""
    return sum(1 for line in text.splitlines() if line.strip())
'''
_LINES_TEST = """import os

import pytest

from {mod} import count_lines


@pytest.mark.skipif(not os.environ.get("LINE_COUNT_FIXTURES"), reason="needs the shared fixtures")
def test_count_lines_ignores_blank_lines():
    assert count_lines("a\\n\\n  \\nb\\n") == 2


def test_count_lines_of_nothing_is_zero():
    assert count_lines("") == 0
"""
_LINES_TEST_TWIN = """from {mod} import count_lines


def test_count_lines_ignores_blank_lines():
    assert count_lines("a\\n\\n  \\nb\\n") == 2


def test_count_lines_of_nothing_is_zero():
    assert count_lines("") == 0
"""


def _pair(
    key: str,
    cls: str,
    stem: str,
    title: str,
    body: str,
    src: tuple[str, str],
    test: tuple[str, str],
    where: str,
    what: str,
    mutation: tuple[str, str] = ("", ""),
) -> tuple[Control, Control]:
    """A defective control and its clean twin: same paths, same title and body, only the hidden line differs."""
    mod, tst = f"tests/tools/{stem}.py", f"tests/tools/test_{stem}.py"
    common = dict(module=mod, test=tst, title=title, body=body, mutation=mutation)
    bad = Control(key, cls, f"{key}-clean", test_src=test[0].replace("{mod}", stem), module_src=src[0], where=where,
                  what=what, **common)  # fmt: skip
    good = Control(f"{key}-clean", "", "", test_src=test[1].replace("{mod}", stem), module_src=src[1], where="",
                   what="nothing is wrong", **common)  # fmt: skip
    return bad, good


CONTROLS = (
    *_pair(
        "swallow",
        "swallowed-exception",
        "retry_budget",
        "Read the retry budget from a job file",
        "Jobs declare how many retries they may spend. This adds the parser and its table test.\n",
        (_BUDGET, _BUDGET_TWIN),
        (_BUDGET_TEST, _BUDGET_TEST_TWIN),
        "except Exception:",
        "a broad except turns text that is not a number into a budget of 0, so a typo silently disables retries",
    ),
    *_pair(
        "vacuous",
        "test-that-cannot-fail",
        "name_slugs",
        "Add a slug helper for report file names",
        "Report names are lowercased and dash-joined. Adds `slugify` with two tests.\n",
        (_SLUG, _SLUG),
        (_SLUG_TEST, _SLUG_TEST_TWIN),
        "assert result == _expected(",
        "the expected value is computed by the function under test, so the assertions hold for any implementation",
        (".lower()", ""),
    ),
    *_pair(
        "skipped",
        "green-by-skipping",
        "line_counts",
        "Count non-blank lines for the size column",
        "A small helper for the size column, with two tests.\n",
        (_LINES, _LINES),
        (_LINES_TEST, _LINES_TEST_TWIN),
        "@pytest.mark.skipif(",
        "the only test of the blank-line rule is skipped unless an environment variable that CI never sets is present",
        ("if line.strip()", "if line"),
    ),
)

BY_KEY = {c.key: c for c in CONTROLS}


def problems(controls: tuple[Control, ...] = CONTROLS) -> list[str]:
    """Why a catalog is unsafe, leaky or lopsided: a path it must not touch, a word a reviewer must not see, a bad twin."""
    out: list[str] = []
    seen: set[str] = set()
    for c in controls:
        for path, src in c.files.items():
            norm = path.replace("\\", "/")
            if path in seen and c.cls:  # a twin shares its defect's paths by design
                out.append(f"{c.key}: {path} is shipped twice")
            if c.cls:
                seen.add(path)
            if norm.startswith("/") or ".." in norm.split("/"):
                out.append(f"{c.key}: {path} leaves the repo")
            if norm.startswith(FORBIDDEN_PREFIXES) or norm.rsplit("/", 1)[-1] in FORBIDDEN_NAMES:
                out.append(f"{c.key}: {path} is a workflow, release or secret path")
            if (REPO / path).exists():
                out.append(f"{c.key}: {path} already exists (a control is new files)")
            if UNSAFE.search(src):
                out.append(f"{c.key}: {path} uses something a control must not (network, process, secret)")
            if LEAKY.search(path + "\n" + src):
                out.append(f"{c.key}: {path} names the experiment")
        if LEAKY.search(c.title + "\n" + c.body):
            out.append(f"{c.key}: the title or body names the experiment")
        if c.twin:
            twin = next((t for t in controls if t.key == c.twin), None)
            if twin is None:
                out.append(f"{c.key}: its twin {c.twin!r} is missing")
            elif (twin.module, twin.test, twin.title, twin.body) != (c.module, c.test, c.title, c.body):
                out.append(f"{c.key}: its twin does not share paths, title and body")
            if not c.where or not any(c.where in line for src in c.files.values() for line in src.splitlines()):
                out.append(f"{c.key}: `where` names no line of the diff")
        elif c.cls:
            out.append(f"{c.key}: a defect with no clean twin")
        elif not any(d.twin == c.key for d in controls):
            out.append(f"{c.key}: a clean control no defect points at is an orphan")
    return out


def diff(c: Control) -> str:
    """The new-file diff of a control, in `git apply` form."""
    parts = []
    for path, src in sorted(c.files.items()):
        lines = src.splitlines(keepends=True)
        body = "".join(difflib.unified_diff([], lines, "/dev/null", f"b/{path}", n=0)).split("\n", 2)[2]
        parts.append(f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n{body}")
    return "".join(parts)


def reviewer_packet(c: Control) -> dict:
    """Exactly what a blind reviewer is shown: a title, a description and a diff. No key, class or marker."""
    return {"title": c.title, "body": c.body, "diff": diff(c)}


def answer_key(c: Control) -> dict:
    """The ground truth for scoring a review later: never shown to the reviewer."""
    path = next((p for p, src in c.files.items() if c.where and c.where in src), "")
    return {
        "key": c.key,
        "twin": c.twin,
        "defective": bool(c.cls),
        "class": c.cls,
        "file": path,
        "where": c.where,
        "what": c.what,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for name in ("packet", "key"):
        sub.add_parser(name).add_argument("key", choices=sorted(BY_KEY))
    args = ap.parse_args(argv)
    bad = problems()
    if bad:
        print("\n".join(bad), file=sys.stderr)
        return 1
    if args.cmd == "list":
        print(json.dumps([{"key": c.key, "class": c.cls or "clean twin"} for c in CONTROLS], indent=2))
    elif args.cmd == "packet":
        print(json.dumps(reviewer_packet(BY_KEY[args.key]), indent=2))
    else:
        print(json.dumps(answer_key(BY_KEY[args.key]), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
