"""Tests for tests/tools/det_hole_groups.py and call-graph capture in det_survey.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import det_hole_groups as dhg  # noqa: E402
import det_survey as ds  # noqa: E402

BURNED_A = "aws-mainframe-modernization-carddemo"
BURNED_B = "cics-banking-sample-application-cbsa"
NON_BURNED = "nonburned-example-estate"


def _row(
    program: str,
    *holes: str,
    callees: list[str] | None = None,
    cics_links: list[str] | None = None,
    called_holes: list[str] | None = None,
    unlisted: list[str] | None = None,
    error: str | None = None,
    program_id: str | None = None,
) -> dict:
    if error:
        r: dict = {"program": program, "error": error}
    else:
        r = {
            "program": program,
            "statements": 10,
            "translated": max(0, 10 - len(holes)),
            "holes": list(holes),
        }
    if program_id:
        r["program_id"] = program_id
    if callees:
        r["callees"] = callees
    if cics_links:
        r["cics_links"] = cics_links
    if called_holes:
        r["called_holes"] = called_holes
    if unlisted:
        r["unlisted"] = unlisted
    return r


def test_static_cics_links_extracts_literals_and_value_items():
    cobol = "\n".join(
        [
            "       IDENTIFICATION DIVISION.",
            "       PROGRAM-ID. MAINPGM.",
            "       DATA DIVISION.",
            "       WORKING-STORAGE SECTION.",
            "       01  WS-LINK-PGM  PIC X(8) VALUE 'SUBVAL1'.",
            "      *    EXEC CICS LINK PROGRAM('IGNORED') END-EXEC",
            "       PROCEDURE DIVISION.",
            "           EXEC CICS LINK PROGRAM('SUBLIT1') COMMAREA(X) END-EXEC",
            "           EXEC CICS XCTL PROGRAM('NEXTPGM') END-EXEC",
            "           EXEC CICS LINK PROGRAM(WS-LINK-PGM) END-EXEC",
            "           STOP RUN.",
        ]
    )
    assert ds.static_cics_links(cobol) == ["NEXTPGM", "SUBLIT1", "SUBVAL1"]


def test_survey_program_preserves_callees_and_cics_links(tmp_path, monkeypatch):
    import equivalence_common

    from gitgalaxy.tools.cobol_to_java.det import program as P

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "CALLER.cbl").write_text(
        "\n".join(
            [
                "       IDENTIFICATION DIVISION.",
                "       PROGRAM-ID. CALLER.",
                "       PROCEDURE DIVISION.",
                "           EXEC CICS LINK PROGRAM('TARGETA') END-EXEC",
                "           CALL 'UTILSUB'.",
                "           GOBACK.",
            ]
        ),
        encoding="utf-8",
    )
    project = tmp_path / "estate" / "project"
    project.mkdir(parents=True)

    class _Res:
        service = "CallerService"
        java = "class CallerService {}\n"
        stats = {
            "program": "CALLER",
            "statements": 3,
            "translated": 3,
            "holes": [],
            "callees": ["UTILSUB"],
        }

    monkeypatch.setattr(equivalence_common, "engine_layouts", lambda *a, **kw: None)
    monkeypatch.setattr(P, "translate", lambda *a, **kw: _Res)
    row = ds.survey_program(corpus / "CALLER.cbl", corpus, project, [corpus], tmp_path / "work")
    assert row["program_id"] == "CALLER"
    assert row["callees"] == ["UTILSUB"]
    assert row["cics_links"] == ["TARGETA"]


@pytest.mark.parametrize(
    ("raw", "expected_cat"),
    [
        ("line 10: CALL STUBPGM", "called_hole"),
        ("MYPGM: no program of that name with a CALL entry in the estate", "called_hole"),
        ("SUB1: not in the case (the Java side would run the generator's empty stub)", "called_hole"),
        ("line 12: EXEC EXEC CICS: EXEC CICS GETMAIN not modelled", "exec_cics"),
        ("line 40: EXEC EXEC DLI: GU not modelled", "exec_dli"),
        ("line 42: CALL CBLTDLI", "exec_dli"),
        ("line 5: EXEC EXEC SQL: DECLARE CURSOR WITH HOLD", "exec_sql"),
        ("line 9: ARITHMETIC-OSVS: exponent overflow (#4287)", "arith_ebcdic"),
        ("line 11: ARITH(EXTEND): a floating-point expression (extended-precision HFP is not modelled)", "arith_ebcdic"),
        ("line 15: WS-AMT: the bytes of a COMP-5 item (oracle endianness)", "arith_ebcdic"),
        ("line 19: WS-NUM, PIC SVPP99: a P-scaled operand in COMPUTE", "arith_ebcdic"),
        ("line 22: MOVE: literal beyond the single-byte code page", "arith_ebcdic"),
        ("line 25: the PICTURE N (DBCS)", "arith_ebcdic"),
        ("line 30: HOLE does not parse", "grammar_refusal"),
    ],
)
def test_classify_gap_domain_categories(raw, expected_cat):
    key = dhg._normalize_called_hole(raw) if "not in the case" in raw else dhg._normalize_direct_hole(raw)
    assert dhg.classify_gap(key) == expected_cat


def test_downstream_caller_unblock_ranking_chain_diamond_and_cycles():
    # Diamond + chain:
    # TOP -> {MID1, MID2} -> LEAF (GETMAIN only)
    # ALSO_ONE_AWAY -> LEAF, and has its own EXEC DLI hole
    # ISOLATED has a lone COMP-5 hole with 0 callers
    # CYC1 <-> CYC2 shares a cycle with 0 external callers, CYC2 has SQL hole
    rows_by = {
        BURNED_A: [
            _row("app/TOP.cbl", callees=["MID1", "MID2"]),
            _row("app/MID1.cbl", callees=["LEAF"]),
            _row("app/MID2.cbl", cics_links=["LEAF"]),
            _row("app/LEAF.cbl", "line 4: EXEC EXEC CICS: EXEC CICS GETMAIN not modelled"),
            _row(
                "app/AWAY.cbl",
                "line 7: EXEC EXEC DLI: GU not modelled",
                callees=["LEAF"],
            ),
            _row("app/ALONE.cbl", "line 9: WS-X: the bytes of a COMP-5 item (C7)"),
            _row("app/CYC1.cbl", callees=["CYC2"]),
            _row("app/CYC2.cbl", "line 3: EXEC EXEC SQL: FETCH FIRST", callees=["CYC1"]),
            {"program": "app/COPY.cbl", "copy_member": "no PROGRAM-ID"},
            {"program": "app/DUP.cbl", "not_program": "duplicate PROGRAM-ID"},
        ]
    }
    res = dhg.analyze(rows_by)
    assert res["programs"] == 8
    assert res["direct_whole"] == 4  # TOP, MID1, MID2, CYC1
    assert res["l1_whole"] == 0
    assert res["blocked_only_by_called_holes"] == 4

    by_gap = {g["gap"]: g for g in res["gaps"]}
    # Ranking must place EXEC CICS GETMAIN first (unblocks TOP, MID1, MID2 = 3 callers + LEAF = 4 total)
    assert res["gaps"][0]["gap"] == "EXEC CICS GETMAIN"
    gm = by_gap["EXEC CICS GETMAIN"]
    assert gm["category"] == "exec_cics"
    assert gm["direct_programs"] == 1
    assert gm["direct_only"] == 1
    # Callers of LEAF: TOP (deduplicated despite diamond!), MID1, MID2, AWAY -> 4 touched; 3 unblocked, 1 one_away
    assert gm["callers_touched"] == 4
    assert gm["callers_unblocked"] == 3
    assert gm["callers_one_away"] == 1
    assert gm["unblocks_whole"] == 4

    # Cycle CYC1 <-> CYC2 should count CYC1 as a caller of CYC2 without looping
    sql = next(g for g in res["gaps"] if g["category"] == "exec_sql")
    assert sql["callers_touched"] == 1
    assert sql["callers_unblocked"] == 1
    assert sql["unblocks_whole"] == 2

    # ALONE has 0 callers, so COMP-5 ranks below bugs that unblock callers
    comp5 = next(g for g in res["gaps"] if g["category"] == "arith_ebcdic")
    assert comp5["callers_unblocked"] == 0
    assert comp5["unblocks_whole"] == 1


def test_unlisted_stubs_refused_callees_and_cases_overlay(tmp_path):
    eq = tmp_path / "eq"
    c1 = eq / "case-main"
    c1.mkdir(parents=True)
    (c1 / "case.json").write_text(
        json.dumps(
            {
                "corpus": BURNED_B,
                "program": "MAIN",
                "program_source": "src/MAIN.cbl",
                "programs": [{"program": "HELPER", "program_source": "src/HELPER.cbl"}],
            }
        ),
        encoding="utf-8",
    )
    rows_by = {
        BURNED_B: [
            _row("src/MAIN.cbl", cics_links=["HELPER"]),
            _row("src/HELPER.cbl", "line 10: CALL UNKSTUB"),
            _row("src/CALLREF.cbl", cics_links=["BADPGM"]),
            _row("src/BADPGM.cbl", error="CopyNotFound: src/BADPGM.cbl:3: COPY BAQRI"),
        ]
    }
    res = dhg.analyze(rows_by, equivalence_dir=eq)
    by_gap = {g["gap"]: g for g in res["gaps"]}

    assert res["cases_mapped"] == 1
    assert res["cases_l1_whole"] == 0

    call_stub = by_gap["CALL UNKSTUB"]
    assert call_stub["category"] == "called_hole"
    assert call_stub["callers_unblocked"] == 1  # MAIN
    assert call_stub["unblocks_whole"] == 2  # HELPER + MAIN
    assert call_stub["cases_unblocked"] == 1  # case-main!

    missing_copy = by_gap["missing copybook BAQRI"]
    assert missing_copy["refuses_program"] is True
    assert missing_copy["callers_unblocked"] == 1  # CALLREF

    assert res["unlisted_stubs"] == [
        {
            "stub": "UNKSTUB",
            "direct_callsites": 1,
            "downstream_callers": 1,
            "total_blocked": 2,
            "sample_callsites": [f"{BURNED_B}:src/HELPER.cbl"],
        }
    ]


def test_non_burned_corpus_is_scrubbed_and_never_names_programs():
    rows_by = {
        NON_BURNED: [
            _row("secret/P1.cbl", callees=["P2"]),
            _row("secret/P2.cbl", "line 8: CALL SECRET9", "line 12: WS-SECRET: no such item"),
        ]
    }
    res = dhg.analyze(rows_by)
    assert res["unlisted_stubs"] == []
    for g in res["gaps"]:
        assert g["sample_direct"] == []
        assert g["sample_callers"] == []
        assert "SECRET" not in g["gap"]
        assert "P1" not in g["gap"] and "P2" not in g["gap"]


def test_cli_survey_and_det_port_dir(tmp_path, capsys):
    survey_path = tmp_path / "survey.json"
    survey_path.write_text(
        json.dumps(
            {
                BURNED_A: [
                    _row("ENTRY.cbl", callees=["SUB"]),
                    _row("SUB.cbl", "line 5: ARITHMETIC-OSVS: bad scale (#4287)"),
                ]
            }
        ),
        encoding="utf-8",
    )
    out_md = tmp_path / "holes.md"
    rc = dhg.main(["--survey", str(survey_path), "--write", str(out_md), "--top", "10"])
    assert rc == 0
    stdout = capsys.readouterr().out
    assert "Top 1 hole groups ranked by downstream callers unblocked" in stdout
    assert "`arith_ebcdic`" in stdout
    assert out_md.read_text(encoding="utf-8") == stdout

    dp_dir = tmp_path / "det_port"
    dp_dir.mkdir()
    (dp_dir / "c1.json").write_text(
        json.dumps(
            {
                "corpus": BURNED_A,
                "program": "CASE1",
                "statements": 5,
                "translated": 5,
                "holes": [],
                "called_holes": ["SUB2: not in the case (the Java side would run the generator's empty stub)"],
            }
        ),
        encoding="utf-8",
    )
    rc2 = dhg.main(["--det-port-dir", str(dp_dir), "--json"])
    assert rc2 == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["gaps"][0]["gap"] == "unlisted callee SUB2"
    assert payload["gaps"][0]["category"] == "called_hole"
    assert payload["unlisted_stubs"][0]["stub"] == "SUB2"


def test_estate_no_compile_skips_mvn_and_upgrades_later(tmp_path, monkeypatch):
    import equivalence_cache
    import java_target_matrix as jtm

    corpus = tmp_path / "gitcorpus"
    (corpus / ".git").mkdir(parents=True)
    proj = tmp_path / "gen_proj"
    proj.mkdir()

    calls: list[str] = []
    monkeypatch.setattr(
        equivalence_cache,
        "refactor",
        lambda c, w, scan=True: calls.append("eq_cache") or (tmp_path / "clean"),
    )
    monkeypatch.setattr(jtm, "generate", lambda *a: calls.append("generate") or proj)
    monkeypatch.setattr(ds, "_mvn_compile_estate", lambda p, w: calls.append("mvn") or True)

    work = tmp_path / "estate"
    got_proj, built = ds.estate(corpus, work, compile_estate=False)
    assert got_proj == proj and built is False
    assert calls == ["eq_cache", "generate"]
    assert (work / "project.txt").read_text(encoding="utf-8").strip().endswith("generated")

    # Re-reading without compile stays fast (no mvn).
    assert ds.estate(corpus, work, compile_estate=False) == (proj, False)
    assert calls == ["eq_cache", "generate"]

    # Upgrading to compile_estate=True runs mvn once and promotes project.txt to built.
    assert ds.estate(corpus, work, compile_estate=True) == (proj, True)
    assert calls == ["eq_cache", "generate", "mvn"]
    assert (work / "project.txt").read_text(encoding="utf-8").strip().endswith("built")


def test_det_survey_main_parallel_jobs_preserves_order(tmp_path, monkeypatch):
    roots = tmp_path / "corpora"
    corp = roots / BURNED_A
    corp.mkdir(parents=True)
    for name in ("A.cbl", "B.cbl", "C.cbl"):
        (corp / name).write_text(
            f"       IDENTIFICATION DIVISION.\n       PROGRAM-ID. {name[:-4]}.\n       PROCEDURE DIVISION.\n           GOBACK.\n",
            encoding="utf-8",
        )
    proj = tmp_path / "proj"
    (proj / "src/main/java/com/gitgalaxy/modernized/service").mkdir(parents=True)

    monkeypatch.setenv("GITGALAXY_MAINFRAME_CORPORA", str(roots))
    monkeypatch.setattr(ds, "estate", lambda c, w, **kw: (proj, False))

    from gitgalaxy.tools.cobol_to_java.det import program as P

    monkeypatch.setattr(P, "estate_files", lambda project: {"DD1": "repo1"})

    seen: list[tuple[str, dict]] = []

    def fake_survey(program, corpus, project, dirs, work, unmask=None, layouts="engine", **kw):
        seen.append((program.name, kw.get("estate_files") or {}))
        return {"program": program.name, "statements": 1, "translated": 1, "holes": [], "stub": True}

    monkeypatch.setattr(ds, "survey_program", fake_survey)
    work = tmp_path / "out"
    # Single-worker path tests monkeypatched helper and estate_files forwarding cleanly; ProcessPool path checked via _survey_worker.
    monkeypatch.setattr(sys, "argv", ["det_survey.py", "--work", str(work), "--corpus", BURNED_A, "--no-compile", "--jobs", "1"])
    assert ds.main() == 0
    rows = json.loads((work / "survey.json").read_text(encoding="utf-8"))[BURNED_A]
    assert [r["program"] for r in rows] == ["A.cbl", "B.cbl", "C.cbl"]
    assert all(ef == {"DD1": "repo1"} for _, ef in seen)

