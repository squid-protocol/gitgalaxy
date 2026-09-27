"""#3815 (part 2): stored paths are NFC; include / copybook resolution matches across NFC and NFD.

macOS (HFS+ / APFS exports) and some zip / git checkouts write file names decomposed (NFD: `e` +
U+0301), others composed (NFC: `é`). The engine stores and reports every path in NFC and opens the
real on-disk name, so the same estate scanned from either checkout records the same paths, a delta
scan of an NFD checkout does not read an edit as a rename, and a COPY / #include spelled in one
form resolves a file stored in the other.
"""

import os
import shutil
import sqlite3
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest

from gitgalaxy.core.invocation_resolver import resolve_invocations
from gitgalaxy.core.unicode_paths import nfc, on_disk
from gitgalaxy.galaxyscope import Orchestrator
from gitgalaxy.metrics.chronometer import Chronometer
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db


def NFD(text: str) -> str:  # noqa: N802 -- named for the form it produces
    return unicodedata.normalize("NFD", text)


PROGRAM = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CAFE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY KÖNIG.
       PROCEDURE DIVISION.
           DISPLAY 'HI'.
           STOP RUN.
"""
COPYBOOK = "       01  KREC.\n           05  KNR  PIC 9(4).\n"
PATHS = {"café.cbl", "könig.cpy", "main.c", "naïve.h"}


def _estate(root: Path, form) -> Path:
    """The program `café.cbl` COPYs `KÖNIG` (written NFC) from `könig.cpy`; `main.c` includes
    `naïve.h` written NFD. `form` spells the file names (NFD: a macOS export; NFC: Linux)."""
    root.mkdir(parents=True)
    (root / form("café.cbl")).write_text(PROGRAM, encoding="utf-8")
    (root / form("könig.cpy")).write_text(COPYBOOK, encoding="utf-8")
    (root / "main.c").write_text(f'#include "{NFD("naïve.h")}"\nint main(void) {{ return helper(); }}\n')
    (root / form("naïve.h")).write_text("int helper(void);\n", encoding="utf-8")
    return root


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],  # noqa: S607
        cwd=root,
        check=True,
        capture_output=True,
    )


def _rows(db: Path) -> tuple[dict[int, tuple[str, int]], set[tuple[str, str]]]:
    """({file id: (path, total_loc)}, {(importer, imported)}) of the DB's latest snapshot."""
    con = sqlite3.connect(db)
    try:
        commit = con.execute("SELECT commit_hash FROM file_data ORDER BY id DESC LIMIT 1").fetchone()[0]
        files = {
            fid: (path, loc)
            for fid, path, loc in con.execute(
                "SELECT id, file_path, total_loc FROM file_data WHERE commit_hash = ?", (commit,)
            )
        }
        edges = {
            (files[s][0], files[d][0])
            for s, d in con.execute(
                "SELECT src_file_id, dst_file_id FROM edge_data WHERE commit_hash = ? AND edge_kind = 'import'",
                (commit,),
            )
        }
    finally:
        con.close()
    return files, edges


@pytest.fixture(scope="module")
def nfd_scan(tmp_path_factory):
    """An NFD-named git checkout and its full scan."""
    if shutil.which("git") is None:
        pytest.skip("git is required")
    base = tmp_path_factory.mktemp("nfc_paths")
    estate = _estate(base / "estate", NFD)
    if {p.name for p in estate.iterdir()} == PATHS:
        pytest.skip("this file system normalises names to NFC itself; nothing to test")
    _git(estate, "init", "-q")
    _git(estate, "add", "-A")
    _git(estate, "commit", "-qm", "baseline")
    return estate, scan_to_db(estate, base / "scan")


def test_an_nfd_checkout_stores_nfc_paths(nfd_scan):
    files, _ = _rows(nfd_scan[1])
    paths = {p for p, _ in files.values()}
    assert paths == PATHS
    assert all(unicodedata.is_normalized("NFC", p) for p in paths)


def test_a_copy_written_nfc_resolves_an_nfd_named_copybook(nfd_scan):
    _, edges = _rows(nfd_scan[1])
    assert ("café.cbl", "könig.cpy") in edges


def test_an_include_written_nfd_resolves_an_nfc_stored_header(nfd_scan):
    _, edges = _rows(nfd_scan[1])
    assert ("main.c", "naïve.h") in edges


def test_nfc_and_nfd_checkouts_record_the_same_paths_and_edges(nfd_scan, tmp_path):
    nfc_db = scan_to_db(_estate(tmp_path / "estate", nfc), tmp_path / "scan")
    nfd_files, nfd_edges = _rows(nfd_scan[1])
    nfc_files, nfc_edges = _rows(nfc_db)
    assert sorted(nfd_files.values()) == sorted(nfc_files.values())
    assert nfd_edges == nfc_edges


def test_a_delta_rescan_of_an_nfd_checkout_sees_no_rename(nfd_scan, tmp_path):
    """git names the edited file by its NFD on-disk path (octal-escaped unless quotepath is off);
    the baseline stores it in NFC. The delta must re-scan that one file in place."""
    estate, baseline_db = nfd_scan
    work = tmp_path / "estate"
    shutil.copytree(estate, work)
    program = work / NFD("café.cbl")
    program.write_text(PROGRAM.replace("           STOP RUN.\n", "           DISPLAY 'BYE'.\n           STOP RUN.\n"))
    _git(work, "commit", "-qam", "edit")
    out = tmp_path / "delta"
    out.mkdir()
    env = {**os.environ, "GITGALAXY_DISABLE_GIT_HISTORY": "1"}
    subprocess.run(  # noqa: S603 -- this interpreter + fixed module; paths are argv entries
        [
            sys.executable,
            "-m",
            "gitgalaxy.galaxyscope",
            str(work),
            "--db-only",
            "--output",
            str(out),
            "--incremental",
            str(baseline_db),
        ],  # fmt: skip
        check=True,
        env=env,
        capture_output=True,
        timeout=600,
    )
    files, edges = _rows(out / "estate_galaxy_master.db")
    by_path = {p: loc for p, loc in files.values()}
    assert sorted(p for p, _ in files.values()) == sorted(PATHS)  # one row each: no rename, no stale twin
    before = dict(_rows(baseline_db)[0].values())
    assert by_path["café.cbl"] == before["café.cbl"] + 1  # the edit was re-scanned
    assert ("café.cbl", "könig.cpy") in edges


def test_git_history_of_an_nfd_named_file_is_found_by_its_stored_path(nfd_scan, monkeypatch):
    """The churn / author maps were keyed by git's octal-escaped name; they are keyed in NFC now."""
    monkeypatch.delenv("GITGALAXY_DISABLE_GIT_HISTORY", raising=False)
    history = Chronometer(nfd_scan[0]).get_file_history_metrics("café.cbl")
    assert history["commit_count"] >= 1 and history["authors"] == {"t": 1}


def test_ascii_paths_are_untouched():
    for p in ("src/main.c", "COPYLIB/CUSTREC.cpy", ""):
        assert nfc(p) is p  # not even a copy: ASCII estates stay byte-identical
    assert nfc(NFD("café")) == "café"


def _census() -> Orchestrator:
    orch = object.__new__(Orchestrator)  # only the census maps, not a whole scan's setup
    orch.stem_map, orch.disk_paths = {}, {}
    return orch


def test_the_census_keeps_the_on_disk_name_only_where_it_differs():
    orch = _census()
    assert orch._stored_path("src/main.c", True, None) == ("src/main.c", True, None)
    assert orch.disk_paths == {}
    assert orch._stored_path(NFD("src/café.cbl"), True, None) == ("src/café.cbl", True, None)
    assert orch.disk_paths == {"src/café.cbl": NFD("src/café.cbl")}


def test_two_unicode_equivalent_names_are_not_silently_merged():
    orch = _census()
    orch._stored_path("café.cbl", True, None)
    orch.stem_map["café.cbl"] = "café.cbl"
    path, valid, reason = orch._stored_path(NFD("café.cbl"), True, None)
    assert (path, valid) == ("café.cbl", False) and "Unicode-equivalent" in reason
    assert orch.disk_paths == {}  # the stored file is the NFC one: it opens by its own name


def test_a_call_spelled_nfd_resolves_a_program_declared_nfc():
    files = [
        {"path": "a.cbl", "lang_id": "cobol", "classes": [{"name": "KÖNIG"}]},
        {"path": "b.cbl", "lang_id": "cobol", "call_sites": [{"verb": "CALL", "target": NFD("KÖNIG"), "line": 3}]},
    ]
    sites, _ = resolve_invocations(files)
    assert sites[0]["resolved_path"] == "a.cbl"


def test_on_disk_finds_the_decomposed_spelling(tmp_path):
    (tmp_path / NFD("dïr")).mkdir()
    (tmp_path / NFD("dïr") / NFD("café.cbl")).write_text("x")
    (tmp_path / "plain.cbl").write_text("x")
    assert on_disk(tmp_path, "dïr/café.cbl").read_text() == "x"
    assert on_disk(tmp_path, "plain.cbl") == tmp_path / "plain.cbl"
    assert on_disk(tmp_path, "missing/é.cbl") == tmp_path / "missing/é.cbl"
