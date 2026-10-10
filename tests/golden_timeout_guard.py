"""Detect files a regex timeout pushed into the excluded queue (#4247).

Under heavy machine load a per-file regex timeout moves a file from the parsed set to
`5. Unparsable Artifacts (Excluded Artifacts Queue)` (reasons "Unparsable (Structural
Saturation / Global Regex Timeout)" and "Thread Timeout (Regex ReDoS)" in galaxyscope.py).
Blessing, or checking, in that state records the file as excluded and every one of its rows
as a phantom diff (2,911 of them on #4227 at load average 42). No committed golden master
holds a timeout exclusion, so any one in a run is a load artifact: bless and check refuse.
"""

from __future__ import annotations

import os
import re
from typing import Any
from collections.abc import Mapping

EXCLUDED_QUEUE_KEY = "5. Unparsable Artifacts (Excluded Artifacts Queue)"
_TIMEOUT_REASON = re.compile(r"time[\s-]*out|timed[\s-]*out", re.IGNORECASE)

# Explicit override for a bless whose timeouts are understood and intended.
FORCE_ENV = "GITGALAXY_GOLDEN_ALLOW_TIMEOUTS"


def timeout_exclusions(audit: Mapping[str, Any]) -> list[tuple[str, str]]:
    """`(path, reason)` for every excluded-queue entry whose reason is timeout-class."""
    queue = audit.get(EXCLUDED_QUEUE_KEY) or []
    found = []
    for entry in queue:
        if not isinstance(entry, Mapping):
            continue
        reason = str(entry.get("Diagnostic Reason", ""))
        if _TIMEOUT_REASON.search(reason):
            found.append((str(entry.get("Path", "?")), reason))
    return found


def refusal_message(exclusions: list[tuple[str, str]], action: str, load: float | None = None) -> str:
    """The text a refusing bless/check prints: which files, and what to do about it."""
    if load is None:
        try:
            load = os.getloadavg()[0]
        except (AttributeError, OSError):
            load = None
    shown = "\n".join(f"  - {path}  [{reason}]" for path, reason in exclusions[:25])
    more = f"\n  ... and {len(exclusions) - 25} more" if len(exclusions) > 25 else ""
    load_note = f" (load average now: {load:.1f})" if load is not None else ""
    return (
        f"Regex timeout exclusion: {len(exclusions)} file(s) were excluded by a timeout in this run, "
        f"so the golden {action} would record phantom diffs for them (#4247):\n{shown}{more}\n\n"
        f"This is a load artifact, not a code change. Rerun on a quieter machine{load_note}: "
        "wait for load to drop, and run it under tests/tools/box/golden-lock.sh. "
        f"To bless anyway, deliberately, set {FORCE_ENV}=1 (or pass --allow-timeouts)."
    )


def forced() -> bool:
    return os.environ.get(FORCE_ENV) == "1"
