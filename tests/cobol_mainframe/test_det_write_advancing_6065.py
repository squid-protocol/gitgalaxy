"""#6065: the batch file runtime of an estate with no application JCL job, and WRITE phrase holes named by phrase.

Translation only (no GnuCOBOL, no javac)."""

from __future__ import annotations

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_batch_forge import BatchForge
from gitgalaxy.tools.cobol_to_java.java_target import load_target

PKG = "p"


def _program(proc: list[str], org: str = "SEQUENTIAL", special: str = "") -> str:
    lines = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. ADVTEST.", "       ENVIRONMENT DIVISION."]
    if special:
        lines += ["       CONFIGURATION SECTION.", "       SPECIAL-NAMES.", f"           {special}"]
    lines += [
        "       INPUT-OUTPUT SECTION.",
        "       FILE-CONTROL.",
        "           SELECT OUT-FILE ASSIGN TO OUTDD",
        f"               ORGANIZATION IS {org}",
        "               FILE STATUS WS-ST.",
        "       DATA DIVISION.",
        "       FILE SECTION.",
        "       FD  OUT-FILE.",
        "       01  OUT-REC PIC X(10).",
        "       WORKING-STORAGE SECTION.",
        "       77  WS-ST PIC XX.",
        "       77  WS-N PIC 9 VALUE 2.",
        "       PROCEDURE DIVISION.",
    ]
    lines += [f"           {x}" for x in proc] + ["           GOBACK."]
    return "\n".join(lines) + "\n"


def _translate(tmp_path, source: str):
    pytest.importorskip("tree_sitter_language_pack")  # the translator's parser (not in every CI job)
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "ADVTEST.cbl").write_text(source)
    return P.translate(tmp_path / "ADVTEST.cbl", [], "public class AdvtestService {\n}\n", PKG)


@pytest.mark.parametrize(("proc", "reason"), [
    (["WRITE OUT-REC BEFORE ADVANCING 1 LINE."], "WRITE BEFORE ADVANCING n LINES: carriage control"),
    (["WRITE OUT-REC AFTER ADVANCING 2 LINES."], "WRITE AFTER ADVANCING n LINES: carriage control"),
    (["WRITE OUT-REC AFTER ADVANCING PAGE."], "WRITE AFTER ADVANCING PAGE: carriage control"),
    (["WRITE OUT-REC AFTER ADVANCING WS-N LINES."], "WRITE AFTER ADVANCING identifier / mnemonic-name"),
    (["WRITE OUT-REC AFTER 1."], "WRITE AFTER without ADVANCING"),
    (["WRITE OUT-REC AFTER ADVANCING 1 LINE", "    AT END-OF-PAGE DISPLAY WS-ST", "END-WRITE."], "WRITE AFTER ADVANCING n LINES"),
])  # fmt: skip
def test_a_write_phrase_is_a_hole_named_by_the_phrase(tmp_path, proc, reason):
    """The blanket "WRITE ADVANCING / other phrases" reason said nothing about which phrase (#6065)."""
    r = _translate(tmp_path, _program(proc))
    assert r.stats["holes"] and reason in r.stats["holes"][0]
    assert not any("WRITE ADVANCING / other phrases" in h for h in r.stats["holes"])


def test_a_write_without_a_phrase_still_translates(tmp_path):
    r = _translate(tmp_path, _program(["WRITE OUT-REC FROM WS-ST."]))
    assert not r.stats["holes"]


# ---- the batch file runtime without an application JCL job -----------------------------------------------------
def _forge(skeletons: dict, jobs: list | None = None) -> BatchForge:
    sections = {"job_steps": {"facts": jobs}} if jobs else {}
    return BatchForge(skeletons, {"sections": sections}, "com.gitgalaxy", load_target(None))


def _skel(files: bool, cics: bool = False, pid: str = "PROG") -> dict:
    secs: dict = {"entry_points": {"facts": [{"kind": "PROCEDURE", "params": []}]}}
    if files:
        secs["file_control"] = {"facts": [{"select": "F"}]}
    if cics:
        secs["cics_tasks"] = {"facts": [{"task": "T"}]}
    return {"program": {"file": "f.cbl", "program_ids": [pid]}, "sections": secs}


def test_a_no_jcl_estate_with_a_file_owning_main_program_gets_the_file_runtime():
    out = _forge({"P": _skel(files=True)}).sources()[("base_pkg", "batch")]
    assert {"CobolFiles", "Sysout", "CobolAbend", "Dd", "DatasetResolver"} <= set(out)
    assert not {"JclSteps", "JclJobLauncher", "BatchJobController"} & set(out)  # no Spring Batch job classes


def test_a_cics_only_or_file_free_estate_gets_no_batch_package():
    assert _forge({"P": _skel(files=True, cics=True)}).sources() == {}
    assert _forge({"P": _skel(files=False)}).sources() == {}


def test_an_estate_with_an_application_job_keeps_its_job_classes():
    jobs = [{"file": "f.jcl", "job": "J1", "steps": [{"step": "S1", "ordinal": 1, "program": "PROG"}]}]
    out = _forge({"P": _skel(files=True)}, jobs).sources()[("base_pkg", "batch")]
    assert {"CobolFiles", "JclSteps", "JclJobLauncher"} <= set(out)
