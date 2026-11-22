"""Unit tests for Erlang, OCaml, and Nim import extraction and resolution."""

from __future__ import annotations

from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor
from gitgalaxy.galaxyscope import extract_raw_imports
from gitgalaxy.standards.language_standards.languages import erlang, nim, ocaml


def _resolve(files: list[dict[str, object]]) -> list[tuple[str, str]]:
    sensor = NetworkRiskSensor()
    sensor.build_dependency_graph(files)
    return sorted((e["src"], e["dst"]) for e in sensor.dependency_edges)


def test_erlang_behaviour_ignores_same_stem_asciidoc() -> None:
    src = "-module(cowboy_compress_h).\n-behavior(cowboy_stream).\n"
    d = erlang.DEFINITION
    toks = extract_raw_imports(d["rules"]["_dependency_capture"], src, d)
    assert toks == {"cowboy_stream"}
    edges = _resolve(
        [
            {"path": "src/cowboy_compress_h.erl", "lang_id": "erlang", "raw_imports": list(toks)},
            {"path": "src/cowboy_stream.erl", "lang_id": "erlang", "raw_imports": []},
            {"path": "doc/src/manual/cowboy_stream.asciidoc", "lang_id": "asciidoc", "raw_imports": []},
        ]
    )
    assert edges == [("src/cowboy_compress_h.erl", "src/cowboy_stream.erl")]


def test_ocaml_capitalized_module_and_let_open_prefer_ml_over_mli() -> None:
    src = "include Cmdliner_cmd\nlet f x =\n  let open Cmdliner_base in\n  open Cmdliner_def.Env\n"
    d = ocaml.DEFINITION
    toks = extract_raw_imports(d["rules"]["_dependency_capture"], src, d)
    assert toks == {"Cmdliner_cmd", "Cmdliner_base", "Cmdliner_def.Env"}
    edges = _resolve(
        [
            {"path": "src/cmdliner.ml", "lang_id": "ocaml", "raw_imports": list(toks)},
            {"path": "src/cmdliner_cmd.ml", "lang_id": "ocaml", "raw_imports": []},
            {"path": "src/cmdliner_cmd.mli", "lang_id": "ocaml", "raw_imports": []},
            {"path": "src/cmdliner_base.ml", "lang_id": "ocaml", "raw_imports": []},
            {"path": "src/cmdliner_base.mli", "lang_id": "ocaml", "raw_imports": []},
            {"path": "src/cmdliner_def.ml", "lang_id": "ocaml", "raw_imports": []},
            {"path": "src/cmdliner_def.mli", "lang_id": "ocaml", "raw_imports": []},
        ]
    )
    assert edges == [
        ("src/cmdliner.ml", "src/cmdliner_base.ml"),
        ("src/cmdliner.ml", "src/cmdliner_cmd.ml"),
        ("src/cmdliner.ml", "src/cmdliner_def.ml"),
    ]


def test_nim_comma_list_bracket_group_multiline_and_nimble_guard() -> None:
    src = (
        "import std/strformat, chronos, chronos/threadsync\n"
        'import "."/[asyncloop, config]\n'
        "import\n"
        "  ../chronos,\n"
        "  ../chronos/apps/http/[httpserver, httpclient]\n"
    )
    d = nim.DEFINITION
    toks = extract_raw_imports(d["rules"]["_dependency_capture"], src, d)
    assert {
        "chronos",
        "chronos/threadsync",
        "./asyncloop",
        "./config",
        "../chronos",
        "../chronos/apps/http/httpserver",
        "../chronos/apps/http/httpclient",
    }.issubset(toks)
    edges = _resolve(
        [
            {"path": "chronos/ratelimit.nim", "lang_id": "nim", "raw_imports": ["../chronos", "./timer"]},
            {"path": "chronos.nim", "lang_id": "nim", "raw_imports": []},
            {"path": "chronos.nimble", "lang_id": "nim", "raw_imports": []},
            {"path": "chronos/timer.nim", "lang_id": "nim", "raw_imports": []},
        ]
    )
    assert edges == [
        ("chronos/ratelimit.nim", "chronos.nim"),
        ("chronos/ratelimit.nim", "chronos/timer.nim"),
    ]
