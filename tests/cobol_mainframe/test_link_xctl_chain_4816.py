"""#4816 (X39): the whole input class of a LINKed program XCTLing storage its LINK caller owns.

#4955 refuses, by name, a successful XCTL of the DFHCOMMAREA a program was LINKed with (IBM's EXEC CICS XCTL says only
that "the contents of the data-area are passed": copy vs the caller's storage is not documented). This file pins the
class around that one case: chains of XCTLs below a LINK (only the hop that XCTLs the caller's own area is refused, a
copy of a copy is not), a COMMAREA passed vs a new one, every LENGTH, and nested LINK levels vs a task's own start.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_link_xctl_commarea_4816 as prior
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

base = prior.base

# translation: the mark is on the program that XCTLs its own DFHCOMMAREA, whatever the LENGTH, and only there
_LINKAGE = prior.MID_LINKAGE
PROGRAMS = {
    f"len_{n}": {
        "XCTLR": base.XCTLR,
        "XCTLMID": _LINKAGE.replace("COMMAREA(DFHCOMMAREA)", f"COMMAREA(DFHCOMMAREA)\n                LENGTH({n})"),
        "XCTLEE": base.XCTLEE,
    }
    for n in (2, 12, 40)  # shorter than, equal to, longer than the 12-byte record
}
# LINK -> XCTL (a working copy) -> XCTL (its own DFHCOMMAREA, a copy of a copy)
PROGRAMS["chain_copy_then_linkage"] = {
    "XCTLR": base.XCTLR,
    "XCTLMID": prior.MID_COPY.replace("XCTLEE", "XCTLMD2"),
    "XCTLMD2": _LINKAGE.replace("XCTLMID", "XCTLMD2"),
    "XCTLEE": base.XCTLEE,
}
# LINK -> XCTL (its own DFHCOMMAREA) -> XCTL (a working copy)
PROGRAMS["chain_linkage_then_copy"] = {
    "XCTLR": base.XCTLR,
    "XCTLMID": _LINKAGE.replace("XCTLEE", "XCTLMD2"),
    "XCTLMD2": prior.MID_COPY.replace("XCTLMID", "XCTLMD2"),
    "XCTLEE": base.XCTLEE,
}
prior.PROGRAMS.update(PROGRAMS)  # the shared translate helper reads its own table


@pytest.mark.parametrize(
    ("kind", "flagged"),
    [
        ("len_2", {"XCTLMID"}),
        ("len_12", {"XCTLMID"}),
        ("len_40", {"XCTLMID"}),
        ("chain_copy_then_linkage", {"XCTLMD2"}),
        ("chain_linkage_then_copy", {"XCTLMID"}),
    ],
)
def test_the_translation_marks_only_the_program_that_xctls_its_own_area(tmp_path, kind, flagged):
    *_, java, _, _, _ = prior._translate(tmp_path, kind)
    for prog, text in java.items():
        assert ("task.xctlOfLinkage();" in text) is (prog in flagged), (kind, prog)


MAIN = """package com.acme.cics;

import java.util.ArrayList;
import java.util.List;

public class Main {
    static final List<String> trace = new ArrayList<>();
    static String lastResp = "";

    /** One scenario: `mode` names what each program does; every XCTL passes a new Object (the DTO). */
    static String run(String mode, boolean withBytes, int length) {
        trace.clear();
        lastResp = "";
        CicsTask task = new CicsTask("T001", "ENTER", null, null, java.util.Map.of());
        task.withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return !p.equals("NONE");
            }

            public void run(String p, CicsTask t) {
                trace.add(p);
                byte[] b = t.linkArea();
                switch (p) {
                    case "MID1" -> {
                        if (mode.equals("copy-then-own")) {
                            lastResp = t.xctl("MID2", new Object(), 4, b == null ? null : b.clone());
                            return;
                        }
                        if (mode.equals("copy3")) {
                            lastResp = t.xctl("MID2", new Object(), 4, b == null ? null : b.clone());
                            return;
                        }
                        if (mode.equals("no-commarea")) {
                            lastResp = t.xctl("EE", null, null, (byte[]) null);
                            return;
                        }
                        if (mode.equals("nested")) {
                            lastResp = t.link("MID2", new Object(), 4, new byte[] {1, 2, 3, 4});
                            t.returnTransid(null, null);
                            return;
                        }
                        t.xctlOfLinkage();
                        lastResp = t.xctl(mode.equals("failing") ? "NONE" : "EE", new Object(), length, b);
                        if (!lastResp.equals("NORMAL")) {
                            t.returnTransid(null, null);
                        }
                    }
                    case "MID2" -> {
                        if (mode.equals("copy3")) {
                            lastResp = t.xctl("MID3", new Object(), 4, b == null ? null : b.clone());
                            return;
                        }
                        t.xctlOfLinkage();
                        lastResp = t.xctl("EE", new Object(), length, b);
                    }
                    case "MID3" -> {
                        t.xctlOfLinkage();
                        lastResp = t.xctl("EE", new Object(), length, b);
                    }
                    default -> t.returnTransid(null, null);
                }
            }
        });
        task.withProgram("CALLER");
        try {
            String r = task.link("MID1", new Object(), 4, withBytes ? "    ".getBytes() : null);
            return r + " last=" + lastResp + " ran=" + String.join(",", trace);
        } catch (UnsupportedOperationException e) {
            return "REFUSED " + e.getMessage().contains("not modelled") + " ran=" + String.join(",", trace);
        }
    }

    /** A task's own level-1 program XCTLing its start COMMAREA: nobody else addresses it. */
    static String level1() {
        trace.clear();
        CicsTask task = new CicsTask("T001", "ENTER", new Object(), null, java.util.Map.of());
        task.withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return true;
            }

            public void run(String p, CicsTask t) {
                trace.add(p);
                if (p.equals("A")) {
                    t.xctlOfLinkage();
                    t.xctl("EE", new Object(), 4, new byte[4]);
                } else {
                    t.returnTransid(null, null);
                }
            }
        });
        try {
            task.run("A");
            return "NORMAL ran=" + String.join(",", trace);
        } catch (UnsupportedOperationException e) {
            return "REFUSED";
        }
    }

    public static void main(String[] a) {
        for (int len : new int[] {0, 2, 4, 12, 40, 32763}) {
            System.out.println("len " + len + ": " + run("own", true, len));
        }
        for (int len : new int[] {-1, 32764}) {
            System.out.println("len " + len + ": " + run("own", true, len));
        }
        System.out.println("own-nobytes: " + run("own", false, 4));
        System.out.println("failing: " + run("failing", true, 4));
        System.out.println("no-commarea: " + run("no-commarea", true, 4));
        System.out.println("copy-then-own: " + run("copy-then-own", true, 4));
        System.out.println("copy3: " + run("copy3", true, 4));
        System.out.println("nested: " + run("nested", true, 4));
        System.out.println("level1: " + level1());
    }
}
"""

REFUSED = "REFUSED true ran=MID1"
EXPECTED = [
    # LENGTH 0..32763 all refuse (shorter than, equal to, longer than the 4-byte area): the area is the caller's
    f"len 0: {REFUSED}",
    f"len 2: {REFUSED}",
    f"len 4: {REFUSED}",
    f"len 12: {REFUSED}",
    f"len 40: {REFUSED}",
    f"len 32763: {REFUSED}",
    # a LENGTH outside 0-32763 is LENGERR: the XCTL fails, nothing is passed, the program goes on
    "len -1: NORMAL last=LENGERR ran=MID1",
    "len 32764: NORMAL last=LENGERR ran=MID1",
    # a LINK that passed no bytes has no caller's area to hand on
    "own-nobytes: NORMAL last=NORMAL ran=MID1,EE",
    # a failed XCTL (PGMIDERR) is not refused
    "failing: NORMAL last=PGMIDERR ran=MID1",
    # an XCTL with no COMMAREA passes no storage
    "no-commarea: NORMAL last=NORMAL ran=MID1,EE",
    # LINK -> XCTL (copy) -> XCTL (its own DFHCOMMAREA): a copy of a copy, no LINK caller's storage
    "copy-then-own: NORMAL last=NORMAL ran=MID1,MID2,EE",
    "copy3: NORMAL last=NORMAL ran=MID1,MID2,MID3,EE",
    # LINK -> LINK -> XCTL of the inner caller's area: the inner LINK level is refused too
    "nested: REFUSED true ran=MID1,MID2",
    # the task's own start COMMAREA is nobody else's
    "level1: NORMAL ran=A,EE",
]


def test_cictask_refuses_exactly_the_callers_area_across_the_class(tmp_path):
    jdk = prior._jdk()
    if jdk is None:
        pytest.skip("no JDK (JDK_17 / JAVA_HOME)")
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA

    root = tmp_path / "src" / "com" / "acme" / "cics"
    root.mkdir(parents=True)
    (root / "CicsTask.java").write_text(CICS_TASK_JAVA.replace("__PACKAGE__", "com.acme").replace("__ZONE__", "UTC"),
                                        encoding="utf-8")  # fmt: skip
    (root / "CicsSpec.java").write_text(CICS_SPEC_JAVA.replace("__PACKAGE__", "com.acme"), encoding="utf-8")
    (root / "Main.java").write_text(MAIN, encoding="utf-8")
    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                            *map(str, root.glob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr[:3000]
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "com.acme.cics.Main"],  # noqa: S603
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert out == EXPECTED
