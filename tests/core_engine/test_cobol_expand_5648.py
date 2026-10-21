"""#5648: expand() lives in core.cobol_preprocessor; the member resolver and loader are callbacks."""

from __future__ import annotations

import pytest

from gitgalaxy.core.cobol_preprocessor import MappedLine, expand

MEMBERS = {
    "A": ["01 A1.", "   COPY B."],
    "B": ["05 B1 PIC X(:T:)."],
    "SQLCA": ["01 SQLCA."],
    "LOOP": ["COPY LOOP."],
}


def _lines(*texts: str, file: str = "p.cbl") -> list[MappedLine]:
    return [MappedLine(t, file, n) for n, t in enumerate(texts, 1)]


def _run(lines, **kw):
    seen: list[str] = []

    def resolve(ln, m, where, chain):
        key = m.member
        if key in chain:
            raise RuntimeError(f"{where}: cycle {key}")
        return key if key in MEMBERS else None

    def load(key, where, m):
        return [MappedLine(t, f"{key}.cpy", n) for n, t in enumerate(MEMBERS[key], 1)]

    out = expand(lines, resolve, load, make=MappedLine, on_copy=lambda ln, name: seen.append(name), **kw)
    return out, seen


def test_nested_copy_keeps_each_members_own_line_numbers():
    out, seen = _run(_lines("IDENTIFICATION DIVISION.", "    COPY A.", "    STOP RUN."))
    assert [(x.text.strip(), x.file, x.line) for x in out] == [
        ("IDENTIFICATION DIVISION.", "p.cbl", 1),
        ("01 A1.", "A.cpy", 1),
        ("05 B1 PIC X(:T:).", "B.cpy", 1),
        ("STOP RUN.", "p.cbl", 3),
    ]
    assert seen == ["A"]  # on_copy sees the top level only


def test_replacing_head_tail_two_copies_and_forms_on_other_lines():
    out, _ = _run(_lines("01 X. COPY B REPLACING ==:T:== BY ==9==. COPY SQLCA.", "COPY", "  SQLCA."))
    assert [x.text.strip() for x in out] == ["01 X.", "05 B1 PIC X(9).", "01 SQLCA.", "01 SQLCA."]


def test_exec_sql_include_is_a_copy_and_none_expands_to_nothing():
    out, seen = _run(_lines("EXEC SQL INCLUDE SQLCA END-EXEC.", "COPY NOPE.", "X."))
    assert [x.text for x in out] == ["01 SQLCA.", "X."] and seen == ["SQLCA", "NOPE"]


def test_a_copy_inside_a_literal_is_text():
    out, seen = _run(_lines("DISPLAY 'COPY A.'."))
    assert [x.text for x in out] == ["DISPLAY 'COPY A.'."] and seen == []


def test_resolver_refusal_and_depth_limit_propagate():
    with pytest.raises(RuntimeError, match="cycle LOOP"):
        _run(_lines("COPY LOOP."))
    MEMBERS["DEEP"] = ["COPY DEEP2."]
    MEMBERS["DEEP2"] = ["COPY DEEP."]
    try:
        with pytest.raises(RuntimeError):
            _run(_lines("COPY DEEP."))
    finally:
        del MEMBERS["DEEP"], MEMBERS["DEEP2"]

    # a resolver that never refuses a cycle hits the depth limit
    def resolve(ln, m, where, chain):
        return "LOOP"

    with pytest.raises(ValueError, match="nests deeper than 2"):
        expand(_lines("COPY LOOP."), resolve, make=MappedLine, load=lambda k, w, m: _lines("COPY LOOP."), max_depth=2)
