"""#8411: the compile-listing / expanded-copy test the CICS census (#8112) and the feature inventory share."""

import re
from itertools import pairwise
from pathlib import Path

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
