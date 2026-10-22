"""#4956: a model-port program LINKed with its DTO that XCTLs with that DTO is refused by name, never guessed.

Sibling of #4816 (register X39, the det case). A model port is LINKed with its caller's DTO object only (no bytes), so
CicsTask cannot read the DTO's bytes as the caller's area; it finds the caller's storage by reference instead: the
XCTL's COMMAREA is the program's own DTO, or an object that DTO holds (a nested group, a table, an element, the byte
area). IBM (EXEC CICS XCTL, COMMAREA: "the contents of the data-area are passed") does not say whether the target then
addresses the caller's storage or a copy. A copy (a new object), a failed XCTL, an XCTL at level 1 or of a task's own
start COMMAREA, and the target of an XCTL passing its own DTO again (a copy of a copy) are not refused. A String or
number cannot be traced by reference (#5060): one equal to a value the DTO holds is refused too, an equal-valued copy
included (refuse, never guess); a value the DTO does not hold is passed as it is, a value derived from a field (a suffixed String, a sum) included:
it cannot be traced, so it is a sibling gap, not a refusal.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

MAIN = """package com.acme.cics;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class Main {
    static class Group {
        String text = "g";
        Group inner;
    }

    static class Dto {
        String name = "n";
        int num = 1;
        Group grp = new Group();
        Group[] table = {new Group(), new Group()};
        List<Group> list = new ArrayList<>(List.of(new Group()));
        Map<String, Group> byKey = Map.of("k", new Group());
        byte[] raw = new byte[4];
        int[] nums = {7, 8};
        char[] chars = {'x', 'y'};
        long wide = 5L;
        java.math.BigDecimal amt = new java.math.BigDecimal("1.50");
        boolean flag = true;
        String[] tags = {"t1", "t2"};
        Dto self;
    }

    static String run(String s, boolean level1, boolean linked) {
        Dto dto = new Dto();
        dto.self = dto;
        String[] seen = {""};
        CicsTask task = new CicsTask("T001", "ENTER", level1 ? dto : null, level1 ? 4 : null, Map.of());
        task.withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return !p.equals("NONE");
            }

            public void run(String p, CicsTask t) {
                if (p.equals("MID")) {
                    Dto d = t.hasCommarea() ? t.commarea(Dto.class) : new Dto();
                    Object pass = switch (s) {
                        case "whole" -> d;
                        case "group" -> d.grp;
                        case "table" -> d.table;
                        case "element" -> d.table[1];
                        case "listed" -> d.list.get(0);
                        case "mapped" -> d.byKey.get("k");
                        case "bytes" -> d.raw;
                        case "name" -> d.name;
                        case "number" -> d.num;
                        case "nested" -> d.grp.text;
                        case "tabled" -> d.table[1].text;
                        case "keyed" -> d.byKey.get("k").text;
                        case "tablenum" -> d.nums[1];
                        case "tablechar" -> d.chars[0];
                        case "widened" -> (long) d.num;
                        case "narrowed" -> (int) d.wide;
                        case "scaled" -> new java.math.BigDecimal("1.5");
                        case "flag" -> d.flag;
                        case "otherchar" -> 'q';
                        case "othernum" -> 99L;
                        case "fresh" -> "zzz";
                        case "tag" -> d.tags[1];
                        case "derived" -> d.name + "x";
                        case "sum" -> d.num + 1;
                        case "unset" -> d.grp.inner;
                        case "none" -> null;
                        case "copy", "hop" -> new Dto();
                        default -> d;
                    };
                    String target = s.equals("failed") ? "NONE" : s.equals("hop") ? "HOP" : "EE";
                    String resp = t.xctl(target, pass, 4);
                    seen[0] = resp;
                    if (!resp.equals("NORMAL")) {
                        t.returnTransid(null, null);
                    }
                } else if (p.equals("HOP")) {
                    t.xctl("EE", t.commarea(Dto.class), 4);
                } else {
                    seen[0] += (seen[0].isEmpty() ? "" : ">") + p;
                    t.returnTransid(null, null);
                }
            }
        });
        task.withProgram("CALLER");
        try {
            if (level1) {
                task.run("MID");
            } else {
                task.link("MID", linked ? dto : null, 4);
            }
            return seen[0];
        } catch (UnsupportedOperationException e) {
            return "REFUSED " + e.getMessage().contains("XCTL passing the COMMAREA its LINK caller passed");
        }
    }

    public static void main(String[] a) {
        for (String s : new String[] {"whole", "group", "table", "element", "listed", "mapped", "bytes"}) {
            System.out.println(s + " " + run(s, false, true));
        }
        for (String s : new String[] {"name", "number", "nested", "tabled", "keyed"}) {
            System.out.println(s + " " + run(s, false, true));
        }
        for (String s : new String[] {"tablenum", "tablechar", "widened", "narrowed", "scaled", "flag", "otherchar", "othernum"}) {
            System.out.println(s + " " + run(s, false, true));
        }
        for (String s : new String[] {"tag", "derived", "sum", "unset"}) {
            System.out.println(s + " " + run(s, false, true));
        }
        for (String s : new String[] {"copy", "fresh", "none", "failed", "hop"}) {
            System.out.println(s + " " + run(s, false, true));
        }
        System.out.println("level1 " + run("whole", true, true));
        System.out.println("nodto " + run("whole", false, false));
    }
}
"""


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin" / "javac").is_file() else None


@pytest.mark.skipif(_jdk() is None, reason="no JDK (JDK_17 / JAVA_HOME)")
def test_cictask_refuses_an_xctl_of_the_dto_its_program_was_linked_with(tmp_path):
    """The whole DTO and every object it holds (group, table, element, list element, map value, byte area) are the
    caller's storage: refused; so is a String or number equal to a value the DTO holds (#5060: a value cannot be traced,
    so an equal-valued copy is refused too). A copy, a distinct value, no COMMAREA, a failed XCTL (the program goes on), a copy-of-a-copy
    hop, a level-1 task and a LINK that passed no DTO are not; the DTO holding itself does not loop."""
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
    assert out == [
        "whole REFUSED true",
        "group REFUSED true",
        "table REFUSED true",
        "element REFUSED true",
        "listed REFUSED true",
        "mapped REFUSED true",
        "bytes REFUSED true",
        "name REFUSED true",
        "number REFUSED true",
        "nested REFUSED true",
        "tabled REFUSED true",
        "keyed REFUSED true",
        "tablenum REFUSED true",
        "tablechar REFUSED true",
        "widened REFUSED true",
        "narrowed REFUSED true",
        "scaled REFUSED true",
        "flag REFUSED true",
        "otherchar NORMAL>EE",
        "othernum NORMAL>EE",
        "tag REFUSED true",
        "derived NORMAL>EE",
        "sum NORMAL>EE",
        "unset NORMAL>EE",
        "copy NORMAL>EE",
        "fresh NORMAL>EE",
        "none NORMAL>EE",
        "failed PGMIDERR",
        "hop NORMAL>EE",
        "level1 NORMAL>EE",
        "nodto NORMAL>EE",
    ]
