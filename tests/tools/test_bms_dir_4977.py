# ruff: noqa: S101, ARG001, E402, I001
"""#4977: bms_dir() must hand every parallel case the complete symbolic-map set (the det sweep's cases are threads)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests" / "tools"))
sys.path.insert(0, str(REPO_ROOT))

import equivalence_common
from gitgalaxy.tools.cobol_to_java.det import source

N = 6


def _slow_copybooks(paths, out: Path) -> None:
    """Like bms_copybooks: make the directory first, then write the members one by one (slowly)."""
    out.mkdir(parents=True, exist_ok=True)
    for i in range(N):
        time.sleep(0.01)
        (out / f"MAP{i}.cpy").write_text("       01 X PIC X.\n")


def test_parallel_threads_see_the_whole_set(tmp_path, monkeypatch):
    monkeypatch.setattr(source, "bms_copybooks", _slow_copybooks)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "M.bms").write_text("")
    with ThreadPoolExecutor(8) as ex:
        seen = list(ex.map(lambda _: sorted(p.name for p in equivalence_common.bms_dir(corpus).iterdir()), range(8)))
    assert all(len(s) == N for s in seen), seen
    assert [p.name for p in (tmp_path / "_bms").iterdir()] == ["corpus"]  # no temp directories left behind
