# ==============================================================================
# GitGalaxy -- cobol_source_format: fixed / free reference format, per line (#4264)
# ==============================================================================
"""
COBOL source comes in two reference formats, and a reader must know which one a line is in:

    fixed     cols 1-6 sequence area, col 7 indicator, cols 8-72 program text, cols 73-80 an
              identification area the compiler ignores (NIST CCVS `IC2014.2`, `00220000`)
    free      program text anywhere on the line, any length; `*>` comments (GnuCOBOL `-free`,
              Micro Focus SOURCEFORMAT"FREE", Enterprise COBOL 6 `>>SOURCE FREE`)
    variable  fixed's areas without the column-72 limit (GnuCOBOL `>>SOURCE FORMAT VARIABLE`)

`line_formats` gives every line its format: the file's detected format, switched from the line
after each directive -- `>>SOURCE [FORMAT] [IS] FREE|FIXED|VARIABLE`, `>>FORMAT [IS] ...` and
Micro Focus `$SET SOURCEFORMAT"FREE"` / `SOURCEFORMAT(FIXED)`. `blank_identification_area` blanks
columns 73+ of the fixed lines only, offsets and line lengths kept: a free-format line that runs
past column 72 is program text, and cutting it there loses code.

Detection (no directive before the first line of code) votes over the lines, fixed by default --
the mainframe format, and the safe one: with no evidence either way nothing reaches column 73.

    free evidence   `*>` opening in cols 1-6; program text in cols 1-6 running into col 7
                    (`IDENTIFICATION DIVISION.` at column 1 -- a sequence area is followed by an
                    indicator or a blank); a word crossing the col 72 / 73 boundary; text past
                    column 80
    fixed evidence  a six-digit sequence area; an indicator (`*`, `/`, `-`, `D`) in col 7 behind a
                    blank or numbered sequence area; a token alone in cols 73-80 (an
                    identification area) with col 72 blank

The file is free when its free evidence outweighs its fixed evidence.
"""

from __future__ import annotations

import re

FIXED, FREE, VARIABLE = "fixed", "free", "variable"

# `>>SOURCE FORMAT IS FREE`, `>>SOURCE FREE`, `>>FORMAT FIXED`; the directive may sit in the sequence /
# indicator area of a fixed line (cols 1-7) or anywhere a free line starts.
_DIRECTIVE = re.compile(
    r"^[ \t0-9]{0,8}>>[ \t]*(?:SOURCE(?:[ \t]+FORMAT)?|FORMAT)(?:[ \t]+IS)?[ \t]+(FREE|FIXED|VARIABLE)\b",
    re.I,
)
# Micro Focus: `      $SET SOURCEFORMAT"FREE"`, `$SET SOURCEFORMAT(FIXED)`, `$SET SOURCEFORMAT 'VARIABLE'`.
_MF_DIRECTIVE = re.compile(
    r"^[ \t0-9]{0,8}\$[ \t]*SET\b[^\n]{0,200}?\bSOURCEFORMAT[ \t]*[\"'(][ \t]*(FREE|FIXED|VARIABLE)\b", re.I
)
_SEQUENCE_DIGITS = re.compile(r"[0-9]{6}")
_INDICATORS = frozenset("*/-dD")


def directive_format(line: str) -> str | None:
    """The format a source-format directive on `line` switches to, or None."""
    m = _DIRECTIVE.match(line) or _MF_DIRECTIVE.match(line)
    return m.group(1).lower() if m else None


def _vote(line: str) -> int:
    """+1 a line that only free format explains, -1 one that only fixed format does, else 0."""
    body = line.rstrip()
    if not body.strip():
        return 0
    head = body[:6]
    if "*>" in head:
        return 1
    if len(body) > 80:
        return 1
    if len(body) > 72:
        if body[71] not in " \t" and body[72] not in " \t":
            return 1  # a word crossing the boundary: program text, not an identification area
        if body[71] in " \t" and len(body[72:].split()) == 1:
            return -1  # one token alone in cols 73-80: an identification area
    if _SEQUENCE_DIGITS.fullmatch(head):
        return -1
    if len(body) >= 7 and head.strip() and body[6] not in " \t" and body[6] not in _INDICATORS:
        return 1  # cols 1-6 run straight into col 7: program text from column 1
    if len(body) >= 7 and body[6] in _INDICATORS and (not head.strip() or head.strip().isdigit()):
        return -1
    return 0


def detect_format(lines: list[str]) -> str:
    """The file's reference format before any directive: FREE when its free evidence outweighs its
    fixed evidence, else FIXED (the mainframe default)."""
    score = 0
    for line in lines:
        if directive_format(line):
            continue
        score += _vote(line)
    return FREE if score > 0 else FIXED


def line_formats(code_stream: str) -> list[str]:
    """Each line's format: the detected one, switched by a directive from the line after it."""
    lines = code_stream.split("\n")
    # A directive ahead of the first line of program text states the file's format outright.
    current = None
    for line in lines:
        fmt = directive_format(line)
        if fmt:
            current = fmt
            break
        if line.strip():
            break
    if current is None:
        current = detect_format(lines)
    out = []
    for line in lines:
        out.append(current)
        fmt = directive_format(line)
        if fmt:
            current = fmt
    return out


def blank_identification_area(code_stream: str, formats: list[str] | None = None) -> str:
    """`code_stream` with columns 73+ of its fixed-format lines blanked -- offsets and lengths kept.
    Free and variable lines keep their text past column 72. `formats` (line_formats of the raw
    source, comment lines included) may be passed when `code_stream` is that source with its
    comments already blanked line for line."""
    lines = code_stream.split("\n")
    if formats is None or len(formats) != len(lines):
        formats = line_formats(code_stream)
    for i, (line, fmt) in enumerate(zip(lines, formats, strict=True)):
        body = line.rstrip("\r")
        if fmt == FIXED and len(body) > 72 and body[72:].strip():
            lines[i] = body[:72] + " " * (len(body) - 72) + line[len(body) :]
    return "\n".join(lines)


# #4300: a numbered sequence area -- six letters/digits with at least one digit (ISPF
# `NUMBER ON STD` writes `000100`), never a space inside. Free-format text in cols 1-6
# (`   02  DELTA`, `EXEC S`) does not match, and neither does a level number.
_NUMBERED_SEQUENCE_AREA = re.compile(r"(?=[A-Za-z]{0,5}[0-9])[0-9A-Za-z]{6}")


def blank_sequence_area(code_stream: str, formats: list[str] | None = None) -> str:
    """`code_stream` with the numbered sequence area (cols 1-6) of its fixed-format lines blanked
    -- offsets and lengths kept. The area is not program text, but a verb whose operand starts on
    the next line (`PERFORM` / `000900     INIT-PARA`) read the sequence number as its operand.
    A debug line's col-7 `D` indicator behind an all-digit area is blanked too (`064000D   PASS.`
    is the operand `PASS`); a continuation `-` stays. Free and variable lines are left alone.
    `formats` as for `blank_identification_area`."""
    lines = code_stream.split("\n")
    if formats is None or len(formats) != len(lines):
        formats = line_formats(code_stream)
    for i, (line, fmt) in enumerate(zip(lines, formats, strict=True)):
        if fmt != FIXED or not _NUMBERED_SEQUENCE_AREA.match(line):
            continue
        indicator = line[6:7]
        if indicator in ("", " ", "\t", "-", "\r"):
            lines[i] = " " * 6 + line[6:]
        elif indicator in "Dd" and line[:6].isdigit():
            lines[i] = " " * 7 + line[7:]
    return "\n".join(lines)


# ------------------------------------------------------------------------------
# A saved ISPF editor screen is no COBOL source (#4735)
# ------------------------------------------------------------------------------
# What a 3270 ISPF edit panel puts on the screen, which a screen capture saved as `PROG.cbl` keeps: the menu bar, the
# `EDIT <dataset> Columns 00001 00072` title, the `Command ===>` / `Scroll ===>` line, the `****** ... Top of Data`
# and `Bottom of Data` banners, the `=COLS>` / `=BNDS>` / `=NOTE=` line commands. (A six-digit line number in front
# of every source line is an ordinary sequence area, so it is no marker.)
_ISPF_MARKERS = (
    ("menu bar", re.compile(r"^\s*File\s+Edit\s+Edit_Settings\s+Menu\b", re.I | re.M)),
    ("EDIT title", re.compile(r"^\s*EDIT\s+\S+.*\bColumns\s+\d{5}\s+\d{5}\b", re.I | re.M)),
    ("command line", re.compile(r"^\s*Command\s*={2,}>.*\bScroll\s*={2,}>", re.I | re.M)),
    ("data banner", re.compile(r"^\s*\*{6}\s+\*{5,}\s+(?:Top|Bottom)\s+of\s+Data\b", re.I | re.M)),
    ("ruler", re.compile(r"^\s*(?:=COLS>|=BNDS>|=NOTE=|=TABS>)", re.M)),
)


def ispf_screen(text: str) -> str | None:
    """#4735: why `text` is a saved ISPF editor screen rather than COBOL source (e.g. `menu bar, command line`), or
    None. Two independent ISPF markers are needed (a COBOL comment may mention one)."""
    seen = [name for name, rx in _ISPF_MARKERS if rx.search(text)]
    if len(seen) < 2:
        return None
    return ", ".join(seen)


def ispf_screens(root, exts=(".cbl", ".cob", ".cobol")) -> list[tuple[str, str]]:
    """#4735: [(path relative to `root`, ispf_screen reason)] of each COBOL-named file under `root` that is a saved ISPF
    screen. `root` is a directory or one file."""
    from pathlib import Path

    from gitgalaxy.core.source_text import read_source

    top = Path(root)
    files = [top] if top.is_file() else sorted(p for p in top.rglob("*") if p.is_file() and ".git" not in p.parts)
    out = []
    for p in files:
        if p.suffix.lower() not in exts:
            continue
        try:
            why = ispf_screen(read_source(p).text)
        except OSError:
            continue
        if why:
            out.append((p.name if top.is_file() else p.relative_to(top).as_posix(), why))
    return out
