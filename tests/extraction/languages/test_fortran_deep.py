import re

func_start = re.compile(
    r"^[ \t]*(?!\bEND\b)"
    r"(?:(?:PURE|ELEMENTAL|RECURSIVE|IMPURE|MODULE)[ \t\n]+){0,5}"
    r"(?:"
    r"(?:INTEGER|REAL|COMPLEX|LOGICAL|CHARACTER|TYPE|CLASS|DOUBLE[ \t\n]+PRECISION|DOUBLE[ \t\n]+COMPLEX)"
    r"[A-Za-z0-9_ \t\n&*,()=:]*?"
    r")?"
    r"(?:FUNCTION|SUBROUTINE|PROGRAM|ENTRY)[ \t\n&+]+"
    r"([A-Za-z_]\w*)"
    r"(?=[ \t\n]*(?:[\(!&]|$|\bRESULT\b|\bBIND\b))",
    re.I | re.M,
)

cases = [
    "INTEGER(KIND=4), DIMENSION(:) FUNCTION foo()",
    "CLASS(*), POINTER :: FUNCTION poly_func()",
]

for pos in cases:
    if not func_start.search(pos):
        print(f"FAILED POSITIVE: {pos!r}")
    else:
        print(f"PASSED POSITIVE: {pos!r}")
