"""#5054 done-when 2: the anonymized `readiness --blockers` output leaks nothing of the source it was made from.

Unlike tests/tools/test_blocker_report.py (which injects names into hand-built gap strings), this runs the real
`readiness_report --blockers` path on an estate's evidence report, then scans both anonymized files for every
identifier, quoted literal, comment line and path of the source: the checked-out corpora for the burned estates
(CardDemo, GenApp, CBSA, zECS) and the cics-crucible cases. A fixture estate with planted secrets runs without any
corpus, so the path is checked on every PR."""

import json
import os
import re
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import blocker_report as br
import readiness_report as rr

from gitgalaxy.core.source_text import read_source

REPO = Path(__file__).resolve().parents[2]
_CORPORA_ENV = os.environ.get("GITGALAXY_MAINFRAME_CORPORA", "")
CORPORA = Path(_CORPORA_ENV or REPO / ".mainframe_corpora")
CRUCIBLE = Path(os.environ.get("CICS_CRUCIBLE_PATH") or REPO.parent / "cics-crucible")
ESTATES = [
    "aws-mainframe-modernization-carddemo",
    "cics-genapp",
    "cics-banking-sample-application-cbsa",
    "zecs",
    "cics-crucible",
]
SOURCE_SUFFIXES = {".cbl", ".cob", ".cobol", ".cpy", ".copy", ".jcl", ".proc", ".bms", ".asm", ".mac", ".pli"}
MAX_FILES, MAX_BYTES = 6000, 400_000
MIN_LEN = 4
WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*")
LITERAL = re.compile(r"\"([^\"\n]{4,80})\"|'([^'\n]{4,80})'")
BOILERPLATE = set(
    "IDENTIFICATION DIVISION PROGRAM-ID DATA WORKING-STORAGE SECTION COPY PROCEDURE GOBACK MOVE END-EXEC "
    "STOP RUN PERFORM DISPLAY CALL USING EXEC CICS SQL PICTURE VALUE SPACES ZEROS ZERO".split()
)  # fmt: skip
SALT_BYTES = bytes.fromhex("5a" * 32)


def _template_words(salt: bytes) -> set[str]:
    """Every word of an anonymized report that has no source behind it: the fixed text the files always carry."""
    anon = br.anon_report({"whole": 0, "proven": 0, "gaps": [], "programs": []}, salt, "e")
    return {w.upper() for w in WORD.findall(json.dumps(anon) + br.anon_markdown(anon))}


def source_tokens(root: Path) -> dict[str, set[str]]:
    """Every identifier, literal, comment line and path piece under `root`, by kind. Uppercased for matching."""
    found: dict[str, set[str]] = {"identifier": set(), "literal": set(), "comment": set(), "path": set()}
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SOURCE_SUFFIXES)
    for f in files[:MAX_FILES]:
        if f.stat().st_size > MAX_BYTES:
            continue
        rel = f.relative_to(root)
        found["path"].update(part.upper() for part in (*rel.parts[:-1], f.stem, f.name))
        for line in read_source(f).text.splitlines():
            body = line[6:] if len(line) > 6 else ""
            if (len(line) > 6 and line[6] == "*") or line.lstrip().startswith(("*>", "*")):
                text = line.lstrip().lstrip("*>").strip()
                if len(text) >= 12:
                    found["comment"].add(text.upper())
            elif "*>" in line:
                text = line.split("*>", 1)[1].strip()
                if len(text) >= 12:
                    found["comment"].add(text.upper())
            for m in LITERAL.finditer(line):
                found["literal"].add((m.group(1) or m.group(2)).upper())
            found["identifier"].update(w.upper() for w in WORD.findall(body or line))
    return found


def leaks(text: str, tokens: dict[str, set[str]], skip: set[str]) -> list[tuple[str, str]]:
    """(kind, token) for each source token present in `text` (case-folded; identifiers match on word boundaries)."""
    up = text.upper()
    words = {w.upper() for w in WORD.findall(text)}
    found = []
    for kind, toks in tokens.items():
        for raw in sorted(toks):
            t = raw.strip()
            if len(t) < MIN_LEN or t in skip:
                continue
            parts = [w.upper() for w in WORD.findall(t)]
            if kind != "identifier" and parts and all(w in skip for w in parts):
                continue  # prose made of words the report spells itself is not the source's
            if kind == "identifier":
                hit = t in words
            else:
                hit = re.search(r"(?<![A-Z0-9-])" + re.escape(t) + r"(?![A-Z0-9-])", up) is not None
            if hit:
                found.append((kind, t))
    return found


def run_blockers(out: Path, salt_file: Path, estate: str, *more: str) -> dict[str, str]:
    """The real CLI path; the two anonymized files of `estate` as text, keyed by suffix."""
    argv = ["--blockers", str(out), "--salt-file", str(salt_file), "--out", str(out / "readiness.md")]
    if more:
        argv += ["--redact-more", *more]
    assert rr.main([estate, *argv]) == 0  # the estate first: --redact-more takes every word after it
    d = out / estate
    return {s: (d / f"blocker_report.anon.{s}").read_text(encoding="utf-8") for s in ("json", "md")}


# ---- a fixture estate: no corpus needed -------------------------------------------------------------------------
SECRETS = [
    "ACMEPAY",
    "CUSTLEDG",
    "PAYROLL-MASTER",
    "SECRETFLD",
    "ZZCOPY1",
    "PGMALPHA",
    "acme-widgets",
    "never ship this comment",
    "/home/acme/src/pay.cbl",
]


def _fixture_program(name: str, whole: bool, gaps: list[str], nxt: list[str]) -> dict:
    return {
        "program": name,
        "level": "L1",
        "next": nxt,
        "translation": {
            "whole": whole,
            "refused": None,
            "gap_classes": gaps,
            "holes": [],
            "hole_count": 0,
        },
    }


@pytest.fixture
def fixture_estate(tmp_path, monkeypatch):
    reports, inv = tmp_path / "reports", tmp_path / "inv"
    est = "acme-widgets"
    (reports / est).mkdir(parents=True)
    inv.mkdir()
    (inv / f"{est}.json").write_text("{}", encoding="utf-8")
    progs = [
        _fixture_program("PGMALPHA", False, ["missing copybook ZZCOPY1", "EXEC CICS READ FILE CUSTLEDG"], []),
        _fixture_program("ACMEPAY", False, ["refused: LayoutError: cuts the literal 'SECRETFLD' open"], []),
        _fixture_program("PAYROLL-MASTER", False, ["fact: PAYROLL-MASTER", "something new about /home/acme/src/pay.cbl"], []),
        _fixture_program("CUSTLEDG", True, [], ["an equivalence case that runs it (CUSTLEDG)"]),
        _fixture_program("PGMBETA", True, [], ["its det port equal on every scenario of PGMBETA, a Db2 case"]),
    ]  # fmt: skip
    (reports / est / "report.json").write_text(
        json.dumps({"programs": progs, "bars": {"paragraphs": 100.0, "branches": 100.0}, "levels": {}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(rr, "REPORTS", reports)
    monkeypatch.setattr(rr, "INVENTORY", inv)
    return est


@pytest.mark.parametrize("more", [(), ("subclass",), ("counts",), ("repro",), ("subclass", "counts", "repro")])
def test_fixture_estate_planted_secrets_do_not_reach_the_anonymized_files(tmp_path, fixture_estate, more):
    files = run_blockers(tmp_path / "out", tmp_path / "salt", fixture_estate, *more)
    text = files["json"] + files["md"]
    for secret in SECRETS:
        assert secret.upper() not in text.upper(), secret
    assert not re.search(r"[^\x00-\x7f]", text)
    assert (tmp_path / "salt").read_text(encoding="utf-8").strip() not in text  # the salt itself
    assert json.loads(files["json"])["blockers"], "the fixture has blockers to anonymize"


def test_fixture_estate_full_twin_keeps_the_names_the_anonymized_one_drops(tmp_path, fixture_estate):
    """The scan has teeth: the full report carries the planted names, so absence from the twin is not vacuous."""
    run_blockers(tmp_path / "out", tmp_path / "salt", fixture_estate)
    full = (tmp_path / "out" / fixture_estate / "blocker_report.full.json").read_text(encoding="utf-8")
    assert "ZZCOPY1" in full and "CUSTLEDG" in full


def test_leak_scan_catches_every_kind(tmp_path):
    src = tmp_path / "estate" / "payroll-app" / "src"
    src.mkdir(parents=True)
    (src / "ledgerx.cbl").write_text(
        "      * MONTHLY RECONCILIATION OF THE LEDGER\n"
        "       01 SECRETFLD PIC X(8) VALUE 'HUSHHUSH'.\n"
        "           MOVE 1 TO WS-OUT *> inline remark about taxes\n",
        encoding="utf-8",
    )
    toks = source_tokens(tmp_path / "estate")
    assert {"SECRETFLD"} <= toks["identifier"] and "HUSHHUSH" in toks["literal"]
    assert "MONTHLY RECONCILIATION OF THE LEDGER" in toks["comment"]
    assert "INLINE REMARK ABOUT TAXES" in toks["comment"]
    assert {"PAYROLL-APP", "LEDGERX"} <= toks["path"]
    for kind, token in (
        ("identifier", "SECRETFLD"),
        ("literal", "hushhush"),
        ("comment", "monthly reconciliation of the ledger"),
        ("path", "payroll-app"),
    ):
        assert (kind, token.upper()) in leaks(f"x {token} y", toks, set())
    assert not leaks("BLK_016e2d unclassified", toks, set())


# ---- the real names of the burned estates -----------------------------------------------------------------------
def _source_root(estate: str) -> Path:
    return CRUCIBLE / "cases" if estate == "cics-crucible" else CORPORA / estate


@pytest.fixture(scope="module")
def template_words() -> set[str]:
    own = {w.upper() for w in WORD.findall(Path(br.__file__).read_text(encoding="utf-8"))}  # words the tool spells
    return _template_words(SALT_BYTES) | own | BOILERPLATE | set(br.vocabulary())


@pytest.mark.parametrize("estate", ESTATES)
def test_anonymized_blockers_leak_nothing_of_the_estate_source(estate, tmp_path, template_words):
    root = _source_root(estate)
    if not root.is_dir():
        if _CORPORA_ENV and estate != "cics-crucible":
            pytest.fail(f"{estate} missing under GITGALAXY_MAINFRAME_CORPORA: the leak scan would skip")
        pytest.skip(f"{estate} not checked out (GITGALAXY_MAINFRAME_CORPORA / CICS_CRUCIBLE_PATH)")
    toks = source_tokens(root)
    assert toks["identifier"] and toks["path"], "the source scan found nothing to look for"
    if estate == "cics-crucible":  # no feature inventory, so the CLI's estate list omits it: the same writer it calls
        rr.write_blockers([estate], tmp_path / "out", SALT_BYTES)
        d = tmp_path / "out" / estate
        files = {s: (d / f"blocker_report.anon.{s}").read_text(encoding="utf-8") for s in ("json", "md")}
        assert estate not in files["json"] + files["md"]
    else:
        files = run_blockers(tmp_path / "out", tmp_path / "salt", estate)
        assert estate not in files["json"] + files["md"]
    found = leaks(files["json"] + "\n" + files["md"], toks, template_words)
    assert not found, found[:10]
