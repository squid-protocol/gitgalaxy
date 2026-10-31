"""#4975: an Easytrieve .mac file resolves to easytrieve on Easytrieve evidence.

Class: an extension (.mac) claimed by several languages in COLLISION_FREQUENCIES
resolves to the wrong language when the losing claimant has no internal_discriminator.
Repro: `FILE INPUT1 ... JOB INPUT ... PRINT` in x.mac resolves to hlasm alone,
beside .cbl, and beside .ezt.
Acceptance: easytrieve claims .mac on Easytrieve evidence (FILE/JOB/PRINT statement
shapes), tests alone + each neighbourhood, golden reviewed.
Sibling: #4546 (see test_header_language_collision.py for the pattern).
Uses the REAL registry, not an isolated mock.
"""

import pytest

from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

EASYTRIEVE = {
    "issue_repro": "FILE INPUT1 FB(80 800)\nJOB INPUT INPUT1\n  PRINT REPORT-1\n",
    "file_only": "FILE INPUT1\n",
    "file_fb": "FILE INPUT1 FB(80 800)\n",
    "file_macro_param": "FILE &FILE ORGANIZATION &ORG RECORDS &SIZE\n",
    "job_input": "JOB INPUT FILEA\n",
    "job_input_call": "JOB INPUT(INPUT1)\n",
    "job_named": "JOB MYJOB INPUT(PERSNL)\n",
    "print_bare": "PRINT\n",
    "print_named": "PRINT REPORT-1\n",
    "report_def": "REPORT REPORT-1\n  LINES 55\nEND-REPORT\n",
    "proc_def": "PROC MY-PROC\n  X = 1\nEND-PROC\n",
    "macro_def": "MACRO 2 FILE SIZE\nFILE &FILE\nMEND\n",
    "macro_param": "MACRO &COUNT\n",
    "macro_invocation": "%MSTFILE CUSTOMER 100\n",
    "end_macro": "END-MACRO\n",
    "control_boundary": "END-JOB\n",
}

HLASM = {
    "csect_using": "ACCTPGM  CSECT\n         USING ACCTPGM,15\n         BR    14\n",
    "equ_registers": "R1       EQU   1\nR2       EQU   2\nR3       EQU   3\n",
    "print_nogen": "         PRINT NOGEN\nACCTPGM  CSECT\n",
    "file_label_dc": "FILE     DC    CL80' '\nACCTPGM  CSECT\n",
    "file_label_ds": "FILE     DS    0H\nACCTPGM  CSECT\n",
    "file_label_equ": "FILE     EQU   *\nACCTPGM  CSECT\n",
    "job_label_csect": "JOB      CSECT\n         USING *,15\n",
    "print_label_equ": "PRINT    EQU   *\nACCTPGM  CSECT\n",
}

NEIGHBOURHOODS = {
    "alone": (),
    "beside_cbl": ("zz_prog.cbl", "zz_prog2.cbl"),
    "beside_ezt": ("zz_prog.ezt", "zz_prog2.ezt"),
    "beside_asm": ("zz_prog.asm", "zz_prog2.asm"),
    "beside_mac": ("zz_other.mac", "zz_other2.mac"),
}


def _classify(tmp_path, name, text, extras):
    (tmp_path / name).write_text(text)
    for extra in extras:
        (tmp_path / extra).write_text("* placeholder\n")
    tally: dict[str, int] = {}
    for child in tmp_path.iterdir():
        tally[child.suffix.lower()] = tally.get(child.suffix.lower(), 0) + 1
        tally[child.name.lower()] = 1
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, LEXICAL_FAMILY_HEURISTICS)
    return detector.inspect(tmp_path / name, text, ext_tally=tally)["lang_id"]


@pytest.mark.parametrize("hood", NEIGHBOURHOODS)
@pytest.mark.parametrize("style", EASYTRIEVE)
def test_mac_with_easytrieve_evidence_resolves_to_easytrieve(tmp_path, style, hood):
    text = EASYTRIEVE[style]
    assert _classify(tmp_path, "probe.mac", text, NEIGHBOURHOODS[hood]) == "easytrieve"


@pytest.mark.parametrize("hood", NEIGHBOURHOODS)
@pytest.mark.parametrize("style", HLASM)
def test_mac_with_hlasm_evidence_resolves_to_hlasm(tmp_path, style, hood):
    text = HLASM[style]
    assert _classify(tmp_path, "probe.mac", text, NEIGHBOURHOODS[hood]) == "hlasm"


@pytest.mark.parametrize("hood", NEIGHBOURHOODS)
def test_issue_4975_repro_resolves_to_easytrieve_in_all_neighbourhoods(tmp_path, hood):
    repro_text = "FILE INPUT1 FB(80 800)\nJOB INPUT INPUT1\n  PRINT REPORT-1\n"
    assert _classify(tmp_path, "x.mac", repro_text, NEIGHBOURHOODS[hood]) == "easytrieve"


def test_dot_ezt_files_unaffected(tmp_path):
    text = "JOB INPUT PERSNL\n  PRINT REPORT-1\n"
    assert _classify(tmp_path, "prog.ezt", text, ()) == "easytrieve"


TROFF_MAC = '.\\" troff macros\n.de PP\n.sp .5v\n.ne 2\n..\n.de SH\n.sp 1\n.ft B\n..\n'
MASM_MAC = "PUSHALL MACRO\n   push ax\nENDM\n"


@pytest.mark.parametrize("hood", NEIGHBOURHOODS)
@pytest.mark.parametrize("text", [TROFF_MAC, MASM_MAC], ids=["troff", "masm"])
def test_mac_without_easytrieve_evidence_is_not_easytrieve(tmp_path, text, hood):
    # #7064: troff `.mac` macro packages won the lexical fallback by default (easytrieve was the only unproven claimant).
    assert _classify(tmp_path, "probe.mac", text, NEIGHBOURHOODS[hood]) not in {"easytrieve", "hlasm"}


def test_dot_ezp_without_discriminator_still_easytrieve(tmp_path):
    assert _classify(tmp_path, "prog.ezp", "JOB INPUT PERSNL\n  PRINT REPORT-1\n", ()) == "easytrieve"
