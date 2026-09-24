"""#3491: PL/I program call sites -- EXEC CICS transfers through the COBOL reader,
CALLs that leave the compilation unit, and the resolver's PL/I program index. The
shapes are navikt/DSF's (the keyed PL/I corpus). The boundary reads the PRISM code
stream, whose comments are already gone, so these fixtures carry none."""

from gitgalaxy.core.invocation_resolver import resolve_invocations
from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.core.pli_calls import blank_sequence_fields, pli_cics_stream


def _seq(text: str, n: str) -> str:
    """One fixed-format line: text in columns 1-72, a sequence field in 73-80."""
    return text.ljust(72) + n


SOURCE = "\n".join(
    [
        " R001B1: PROC(COMMAREA_PEKER) OPTIONS(MAIN);",
        " DCL PROGRAM_ID CHAR(8) INIT('R0010301');",
        " IF KODE = 'A' THEN EXEC CICS XCTL PROGRAM('R0010420') COMMAREA(KOM_OMR);",
        _seq("    EXEC CICS LINK PROGRAM", "00001740"),
        _seq("         ('R0015501') COMMAREA(LOKAL) ;", "00001750"),
        " EXEC CICS XCTL PROGRAM(PROGRAM_ID);",
        " EXEC CICS RETURN TRANSID(TRANSKODE) COMMAREA(KOM_OMR);",
        " EXEC CICS RETURN;",
        _seq("    CALL", "00004100"),
        "        ÅPNE_DATABASE;",
        " CALL SEND_MAP;",
        " CALL PLITDLI(TRE, GU, PCB);",
        _seq(" SEND_MAP:", "R0015160"),
        "    PROC;",
        " END SEND_MAP;",
        " END R001B1;",
    ]
)


def _calls(src: str) -> list[tuple]:
    return [(c["verb"], c["operand"], c["target"], c["line"]) for c in extract_boundary("pli", src)["calls"]]


def test_cics_transfers_and_external_calls():
    assert _calls(SOURCE) == [
        ("XCTL", "R0010420", "R0010420", 3),  # after THEN, same statement
        ("LINK", "R0015501", "R0015501", 4),  # operand on the next line, past the sequence field
        ("XCTL", "PROGRAM_ID", "R0010301", 6),  # through the DCL's INIT
        ("RETURN TRANSID", "TRANSKODE", None, 7),
        ("CALL", "ÅPNE_DATABASE", "ÅPNE_DATABASE", 9),  # a national letter first; name on the next line
        ("CALL", "PLITDLI", "PLITDLI", 12),
    ]  # SEND_MAP is this file's own procedure (its label carries a tagged sequence field)


def test_the_cics_stream_keeps_every_line():
    stream = pli_cics_stream(SOURCE)
    assert stream.count("\n") == SOURCE.count("\n")
    assert stream.count("END-EXEC") == 5


def test_sequence_fields_are_recognised_by_shape_not_column():
    # A comment removed from the start of a line shifts its sequence field left.
    assert blank_sequence_fields("      CALL                               00002080").rstrip() == "      CALL"
    assert blank_sequence_fields(" X: " + " " * 40 + "R0015160").rstrip() == " X:"
    assert blank_sequence_fields(" IF A = 10") == " IF A = 10"  # one blank: a statement's own number


def _file(path: str, functions: list[tuple[str, int]], sites: list[dict]) -> dict:
    return {
        "path": path,
        "lang_id": "pli",
        "functions": [{"name": n, "start_line": line} for n, line in functions],
        "call_sites": sites,
    }


def test_resolver_indexes_members_and_outer_entries_and_drops_include_internal_calls():
    files = [
        _file("src/R0010420.pli", [("SEND_MAP", 80), ("R001B1", 1)], []),  # ordered by size, not line
        _file("src/R0019956.pli", [("P9956_BER_G_CICS", 3)], []),
        _file("src/R0015301.pli", [("R001530", 1), ("P020_SKRIV", 900)], []),
        _file(
            "src/R00153NC.pli",
            [("SOMETHING", 5)],
            [
                {"verb": "XCTL", "form": "literal", "operand": "R0010420", "target": "R0010420", "line": 10},
                {"verb": "CALL", "form": "literal", "operand": "R001B1", "target": "R001B1", "line": 11},
                {
                    "verb": "CALL",
                    "form": "literal",
                    "operand": "P9956_BER_G_CICS",
                    "target": "P9956_BER_G_CICS",
                    "line": 12,
                },
                {"verb": "CALL", "form": "literal", "operand": "P020_SKRIV", "target": "P020_SKRIV", "line": 13},
            ],
        ),
    ]
    sites, _edges = resolve_invocations(files)
    got = {(s["target"], s["resolved_path"]) for s in sites}
    assert got == {
        ("R0010420", "src/R0010420.pli"),  # the load module is the member
        ("R001B1", "src/R0010420.pli"),  # the outermost procedure's label, by start line
        ("P9956_BER_G_CICS", "src/R0019956.pli"),  # an included member's entry
    }  # P020_SKRIV is a nested procedure of the includer: an internal call, dropped
