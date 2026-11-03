"""#7504: several definitions on one physical line are each extracted, with correct names, args and spans.

Every fixture is synthetic. A packed file is compared with the same units one per line.
"""

import logging
import time

import pytest

from gitgalaxy.core import dense_source
from gitgalaxy.galaxyscope import _init_worker, _process_file_worker, _worker_state
from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG, LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _units(lang: str, n: int) -> list[str]:
    if lang == "c":
        return [f"static int f{i}(int a, int b) {{ int r = a + {i}; return r * b; }}" for i in range(n)]
    if lang == "rust":
        return [f"fn f{i}(a: i32, b: i32) -> i32 {{ let r = a + {i}; r * b }}" for i in range(n)]
    return [f"int f{i}(int a, int b) {{ int r = a + {i}; return r * b; }}" for i in range(n)]


def _source(lang: str, units: list[str], per_line: int) -> str:
    chunks = [" ".join(units[i : i + per_line]) for i in range(0, len(units), per_line)]
    if lang == "java":
        return "class M {\n" + "\n".join(chunks) + "\n}\n"
    return "\n".join(chunks) + "\n"


EXT = {"c": "c", "rust": "rs", "java": "java"}


@pytest.fixture
def scan(tmp_path):
    saved = dict(_worker_state)
    root_logger = logging.getLogger()
    level = root_logger.level
    config = {
        "LANGUAGE_DEFINITIONS": LANGUAGE_DEFINITIONS,
        "LEXICAL_FAMILY_HEURISTICS": LEXICAL_FAMILY_HEURISTICS,
        "APERTURE_CONFIG": APERTURE_CONFIG,
    }

    def run(name: str, text: str) -> list[dict]:
        (tmp_path / name).write_text(text, encoding="utf-8")
        _init_worker(str(tmp_path), config, {"." + name.rsplit(".", 1)[1]: 1}, logging.WARNING, {name}, set())
        res = _process_file_worker(name)
        assert res["status"] == "success", res
        return [f for f in res["data"]["functions"] if not f.get("calls_only")]

    try:
        yield run
    finally:
        _worker_state.clear()
        _worker_state.update(saved)
        root_logger.setLevel(level)


@pytest.mark.parametrize("lang", ["c", "rust", "java"])
@pytest.mark.parametrize("per_line", [2, 5, 10])
def test_packed_definitions_match_one_per_line(scan, lang, per_line):
    units = _units(lang, 20)
    name = f"m.{EXT[lang]}"
    packed_text = _source(lang, units, per_line)
    packed = scan(name, packed_text)
    wrapped = scan(name, _source(lang, units, 1))
    assert [f["name"] for f in packed] == [f"f{i}" for i in range(20)]
    assert [f["name"] for f in packed] == [f["name"] for f in wrapped]
    assert [f.get("args") for f in packed] == [f.get("args") for f in wrapped]
    # a span stays on its own line: the next function does not start before this one ends
    lines = [(f["start_line"], f["end_line"]) for f in packed]
    assert all(s == e for s, e in lines), lines
    assert [s for s, _ in lines] == sorted(s for s, _ in lines)


def test_long_lines_without_second_definition_are_unchanged():
    text = "int f(int a) { return a; }  " + "/* " + "y" * 300 + " */\nint g(void) { return 1; }\n"
    assert dense_source.split_inline_definitions(text) is text
    one = "int f(void){if (1) {return 1;}}\nint g(void){return 2;}\n"
    assert dense_source.split_inline_definitions(one) is one
    two = "int f(void){return 1;} int g(void){return 2;}\n"
    assert dense_source.split_inline_definitions(two) == two.replace("} int", "}\nint")


def test_control_flow_and_calls_are_not_split_points():
    line = (
        "int f(int a){ if (a) { return g(a); } for (;;) { a++; } while (a) { a--; } return a; } "
        + "/*"
        + "z" * 200
        + "*/"
    )
    assert dense_source.split_inline_definitions(line) is line


def test_split_keeps_length_and_only_swaps_whitespace():
    line = " ".join(_units("c", 8))
    out = dense_source.split_inline_definitions(line)
    assert len(out) == len(line) and out.count("\n") == 7
    assert out.replace("\n", " ") == line


def test_split_is_linear_on_adversarial_lines():
    lines = [
        "int " + "a" * 4900,
        "int f(" + "(" * 2400 + ")" * 2400,
        "fn " * 1600,
        "int a(int x){} " * 330,
    ]
    start = time.perf_counter()
    for line in lines:
        dense_source.split_inline_definitions(line)
    assert time.perf_counter() - start < 1.0
