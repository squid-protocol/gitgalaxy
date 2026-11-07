"""#7964: `cics_census.py preflight` is counts-only and exits non-zero on any finding, one check at a time."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_census as cc  # noqa: E402
import cics_preflight as pf  # noqa: E402

PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. ZZPGM1.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n{copies}       PROCEDURE DIVISION.\n"
    "           EXEC CICS RETURN END-EXEC.\n"
)
DATA_ONLY = "       01  ZZREC.\n           05  ZZ-ID   PIC X(8).\n"
SECRET = "ZZSECRETREPO"


def head_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cc.REPO, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def census(tmp_path, monkeypatch):
    root = tmp_path / "census"
    repo = root / SECRET
    repo.mkdir(parents=True)
    copies = "           COPY ZZREC.\n           COPY DFHAID.\n           COPY BAQRINFO.\n           COPY HWTJICAL.\n"
    (repo / "pgm.cbl").write_text(PROGRAM.format(copies=copies), encoding="utf-8")
    (repo / "ZZREC.cpy").write_text(DATA_ONLY, encoding="utf-8")
    (repo / "mem.cbl").write_text(DATA_ONLY, encoding="utf-8")
    monkeypatch.setattr(cc, "census_root_problems", lambda path: [])
    monkeypatch.setattr(pf, "owner_issues", lambda: [1, 2])
    return root


def run(census_dir, tmp_path, capsys, t0=None, state="open"):
    args = argparse.Namespace(root=tmp_path, census_corpora=census_dir, t0=t0 if t0 is not None else head_sha())
    rc = pf.cmd_preflight(args, state_of=lambda n: state)
    return rc, capsys.readouterr().out


def test_clean_fixture_passes_and_counts(census, tmp_path, capsys):
    rc, out = run(census, tmp_path, capsys)
    assert rc == 0, out
    assert "programs 1, copy members 1" in out
    assert "unknown copybook prefixes 0" in out
    assert "0 finding(s)" in out


def test_output_names_nothing(census, tmp_path, capsys):
    _, out = run(census, tmp_path, capsys)
    for word in (SECRET, "pgm", "ZZPGM1", "ZZREC", "DFHAID", "BAQRINFO"):
        assert word not in out


def test_unknown_prefix_is_a_finding(census, tmp_path, capsys):
    (census / SECRET / "pgm2.cbl").write_text(PROGRAM.format(copies="           COPY QQQREC.\n"), encoding="utf-8")
    rc, out = run(census, tmp_path, capsys)
    assert rc == 1
    assert "FAIL unknown copybook prefixes 1" in out
    assert "QQQ" not in out


def test_closed_owner_is_a_finding(census, tmp_path, capsys):
    rc, out = run(census, tmp_path, capsys, state="closed")
    assert rc == 1
    assert "FAIL gap-map owners 2, not open 2" in out


def test_gh_failure_is_a_finding(census, tmp_path, capsys):
    rc, _ = run(census, tmp_path, capsys, state="unknown")
    assert rc == 1


def test_census_dir_problem_is_a_finding(census, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cc, "census_root_problems", lambda path: ["unexpected: before-nb-local"])
    rc, out = run(census, tmp_path, capsys)
    assert rc == 1
    assert "FAIL census dir: 1 problems (unexpected)" in out
    assert "before-nb-local" not in out


def test_missing_census_dir_is_a_finding(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(pf, "owner_issues", lambda: [])
    rc, out = run(tmp_path / "absent", tmp_path, capsys)
    assert rc == 1
    assert "FAIL census dir: not given" in out


def test_no_program_is_a_finding(census, tmp_path, capsys):
    (census / SECRET / "pgm.cbl").unlink()
    rc, out = run(census, tmp_path, capsys)
    assert rc == 1
    assert "FAIL programs 0, copy members 1" in out


def test_t0_missing_unresolvable_and_recorded_file(census, tmp_path, capsys):
    args = argparse.Namespace(root=tmp_path, census_corpora=census, t0=None)
    assert pf.cmd_preflight(args, state_of=lambda n: "open") == 1
    assert "T0 SHA: not recorded" in capsys.readouterr().out
    rc, out = run(census, tmp_path, capsys, t0="0" * 40)
    assert rc == 1
    assert "does not resolve" in out
    (tmp_path / pf.T0_FILE).write_text(json.dumps({"sha": head_sha()}), encoding="utf-8")
    assert pf.cmd_preflight(args, state_of=lambda n: "open") == 0
    assert "T0 SHA: recorded" in capsys.readouterr().out


def test_owner_issues_skip_accounted_rows():
    import gap_prevalence as gp

    got = set(pf.owner_issues())
    assert 7709 not in got or any(
        o.startswith("#7709") and "source defect" not in o and "product copybook frontier" not in o
        for _, o in gp.OWNERS
    )
    assert got and all(isinstance(n, int) for n in got)


def test_gh_state_failure_reads_unknown(monkeypatch):
    monkeypatch.setattr(pf.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "boom"))
    assert pf.gh_state(1) == "unknown"


def test_census_root_problems_matches_the_raising_check(tmp_path):
    (tmp_path / "scratch").mkdir()
    parts = cc.census_root_problems(tmp_path)
    assert parts
    with pytest.raises(SystemExit) as e:
        cc.check_census_root(tmp_path)
    assert "; ".join(parts) in str(e.value)
