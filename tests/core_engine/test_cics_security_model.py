"""#8606 step 1: the CICS security model table. Every CICS and EXEC SQL verb the burned estates use is classified or
listed as not security-relevant, and every entry cites a manual by name. No detection claim is tested: none exists."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from gitgalaxy.standards import cics_security as sec

BURNED_DIRS = (
    "aws-mainframe-modernization-carddemo",
    "cics-banking-sample-application-cbsa",
    "cics-genapp",
    "zecs",
    "dbb-mortgage-application",
    "cics-async-api-credit-card-application-example",
    "example-health-apis",
)
_EXEC = re.compile(r"EXEC\s+(CICS|SQL)\s+(.*?)END-EXEC", re.S | re.I)


def _corpora() -> Path | None:
    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    if not root or not all((Path(root) / d).is_dir() for d in BURNED_DIRS):
        return None
    return Path(root)


def _source_text(path: Path) -> str:
    """Fixed-format COBOL: drop the sequence area, the indicator column's comment lines and columns 73-80."""
    from gitgalaxy.core.source_text import read_source

    out = []
    for line in read_source(path).text.splitlines():
        if len(line) > 6 and line[:6].strip().isdigit() or line[:6].strip() == "":
            if len(line) > 6 and line[6] in "*/":
                continue
            line = line[6:72]
        out.append(line)
    return "\n".join(out)


def _scan_burned(root: Path) -> tuple[set[str], set[str]]:
    cics: set[str] = set()
    sql: set[str] = set()
    for d in BURNED_DIRS:
        for p in (root / d).rglob("*"):
            if not p.is_file() or p.suffix.lower() not in {".cbl", ".cob", ".cpy", ".sqlcbl", ".cobol"}:
                continue
            for m in _EXEC.finditer(_source_text(p)):
                kind = "exec_cics" if m.group(1).upper() == "CICS" else "exec_sql"
                verb = sec.canonical_verb(kind, m.group(2))
                (cics if kind == "exec_cics" else sql).add(verb)
    return cics, sql


def test_the_pinned_verbs_are_all_classified_or_not_relevant():
    missing_cics = {
        v
        for v in sec.BURNED_CICS_VERBS
        if not (sec.entries_for("exec_cics", v) or ("exec_cics", v) in sec.NOT_SECURITY_RELEVANT)
    }
    missing_sql = {
        v
        for v in sec.BURNED_SQL_VERBS
        if not (sec.entries_for("exec_sql", v) or ("exec_sql", v) in sec.NOT_SECURITY_RELEVANT)
    }
    assert not missing_cics, f"unclassified CICS verbs: {sorted(missing_cics)}"
    assert not missing_sql, f"unclassified SQL verbs: {sorted(missing_sql)}"


def test_a_verb_is_never_both_classified_and_listed_not_relevant():
    both = {(kind, key) for (kind, key) in sec.NOT_SECURITY_RELEVANT if sec.entries_for(kind, key)}
    assert not both, f"in ENTRIES and NOT_SECURITY_RELEVANT: {sorted(both)}"


def test_the_pinned_census_matches_the_burned_corpora_when_they_are_present():
    root = _corpora()
    if root is None:
        pytest.skip("burned corpora not available (GITGALAXY_MAINFRAME_CORPORA)")
    cics, sql = _scan_burned(root)
    cics.discard("")
    sql.discard("")
    unclassified = {
        v for v in cics if not (sec.entries_for("exec_cics", v) or ("exec_cics", v) in sec.NOT_SECURITY_RELEVANT)
    } | {
        f"SQL {v}" for v in sql if not (sec.entries_for("exec_sql", v) or ("exec_sql", v) in sec.NOT_SECURITY_RELEVANT)
    }
    assert not unclassified, f"burned-estate verbs with no classification: {sorted(unclassified)}"
    assert cics == set(sec.BURNED_CICS_VERBS), (
        f"pinned CICS census is stale: only in scan {sorted(cics - sec.BURNED_CICS_VERBS)}, "
        f"only pinned {sorted(sec.BURNED_CICS_VERBS - cics)}"
    )
    assert sql == set(sec.BURNED_SQL_VERBS)


@pytest.mark.parametrize("entry", sec.ENTRIES, ids=lambda e: f"{e.role}:{e.key}")
def test_every_entry_cites_a_manual_or_is_refused_by_name(entry):
    if entry.status == "refused":
        assert entry.note
    else:
        assert entry.cites
    for cite in entry.cites:
        assert cite.manual in sec.MANUALS


def test_the_manuals_name_their_release():
    for name, title in sec.MANUALS.items():
        assert re.search(r"Version 6|Db2 13|Enterprise COBOL for z/OS 6\.4", title), name


def test_the_four_sink_classes_the_issue_names_each_have_a_sink():
    classes = {e.sink_class for e in sec.ENTRIES if e.role == "sink"}
    assert classes == set(sec.SINK_CLASSES)
    by = {(e.key, e.sink_class) for e in sec.ENTRIES if e.role == "sink"}
    assert {
        ("PREPARE", "sql_injection"),
        ("EXECUTE IMMEDIATE", "sql_injection"),
        ("WRITE", "file_write"),
        ("REWRITE", "file_write"),
        ("DELETE", "file_write"),
        ("LINK", "control_transfer"),
        ("XCTL", "control_transfer"),
        ("START", "control_transfer"),
    } <= by


def test_the_sources_the_issue_names_are_present():
    sources = {e.key for e in sec.ENTRIES if e.role == "source"}
    assert {"RECEIVE", "RECEIVE MAP", "DFHCOMMAREA", "GET CONTAINER", "READQ", "WEB RECEIVE", "WEB READ"} <= sources


def test_what_ibm_leaves_open_is_assumed_or_refused_by_name():
    commarea = sec.entries_for("linkage", "DFHCOMMAREA")[0]
    assert commarea.status == "assumed" and "silent" in commarea.note
    assert {e.key for e in sec.ENTRIES if e.status == "refused"} >= {"EIBCALEN check", "MOVE or INSPECT REPLACING"}


def test_sanitizers_are_narrow():
    """Each stated sanitizer says what it removes; the NUMERIC test and DEEDIT never claim a range."""
    for e in sec.ENTRIES:
        if e.role == "sanitizer":
            assert e.when, e.key
    assert "never a range" in next(e for e in sec.ENTRIES if e.key == "NUMERIC class test").when


def test_a_sink_without_a_class_or_a_class_on_a_non_sink_is_refused_when_built():
    with pytest.raises(ValueError, match="sink class"):
        sec.Entry("X", "exec_cics", "sink", (), sec._c("cics-api", "X"))
    with pytest.raises(ValueError, match="sink class"):
        sec.Entry("X", "exec_cics", "source", (), sec._c("cics-api", "X"), sink_class="file_write")
    with pytest.raises(ValueError, match="no manual"):
        sec.Entry("X", "exec_cics", "source", (), (sec.Cite("nope", "X"),))
    with pytest.raises(ValueError, match="cites its manual"):
        sec.Entry("X", "exec_cics", "source", (), ())
    with pytest.raises(ValueError, match="says what the manual leaves open"):
        sec.Entry("X", "exec_cics", "source", (), sec._c("cics-api", "X"), status="assumed")


@pytest.mark.parametrize(
    ("kind", "body", "expected"),
    [
        ("exec_cics", " READ FILE('ACCTDAT') INTO(REC) RIDFLD(KEY) ", "READ"),
        ("exec_cics", "GET CONTAINER(WS-NAME) INTO(WS-AREA)", "GET CONTAINER"),
        ("exec_cics", "DELETE COUNTER(GENACNT100) POOL(X)", "DELETE COUNTER"),
        ("exec_cics", "DELETE FILE('ACCTDAT')", "DELETE"),
        ("exec_cics", "RECEIVE MAP('CC00M') MAPSET('CC00')", "RECEIVE MAP"),
        ("exec_cics", "WRITEQ TS QUEUE(Q) FROM(R)", "WRITEQ"),
        ("exec_sql", "SELECT NAME INTO :N FROM T", "SELECT"),
        ("exec_sql", "EXECUTE IMMEDIATE :STMT", "EXECUTE IMMEDIATE"),
    ],
)
def test_canonical_verb(kind, body, expected):
    assert sec.canonical_verb(kind, body) == expected
