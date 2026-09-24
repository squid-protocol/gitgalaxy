"""
#3450: IMS DL/I calls (core/dli_calls.py), through `extract_boundary`: EXEC DLI
(CardDemo COPAUS0C / COPAUA0C shapes: PCB, SEGMENT path, INTO / FROM, WHERE,
SCHD PSB((name))) and CALL 'CBLTDLI' (PAUDBLOD: function, PCB mask, I/O area,
SSAs), with a numbered line's cols 73-80 tag ignored.
"""

from gitgalaxy.core.mainframe_boundary import extract_boundary


def _calls(src: str) -> list[dict]:
    return [{k: v for k, v in r.items() if v} for r in extract_boundary("cobol", src)["dli_calls"]]


def test_exec_dli_commands():
    src = (
        "           EXEC DLI SCHD PSB((PSB-NAME)) NODHABEND END-EXEC\n"
        "           EXEC DLI GU USING PCB(PAUT-PCB-NUM)\n"
        "               SEGMENT (PAUTSUM0)\n"
        "               INTO (PENDING-AUTH-SUMMARY)\n"
        "               WHERE (ACCNTID = PA-ACCT-ID)\n"
        "           END-EXEC\n"
        "           EXEC DLI ISRT USING PCB(PAUT-PCB-NUM)\n"
        "               SEGMENT (PAUTSUM0) WHERE (ACCNTID = PA-ACCT-ID)\n"
        "               SEGMENT (PAUTDTL1) FROM (PENDING-AUTH-DETAILS)\n"
        "           END-EXEC\n"
        "           DISPLAY 'EXEC DLI GU FAILED'.\n"
        "           EXEC DLI TERM END-EXEC\n"
    )
    assert _calls(src) == [
        {"interface": "EXEC", "function": "SCHD", "psb": "PSB-NAME", "line": 1},
        {
            "interface": "EXEC",
            "function": "GU",
            "pcb": "PAUT-PCB-NUM",
            "io_area": "PENDING-AUTH-SUMMARY",
            "segments": "PAUTSUM0",
            "where": "ACCNTID = PA-ACCT-ID",
            "line": 2,
        },
        {
            "interface": "EXEC",
            "function": "ISRT",
            "pcb": "PAUT-PCB-NUM",
            "io_area": "PENDING-AUTH-DETAILS",
            "segments": "PAUTSUM0,PAUTDTL1",
            "where": "ACCNTID = PA-ACCT-ID",
            "line": 7,
        },
        {"interface": "EXEC", "function": "TERM", "line": 12},
    ]


def test_cbltdli_calls_keep_their_operands():
    body = [
        "      CALL 'CBLTDLI'       USING  FUNC-GU",
        "                                 PAUTBPCB",
        "                                 PENDING-AUTH-SUMMARY",
        "                                 ROOT-QUAL-SSA.",
        "      CALL 'CBLTDLI' USING FUNC-ISRT PASFLPCB REC.",
    ]
    # Cols 1-6 and 73-80 numbered exactly, as in CardDemo PAUDBLOD.CBL.
    src = "".join(f"{19200 + i * 100:06d} {line:<65}{2370053 + i * 10000:08d}\n" for i, line in enumerate(body))
    assert all(len(line) == 80 for line in src.splitlines())
    assert _calls(src) == [
        {
            "interface": "CALL",
            "function_operand": "FUNC-GU",
            "pcb": "PAUTBPCB",
            "io_area": "PENDING-AUTH-SUMMARY",
            "ssas": "ROOT-QUAL-SSA",
            "line": 1,
        },
        {"interface": "CALL", "function_operand": "FUNC-ISRT", "pcb": "PASFLPCB", "io_area": "REC", "line": 5},
    ]


def test_no_dli_draws_nothing():
    assert _calls("           CALL 'CEE3ABD' USING X.\n") == []
