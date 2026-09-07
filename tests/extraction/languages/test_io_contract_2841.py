# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
The `io` contract (#2841, docs/io_rule_contract.md), held across every corpus
language in one place.

    One hit is an operation that moves data between the program and a system
    outside its own runtime, in a form an ordinary identifier cannot match.

The per-language strict suites keep their one positive/negative pair per signal;
this module pins the contract's corollaries -- exactly the shapes the
46-language audit found the old rules disagreeing on:

  C1 ambiguity anchor: a token the crucible showed matching a non-I/O
     identifier, string, or comment fires only in its operative form
     (javascript's bare `path` matched probeIo's parameter; assembly's bare
     `in`/`out` matched comment prose; a facility name with no measured
     collision -- fetch, axios, URLSession, io.open -- may fire bare)
  C2 one owner: dependency inclusion is import's hit (tcl `source`, sqlite
     `.read`/`.import`), releasing a resource is cleanup's (close/fclose/
     io.close/CLOSE), executing a command is high_risk_execution's
  C3 the boundary is the program's runtime: a .sql script executes inside the
     engine, so DML is computation; io is what leaves the engine. A client
     language's DML (abap SELECT) IS the boundary crossing.
  C4 one statement is one hit: a jcl DD carrying DSN= and DISP= (or two
     SYSOUT-family words) allocates once
  C5 a job-local temporary (jcl DSN=&&) never crosses the boundary

Each language lists (positives, negatives). A positive must match at least
once; a negative must not match at all. `COUNTS` pins one-statement-one-hit
shapes.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strict_harness import assert_redos_immune  # type: ignore


def _rule(lang, signal="io"):
    return LANGUAGE_DEFINITIONS[lang]["rules"][signal]


# lang -> (positives, negatives)
CASES = {
    # --- C1: the ambiguity anchor -------------------------------------------------
    "javascript": (
        ["const web = fetch;", "axios.get(url)", "const disk = fs;", "require('https')", "path.join(a, b)"],
        [
            "function probeIo(path) {",
            "const database = connect();",
            "// see https://react.dev/link/x",
            "'https://example.com'",
        ],
    ),
    "assembly": (
        ["in\tal,dx", "out\tdx,al", "syscall", "SVC", "dq sys_read"],
        ["; data flows in and out of the buffer", "\\ see the COPYING file in the root"],
    ),
    "c": (
        ['fopen(path, "r");', "read (handle, &header, sizeof(header));", "socket(AF_INET, 0, 0);"],
        ["if (read) {", "#include <sys/stat.h>", "int write_count;"],
    ),
    "groovy": (
        ["File disk", "file('local.properties')", "Socket plug"],
        ['def url = "http://repo"', "import org.gradle.api.file.RegularFileProperty", "copy the sync uri"],
    ),
    "dart": (
        ["File disk;", "HttpClient web;", "Uri.parse(routeName)"],
        ["' * file I/O event'", "final directory = 'top'"],
    ),
    # --- C2: one owner ------------------------------------------------------------
    "tcl": (
        ["open $route", "    gets $route", "set fd [read $f]", "file exists $p"],
        ["source a.tcl", "close $conn", "catch {db close}", "fileevent readable"],
    ),
    "lua": (
        ["io.open(path)", "io.read()"],
        ["io.close(conn)"],
    ),
    "matlab": (
        ["fopen('data.bin')", "load('data.mat')", "webread(url)"],
        ["fclose(fid)"],
    ),
    "cobol": (
        ["READ MASTER-STREAM.", "WRITE DETAIL-LINE.", "OPEN INPUT MASTER-STREAM."],
        ["CLOSE MASTER-STREAM."],
    ),
    "fortran": (
        ["OPEN (UNIT=1)", "READ (UNIT=1)", "REWIND (UNIT=1)"],
        ["CLOSE(UNIT=iunit)"],
    ),
    "perl": (
        ["open(my $fh, '<', $file)", "sysread($fh, $buf, 16)", "<STDIN>"],
        ["close($fh)", "closedir($dh)"],
    ),
    "livecode": (
        ["open file tPath", "read from file tPath", "get url tUrl"],
        ["close file tPath", "close socket tSock"],
    ),
    "cpp": (
        ["std::ifstream ifs;", 'fopen(p, "r")'],
        ["fclose(f);"],
    ),
    "yacc": (
        ['fopen(p, "r")', "yyin = stdin;"],
        ["fclose(fp);"],
    ),
    "abap": (
        ["SELECT * FROM t.", "TRANSFER lv_data TO lv_file.", "OPEN DATASET lv_file."],
        ["CLOSE DATASET lv_file."],
    ),
    # --- C3: the boundary is the program's runtime ---------------------------------
    "sqlite": (
        ["SELECT readfile('input.bin');", "SELECT writefile('out.bin', 1);", ".output probe.out", ".dump"],
        [
            "SELECT * FROM t;",
            "INSERT INTO corpus VALUES (1);",
            "UPDATE corpus SET flag = 1;",
            ".read a.sql",
            ".import data.csv t",
            "ATTACH DATABASE 'x.db' AS x;",
        ],
    ),
    # --- C4/C5: one DD statement is one hit; && temps are job-local ----------------
    "jcl": (
        [
            "//DD1 DD DSN=CORPUS.DATA,DISP=SHR",
            "//DD2 DD SYSOUT=A",
            "//SYSUT1   DD DSN=HLQ.WORK,\n//            DISP=(MOD,DELETE)",
        ],
        ["//DD3 DD DSN=&&TMP1,DISP=(OLD,DELETE)", "//* decoy prose about SYSOUT operands", "//IMP1 INCLUDE MEMBER=a"],
    ),
}

# One statement is one hit (C4), and the plant shapes stay pinned.
COUNTS = [
    ("jcl", "//DD1 DD DSN=CORPUS.DATA,DISP=SHR", 1),
    ("jcl", "//SYSPRINT DD SYSOUT=*", 1),
    ("jcl", "//DD1 DD DSN=CORPUS.DATA,DISP=SHR\n//DD2 DD SYSOUT=A\n//DD5 DD SYSOUT=L", 3),
    ("jcl", "//DD3 DD DSN=&&TMP1,DISP=(OLD,DELETE)\n//DD4 DD DSN=&&TMP2,DISP=(,DELETE),UNIT=SYSDA", 0),
    ("sqlite", "SELECT readfile('input.bin');\nSELECT writefile('output.bin', 1);\n.output probe.out", 3),
    ("sqlite", ".read a.sql\nSELECT CASE WHEN 1 THEN 2 ELSE 3 END;\nINSERT INTO corpus VALUES (1);", 0),
    (
        "javascript",
        "export function probeIo(path) {\n  const web = fetch;\n  const grabber = axios;\n  const disk = fs;\n}",
        3,
    ),
    ("tcl", "proc probe_io {route} {\n    open $route\n    gets $route\n    socket $route\n}", 3),
    ("tcl", "source a.tcl\nsource b.tcl\nclose $conn", 0),
    ("c", "fopen(0);\nfread(0);\nsocket(0);\nclose(0);", 3),
]

PAYLOADS = [
    "//X DD " + "DSN=" * 30000,
    "//X DD " + "A" * 100000 + " SYSOUT=",
    ("//X DD B," + "\n//X DD B,") * 5000,
    "in " * 50000,
    "." * 80000 + "output",
    "file " * 40000,
    "[" * 60000 + "read",
    "SELECT " * 30000,
    "require(" * 20000,
    "\t" * 50000 + "open",
]


@pytest.mark.parametrize("lang", sorted(CASES))
def test_io_contract_positive_and_negative(lang):
    rule = _rule(lang)
    positives, negatives = CASES[lang]
    for text in positives:
        assert rule.search(text), f"{lang}: contract positive did not match: {text!r}"
    for text in negatives:
        hits = [m.group(0) for m in rule.finditer(text)]
        assert not hits, f"{lang}: contract negative matched {hits!r} in {text!r}"


@pytest.mark.parametrize("lang,text,expected", COUNTS)
def test_io_one_statement_is_one_hit(lang, text, expected):
    hits = [m.group(0) for m in _rule(lang).finditer(text)]
    assert len(hits) == expected, f"{lang}: expected {expected} hits, got {hits!r}"


def test_io_release_is_cleanups_hit_alone():
    """C2: the retired duals stay single-owner -- cleanup still claims the
    release form the io rule dropped (mass conserved, #2765's shape)."""
    for lang, release in [
        ("c", "close(fd);"),
        ("cpp", "fclose(f);"),
        ("tcl", "close $conn"),
        ("lua", "io.close(conn)"),
        ("matlab", "fclose(fid)"),
        ("cobol", "CLOSE MASTER-STREAM."),
        ("perl", "close($fh)"),
    ]:
        assert _rule(lang, "cleanup").search(release), f"{lang}: cleanup lost {release!r}"
        assert not _rule(lang).search(release), f"{lang}: io still claims {release!r}"


def test_io_dependency_inclusion_is_imports_hit_alone():
    """C2: tcl `source` and sqlite `.read`/`.import` stay import's."""
    assert _rule("tcl", "import").search("source a.tcl")
    assert not _rule("tcl").search("source a.tcl")
    assert _rule("sqlite", "import").search(".read a.sql")
    assert not _rule("sqlite").search(".read a.sql")


@pytest.mark.parametrize("lang", sorted(CASES))
def test_io_contract_rules_are_redos_immune(lang):
    rule = _rule(lang)
    for payload in PAYLOADS:
        assert_redos_immune(rule, payload, timeout_sec=3.0)
