"""#4391: a nonnumeric VALUE literal continued onto the next line (fixed format: the literal runs to
column 72, the continuation line has `-` in column 7 and resumes after a quote) was stored with the
raw continuation line -- CardDemo CBSTM03A.CBL:157-158 HTML-L08 read
`<table  align="center" frame="box" styl\\n      -             `. The value is the joined literal."""

from gitgalaxy.core.mainframe_boundary import _continued_literal, extract_boundary

HEAD = "       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       01  HTML-LINES.\n"
# CBSTM03A.CBL:157-158 / 161-162, the literal reaching column 72 exactly
L08 = (
    "         05  HTML-L.\n"
    '             88  HTML-L08 VALUE \'<table  align="center" frame="box" styl\n'
    "      -             'e=\"width:70%; font:12px Segoe UI,sans-serif;\">'.\n"
)
SHORT = "         05  SHORT-L.\n             88  SHORT-88 VALUE 'AB\n      -    'CD'.\n"
THREE = "         05  LONG-F   PIC X(140) VALUE '" + "A" * 33 + "\n      -    '" + "B" * 60 + "\n      -    'CCC'.\n"


def _values(src: str) -> dict:
    return {r["name"]: r["value"] for r in extract_boundary("cobol", HEAD + src)["records"]}


def test_a_continued_literal_is_joined():
    assert (
        _values(L08)["HTML-L08"]
        == '<table  align="center" frame="box" style="width:70%; font:12px Segoe UI,sans-serif;">'
    )


def test_the_first_line_runs_to_column_72_spaces_included():
    # the first line stops short of column 72: its blank columns up to 72 are part of the literal
    first = SHORT.splitlines()[1]
    quote = first.index("'")
    assert _values(SHORT)["SHORT-88"] == first[quote + 1 :].ljust(72 - quote - 1) + "CD"


def test_a_literal_continued_twice():
    first = THREE.splitlines()[0]
    a_run = first[first.index("'") + 1 : 72]  # the A's that fit up to column 72
    second = THREE.splitlines()[1]
    b_run = second[second.index("'") + 1 : 72]
    assert _values(THREE)["LONG-F"] == a_run + b_run + "CCC"


def test_a_single_line_literal_is_untouched():
    assert _values("         05  ONE PIC X(3) VALUE 'ABC'.\n")["ONE"] == "ABC"
    assert _continued_literal("       05 X VALUE 'ABC'.\n", 18) is None
