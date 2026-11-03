"""#7485: a LINKed program's typed COMMAREA write-back never rewrites a signed DISPLAY field the program did not touch.

`caBack` filled the contract DTO (`fill_<Dto>`) and only then copied the storage to the caller's link area. `fill_`
reads a signed DISPLAY field through `Cobol.num`, which does GnuCOBOL's PUT_SIGN: a read of a field holding spaces
wrote a sign into the bytes that went back (CBSA ABNDPROC: SIGN LEADING SEPARATE, nine spaces came back `+` and eight
spaces; UPDACC: an overpunch last byte came back `{`). The bytes now go first, the typed fill after. The oracle is
GnuCOBOL, not z/OS.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"

# every signed DISPLAY form (the field the callee never touches is sent as spaces): overpunch trailing and leading,
# separate trailing and leading, beside a field the callee does write
FIELDS = [
    ("S9(10)V99", ""),
    ("S9(10)V99", " SIGN LEADING"),
    ("S9(4)", " SIGN TRAILING SEPARATE"),
    ("S9(8)", " SIGN LEADING SEPARATE"),
]


def _layout(field: tuple[str, str]) -> str:
    pic, sign = field
    return f"""\
          03 LK-CODE                 PIC X(4).
          03 LK-AMT                  PIC {pic}{sign}.
          03 LK-CNT                  PIC 9(2).
"""


def _callee() -> str:
    return """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SGNCALEE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       LINKAGE SECTION.
       01 DFHCOMMAREA.
       COPY SGNLAY.
       PROCEDURE DIVISION.
           MOVE 'DONE' TO LK-CODE
           MOVE 7 TO LK-CNT
           EXEC CICS RETURN END-EXEC.
"""


CALLER = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SGNCALLR.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-CA.
          03 WS-CODE                 PIC X(4).
          03 WS-AMT                  PIC X(__AMT__).
          03 WS-CNT                  PIC X(2).
       LINKAGE SECTION.
       01 DFHCOMMAREA.
          03 CA-CODE                 PIC X(4).
          03 CA-AMT                  PIC X(__AMT__).
          03 CA-CNT                  PIC X(2).
       PROCEDURE DIVISION.
           MOVE SPACES TO WS-CA
           EXEC CICS LINK PROGRAM('SGNCALEE') COMMAREA(WS-CA)
                LENGTH(__LEN__) END-EXEC
           MOVE WS-CA TO DFHCOMMAREA
           EXEC CICS RETURN END-EXEC.
"""
LENGTHS = {"S9(10)V99": 12, "S9(4)": 4, "S9(8)": 8}


def _length(field: tuple[str, str]) -> int:
    return 4 + LENGTHS[field[0]] + (1 if "SEPARATE" in field[1] else 0) + 2


def _estate(tmp_path: Path, field: tuple[str, str]) -> Path:
    estate = tmp_path / "estate"
    (estate / "cbl").mkdir(parents=True)
    (estate / "cbl" / "SGNCALLR.cbl").write_text(
        CALLER.replace("__LEN__", str(_length(field))).replace("__AMT__", str(_length(field) - 6)), encoding="ascii"
    )
    (estate / "cbl" / "SGNCALEE.cbl").write_text(_callee(), encoding="ascii")
    (estate / "cbl" / "SGNLAY.cpy").write_text(_layout(field), encoding="ascii")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    return estate


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    """For the text test only: the stubs' DTO types follow the field, so the e2e builds its own project."""
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(TOOLS))
    import det_port

    base = tmp_path_factory.mktemp("project7485")
    return det_port.estate(_estate(base, FIELDS[0]), base / "translate")


def _translate(tmp_path: Path, field: tuple[str, str], project: Path | None = None):
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = _estate(tmp_path, field)
    if project is None:
        project = det_port.estate(estate, tmp_path / "translate")
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    java = {}
    for prog in ("SGNCALLR", "SGNCALEE"):
        svc = prog[0] + prog[1:].lower() + "Service"
        stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / f"{svc}.java").read_text("utf-8")
        r = P.translate(estate / "cbl" / f"{prog}.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project),
                        project)  # fmt: skip
        assert r.stats["holes"] == [], (prog, r.stats["holes"])
        (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
        java[prog] = r.java
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    return estate, port, java


@pytest.mark.slow(reason="builds the generated estate project once (~17 s) for the module")
@pytest.mark.parametrize("field", FIELDS, ids=lambda f: (f[0] + f[1]).replace(" ", "_"))
def test_the_link_area_is_copied_before_the_typed_fill(tmp_path, project, field):
    """The generated write-back copies the storage to the link area, then fills the DTO (never the reverse)."""
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(TOOLS))
    _, _, java = _translate(tmp_path, field, project)
    line = next(x for x in java["SGNCALEE"].splitlines() if "caBack = () -> { System.arraycopy(" in x)
    assert line.index("System.arraycopy(") < line.index("typed.run()"), line
    assert "caBack = () -> { typed.run();" not in java["SGNCALEE"]
    # the sending side: the DTO is read from a copy of the area, so the bytes passed by reference are not rewritten
    assert "= out_SgncaleeDfhcommarea(Cobol.commarea(" in java["SGNCALLR"]


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
@pytest.mark.parametrize("field", FIELDS, ids=lambda f: (f[0] + f[1]).replace(" ", "_"))
def test_the_untouched_signed_field_comes_back_as_sent(tmp_path, field):
    """Against GnuCOBOL: the caller's spaces in the signed field stay spaces; the callee's writes arrive."""
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(TOOLS))
    estate, port, _ = _translate(tmp_path, field)
    case = {"kind": "cics", "corpus": "link-7485-synthetic", "program": "SGNCALLR",
            "program_source": "cbl/SGNCALLR.cbl", "copy_dirs": ["cbl"], "transid": "LNK1",
            "clock": "2026/10/09 10:00:00.00", "datasets": {}, "screens": {}, "linked": True,
            "programs": [{"program": "SGNCALEE", "program_source": "cbl/SGNCALEE.cbl", "copy_dirs": ["cbl"]}],
            "commarea": {"segments": [{"copybook": "cbl/SGNCALLR.cbl", "record": "DFHCOMMAREA"}]},
            "scenarios": [{"name": "untouched-sign", "commarea": {}}]}  # fmt: skip
    (tmp_path / "link_case.json").write_text(json.dumps(case), encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "link-7485", "--case-file",  # noqa: S603
                           str(tmp_path / "link_case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none"], capture_output=True, text=True, check=False)  # fmt: skip
    report_file = keep / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    assert proc.returncode == 0 and report.get("proven") is True, proc.stdout[-4000:] + proc.stderr[-3000:]
    got = [p.read_bytes()[: _length(field)] for p in (keep / "cobol").rglob("commarea.out")]
    width = _length(field) - 6
    assert got and all(b == b"DONE" + b" " * width + b"07" for b in got), got
