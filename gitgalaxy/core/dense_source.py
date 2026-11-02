"""#7501: dense hand-written source, told apart from minifier output and packed payloads.

Dense source (typical of AI coding agents) is a whole program on a few dozen 500-3,000 char lines,
several functions defined inline per line: `int f(..){..} int g(..){..}`. The generated-noise guards
(aperture Gates 3.4, 4.1, 5.1, the worker's minification test, the detector's long-line shield and the
auditor's Packed Payload Guard) read width and density, so they took it for a minified bundle.

The signal is the language plus inline definitions. Minifiers and packers emit web languages (JS,
CSS, HTML) and data; nobody minifies C, Rust or Go. So only in the compiled languages below does a
function defined inline on a long line make the line source -- and only up to DENSE_LINE_MAX, the
ceiling the regex engines downstream are trusted with.
"""

import os
import re

DENSE_EXTENSIONS = frozenset(
    {
        ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx", ".rs", ".go",
        ".java", ".cs", ".zig", ".swift", ".kt", ".scala",
    }
)  # fmt: skip
DENSE_LANGS = frozenset({"c", "cpp", "rust", "go", "java", "csharp", "zig", "swift", "kotlin", "scala"})
DENSE_LINE_MAX = 5000
# Lines up to this length are read by the ordinary (one definition per line) checks.
SHORT_LINE_MAX = 200

# A keyword-led head (`fn name(`, `func (r *T) name(`, `fun`, `def`) or a C-family typed head
# (`[type] name(args) {`). Every quantifier is bounded and each class is disjoint from the one that
# follows it (type / separator / name / argument list), so a match attempt is linear in its bound and
# the scan is linear in the line: no backtracking on a 5,000-char line.
_DENSE_DEF = re.compile(
    r"\b(?:fn|func|fun|def)[ \t]{1,8}(?:\([^(){};]{0,120}\)[ \t]{0,8})?([A-Za-z_]\w{0,60})[ \t]{0,8}[(<\[]"
    r"|\b([A-Za-z_][\w:<>,\[\]]{0,60})[ \t*&]{1,8}([A-Za-z_~][\w:~]{0,80})[ \t]{0,8}"
    r"\([^(){};]{0,240}\)[ \t]{0,8}(?:const[ \t]{0,8}|noexcept[ \t]{0,8}|throws[ \t][\w., \t]{1,80})?\{"
)
_NOT_NAME = frozenset({"if", "for", "while", "switch", "return", "else", "do", "sizeof", "typedef", "case", "goto"})
_NOT_TYPE = frozenset({"else", "return", "new", "throw", "case", "goto", "delete", "do"})


def defines_inline(line: str) -> bool:
    """True when `line` (at most DENSE_LINE_MAX chars) defines a function inline."""
    if len(line) > DENSE_LINE_MAX:
        return False
    for m in _DENSE_DEF.finditer(line):
        if (m.group(1) or m.group(3)) not in _NOT_NAME and m.group(2) not in _NOT_TYPE:
            return True
    return False


def has_dense_definitions(lines: list[str], low_path: str) -> bool:
    """A compiled-language file that defines a function inline on one of its long lines."""
    if os.path.splitext(low_path)[1] not in DENSE_EXTENSIONS:
        return False
    return any(SHORT_LINE_MAX < len(line) <= DENSE_LINE_MAX and defines_inline(line) for line in lines)


def is_dense_source(lines: list[str], low_path: str) -> bool:
    """Dense source: a compiled language, no line over DENSE_LINE_MAX, functions defined inline on its long lines."""
    return (
        os.path.splitext(low_path)[1] in DENSE_EXTENSIONS
        and all(len(line) <= DENSE_LINE_MAX for line in lines)
        and has_dense_definitions(lines, low_path)
    )
