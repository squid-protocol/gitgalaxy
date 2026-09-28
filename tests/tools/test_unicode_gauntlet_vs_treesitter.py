"""#3811: the Unicode Gauntlet run side by side with tree-sitter (unicode_gauntlet_vs_treesitter.py).

The pure parts (the multiset oracle, the careful integrator's decode, a broken name recorded with its
bytes) are pinned directly; one small real run -- python, java and lua, the French script written as
UTF-8, UTF-16 and cp1252 -- checks the report's shape and the tool's reason to exist: a cp1252 file
fails tree-sitter reading raw bytes and passes GitGalaxy and tree-sitter-after-decoding.

Sibling-module import pattern per CLAUDE.md "Testing conventions" (no tests/__init__.py).
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import unicode_gauntlet as ug  # noqa: E402
import unicode_gauntlet_vs_treesitter as vs  # noqa: E402

CORPUS = Path(os.environ.get("KEYWORD_ROSETTA_PATH", ug.REPO_ROOT.parent / "keyword-rosetta"))


def test_the_oracle_is_a_multiset_and_names_the_first_difference():
    assert vs.verdict(Counter(["a", "b"]), Counter(["b", "a"])) == {"pass": True, "diff": ""}
    v = vs.verdict(Counter(["probe_नाम", "entry"]), Counter(["probe_न", "entry"]))
    assert not v["pass"] and "missing ['probe_नाम']" in v["diff"] and "extra ['probe_न']" in v["diff"]
    assert not vs.verdict(Counter(["f"]), Counter(["f", "f"]))["pass"]  # a duplicated function is a difference


def test_the_integrator_decodes_with_the_true_encoding():
    assert vs._decode_for_ts("def fé(): pass\n".encode("cp1252"), "cp1252") == "def fé(): pass\n".encode()
    assert vs._decode_for_ts("x = 1\n".encode("utf-16"), "utf-16") == b"x = 1\n"
    assert vs._decode_for_ts(b"\xef\xbb\xbfx\n", "utf-8-sig") == b"x\n"
    fb = ug.fixed_block("A\nB\n", "cp037")
    assert fb is not None and vs._decode_for_ts(fb, "cp037") == b"A\nB\n"  # card images, padding trimmed


def test_a_name_in_a_legacy_code_page_never_reads_whole():
    names = vs.ts_functions("def probe_éèç(x):\n    return x\n".encode("cp1252"), "python")
    assert names and all("éèç" not in n for n in names)
    assert vs.ts_functions("def probe_éèç(x):\n    return x\n".encode(), "python") == ["probe_éèç"]


@pytest.mark.skipif(not (CORPUS / "data" / "python").is_dir(), reason="keyword-rosetta corpus not available")
def test_a_cp1252_cell_fails_tree_sitter_raw_and_passes_gitgalaxy(tmp_path, monkeypatch):
    monkeypatch.setattr(ug, "SCRIPTS", {"french": "éèç"})
    monkeypatch.setattr(ug, "NATIONAL", {})  # the mainframe seed's national letters: not in this run
    monkeypatch.setattr(ug, "ENCODINGS", ["utf-8", "utf-16", "cp1252"])
    out = tmp_path / "out"
    rc = vs.main(["--corpus", str(CORPUS), "--only", "python", "java", "lua", "--full",
                  "--work", str(tmp_path / "work"), "--out", str(out), "--jobs", "4"])  # fmt: skip
    assert rc == 0
    data = json.loads((out / "results.json").read_text(encoding="utf-8"))
    summ = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    report = (out / "report.md").read_text(encoding="utf-8")

    cell = data["cells"]["python|french|cp1252"]
    assert cell["gitgalaxy"]["pass"] and cell["ts_decode"]["pass"], cell
    assert not cell["ts_raw"]["pass"] and cell["outcome"] == "gg-only", cell
    # the seed only re-encoded as UTF-8 is the control: every engine reads it as the seed
    assert all(data["cells"]["python|ascii|utf-8"][e]["pass"] for e in vs.ENGINES)
    assert data["controls"]["python"]["ts_raw"]["pass"] and data["controls"]["python"]["gitgalaxy"]["pass"]

    assert set(summ["headline"]) == {"cells", *vs.ENGINES} and summ["headline"]["cells"] > 0
    assert "french" in summ["by_script"] and "cp1252" in summ["by_encoding"]
    for section in ("## 1. Headline", "## 2. By script", "## By encoding", "## 3. Why", "## 4. Methodology"):
        assert section in report
