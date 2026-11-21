"""A det port onto a generated project with no CICS package compiles (#7065, estate-crucible Batch Badlands).

The det runtime's cobolrt/cics/ (DetCics and DetMq import the generated project's CICS package, CicsTask and CicsSpec;
DetJustify calls DetCics) went into every port. A batch-only estate (BDLD: no CICS program, so no cics package) got it
anyway, and every port's Java failed to compile ("package ...cics does not exist") before a proof could run. It is
left out of a project without the package; a project with it, or none named, keeps the whole runtime as before.
"""

from __future__ import annotations

import sys
from pathlib import Path

from gitgalaxy.tools.cobol_to_java.det import program as P

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import mainframe_corpus as mc

PKG = "com.x"


def _project(tmp_path: Path, *, batch: bool, cics: bool) -> Path:
    root = tmp_path / "proj" / "src/main/java/com/x"
    if batch:
        (root / "batch").mkdir(parents=True)
        (root / "batch/CobolFiles.java").write_text("", encoding="utf-8")
    if cics:
        (root / "cics").mkdir(parents=True)
        (root / "cics/CicsTask.java").write_text("", encoding="utf-8")
    return tmp_path / "proj"


def test_has_cics_reads_the_generated_package(tmp_path):
    assert P.has_cics(None)
    assert P.has_cics(_project(tmp_path / "a", batch=True, cics=True))
    assert not P.has_cics(_project(tmp_path / "b", batch=True, cics=False))


def test_without_cics_the_cics_runtime_is_left_out():
    whole, batch_only = P.runtime_files(PKG, True), P.runtime_files(PKG, True, cics=False)
    gone = set(whole) - set(batch_only)
    assert {"cobolrt/cics/DetCics.java", "cobolrt/cics/DetMq.java", "cobolrt/cics/DetJustify.java"} <= gone
    assert all(rel.startswith("cobolrt/cics/") for rel in gone)
    # nothing left names the generated CICS package or the cics runtime (DetJustify called DetCics unimported)
    code = [ln for t in batch_only.values() for ln in t.splitlines() if not ln.lstrip().startswith(("*", "//", "/*"))]
    assert not any(f"import {PKG}.cics." in ln or "DetCics." in ln or "DetMq." in ln for ln in code)
    assert set(batch_only) <= set(whole) and all(batch_only[k] == whole[k] for k in batch_only)


def test_project_runtime_follows_the_project(tmp_path):
    batch_only = _project(tmp_path / "b", batch=True, cics=False)
    both = _project(tmp_path / "c", batch=True, cics=True)
    cics_only = _project(tmp_path / "d", batch=False, cics=True)
    assert P.project_runtime(PKG, batch_only) == P.runtime_files(PKG, True, cics=False)
    assert P.project_runtime(PKG, both) == P.runtime_files(PKG, True)
    assert P.project_runtime(PKG, cics_only) == P.runtime_files(PKG, False)
    assert P.project_runtime(PKG, None) == P.runtime_files(PKG, True)


def test_estate_crucible_is_a_case_corpus_at_its_own_pin(monkeypatch, tmp_path):
    (entry,) = mc.select(["estate-crucible"])
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _estate_crucible_pin import PINNED_REF

    assert entry["crucible"] == "estate" and entry["ref"] == PINNED_REF
    assert "estate-crucible" not in {c["name"] for c in mc.select([])}  # not a manifest corpus
    monkeypatch.setenv("ESTATE_CRUCIBLE_PATH", str(tmp_path / "estate"))
    monkeypatch.setenv("CICS_CRUCIBLE_PATH", str(tmp_path / "cics"))
    assert mc.clone_path(entry) == tmp_path / "estate"  # its pin's path_env, not cics-crucible's
    assert mc.clone_path(mc.select(["cics-crucible"])[0]) == tmp_path / "cics"
