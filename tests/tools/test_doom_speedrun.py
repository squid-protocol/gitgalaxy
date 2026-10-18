"""DOOM Port Speedrun harness (#5468): manifest shape, scorer helpers, pinned-SHA fetch, the work-dir guard.

No network and no scan: the fetch test clones a throwaway local repo. Sibling tool dir goes on sys.path and the
modules are imported as bare names (tests/ has no __init__.py).
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "doom_speedrun"))

import doom_scorer  # noqa: E402
import doom_speedrun  # noqa: E402


def test_manifest_is_39_pinned_unique_ports():
    rows = doom_speedrun.read_manifest()
    names = [r["name"] for r in rows]
    assert len(rows) == 39 and len(set(names)) == 39
    for r in rows:
        assert re.fullmatch(r"[0-9a-f]{40}", r["sha"]), r["name"]
        assert r["upstream"].startswith("https://github.com/"), r["name"]
        assert r["lineage"].strip(), r["name"]


def test_manifest_unknown_port_is_an_error():
    with pytest.raises(SystemExit, match="nope"):
        doom_speedrun.read_manifest(only=["linuxdoom", "nope"])


@pytest.mark.parametrize(
    ("gg", "ct", "ok"),
    [(0, 0, True), (5, 0, True), (103, 100, True), (104, 100, False), (97, 100, True), (96, 100, False)],
)
def test_functions_tolerance_is_a_scaled_bound(gg, ct, ok):
    assert doom_scorer.functions_ok(gg, ct) is ok


def test_verdict():
    assert doom_scorer.verdict([]) == "PERFECT"
    assert doom_scorer.verdict(["coverage", "health"]) == "4/6"


def test_log_problems_ignores_engine_wide_and_typosquat_lines():
    pad = "2026-10-18 00:00:00,000 - "  # the scorer drops the 24-char timestamp prefix
    log = "\n".join(
        [
            pad + "[ERROR] boom in x.c",
            pad + "[ERROR] XGBoost model missing",
            pad + "[ERROR] TYPOSQUATTING DETECTED: foo",
            pad + "CLASSIFICATION REFUTATION for y.c",
            "Traceback (most recent call last):",
            pad + "[INFO] fine",
        ]
    )
    assert len(doom_scorer.log_problems(log)) == 3


def test_language_misfits(tmp_path):
    (tmp_path / "a.h").write_text("int f(void);\n")
    (tmp_path / "b.h").write_text("@interface Foo\n@end\n")
    mapped = {
        "a.h": ("objective-c", 1),  # no ObjC syntax in a C header
        "b.h": ("objective-c", 2),
        "c.c": ("c", 3),
        "d.c": ("cpp", 4),
        "v/e.c": ("cpp", 5),  # vendored: not judged
    }
    bad = doom_scorer.language_misfits(mapped, tmp_path, lambda p: p.startswith("v/"))
    assert sorted(bad) == [("a.h", "objective-c"), ("d.c", "cpp")]


def test_treesitter_counts_c_and_macro_defined_function(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    (tmp_path / "x.c").write_text("int g(int a){return a;}\nstatic void h(void){}\n")
    (tmp_path / "y.c").write_text("CCMD(foo)\n{\n  return;\n}\nint k(void){return 1;}\n")
    counts = doom_scorer.treesitter_counts(tmp_path, {"c": ["x.c", "y.c"]})
    assert counts["x.c"] == 2
    assert counts["y.c"] >= 1  # the plain function; the macro-defined one is the oracle's own blind spot


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def test_fetch_port_checks_out_exactly_the_pinned_sha(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q")
    _git(src, "config", "user.email", "t@example.com")
    _git(src, "config", "user.name", "t")
    _git(src, "config", "uploadpack.allowAnySHA1InWant", "true")
    (src / "a.c").write_text("int a(void){return 1;}\n")
    _git(src, "add", "a.c")
    _git(src, "commit", "-q", "-m", "one")
    pinned = subprocess.run(
        ["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    (src / "a.c").write_text("int a(void){return 2;}\n")
    _git(src, "commit", "-q", "-am", "two")
    repos = tmp_path / "repos"
    repos.mkdir()
    row = {"name": "p", "upstream": src.as_uri(), "sha": pinned}
    assert doom_speedrun.fetch_port(row, repos) is None
    assert (repos / "p" / "a.c").read_text() == "int a(void){return 1;}\n"
    assert doom_speedrun.fetch_port(row, repos) is None  # resumable: already at the SHA
    assert doom_speedrun.fetch_port({**row, "sha": "0" * 40}, repos) is not None


def test_work_dir_inside_repo_is_refused():
    with pytest.raises(SystemExit, match="outside the repo"):
        doom_speedrun.main(["fetch", "--only", "linuxdoom", "--work", str(doom_speedrun.REPO_ROOT / "scratch_doom")])
