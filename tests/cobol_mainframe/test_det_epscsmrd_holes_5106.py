"""#5106: DBB MortgageApplication epscsmrd's holes are refused by name and each maps to exactly one refusal_map entry.

The input class: LE condition handler registration (CEEHDLR / CEEHDLU, static and dynamic CALL), SET ... TO ENTRY,
ADDRESS OF a record with no storage of its own, GETMAIN without INITIMG, and the sibling-program CALL (still the generic
refusal: #4447 / #4404). A handler call is never a silent no-op: it translates to a Hole that names the service.
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import support_matrix as sm  # noqa: E402

PKG = "t"


def _program(*stmts: str) -> str:
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. HNDL.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
             "01 ROUTINE PROCEDURE-POINTER.", "01 TOKEN POINTER.", "01 FC PIC X(12).", "01 PGM PIC X(8) VALUE 'CEEHDLR'.",
             "PROCEDURE DIVISION.", "MAIN-PARA.", *(f"    {s}" for s in stmts), "    STOP RUN."]  # fmt: skip
    return "\n".join(" " * 7 + ln for ln in lines) + "\n"


def _holes(src: str) -> list[str]:
    pytest.importorskip("tree_sitter_language_pack")
    import test_det_programs as tdp
    from gitgalaxy.tools.cobol_to_java.det import program as P

    tmp = Path(tempfile.mkdtemp(prefix="t5106"))
    (tmp / "HNDL.cbl").write_text(src)
    project = tmp / "project"
    tdp._batch_package(project / "src/main/java")
    return P.translate(tmp / "HNDL.cbl", [], "public class HndlService {\n}\n", PKG, None, project).stats["holes"]


@pytest.mark.parametrize(
    ("stmt", "service"),
    [
        ("CALL 'CEEHDLR' USING ROUTINE TOKEN FC", "CEEHDLR"),
        ("CALL 'CEEHDLU' USING ROUTINE FC", "CEEHDLU"),
        ("CALL 'CEEHDLR' USING ROUTINE TOKEN FC RETURNING FC", "CEEHDLR"),
        ("CALL PGM USING ROUTINE TOKEN FC", "CEEHDLR"),
    ],
)
def test_a_condition_handler_call_is_refused_by_name(stmt, service):
    holes = _holes(_program(stmt))
    assert len(holes) == 1 and f"{service}:" in holes[0] and "not modelled" in holes[0], holes
    if service == "CEEHDLR":  # the refusal names what a registration is missing, not "no condition is raised"
        assert all(w in holes[0] for w in ("SET TO ENTRY", "dispatch", "RESUME / PERCOLATE")), holes
    assert [e["id"] for e in sm.classify(holes[0].split(": ", 1)[1], sm.load_map())] == ["le-condition-handling"]


@pytest.mark.parametrize("service", ["CEEMGET", "CEESGL", "CEENCOD", "CEEMRCE", "CEE3SRP"])
@pytest.mark.parametrize("form", ["static", "dynamic"])
def test_the_other_le_condition_services_are_refused_by_name(service, form):
    call = f"CALL '{service}' USING FC TOKEN" if form == "static" else "CALL PGM USING FC TOKEN"
    src = _program(call).replace("VALUE 'CEEHDLR'", f"VALUE '{service}'")
    holes = _holes(src)
    assert len(holes) == 1 and f"{service}:" in holes[0] and "not modelled" in holes[0], holes
    assert [e["id"] for e in sm.classify(holes[0].split(": ", 1)[1], sm.load_map())] == ["le-condition-handling"]


def test_set_to_entry_stays_a_named_hole():
    holes = _holes(_program("SET ROUTINE TO ENTRY 'EPSCSMRF'"))
    assert len(holes) == 1 and "SET TO ENTRY" in holes[0], holes


def _two_programs(*stmts: str, sibling: str = "SIB", nested: bool = False) -> str:
    """HNDL CALLing `sibling`, a program of the same source (batch-compiled after it, or nested in it)."""
    own = _program(*stmts).splitlines()
    sib = [
        "IDENTIFICATION DIVISION.",
        f"PROGRAM-ID. {sibling}.",
        "DATA DIVISION.",
        "WORKING-STORAGE SECTION.",
        "01 W PIC X.",
        "PROCEDURE DIVISION.",
        "    GOBACK.",
        f"END PROGRAM {sibling}.",
    ]
    sib = [" " * 7 + ln for ln in sib]
    tail = [" " * 7 + "END PROGRAM HNDL."]
    return "\n".join([*own[:-1], *sib, own[-1], *tail] if nested else [*own, *tail, *sib]) + "\n"


@pytest.mark.parametrize(
    "stmt",
    [
        "CALL 'SIB' USING FC",
        "CALL 'SIB' USING FC OMITTED",
        "CALL 'SIB' USING FC RETURNING FC",
        "CALL PGM USING FC",
    ],
)
@pytest.mark.parametrize("nested", [False, True])
def test_a_call_to_a_sibling_program_is_refused_by_name_not_as_an_unknown_program(stmt, nested):
    src = _two_programs(stmt, nested=nested).replace("VALUE 'CEEHDLR'", "VALUE 'SIB'")
    holes = _holes(src)
    assert len(holes) == 1 and "SIB: a sibling program of this source" in holes[0], holes
    assert [e["id"] for e in sm.classify(holes[0].split(": ", 1)[1], sm.load_map())] == ["multi-program-call"]


def test_a_call_to_a_program_of_no_source_is_still_the_generic_refusal():
    holes = _holes(_two_programs("CALL 'ELSEWHR' USING FC"))
    assert len(holes) == 1 and "sibling" not in holes[0] and "CALL ELSEWHR" in holes[0], holes


def test_a_one_program_source_has_no_sibling():
    holes = _holes(_program("CALL 'SIB' USING FC"))
    assert len(holes) == 1 and "sibling" not in holes[0], holes


def test_the_siblings_translate_on_their_own_and_do_not_see_the_caller():
    pytest.importorskip("tree_sitter_language_pack")
    import test_det_programs as tdp
    from gitgalaxy.tools.cobol_to_java.det import program as P

    tmp = Path(tempfile.mkdtemp(prefix="t5106s"))
    (tmp / "HNDL.cbl").write_text(_two_programs("CALL 'SIB' USING FC"))
    project = tmp / "project"
    tdp._batch_package(project / "src/main/java")
    r = P.translate(tmp / "HNDL.cbl", [], "public class SibService {\n}\n", PKG, None, project, unit="SIB")
    assert r.stats["holes"] == []  # SIB calls nothing: its own sibling set is HNDL, never a hole


@pytest.mark.parametrize(
    ("text", "owner"),
    [
        ("CALL CALL CEEHDLR", "le-condition-handling"),  # the committed report's text before the named refusal
        ("CALL CEEHDLU: unregistering an LE user condition handler is not modelled (x)", "le-condition-handling"),
        ("CALL CALL EPSCSMRI", "multi-program-call"),
        ("HOLE SET TO ENTRY: procedure / function pointers are not modelled", "procedure-pointer"),
        ("SET-POINTER ADDRESS OF ERROR-RESPONSE: not a LINKAGE 01 record (not modelled)", "address-of-record"),
        ("SET-ADDRESS ADDRESS OF ZF-DATA: a subordinate item is an offset into its record, not a LINKAGE 01 record "
         "(needs a Storage window; not modelled)", "address-of-record"),
        ("EXEC EXEC CICS: GETMAIN without INITIMG: IBM gives acquired storage no default contents", "getmain-initimg"),
        ("EXEC EXEC CICS: EXEC CICS SOAPFAULT CREATE not modelled (web services (SOAP / WS-Addressing) are not "
         "modelled)", "soap"),
        ("EXEC EXEC CICS: EXEC CICS GETMAIN not modelled", "getmain-freemain"),
    ],
)  # fmt: skip
def test_each_epscsmrd_hole_text_maps_to_exactly_one_entry(text, owner):
    assert [e["id"] for e in sm.classify(text, sm.load_map())] == [owner]


def test_every_new_entry_has_an_owner():
    entries = {e["id"]: e for e in sm.load_map()["entries"]}
    for key in ("address-of-record", "getmain-initimg", "le-condition-handling"):
        assert entries[key].get("issue"), key


def _with_sibling(call: str, linkage: str = "", using: str = "", body: str = "GOBACK.") -> str:
    """HNDL running `call`, then a batch-compiled sibling SIB with the given LINKAGE items, USING and body."""
    own = _program(call).splitlines()
    sib = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. SIB.", "DATA DIVISION.", "WORKING-STORAGE SECTION.", "01 W PIC X."]
    if linkage:
        sib += ["LINKAGE SECTION.", *linkage.split("|")]
    sib += [f"PROCEDURE DIVISION{using}.", f"    {body}", "END PROGRAM SIB."]
    return "\n".join([*own, " " * 7 + "END PROGRAM HNDL.", *(" " * 7 + ln for ln in sib)]) + "\n"


def _translated(src: str):
    pytest.importorskip("tree_sitter_language_pack")
    import test_det_programs as tdp
    from gitgalaxy.tools.cobol_to_java.det import program as P

    tmp = Path(tempfile.mkdtemp(prefix="t5106x"))
    (tmp / "HNDL.cbl").write_text(src)
    project = tmp / "project"
    tdp._batch_package(project / "src/main/java")
    return P.translate(tmp / "HNDL.cbl", [], "public class HndlService {\n}\n", PKG, None, project)


@pytest.mark.parametrize(
    ("call", "linkage", "using", "params"),
    [
        ("CALL 'SIB'", "", "", 0),
        ("CALL 'SIB' USING FC", "01 L PIC X(8).", " USING L", 1),
        ("CALL 'SIB' USING FC FC", "01 L PIC X(8).|01 M PIC X(4).", " USING L M", 2),
        ("CALL PGM USING FC", "01 L PIC X(8).", " USING L", 1),
    ],
)
def test_a_call_to_a_sibling_program_resolves_to_a_service_of_its_own(call, linkage, using, params):
    src = _with_sibling(call, linkage, using)
    if call.startswith("CALL PGM"):
        src = src.replace("VALUE 'CEEHDLR'", "VALUE 'SIB'")
    r = _translated(src)
    assert r.stats["holes"] == [], r.stats["holes"]
    assert [x.service for x in r.extra] == ["SibService"]
    sib = r.extra[0]
    assert f"public int handleCall({', '.join(f'CobolRef<byte[]> arg{k + 1}' for k in range(params))})" in sib.java
    assert "private final ObjectProvider<SibService> sibService" in r.java
    assert "sibService.getObject().handleCall(" in r.java
    assert r.stats["callees"] == ["SIB"]


@pytest.mark.parametrize(
    ("linkage", "using"),
    [
        ("01 L PIC X(8).", " USING BY VALUE L"),
        ("01 L PIC X(8).", " USING BY CONTENT L"),
        ("01 L PIC X(8).", " USING L RETURNING L"),  # RETURNING takes a number
        ("01 L PIC X(8).|01 R PIC 9(11).", " USING L RETURNING R"),  # more than the entry's int
        ("01 L PIC X(8).|01 R PIC 9(4)V9.", " USING L RETURNING R"),  # not a whole number
        ("01 L.|   05 A PIC X OCCURS 4.", " USING L"),
        ("01 L.|   05 P POINTER.", " USING L"),
        ("01 L.|   05 A PIC X.|   05 B REDEFINES A PIC X.", " USING L"),
        ("01 L PIC X(40).", " USING L"),  # longer than the caller's FC: it would read past FC's end
    ],
)
def test_a_sibling_whose_entry_is_not_a_plain_record_stays_refused_by_name(linkage, using):
    holes = _translated(_with_sibling("CALL 'SIB' USING FC", linkage, using)).stats["holes"]
    assert len(holes) == 1 and "SIB: a sibling program of this source" in holes[0], holes


@pytest.mark.parametrize(
    ("linkage", "using", "sizes"),
    [
        ("01 L.|   05 A PIC X(4).|   05 B PIC 9(4) COMP.|   05 C PIC S9(5) COMP-3.", " USING L", 1),  # a group
        ("01 L PIC 9(4) COMP.", " USING L", 1),  # a number: its bytes, never its text
        ("01 L PIC X(12).", " USING L", 1),
    ],
)
def test_a_group_or_a_number_crosses_as_its_bytes(linkage, using, sizes):
    r = _translated(_with_sibling("CALL 'SIB' USING FC", linkage, using))
    assert r.stats["holes"] == [] and r.extra[0].stats["holes"] == []
    assert "CobolRef<byte[]> arg1" in r.extra[0].java and ".storage().bytes" in r.extra[0].java
    assert "CobolRef<byte[]> " in r.java and "Arrays.copyOfRange(" in r.java and "System.arraycopy(" in r.java


def test_an_omitted_item_the_sibling_never_names_is_a_null_reference():
    src = _with_sibling("CALL 'SIB' USING FC OMITTED", "01 L PIC X(8).|01 M PIC X(4).", " USING L M")
    src = src.replace("    GOBACK.\n       END PROGRAM SIB", "    MOVE 'A' TO L.\n       END PROGRAM SIB")
    r = _translated(src)
    assert r.stats["holes"] == [] and r.extra[0].stats["holes"] == [], (r.stats["holes"], r.extra[0].stats["holes"])
    assert "= null;" in r.java and "if (arg2 != null)" in r.extra[0].java


def test_an_omitted_item_the_sibling_names_stays_refused():
    # IBM leaves a reference to an omitted parameter undefined (S0C4): it is refused, not run on invented storage
    src = _with_sibling("CALL 'SIB' USING FC OMITTED", "01 L PIC X(8).|01 M PIC X(4).", " USING L M", "MOVE 'A' TO M.")
    holes = _translated(src).stats["holes"]
    assert len(holes) == 1 and "SIB: a sibling program of this source" in holes[0], holes


def test_returning_is_the_sibling_s_item_not_return_code():
    src = _with_sibling("CALL 'SIB' USING FC RETURNING RC9", "01 L PIC X(8).|01 R PIC S9(9) COMP.",
                        " USING L RETURNING R", "MOVE 7 TO R.")  # fmt: skip
    src = src.replace("01 FC PIC X(12).", "01 FC PIC X(12).\n       01 RC9 PIC S9(9) COMP.")
    r = _translated(src)
    assert r.stats["holes"] == [] and r.extra[0].stats["holes"] == []
    store = re.search(r"Cobol\.store\((\w+), BigDecimal\.valueOf\(rc\d+\)", r.java)
    plain = _translated(_with_sibling("CALL 'SIB' USING FC", "01 L PIC X(8).", " USING L"))
    assert store and store.group(1) != re.search(r"Cobol\.store\((\w+), BigDecimal\.valueOf\(rc", plain.java).group(1)
    assert "return Cobol.num(" in r.extra[0].java


@pytest.mark.parametrize(
    ("call", "using"),
    [
        ("CALL 'SIB' USING FC RETURNING FC", " USING L"),  # a RETURNING the sibling has none for
        ("CALL 'SIB' USING FC", " USING L RETURNING R"),  # a sibling that returns an item, a CALL that takes none
    ],
)
def test_returning_must_match_on_both_sides(call, using):
    holes = _translated(_with_sibling(call, "01 L PIC X(8).|01 R PIC S9(9) COMP.", using)).stats["holes"]
    assert len(holes) == 1 and "SIB: a sibling program of this source" in holes[0], holes


def test_a_cics_caller_resolves_its_sibling_and_a_cics_sibling_does_not():
    cics = _with_sibling("CALL 'SIB' USING FC", "01 L PIC X(8).", " USING L")
    cics = cics.replace("    STOP RUN.", "    EXEC CICS RETURN END-EXEC.")
    r = _translated(cics)
    assert [x.service for x in r.extra] == ["SibService"] and "sibService.getObject().handleCall(" in r.java
    sib = _with_sibling("CALL 'SIB' USING FC", "01 L PIC X(8).", " USING L", "EXEC CICS RETURN END-EXEC.")
    holes = _translated(sib).stats["holes"]
    assert len(holes) == 1 and "SIB: a sibling program of this source" in holes[0], holes


def test_a_call_passing_another_number_of_items_than_the_sibling_takes_stays_refused():
    r = _translated(_with_sibling("CALL 'SIB' USING FC FC", "01 L PIC X(8).", " USING L"))
    assert r.extra == [] and len(r.stats["holes"]) == 1 and "sibling program" in r.stats["holes"][0]


def test_a_sibling_calling_back_into_the_caller_is_refused_not_looped():
    r = _translated(_with_sibling("CALL 'SIB'", body="CALL 'HNDL'."))
    assert [x.service for x in r.extra] == ["SibService"]  # HNDL -> SIB resolves ...
    holes = r.extra[0].stats["holes"]
    assert len(holes) == 1 and "HNDL: a sibling program of this source" in holes[0], holes  # ... SIB -> HNDL does not


def test_a_sibling_hole_is_reported_on_the_sibling_not_lost():
    r = _translated(_with_sibling("CALL 'SIB'", body="CALL 'CEEHDLR' USING ROUTINE TOKEN FC."))
    assert r.stats["holes"] == []
    assert len(r.extra[0].stats["holes"]) == 1 and "CEEHDLR" in r.extra[0].stats["holes"][0]


def _writebacks(r) -> int:
    """The copies a CALL writes back into the caller's item (BY REFERENCE only)."""
    return len(re.findall(r"System\.arraycopy\(arg\d+\.get\(\)", r.java))


@pytest.mark.parametrize("linkage", ["01 L PIC X(8).", "01 L.|   05 A PIC X(4).|   05 B PIC 9(4) COMP."])
def test_by_content_hands_the_sibling_a_copy_that_is_never_written_back(linkage):
    by_content = _translated(_with_sibling("CALL 'SIB' USING BY CONTENT FC", linkage, " USING L", "MOVE 'A' TO L."))
    by_ref = _translated(_with_sibling("CALL 'SIB' USING BY REFERENCE FC", linkage, " USING L", "MOVE 'A' TO L."))
    for r in (by_content, by_ref):
        assert r.stats["holes"] == [] and r.extra[0].stats["holes"] == [], r.stats["holes"]
        assert "Arrays.copyOfRange(" in r.java
    assert _writebacks(by_ref) == 1 and _writebacks(by_content) == 0


def test_by_content_and_by_reference_mix_and_omitted_keeps_its_rule():
    src = _with_sibling("CALL 'SIB' USING BY CONTENT FC BY REFERENCE FC OMITTED", "01 L PIC X(8).|01 M PIC X(8).|01 N PIC X.",
                        " USING L M N")  # fmt: skip
    r = _translated(src)
    assert r.stats["holes"] == [] and _writebacks(r) == 1 and "= null;" in r.java


@pytest.mark.parametrize("arg", ["'ABCDEFGH'", "12345678", "FC(1:4)"])
def test_by_content_of_a_literal_or_a_reference_modified_item_stays_refused(arg):
    holes = _translated(_with_sibling(f"CALL 'SIB' USING BY CONTENT {arg}", "01 L PIC X(4).", " USING L")).stats[
        "holes"
    ]
    assert len(holes) == 1 and "SIB: a sibling program of this source" in holes[0], holes


def test_by_content_to_an_estate_program_is_still_refused():
    holes = _translated(_program("CALL 'ELSEWHR' USING BY CONTENT FC")).stats["holes"]
    assert len(holes) == 1 and "CALL ELSEWHR" in holes[0], holes


# DBB epscsmrd's EPSCSMRX: `IF ADDRESS OF item NOT EQUAL NULL` guards each write to a USING item, and the caller passes
# OMITTED for two of them. IBM sets the address of an OMITTED item to NULL, so the test is the only reference allowed.
_OMIT_LINKAGE = "01 L PIC X(8).|01 M PIC X(4)."


@pytest.mark.parametrize(
    "body, passed",
    [
        ("IF ADDRESS OF M NOT EQUAL NULL MOVE 'A' TO M END-IF GOBACK.", True),
        ("IF ADDRESS OF M NOT = NULL MOVE 'A' TO M END-IF GOBACK.", True),
        ("IF ADDRESS OF M IS NOT EQUAL TO NULL MOVE 'A' TO M END-IF GOBACK.", True),
        ("IF ADDRESS OF M NOT = NULL IF L = 'X' MOVE 'A' TO M END-IF END-IF GOBACK.", True),
        ("IF ADDRESS OF M NOT = NULL MOVE 'A' TO M ELSE MOVE 'B' TO L END-IF GOBACK.", True),
        ("IF ADDRESS OF M = NULL MOVE 'B' TO L END-IF GOBACK.", True),
        # a reference the test does not guard: still undefined on IBM, so refused
        ("IF ADDRESS OF M NOT = NULL MOVE 'A' TO L ELSE MOVE 'A' TO M END-IF GOBACK.", False),
        ("IF ADDRESS OF M = NULL MOVE 'A' TO M END-IF GOBACK.", False),
        ("IF ADDRESS OF M NOT = NULL MOVE 'A' TO M END-IF MOVE 'A' TO M GOBACK.", False),
        ("IF ADDRESS OF M NOT = NULL OR L = 'X' MOVE 'A' TO M END-IF GOBACK.", False),
        ("IF ADDRESS OF L NOT = NULL MOVE 'A' TO M END-IF GOBACK.", False),
        ("IF ADDRESS OF M NOT = NULL MOVE 'A' TO M. MOVE 'A' TO M. GOBACK.", False),
    ],
)
def test_an_omitted_item_is_named_only_by_its_address_test_and_the_branch_it_guards(body, passed):
    body = re.sub(r" (?=(?:IF|MOVE|ELSE|END-IF|GOBACK)\b)", "\n       ", body)  # one statement a line, as source is
    src = _with_sibling("CALL 'SIB' USING FC OMITTED", _OMIT_LINKAGE, " USING L M", body)
    r = _translated(src)
    if passed:
        assert r.stats["holes"] == [] and r.extra[0].stats["holes"] == [], (r.stats["holes"], r.extra[0].stats["holes"])
        assert (
            "present[1]" in r.extra[0].java
            and "present = new boolean[] {arg1 != null, arg2 != null}" in r.extra[0].java
        )
    else:
        assert len(r.stats["holes"]) == 1 and "SIB: a sibling program of this source" in r.stats["holes"][0]


def test_a_sibling_that_tests_an_item_the_caller_passes_keeps_the_ordinary_entry():
    # nothing tests an address: no `present` field, so a sibling without the idiom is byte-for-byte what it was
    r = _translated(_with_sibling("CALL 'SIB' USING FC", "01 L PIC X(8).", " USING L"))
    assert "present" not in r.extra[0].java


def test_address_of_outside_a_sibling_s_using_items_is_still_refused_by_name():
    holes = _translated(_program("IF ADDRESS OF FC NOT EQUAL NULL MOVE 'A' TO FC END-IF")).stats["holes"]
    assert any("condition: ADDRESS OF" in h for h in holes), holes


# DBB epscsmrd's handler program EPSCSMRF, reduced: LE calls it with the condition token, the registered TOKEN pointer,
# a RESULT code and a NEW-CONDITION, and it reads the condition's message text with CEEMGET.
_HANDLER_HEAD = [
    "IDENTIFICATION DIVISION.", "PROGRAM-ID. HNDL.", "DATA DIVISION.", "WORKING-STORAGE SECTION.", "01 MSG-PART PIC X(80).",
    "01 MSG-PTR PIC S9(9) COMP.", "01 FC PIC X(12).", "LINKAGE SECTION.", "01 TOKEN POINTER.",
    "01 RESULT PIC S9(9) BINARY.", "   88 RESUME VALUE 10.", "01 CURRENT-CONDITION PIC X(12).", "01 NEW-CONDITION PIC X(12).",
    "01 ERROR-RESPONSE.", "   05 ERROR-OCCURRED PIC X.", "PROCEDURE DIVISION USING CURRENT-CONDITION TOKEN RESULT NEW-CONDITION.",
    "MAIN-PARA.",
]  # fmt: skip


def _handler(*stmts: str) -> str:
    lines = [*_HANDLER_HEAD, *(f"    {s}" for s in stmts), "    GOBACK."]
    return "\n".join(" " * 7 + ln for ln in lines) + "\n"


def _ids(holes: list[str]) -> list[list[str]]:
    return [[e["id"] for e in sm.classify(h.split(": ", 1)[1] if ": " in h else h, sm.load_map())] for h in holes]


def test_the_handler_s_resume_result_translates_and_owns_no_hole():
    assert _holes(_handler("MOVE 'Y' TO ERROR-OCCURRED", "SET RESUME TO TRUE")) == []


def test_the_handler_program_s_holes_are_each_owned_by_one_refusal_map_entry():
    holes = _holes(
        _handler(
            "SET ADDRESS OF ERROR-RESPONSE TO TOKEN",
            "CALL 'CEEMGET' USING CURRENT-CONDITION MSG-PART MSG-PTR FC",
            "MOVE 'Y' TO ERROR-OCCURRED",
            "SET RESUME TO TRUE",
        )
    )
    assert len(holes) == 1, holes
    assert "CEEMGET:" in holes[0] and "not modelled" in holes[0], holes
    assert _ids(holes) == [["le-condition-handling"]], holes


@pytest.mark.parametrize("service", ["CEEMGET", "CEESGL", "CEENCOD", "CEEMRCE", "CEE3SRP"])
def test_every_condition_service_a_handler_calls_is_a_named_refusal(service):
    holes = _holes(_handler(f"CALL '{service}' USING CURRENT-CONDITION FC"))
    assert len(holes) == 1 and f"{service}:" in holes[0] and "not modelled" in holes[0], holes
    assert _ids(holes) == [["le-condition-handling"]], holes


@pytest.mark.parametrize("call", ["CALL 'SIB' USING FC", "CALL PGM USING FC"])
def test_a_sibling_refused_for_its_own_reason_maps_to_the_entry_owning_that_reason(call):
    src = _with_sibling(call, "01 L PIC X(8).|01 N PIC N(4).", " USING L")
    if call.startswith("CALL PGM"):
        src = src.replace("VALUE 'CEEHDLR'", "VALUE 'SIB'")
    holes = _translated(src).stats["holes"]
    assert len(holes) == 1 and "SIB: no service of its own, its translation is refused: " in holes[0], holes
    assert "a sibling program of this source" not in holes[0]
    assert [e["id"] for e in sm.classify(holes[0].split(": ", 1)[1], sm.load_map())] == ["national-text"]


@pytest.mark.parametrize(
    ("text", "owner"),
    [
        ("CALL EPSCSMRI: no service of its own, its translation is refused: epscsmrd.cbl:1266: the PICTURE N (a "
         "national / DBCS item) is not modelled (national / DBCS data, #4664)", "national-text"),
        ("CALL EPSCSMRO: no service of its own, its translation is refused: LE recovery point: SERVICE LABEL "
         "(line 3332): the resume point after CEE3SRP, not BLL addressing: not modelled", "le-recovery-point"),
        ("CALL EPSCSMRX: a sibling program of this source (translated on its own)", "multi-program-call"),
        ("CALL CALL EPSCSMRX", "multi-program-call"),
    ],
)  # fmt: skip
def test_a_refused_sibling_call_text_maps_to_exactly_one_entry(text, owner):
    assert [e["id"] for e in sm.classify(text, sm.load_map())] == [owner]


def test_the_real_epscsmrd_resolves_its_translatable_sibling_and_names_the_others_owner():
    """DBB epscsmrd.cbl itself (the only burned multi-program source): EPSCSMRX is a service of its own; EPSCSMRI and
    EPSCSMRO are refused for their own reasons, each owned by one entry, none left to `multi-program-call`."""
    import os

    pytest.importorskip("tree_sitter_language_pack")
    root = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA") or ROOT / ".mainframe_corpora")
    src = root / "dbb-mortgage-application/zBuilder/MortgageApplication/cobol/epscsmrd.cbl"
    if not src.is_file():
        pytest.skip("no dbb-mortgage-application corpus")
    import test_det_programs as tdp
    from gitgalaxy.tools.cobol_to_java.det import program as P

    project = Path(tempfile.mkdtemp(prefix="t5106r")) / "project"
    tdp._batch_package(project / "src/main/java")
    holes = P.translate(src, [], "public class EpscsmrdService {\n}\n", PKG, None, project).stats["holes"]
    calls = {}
    for h in holes:
        m = re.match(r"line \d+: (CALL \w+): no service of its own", h)
        if m:
            calls[m.group(1)] = h.split(": ", 1)[1]
    assert not any("EPSCSMRX" in h for h in holes), holes
    assert sorted(calls) == ["CALL EPSCSMRI", "CALL EPSCSMRO"], calls
    owners = {k: [e["id"] for e in sm.classify(v, sm.load_map())] for k, v in calls.items()}
    assert owners == {"CALL EPSCSMRI": ["national-text"], "CALL EPSCSMRO": ["le-recovery-point"]}, owners
    assert not [h for h in holes if "a sibling program of this source" in h]


def _real_epscsmrd(unit: str | None = None) -> list[str]:
    """The holes of DBB epscsmrd.cbl translated as `unit` (None: the main program EPSCSMRD)."""
    import os

    pytest.importorskip("tree_sitter_language_pack")
    root = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA") or ROOT / ".mainframe_corpora")
    src = root / "dbb-mortgage-application/zBuilder/MortgageApplication/cobol/epscsmrd.cbl"
    if not src.is_file():
        pytest.skip("no dbb-mortgage-application corpus")
    import test_det_programs as tdp
    from gitgalaxy.tools.cobol_to_java.det import program as P

    project = Path(tempfile.mkdtemp(prefix="t5106u")) / "project"
    tdp._batch_package(project / "src/main/java")
    r = P.translate(
        src, [], "public class EpscsmrdService {\n}\n", PKG, None, project, **({"unit": unit} if unit else {})
    )
    return r.stats["holes"]


def test_the_real_epscsmrd_registration_holes_are_each_owned_by_one_entry():
    """The main program: the registration (CEEHDLR line 306) and its undo (CEEHDLU line 310) each name the service and
    map to `le-condition-handling`; the pointer they take (SET TO ENTRY line 304) maps to `procedure-pointer`."""
    holes = _real_epscsmrd()
    found = {re.match(r"line (\d+): ", h).group(1): h for h in holes if re.search(r"CEEHDL[RU]|SET TO ENTRY", h)}
    assert sorted(found) == ["304", "306", "310"], holes
    assert "CEEHDLR:" in found["306"] and "CEEHDLU:" in found["310"], found
    assert _ids([found["304"], found["306"], found["310"]]) == [
        ["procedure-pointer"], ["le-condition-handling"], ["le-condition-handling"],
    ], found  # fmt: skip


def test_the_real_epscsmrd_handler_program_holds_two_ceemget_holes_only():
    """EPSCSMRF translated as its own unit: CEEMGET at lines 406 and 422 (`le-condition-handling`); SET ADDRESS OF ... TO
    TOKEN (line 383) now translates, as does its SET RESUME TO TRUE and the rest. CEE3SRP / CEENCOD (EPSCSMRI, EPSCSMRO) sit
    behind those programs' own refusals (national-text, le-recovery-point) and so are not reached."""
    holes = _real_epscsmrd("EPSCSMRF")
    by_line = {re.match(r"line (\d+): ", h).group(1): h for h in holes}
    assert sorted(by_line) == ["406", "422"], holes
    assert all("CEEMGET:" in by_line[k] and "not modelled" in by_line[k] for k in ("406", "422")), by_line
    assert _ids([by_line["406"], by_line["422"]]) == [["le-condition-handling"]] * 2, by_line


def test_the_real_epscsmrd_soapfault_hole_is_owned_by_soap_only():
    """The CICS lane (a stub with `runTask(CicsTask)`, as the forge's has) on DBB epscsmrd.cbl: SEND-SOAP-FAULT's
    `EXEC CICS SOAPFAULT CREATE CLIENT FAULTSTRING ...` (line 276) is the one SOAP hole, refused whole by name and owned by
    the `soap` entry alone. No model: GnuCOBOL has no web-service reply and no cics-crucible event kind carries a fault, so
    one would have no oracle (see the entry's note)."""
    import os

    pytest.importorskip("tree_sitter_language_pack")
    root = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA") or ROOT / ".mainframe_corpora")
    src = root / "dbb-mortgage-application/zBuilder/MortgageApplication/cobol/epscsmrd.cbl"
    if not src.is_file():
        pytest.skip("no dbb-mortgage-application corpus")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    project = Path(tempfile.mkdtemp(prefix="t5106s")) / "project"
    vsam = project / "src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    stub = (
        "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class EpscsmrdService {\n"
        "    public void runTask(CicsTask task) {}\n}\n"
    )
    holes = P.translate(src, [], stub, "com.x", {}, project).stats["holes"]
    soap = [h for h in holes if "SOAPFAULT" in h]
    assert len(soap) == 1 and soap[0].startswith("line 276: ") and "not modelled" in soap[0], holes
    assert _ids(soap) == [["soap"]], soap
