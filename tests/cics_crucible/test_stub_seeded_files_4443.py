"""#4443: the cobol-stub's files.cfg carries the case's seeded files (it was empty: every file READ was FILENOTFOUND).

A case's `data/<FILE>.dat` (one record per line) becomes fixed-length records and a files.cfg line; the key length is the
RIDFLD length of the expected READ events. A file with no seed, no expected READ, or ragged lines is left out."""

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402
import crucible_events as ev  # noqa: E402
import pytest  # noqa: E402

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
    assert cfg == "HCUF /work/runs/read-short/files/HCUF 16 0 4 NONE\n"
    assert (work / "runs/read-short/files/HCUF").read_bytes() == b"K001ALPHA   0010K002BRAVO   0020"


def test_seed_files_leaves_out_a_case_without_files(tmp_path):
    assert runner.seed_files(_case(tmp_path, "DEFINE PROGRAM(P) GROUP(G)\n"), tmp_path / "w", "s") == ""


# #7956: the SYNCPOINT / SYNCPOINT-ROLLBACK events (SPEC 6.2): the runtimes recorded them, the crucible tables had no row.
# A case file is not recoverable (SPEC section 2), so the stub's files.cfg line above carries NONE: a rollback keeps its records.
KINDS = ("SYNCPOINT", "SYNCPOINT-ROLLBACK")


@pytest.mark.parametrize("kind", KINDS)
def test_the_event_builder_takes_resp_and_refuses_other_keys(kind):
    assert ev.event(kind, "P", resp="NORMAL") == {"event": kind, "program": "P", "resp": "NORMAL"}
    assert ev.event(kind, "P", resp="INVREQ", resp2=200)["resp2"] == 200
    with pytest.raises(ValueError, match="missing"):
        ev.event(kind, "P")
    with pytest.raises(ValueError, match="unknown"):
        ev.event(kind, "P", resp="NORMAL", file="F")


@pytest.mark.parametrize("kind", KINDS)
def test_the_comparison_and_both_legs_carry_the_keys(kind):
    assert cc.EVENT_KEYS[kind] == ("resp", "resp2")
    assert runner.COBOL_CAPS.events[kind] == frozenset({"resp", "resp2"})
    assert runner.JAVA_CAPS.events[kind] == frozenset({"resp", "resp2"})


def test_a_syncpoint_only_program_records_file_events_only_in_a_crucible_port():
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import cics_filecontrol as fc

    class Prog(fc.FileControlCommands):
        class g:  # noqa: N801
            class p:  # noqa: N801
                class proc:  # noqa: N801
                    execs = {1: "READ FILE('F') INTO(R) RIDFLD(K) UPDATE", 2: "SYNCPOINT RESP(X)"}

    assert Prog()._records_file_events() is False
    with fc.record_file_updates():
        assert Prog()._records_file_events() is True
