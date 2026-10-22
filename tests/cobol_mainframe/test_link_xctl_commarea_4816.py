"""#4816: a LINKed program that XCTLs with the COMMAREA its caller passed is refused by name, never guessed.

IBM (EXEC CICS LINK): the COMMAREA is passed by address, the caller's own storage. EXEC CICS XCTL says only that "the
contents of the data-area are passed": not whether a target of the LINKed program's own DFHCOMMAREA addresses the
caller's storage (its writes reach the LINK caller) or a copy (they do not). Register X39. Both runtimes stop at such an
XCTL ("not modelled"); an XCTL of the program's own WORKING-STORAGE passes no caller storage and still runs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_link_commarea_bytes_4806 as base  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

TOOLS = base.TOOLS

# the middle program XCTLs with its own DFHCOMMAREA (the caller's storage) -- or, the control, with a working copy
MID_LINKAGE = base.XCTLMID.replace("COMMAREA(WS-CA) END-EXEC", "COMMAREA(DFHCOMMAREA)\n                END-EXEC")
MID_LINKAGE = MID_LINKAGE.replace("           MOVE SPACES TO WS-CA\n", "")
MID_PART = MID_LINKAGE.replace("COMMAREA(DFHCOMMAREA)", "COMMAREA(CA-NUM) LENGTH(6)")
MID_COPY = base.XCTLMID.replace("MOVE SPACES TO WS-CA", "MOVE DFHCOMMAREA TO WS-CA")
PROGRAMS = {
    "linkage": {"XCTLR": base.XCTLR, "XCTLMID": MID_LINKAGE, "XCTLEE": base.XCTLEE},
    "part": {"XCTLR": base.XCTLR, "XCTLMID": MID_PART, "XCTLEE": base.XCTLEE},
    "copy": {"XCTLR": base.XCTLR, "XCTLMID": MID_COPY, "XCTLEE": base.XCTLEE},
}
# the caller of XCTLMID passes its area: LINK PROGRAM('XCTLMID') COMMAREA(DFHCOMMAREA)
CALLER = base.XCTLR.replace(
    "LINK PROGRAM('XCTLMID') END-EXEC",
    "LINK PROGRAM('XCTLMID') COMMAREA(DFHCOMMAREA)\n                LENGTH(12) END-EXEC",
)


def _estate(tmp_path: Path, kind: str) -> Path:
    estate = tmp_path / "estate"
    (estate / "cbl").mkdir(parents=True)
    for name, src in {**PROGRAMS[kind], "XCTLR": CALLER}.items():
        (estate / "cbl" / f"{name}.cbl").write_text(src, encoding="ascii")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    return estate


def _translate(tmp_path: Path, kind: str):
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(TOOLS))
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = _estate(tmp_path, kind)
    project = det_port.estate(estate, tmp_path / "translate")
    java = {}
    results = {}
    for prog in PROGRAMS[kind]:
        svc = prog[0] + prog[1:].lower() + "Service"
        stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / f"{svc}.java").read_text("utf-8")
        r = P.translate(estate / "cbl" / f"{prog}.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project),
                        project)  # fmt: skip
        assert r.stats["holes"] == [], (prog, r.stats["holes"])
        java[prog] = r.java
        results[prog] = r
    return estate, project, java, results, det_port, P


@pytest.mark.parametrize(("kind", "flagged"), [("linkage", True), ("part", True), ("copy", False)])
def test_the_translation_marks_an_xctl_of_the_programs_own_dfhcommarea(tmp_path, kind, flagged):
    """Only an XCTL whose COMMAREA lies inside DFHCOMMAREA (the whole record or a field of it) is marked."""
    *_, java, _, _, _ = _translate(tmp_path, kind)
    assert ("task.xctlOfLinkage();" in java["XCTLMID"]) is flagged
    assert "xctlOfLinkage" not in java["XCTLR"] + java["XCTLEE"]


MAIN = """package com.acme.cics;

public class Main {
    static String run(boolean linked, boolean ofLinkage, boolean failing) {
        CicsTask task = new CicsTask("T001", "ENTER", null, null, java.util.Map.of());
        task.withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return !p.equals("NONE");
            }

            public void run(String p, CicsTask t) {
                if (p.equals("MID")) {
                    byte[] b = t.linkArea();
                    if (ofLinkage) {
                        t.xctlOfLinkage();
                    }
                    t.xctl(failing ? "NONE" : "EE", new Object(), 4, b);
                    if (failing) {
                        t.returnTransid(null, null);
                    }
                } else {
                    t.returnTransid(null, null);
                }
            }
        });
        task.withProgram("CALLER");
        try {
            return task.link("MID", new Object(), 4, linked ? "    ".getBytes() : null);
        } catch (UnsupportedOperationException e) {
            return "REFUSED " + e.getMessage().contains("not modelled");
        }
    }

    public static void main(String[] a) {
        System.out.println(run(true, true, false));
        System.out.println(run(true, false, false));
        System.out.println(run(true, true, true));
        System.out.println(run(false, true, false));
    }
}
"""


def _jdk() -> Path | None:
    return base._jdk()


@pytest.mark.skipif(_jdk() is None, reason="no JDK (JDK_17 / JAVA_HOME)")
def test_cictask_refuses_only_a_successful_xctl_of_the_callers_area(tmp_path):
    """CicsTask.xctl: refused for the LINK caller's area marked xctlOfLinkage; not for a copy, a failed XCTL (the program
    goes on) or a LINK that passed no bytes."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA

    root = tmp_path / "src" / "com" / "acme" / "cics"
    root.mkdir(parents=True)
    (root / "CicsTask.java").write_text(CICS_TASK_JAVA.replace("__PACKAGE__", "com.acme").replace("__ZONE__", "UTC"),
                                        encoding="utf-8")  # fmt: skip
    (root / "CicsSpec.java").write_text(CICS_SPEC_JAVA.replace("__PACKAGE__", "com.acme"), encoding="utf-8")
    (root / "Main.java").write_text(MAIN, encoding="utf-8")
    jdk = _jdk()
    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                            *map(str, root.glob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr[:3000]
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "com.acme.cics.Main"],  # noqa: S603
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert out == ["REFUSED true", "NORMAL", "NORMAL", "NORMAL"]


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
@pytest.mark.parametrize(("kind", "refused"), [("linkage", True), ("part", True), ("copy", False)])
def test_the_oracle_and_the_port_stop_at_an_xctl_of_the_callers_area(tmp_path, kind, refused):
    """The case through the equivalence harness: the XCTL of the caller's area is refused by name (the case is
    unsupported, the stub's "not modelled"); the same XCTL of a working copy is proven."""
    estate, project, java, results, det_port, P = _translate(tmp_path, kind)
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    for r in results.values():
        (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        (port / rel).parent.mkdir(parents=True, exist_ok=True)
        (port / rel).write_text(text, encoding="utf-8")
    case = {"kind": "cics", "corpus": "xctl-4816-synthetic", "program": "XCTLR", "program_source": "cbl/XCTLR.cbl",
            "copy_dirs": [], "transid": "LNK1", "clock": "2026/10/09 10:00:00.00", "datasets": {}, "screens": {},
            "programs": [{"program": p, "program_source": f"cbl/{p}.cbl"} for p in ("XCTLMID", "XCTLEE")],
            "commarea": {"segments": [{"copybook": "cbl/XCTLR.cbl", "record": "DFHCOMMAREA"}]},
            "scenarios": [{"name": "caller-area", "commarea": {}}]}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "xctl-4816", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none"], capture_output=True, text=True, check=False)  # fmt: skip
    said = proc.stdout + proc.stderr
    if refused:
        assert proc.returncode != 0 and "XCTL passing the COMMAREA its LINK caller passed" in said, said[-4000:]
    else:
        report = (
            json.loads((keep / "report.json").read_text(encoding="utf-8")) if (keep / "report.json").is_file() else {}
        )
        assert proc.returncode == 0 and report.get("proven") is True, said[-4000:]
