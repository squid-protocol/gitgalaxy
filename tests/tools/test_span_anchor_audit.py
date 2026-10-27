"""span_anchor_audit.py (#3543): a start_line on the line that ENDS other code is
mis-anchored; one on an annotation, attribute or return type is not."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import span_anchor_audit as saa


def test_the_3543_shapes_are_misanchored():
    ts = ["export class A {", "  constructor(x: number) {}", "}"]
    assert saa.misanchored(ts, 1, "constructor", "typescript") is True
    member = ["  a: () => 1,", "  b: () => 2,"]
    assert saa.misanchored(member, 1, "b", "typescript") is True
    php = ["/**", " * Docs.", " */", "function f() {}"]
    assert saa.misanchored(php, 3, "f", "php") is True


def test_declaration_prefix_lines_are_not_misanchored():
    assert saa.misanchored(["@Override", "public void run() {"], 1, "run", "java") is False
    assert saa.misanchored(["#[inline]", "fn run() {"], 1, "run", "rust") is False
    assert saa.misanchored(["static int", "run(void) {"], 1, "run", "c") is False
    assert saa.misanchored(["template <typename T>", "T run(T x) {"], 1, "run", "cpp") is False
    assert saa.misanchored(["def run():"], 1, "run", "python") is False
    assert saa.misanchored(["#[\\Override]", "public function run() {"], 1, "run", "php") is False
    assert saa.misanchored(["int\t\t/* Return 1 on error */", "run(void) {"], 1, "run", "c") is False


def test_unjudgeable_units_are_skipped():
    assert saa.misanchored(["x"], 5, "run", "c") is None  # out of range
    assert saa.misanchored(["{", "}"], 1, "run", "c") is None  # name never appears


def test_regressions_read_a_rise_and_skip_small_languages():
    base = {"php": {"units": 100, "misanchored_pct": 20.0}, "kotlin": {"units": 5, "misanchored_pct": 0.0}}
    assert saa.regressions({"php": {"misanchored_pct": 20.4}, "kotlin": {"misanchored_pct": 40.0}}, base) == []
    assert saa.regressions({"php": {"misanchored_pct": 21.0}}, base) == ["php: misanchored_pct 20.0 -> 21.0"]
    assert saa.regressions({"php": {"misanchored_pct": 0.0}}, base) == []  # a fix is never a regression


def test_shards_are_disjoint_and_cover_every_language_directory(tmp_path):
    for name in ("c", "cpp", "go", "java", "python", "zig", "xml"):
        (tmp_path / name).mkdir()
    (tmp_path / "PROVENANCE.json").write_text("{}")  # a file is not a language directory
    for count in (1, 2, 3, 8):
        parts = [{d.name for d in saa.shard_dirs(tmp_path, (i, count))} for i in range(count)]
        assert set().union(*parts) == {"c", "cpp", "go", "java", "python", "zig", "xml"}
        assert sum(len(p) for p in parts) == 7


def test_shard_argument_is_validated():
    assert saa.parse_shard("1/2") == (1, 2)
    for bad in ("2/2", "-1/2", "a/b", "1", "0/0", ""):
        with pytest.raises(ValueError):
            saa.parse_shard(bad)


def test_a_shard_cannot_gate_or_rewrite_the_baseline():
    for flags in (["--ci"], ["--regenerate"], ["--merge", "x.json"]):
        with pytest.raises(SystemExit) as exc:
            saa.main(["--shard", "0/2", *flags])
        assert exc.value.code == 2


def test_merge_sums_counts_for_a_language_split_across_shards():
    a = {"c": {"units": 10, "misanchored": 1, "misanchored_pct": 10.0, "examples": ["a"]}}
    b = {
        "c": {"units": 30, "misanchored": 1, "misanchored_pct": 3.3, "examples": ["b"]},
        "go": {"units": 4, "misanchored": 0, "misanchored_pct": 0.0, "examples": []},
    }
    merged = saa.merge([a, b], samples=1)
    assert merged["c"] == {"units": 40, "misanchored": 2, "misanchored_pct": 5.0, "examples": ["a"]}
    assert merged["go"]["units"] == 4


def test_main_merge_gates_the_sum_against_the_baseline(tmp_path, monkeypatch):
    base = {"c": {"units": 100, "misanchored_pct": 5.0}}
    baseline = tmp_path / "base.json"
    baseline.write_text(json.dumps(base))
    monkeypatch.setattr(saa, "BASELINE", baseline)
    parts = []
    for i, (units, bad) in enumerate([(50, 2), (50, 6)]):  # 8 of 100: 8.0% > 5.0% + tolerance
        f = tmp_path / f"{i}.json"
        f.write_text(json.dumps({"c": {"units": units, "misanchored": bad, "misanchored_pct": 0, "examples": []}}))
        parts.append(str(f))
    assert saa.main(["--merge", *parts, "--ci"]) == 1
    baseline.write_text(json.dumps({"c": {"units": 100, "misanchored_pct": 8.0}}))
    assert saa.main(["--merge", *parts, "--ci"]) == 0
