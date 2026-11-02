"""#7501: dense hand-written source is scanned; minified, packed and data payloads are still excluded.

Dense source (typical of AI coding agents) is a whole program on a few dozen 500-3,000 char lines,
several functions defined inline per line. Every fixture here is synthetic.
"""

import logging
import time

import pytest

from gitgalaxy.core import dense_source
from gitgalaxy.core.aperture import ApertureFilter
from gitgalaxy.galaxyscope import _init_worker, _process_file_worker, _worker_state
from gitgalaxy.metrics.statistical_auditor import StatisticalAuditor
from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG, LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

WIDTHS = (5, 9, 15, 22)  # functions per packed line: ~580 to ~2,900 chars


def _pack(header: str, units: list[str]) -> str:
    lines, i, j = [header], 0, 0
    while i < len(units):
        k = WIDTHS[j % len(WIDTHS)]
        lines.append(" ".join(units[i : i + k]))
        i, j = i + k, j + 1
    return "\n".join(lines) + "\n"


def dense_c(n: int = 420) -> str:
    units = [
        f"static int step{i}(int a,int b){{int r=0;for(int k=0;k<a;k++){{if(B[k&63]>b)r+=B[k&63]-b;"
        f"else r^=k*{i + 3};}}T+=r;return r;}}"
        for i in range(n)
    ]
    units.append("int main(void){int s=0;" + "".join(f"s+=step{i}(s&7,{i});" for i in range(8)) + "return s;}")
    return _pack("#include <stdio.h>\nstatic int B[64],T;", units)


def dense_rust(n: int = 420) -> str:
    units = [
        f"fn step{i}(a: i64, b: i64) -> i64 {{ let mut r = 0; for k in 0..a {{ if k % 3 == {i % 3} {{ r += b; }}"
        f" else {{ r ^= k * {i + 3}; }} }} r }}"
        for i in range(n)
    ]
    units.append("fn main() { let mut s: i64 = 0; " + "".join(f"s += step{i}(s & 7, {i}); " for i in range(8)) + "}")
    return _pack("use std::io;", units)


def dense_go(n: int = 420) -> str:
    units = [
        f"func step{i}(a, b int) int {{ r := 0; for k := 0; k < a; k++ {{ if k%3 == {i % 3} {{ r += b }} else"
        f" {{ r ^= k * {i + 3} }} }}; return r }}"
        for i in range(n)
    ]
    units.append("func main() { s := 0; " + "".join(f"s += step{i}(s&7, {i}); " for i in range(8)) + "}")
    return _pack('package main\nimport "fmt"', units)


DENSE = {"dense.c": dense_c, "dense.rs": dense_rust, "dense.go": dense_go}


def minified_js() -> str:
    body = "".join(
        f"function a{i}(e,t){{var n=t[e];if(!n)return e;for(var r=0;r<n.length;r++)e+=n[r];return e}}"
        for i in range(40)
    )
    return "!function(){" + body + "}();\n"


def minified_css() -> str:
    return "".join(f".c{i}{{color:#{i:03x};margin:0 {i}px;padding:0}}" for i in range(120)) + "\n"


def packed_hex() -> str:
    rows = [",".join(f"0x{(i * 31 + k) & 0xFF:02x}" for k in range(300)) for i in range(40)]
    return "static const unsigned char blob[] = {\n" + ",\n".join(rows) + "\n};\n"


def data_table() -> str:
    rows = [", ".join(f"{{{i}, {k}, {i * k}}}" for k in range(80)) + "," for i in range(40)]
    return "static const int tab[][3] = {\n" + "\n".join(rows) + "\n};\n"


@pytest.fixture
def engine(tmp_path):
    return ApertureFilter(root_dir=tmp_path, language_definitions=LANGUAGE_DEFINITIONS, aperture_config=APERTURE_CONFIG)


def _scope(engine, tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return engine.is_in_scope(path, content=content)


# ---- fixture shape ---------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(DENSE))
def test_fixtures_are_dense(name):
    lines = DENSE[name]().splitlines()
    assert len(lines) > 30
    assert 500 <= max(len(line) for line in lines) <= 3000
    assert sum(len(line) >= 500 for line in lines) >= len(lines) - 4  # all but the header and the tail


# ---- Gate 4.1 (saturation) ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(DENSE))
def test_dense_source_passes_the_saturation_gate(engine, tmp_path, name):
    assert _scope(engine, tmp_path, name, DENSE[name]())["is_in_scope"] is True


@pytest.mark.parametrize(
    ("name", "make"),
    [("app.js", minified_js), ("site.css", minified_css), ("blob.c", packed_hex), ("tab.c", data_table)],
)
def test_minified_packed_and_data_files_are_still_saturated(engine, tmp_path, name, make):
    res = _scope(engine, tmp_path, name, make())
    assert res["is_in_scope"] is False
    assert "Saturation" in res["reason"]


def test_the_language_carries_the_signal(engine, tmp_path):
    """The same inline definitions in a web language are minifier output."""
    dense_js = dense_c().replace("static int ", "function ")
    assert _scope(engine, tmp_path, "dense.js", dense_js)["is_in_scope"] is False
    assert _scope(engine, tmp_path, "dense.ts", dense_js)["is_in_scope"] is False


def test_a_line_past_the_dense_ceiling_is_still_saturated(engine, tmp_path):
    lines = dense_c().splitlines()
    i = max(range(len(lines)), key=lambda k: len(lines[k]))
    lines[i] = " ".join([lines[i]] * 2)  # > _DENSE_LINE_MAX
    assert len(lines[i]) > dense_source.DENSE_LINE_MAX
    res = _scope(engine, tmp_path, "huge.c", "\n".join(lines) + "\n")
    assert res["is_in_scope"] is False and "Saturation" in res["reason"]


# ---- Gate 3.4 (hex / array payload) and Gate 5.1 (monotony) --------------------------------------------


def _dense_hex_c(lines: int) -> str:
    unit = "static unsigned h{n}(unsigned a,unsigned b){{return ((a^0x9e3779b9u)+(b*0x85ebca6bu))^0xc2b2ae35u;}}"
    return "".join(" ".join(unit.format(n=i * 3 + k) for k in range(3)) + "\n" for i in range(lines))


def test_dense_source_passes_the_hex_payload_gate(engine, tmp_path):
    content = _dense_hex_c(600)
    assert _scope(engine, tmp_path, "mix.c", content)["is_in_scope"] is True
    res = _scope(engine, tmp_path, "mix.js", content.replace("static unsigned ", "function "))
    assert res["is_in_scope"] is False and "Embedded Hex Payload" in res["reason"]


def test_dense_source_passes_the_monotony_gate(engine, tmp_path):
    content = _dense_hex_c(2100).replace("0x", "")  # under the hex gate, flat at indent 0
    assert _scope(engine, tmp_path, "flat.c", content)["is_in_scope"] is True
    res = _scope(engine, tmp_path, "flat.js", content.replace("static unsigned ", "function "))
    assert res["is_in_scope"] is False and "Lexical Monotony" in res["reason"]


# ---- the bounded inline-definition scan ---------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "int f(int a){return a;} " * 20,
        "fn f(a: i64) -> i64 { a } " * 20,
        "func (r *T) f(a int) int { return a } " * 20,
        "class Main { int f(){return 1;} int g(){return 2;} " * 10 + "}",
        "public static void main(String[] a) throws IOException {x();} " * 8,
    ],
)
def test_inline_definitions_are_counted(line):
    assert dense_source.has_dense_definitions([line], "x.c") is True


@pytest.mark.parametrize(
    "line",
    [
        "if(a){b();}else if(c){d();}while(e){f();}for(;;){g();} " * 8,
        "x = new Thread(r) { }; return f(a); " * 12,
        "0x1f, 0x2e, 0x3d, " * 40,
        '"' + "abc def " * 40 + '",',
        "short line",
    ],
)
def test_statements_and_data_are_not_definitions(line):
    assert dense_source.has_dense_definitions([line], "x.c") is False


def test_the_scan_is_linear_on_adversarial_lines():
    cap = dense_source.DENSE_LINE_MAX
    lines = [
        ("a" * cap),
        ("a " * cap)[:cap],
        ("a*" * cap)[:cap],
        ("int f(" + "x," * cap)[:cap],
        ("fn " * cap)[:cap],
        ("a<b,c>[d] " * cap)[:cap],
        ("x::y~z " * cap)[:cap],
    ]
    start = time.perf_counter()
    for line in lines:
        dense_source.has_dense_definitions([line], "x.c")
    assert time.perf_counter() - start < 1.0


# ---- the worker's minification test and extraction ----------------------------------------------------


@pytest.fixture
def worker(tmp_path):
    saved = dict(_worker_state)
    root_logger = logging.getLogger()
    level = root_logger.level
    config = {
        "LANGUAGE_DEFINITIONS": LANGUAGE_DEFINITIONS,
        "LEXICAL_FAMILY_HEURISTICS": LEXICAL_FAMILY_HEURISTICS,
        "APERTURE_CONFIG": APERTURE_CONFIG,
    }

    def run(files: dict[str, str]) -> dict[str, dict]:
        for name, text in files.items():
            (tmp_path / name).write_text(text, encoding="utf-8")
        exts = {"." + n.rsplit(".", 1)[1]: 1 for n in files}
        _init_worker(str(tmp_path), config, exts, logging.WARNING, set(files), set())
        return {name: _process_file_worker(name) for name in files}

    try:
        yield run
    finally:
        _worker_state.clear()
        _worker_state.update(saved)
        root_logger.setLevel(level)


def test_dense_source_is_extracted_not_bypassed_as_minified(worker):
    results = worker({name: make() for name, make in DENSE.items()})
    for name, res in results.items():
        assert res["status"] == "success", name
        data = res["data"]
        assert data["is_minified"] is False, name
        names = [f["name"] for f in data["functions"] if not f.get("calls_only")]
        packed_lines = len(DENSE[name]().splitlines()) - 2
        # the detector reads a definition per line start: one per packed line, at least
        assert len(names) >= packed_lines, (name, names)
        assert all(n.startswith("step") or n == "main" for n in names), name


def test_wide_lines_without_inline_definitions_are_still_minified(worker):
    """A wide data file the aperture admits for an ordinary definition (#5460) still skips extraction."""
    rows = "".join("    " + ", ".join(str(k) for k in range(300)) + ",\n" for _ in range(20))
    text = "int lookup(int i)\n{\n    return tab[i];\n}\nstatic const int tab[] = {\n" + rows + "};\n"
    res = worker({"wide.c": text})["wide.c"]
    assert res["status"] == "success" and res["data"]["is_minified"] is True


# ---- statistical_auditor Packed Payload Guard ---------------------------------------------------------


def _artifact(lang, path, functions, total_loc=36, avg_line=1500):
    return {
        "path": path,
        "name": path,
        "lang_id": lang,
        "coding_loc": total_loc,
        "total_loc": total_loc,
        "size_bytes": total_loc * avg_line,
        "equations": {"branch": total_loc * 8, "structural_boundaries": total_loc * 8},
        "functions": [{"name": f"step{i}"} for i in range(functions)],
        "telemetry": {"identity_lock_tier": 0},
    }


@pytest.fixture
def auditor():
    defs = {k: {"rules": {"branch": 1, "structural_boundaries": 1}} for k in ("c", "rust", "go", "javascript")}
    return StatisticalAuditor(lang_defs=defs)


@pytest.mark.parametrize(("lang", "path"), [("c", "engine.c"), ("rust", "main.rs"), ("go", "main.go")])
def test_dense_source_is_not_a_packed_payload(auditor, lang, path):
    verified, unparsable = auditor.audit([_artifact(lang, path, functions=19)])
    assert [f["path"] for f in verified] == [path] and not unparsable


@pytest.mark.parametrize(
    "art",
    [
        _artifact("javascript", "app.js", functions=19),  # a web language: minifier output
        _artifact("c", "blob.c", functions=1),  # one function beside a packed payload
        _artifact("c", "blob.c", functions=3, total_loc=3000, avg_line=900),  # too few for its lines
    ],
    ids=["web-language", "one-function", "sparse-functions"],
)
def test_packed_payloads_are_still_relegated(auditor, art):
    verified, unparsable = auditor.audit([art])
    assert not verified and "Packed Payload Guard" in unparsable[0]["reason"]
