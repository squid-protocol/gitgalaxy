"""A case-only change keeps the port's translate fingerprint, so `det_port.port_case` serves the cached port (#8599)."""

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parent.parent))

pytest.importorskip("tree_sitter_language_pack")

import det_port as dp  # noqa: E402
import equivalence as eq  # noqa: E402
import equivalence_cache as ec  # noqa: E402

CASE = {"program": "P", "program_source": "p.cbl", "corpus": "c", "scenarios": [{"a": 1}], "notes": "n"}


@pytest.mark.parametrize("change", [{"scenarios": [{"a": 2}, {"a": 3}]}, {"notes": "other"}])
def test_a_case_only_change_keeps_the_fingerprint(change):
    assert dp.translate_key({**CASE, **change}, "dispatch", False, False) == dp.translate_key(
        CASE, "dispatch", False, False
    )


@pytest.mark.parametrize(
    "change",
    [{"copy_dirs": ["x"]}, {"program_source": "q.cbl"}, {"strict_copy": True}, {"subprograms": ["s.cbl"]}],
)
def test_a_translated_input_moves_the_fingerprint(change):
    assert dp.translate_key({**CASE, **change}, "dispatch", False, False) != dp.translate_key(
        CASE, "dispatch", False, False
    )


def test_layers_move_the_fingerprint():
    base = dp.translate_key(CASE, "dispatch", False, False)
    assert dp.translate_key(CASE, "dispatch", True, False) != base
    assert dp.translate_key(CASE, "structured", False, False) != base


def _stub_world(monkeypatch, tmp_path, case, calls):
    monkeypatch.setenv(ec.CACHE_ENV, str(tmp_path / "cache"))
    monkeypatch.setattr(eq, "load_case", lambda name: dict(case))
    monkeypatch.setattr(ec, "key", lambda kind, corpus, extra="": "k" + str(hash(extra) % 10**8))

    def fake(name, work, project, corpus, style="dispatch", typed=False, groups=False):
        calls.append(name)
        (work / name / "port").mkdir(parents=True)
        (work / name / "port" / "A.java").write_text("class A {}", encoding="utf-8")
        return {"case": name, "statements": 3, "translated_statements": 3, "holes": []}

    monkeypatch.setattr(dp, "_port_case", fake)


def test_the_second_translation_of_an_unchanged_fingerprint_is_served_from_the_cache(monkeypatch, tmp_path):
    calls: list[str] = []
    _stub_world(monkeypatch, tmp_path, CASE, calls)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    first = dp.port_case("c1", tmp_path / "w1", tmp_path, corpus)
    again = dp.port_case("c1", tmp_path / "w2", tmp_path, corpus)
    assert calls == ["c1"]
    assert first == again
    assert (tmp_path / "w2" / "c1" / "port" / "A.java").read_text(encoding="utf-8") == "class A {}"


def test_a_changed_scenario_list_is_still_a_hit_and_a_changed_option_is_a_miss(monkeypatch, tmp_path):
    calls: list[str] = []
    _stub_world(monkeypatch, tmp_path, CASE, calls)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    dp.port_case("c1", tmp_path / "w1", tmp_path, corpus)
    monkeypatch.setattr(eq, "load_case", lambda name: {**CASE, "scenarios": [{"a": 9}] * 64})
    dp.port_case("c1", tmp_path / "w2", tmp_path, corpus)
    assert calls == ["c1"]
    monkeypatch.setattr(eq, "load_case", lambda name: {**CASE, "copy_dirs": ["other"]})
    dp.port_case("c1", tmp_path / "w3", tmp_path, corpus)
    assert calls == ["c1", "c1"]


def test_a_failed_translation_is_returned_and_never_cached(monkeypatch, tmp_path):
    calls: list[str] = []
    _stub_world(monkeypatch, tmp_path, CASE, calls)

    def failing(name, work, *a, **k):
        calls.append(name)
        return {"case": name, "translated": False, "error": "boom"}

    monkeypatch.setattr(dp, "_port_case", failing)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    assert dp.port_case("c1", tmp_path / "w1", tmp_path, corpus)["error"] == "boom"
    assert dp.port_case("c1", tmp_path / "w2", tmp_path, corpus)["error"] == "boom"
    assert calls == ["c1", "c1"]


def test_cache_off_translates_every_time(monkeypatch, tmp_path):
    calls: list[str] = []
    _stub_world(monkeypatch, tmp_path, CASE, calls)
    monkeypatch.setenv(ec.CACHE_ENV, "off")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    dp.port_case("c1", tmp_path / "w1", tmp_path, corpus)
    dp.port_case("c1", tmp_path / "w2", tmp_path, corpus)
    assert calls == ["c1", "c1"]
