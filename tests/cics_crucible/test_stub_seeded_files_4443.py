"""#4443: the cobol-stub's files.cfg carries the case's seeded files (it was empty: every file READ was FILENOTFOUND).

A case's `data/<FILE>.dat` (one record per line) becomes fixed-length records and a files.cfg line; the key length is the
RIDFLD length of the expected READ events. A file with no seed, no expected READ, or ragged lines is left out."""

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402

CSD = "DEFINE FILE(HCUF) GROUP(G) DSNAME(A.B)\nDEFINE FILE(NOSEED) GROUP(G)\nDEFINE FILE(RAGGED) GROUP(G)\nDEFINE FILE(NOREAD) GROUP(G)\n"


def _case(tmp_path: Path, csd: str = CSD) -> cc.Case:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "HCUF.dat").write_bytes(b"K001ALPHA   0010\nK002BRAVO   0020\n")
    (tmp_path / "data" / "RAGGED.dat").write_bytes(b"A1\nB22\n")
    (tmp_path / "data" / "NOREAD.dat").write_bytes(b"A1\nB2\n")
    log = {"tasks": [{"events": [{"event": "READ", "file": f, "ridfld": "K002"} for f in ("HCUF", "RAGGED")]}]}
    return cc.Case(tmp_path, {}, {"s": log}, cc.parse_csd(csd))


def test_parse_csd_names_the_files_only_when_there_are_some():
    assert cc.parse_csd(CSD)["files"] == {"HCUF", "NOSEED", "RAGGED", "NOREAD"}
    assert "files" not in cc.parse_csd("DEFINE PROGRAM(P) GROUP(G)\n")


def test_seed_files_writes_fixed_records_and_the_cfg_line(tmp_path):
    work = tmp_path / "work"
    cfg = runner.seed_files(_case(tmp_path), work, "read-short")
    assert cfg == "HCUF /work/runs/read-short/files/HCUF 16 0 4\n"
    assert (work / "runs/read-short/files/HCUF").read_bytes() == b"K001ALPHA   0010K002BRAVO   0020"


def test_seed_files_leaves_out_a_case_without_files(tmp_path):
    assert runner.seed_files(_case(tmp_path, "DEFINE PROGRAM(P) GROUP(G)\n"), tmp_path / "w", "s") == ""
