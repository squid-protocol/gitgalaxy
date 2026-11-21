"""#8411: the compile-listing / expanded-copy test the CICS census (#8112) and the feature inventory share."""

import re
from itertools import pairwise
from pathlib import Path

from gitgalaxy.core.cobol_source_format import line_formats

LISTING_DIRS = {"expanded", "listing", "listings", "lst", "sysprint", "precomp", "precompiled", "translated"}
LISTING_NAME = re.compile(r"(?:^|[._-])(?:lst|list|listing|sysprint|expanded)(?:[._-]|$)", re.I)
# banners a compiler or a precompiler prints into its listing, and the statements a CICS translator inserts
LISTING_MARKERS = (
    "PP 5655-", "PP 5648-", "PP 5668-", "IBM COBOL FOR", "COBOL FOR Z/OS", "ENTERPRISE COBOL FOR", "LINEID  PL SL",
    "DB2 SQL PRECOMPILER", "COMPILER OPTIONS", "END OF COMPILATION", "CALL 'DFHEI1'", "DFHEIGBL", "DFHEIVAR",
)  # fmt: skip
_LISTING_NUMBER = re.compile(r"^ {1,5}(\d{1,5}) +\S")  # a zero-padded or full 6-digit sequence area never matches
LISTING_NUMBER_MIN_LINES = 20
CONSECUTIVE_NUMBER_MIN_LINES = (
    8  # #8412: a banner-less short listing numbers every line 1, 2, 3 ... (level numbers never do)
)


def listing_reason(text: str, rel_parts: tuple[str, ...] = ()) -> str | None:
    """#8112: why `text` at `rel_parts` is a compile listing, an expanded copy or translator output and no program
    (None: a program). A path shape (a hidden or listing directory, a `.lst` / `sysprint` name), a banner or translator
    marker, or space-padded listing line numbers (a zero-padded sequence area is a real program's and never counts)."""
    dirs, name = rel_parts[:-1], rel_parts[-1] if rel_parts else ""
    if any(d.startswith(".") for d in dirs):
        return "hidden directory (compile-listing copies, COPY already inlined)"
    if any(d.lower() in LISTING_DIRS for d in dirs) or LISTING_NAME.search(Path(name).stem):
        return "listing path (directory or file name)"
    code = text.upper()
    if any(m in code for m in LISTING_MARKERS):
        return "compiler listing or translator output (banner or inserted statements)"
    lines = [ln for ln in text.replace("\r", "").split("\n") if ln.strip()]
    nums = [int(m.group(1)) for m in (_LISTING_NUMBER.match(ln) for ln in lines) if m]
    dense = (
        len(lines) >= LISTING_NUMBER_MIN_LINES and len(nums) >= 0.9 * len(lines) and max(nums) > 49
    )  # not level numbers
    if dense and sum(b > a for a, b in pairwise(nums)) >= 0.9 * (len(nums) - 1):
        return "listing line numbers (space-padded, increasing)"
    # #8412: a short plain listing (no banner, no listing path): every line numbered, one step each
    steps = [b - a for a, b in pairwise(nums)]
    if (
        len(lines) >= CONSECUTIVE_NUMBER_MIN_LINES
        and len(nums) >= 0.9 * len(lines)
        and steps
        and sum(s == 1 for s in steps) >= 0.9 * len(steps)
    ):
        return "listing line numbers (space-padded, consecutive)"
    return None


def source_lines(text: str) -> list[tuple[str, str]]:
    """(format, line) per line: each line's reference format (fixed / free / variable, `>>SOURCE FORMAT` switches
    followed, #4264) beside the line itself. #5089: the one place a fact scan learns the columns."""
    lines = text.replace("\r", "").split("\n")
    if lines and lines[-1] == "":  # the newline ending the file starts no line
        lines.pop()
    return list(zip(line_formats("\n".join(lines)), lines, strict=False))


def fixed_format_text(text: str) -> str:
    """The program's code area, upper-cased and joined: columns 8-72 of a fixed line (to the end of a variable one),
    the whole of a free line; comment lines (column-7 `*` or `/`, free `*>`) dropped. #5089: format-aware."""
    out = []
    for fmt, ln in source_lines(text):
        if fmt == "free":
            if not ln.lstrip().startswith("*>"):
                out.append(ln)
            continue
        if len(ln) > 6 and ln[6] in "*/":
            continue
        out.append(ln[6:] if fmt == "variable" else ln[6:72] if len(ln) > 6 else "")
    return " ".join(out).upper()


def program_id(text: str) -> str | None:
    """The upper-cased PROGRAM-ID of a program (fixed or free format), or None."""
    m = re.search(r"\bPROGRAM-ID\s*\.?\s+([A-Z0-9_$#@-]+)", fixed_format_text(text))
    return m.group(1) if m else None


# #8412: a change-management tree (Endevor, ChangeMan) holds one member per stage; the production stage is the program
PRODUCTION_STAGES = {"prod", "prd", "production", "live"}


def _is_production_path(path: str) -> bool:
    return any(d.lower() in PRODUCTION_STAGES for d in path.replace("\\", "/").split("/")[:-1])


def duplicate_reasons(texts: dict[str, str]) -> dict[str, str]:
    """#8112: path -> reason for every program whose PROGRAM-ID another path already has in this estate; `exact` when
    the normalised code is equal, `near` otherwise. One path per PROGRAM-ID stays the program: the first one under a
    production stage directory (PROD / PRD / PRODUCTION / LIVE, #8412), else the first in sorted order."""
    groups: dict[str, list[str]] = {}
    for path in sorted(texts):
        pid = program_id(texts[path])
        if pid is not None:
            groups.setdefault(pid, []).append(path)
    out: dict[str, str] = {}
    for paths in groups.values():
        keep = next((p for p in paths if _is_production_path(p)), paths[0])
        keep_code = " ".join(fixed_format_text(texts[keep]).split())
        for path in paths:
            if path == keep:
                continue
            same = " ".join(fixed_format_text(texts[path]).split()) == keep_code
            out[path] = f"duplicate PROGRAM-ID ({'exact' if same else 'near'} copy of another program in the estate)"
    return out
