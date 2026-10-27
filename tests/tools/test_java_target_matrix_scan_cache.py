"""#5142: java_target_matrix.py keeps the engine scan under a digest of what decides it."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import java_target_matrix as m


def _tree(root: Path) -> Path:
    for rel, text in {
        "gitgalaxy/core/detector.py": "a = 1\n",
        "gitgalaxy/tools/cobol_to_java/translator.py": "t = 1\n",
        "gitgalaxy/tools/cobol_to_java/det/copy/CEEIGZCT.cpy": "      01 X PIC X.\n",
        "gitgalaxy/cobol_to_java_controller.py": "c = 1\n",
        "gitgalaxy/cobol_refractor_controller.py": "r = 1\n",
        "tests/unrelated.py": "u = 1\n",
    }.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    return root


def _corpus(root: Path, text: str = "       IDENTIFICATION DIVISION.\n") -> Path:
    root.mkdir()
    (root / "A.cbl").write_text(text, encoding="utf-8")
    return root


def test_the_key_ignores_generation_only_files_and_follows_scan_inputs(tmp_path):
    code, corpus = _tree(tmp_path / "code"), _corpus(tmp_path / "corp")
    base = m.scan_key(code, corpus)
    for rel in (
        "gitgalaxy/tools/cobol_to_java/translator.py",
        "gitgalaxy/cobol_to_java_controller.py",
        "gitgalaxy/cobol_refractor_controller.py",
        "tests/unrelated.py",
    ):
        (code / rel).write_text("changed\n", encoding="utf-8")
        assert m.scan_key(code, corpus) == base, rel
    for rel in ("gitgalaxy/core/detector.py", "gitgalaxy/tools/cobol_to_java/det/copy/CEEIGZCT.cpy"):
        (code / rel).write_text("changed\n", encoding="utf-8")
        assert m.scan_key(code, corpus) != base, rel
        base = m.scan_key(code, corpus)
    (corpus / "A.cbl").write_text("       PROGRAM-ID. X.\n", encoding="utf-8")
    assert m.scan_key(code, corpus) != base


def test_a_second_refactor_reuses_the_kept_scan(tmp_path):
    corpus = _corpus(tmp_path / "corp")
    cache = tmp_path / "cache"
    scans, seen = [], []

    def fake_scan(target, out_dir, **_kw):
        scans.append(target)
        out_dir.mkdir(parents=True)
        db = out_dir / f"{target.name}_galaxy_master.db"
        db.write_text("db", encoding="utf-8")
        return db

    def fake_main():
        seen.append(list(sys.argv))
        (Path(sys.argv[1]).parent / f"{Path(sys.argv[1]).name}_gitgalaxy_clean_x").mkdir()

    import gitgalaxy.cobol_refractor_controller as ctl
    import gitgalaxy.tools.cobol_to_cobol.galaxy_ir as gir

    with patch.object(gir, "scan_to_db", fake_scan), patch.object(ctl, "main", fake_main):
        for i in (1, 2):
            work = tmp_path / f"w{i}"
            work.mkdir()
            m.refactor(corpus, work, scan=True, scan_cache=cache)
    assert len(scans) == 1, "the second run must not scan again"
    assert all("--galaxy-db" in argv and "--scan" not in argv for argv in seen)
    assert [p.name for p in cache.iterdir() if p.name.endswith(".tmp")] == [], "no half-built scan is left behind"
    assert len(list(cache.glob("*/.complete"))) == 1
