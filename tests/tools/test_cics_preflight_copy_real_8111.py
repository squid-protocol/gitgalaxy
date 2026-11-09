"""#8111: `cics_census.py preflight` runs the REAL copybook resolver over the census dir (no injected engine): a
member the resolver misses is a finding, every other census class (agree, ambiguous, neither) is not."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_census as cc  # noqa: E402
import cics_preflight as pf  # noqa: E402
import copy_resolution_census as crc  # noqa: E402

PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. ZZPGM1.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n{copies}       PROCEDURE DIVISION.\n           GOBACK.\n"
)
ITEM = "       01  ZZREC.\n           05  ZZ-ID   PIC X(8).\n"
SECRET = "ZZSECRETREPO"


def build(tmp_path: Path, copies: str, members: dict[str, str]) -> Path:
    root = tmp_path / "census"
    repo = root / SECRET
    (repo / "apps").mkdir(parents=True)
    (repo / "apps" / "pgm.cbl").write_text(PROGRAM.format(copies=copies), encoding="utf-8")
    for rel, text in members.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return root


def run(root: Path, tmp_path: Path, capsys, monkeypatch, engine=None):
    monkeypatch.setattr(cc, "census_root_problems", lambda path: [])
    monkeypatch.setattr(pf, "owner_issues", lambda: [])
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cc.REPO, capture_output=True, text=True, check=True
    ).stdout.strip()
    args = argparse.Namespace(root=tmp_path, census_corpora=root, t0=sha)
    rc = pf.cmd_preflight(args, state_of=lambda n: "open", copy_engine=engine)
    out = capsys.readouterr().out
    return rc, next(line for line in out.splitlines() if "copy resolution" in line), out


def test_real_resolver_agreeing_estate_is_clean(tmp_path, capsys, monkeypatch):
    copies = "".join(f"       COPY {m}.\n" for m in ("LOWER1", "UPPER2", "NOEXT3", "NESTED4"))
    root = build(
        tmp_path,
        copies,
        {"apps/lower1.cpy": ITEM, "cpy/UPPER2.CPY": ITEM, "cpy/NOEXT3": ITEM, "cpy/inc/nested4.copy": ITEM},
    )
    rc, line, out = run(root, tmp_path, capsys, monkeypatch)
    assert line.startswith("ok   ") and "agree 4" in line and "miss 0" in line and "different 0" in line, out
    assert rc == 0, out
    assert SECRET not in out


@pytest.mark.parametrize(
    ("copies", "members", "klass"),
    [
        ("       COPY GHOST6.\n", {}, "neither 1"),
        ("       COPY TWIN8.\n", {"a/TWIN8.cpy": ITEM, "b/TWIN8.cpy": ITEM}, "ambiguous 1"),
    ],
)
def test_neither_and_ambiguous_are_not_findings(tmp_path, capsys, monkeypatch, copies, members, klass):
    _rc, line, out = run(build(tmp_path, copies, members), tmp_path, capsys, monkeypatch)
    assert line.startswith("ok   ") and klass in line, out  # (rc may still be 1: a ghost member's prefix is unknown)


def test_a_member_the_resolver_misses_is_a_finding(tmp_path, capsys, monkeypatch):
    """The real census over a resolver that returns no edges: the repo holds the member, the engine does not."""
    root = build(tmp_path, "       COPY ZZREC.\n", {"cpy/ZZREC.cpy": ITEM})
    rc, line, out = run(root, tmp_path, capsys, monkeypatch, engine=lambda repo: ({}, set()))
    assert line.startswith("FAIL ") and "miss 1" in line, out
    assert rc == 1
    assert SECRET not in out
    # and the same estate through the real resolver agrees
    rc2, line2, _ = run(root, tmp_path, capsys, monkeypatch)
    assert rc2 == 0 and "agree 1" in line2
    assert crc.disagreements(crc.census_repo(root / SECRET)) == 0
