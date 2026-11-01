"""Split long lines so a scanner can read them without giving up SecurityLens's regex protection.

SecurityLens._armor empties any line of 250 or more characters, which keeps its patterns from backtracking on minified
files and is why the engine's numbers are stable. For a tool hunting one thing, a blank line is a blind spot: an AWS key
on a 509-character minified line passed Vault Sentinel (#7179). Cutting the line into short overlapping pieces keeps
every piece under the armor's limit, and the overlap keeps a value from being cut in two. The engine doesn't use this.
"""

from __future__ import annotations

CHUNK = 200  # under _armor's 250
OVERLAP = 80  # longer than any single token the scanners look for


def chunk_long_lines(text: str) -> str:
    """`text` with each line of 250+ characters replaced by overlapping pieces, one per line."""
    if not any(len(line) >= 250 for line in text.splitlines()):
        return text
    out: list[str] = []
    for line in text.splitlines():
        if len(line) < 250:
            out.append(line)
        else:
            out.extend(line[i : i + CHUNK] for i in range(0, len(line), CHUNK - OVERLAP))
    return "\n".join(out)
