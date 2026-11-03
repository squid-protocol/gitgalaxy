"""#7531: det_port.py run --all-cases writes summary.json even when a corpus checkout is missing."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import det_port  # noqa: E402
import equivalence as eq  # noqa: E402
import mainframe_corpus as mc  # noqa: E402

CASES = {"a-one": "alpha", "a-two": "alpha", "b-one": "beta"}


def _run(monkeypatch, tmp_path, argv, missing):
    monkeypatch.setattr(det_port, "all_cases", lambda: sorted(CASES))
    monkeypatch.setattr(eq, "load_case", lambda n: {"corpus": CASES[n]})
    monkeypatch.setattr(mc, "select", lambda names: [{"name": names[0]}])

    def require(entry):
        if entry["name"] in missing:
            raise SystemExit(f"{entry['name']}: no checkout at /nowhere")
        return tmp_path

    monkeypatch.setattr(mc, "require_clone", require)
    monkeypatch.setattr(det_port, "estate", lambda corpus, where: tmp_path)
    monkeypatch.setattr(
        det_port, "port_case", lambda n, *a, **k: {"case": n, "statements": 1, "translated_statements": 1}
    )
    monkeypatch.setattr(sys, "argv", ["det_port.py", "run", *argv, "--translate-only", "--work", str(tmp_path / "w")])
    rc = det_port.main()
    return rc, json.loads((tmp_path / "w" / "summary.json").read_text(encoding="utf-8"))


def test_a_missing_corpus_skips_its_cases_and_keeps_the_rest(monkeypatch, tmp_path, capsys):
    rc, summary = _run(monkeypatch, tmp_path, ["--all-cases"], {"alpha"})
    assert rc == 0
    by = {x["case"]: x for x in summary}
    assert by["b-one"]["translated_statements"] == 1
    assert "no checkout" in by["a-one"]["skipped"] and "skipped" in by["a-two"]
    assert "its 2 cases skipped" in capsys.readouterr().out


def test_an_explicitly_named_case_in_a_missing_corpus_still_writes_the_summary_and_fails(monkeypatch, tmp_path):
    rc, summary = _run(monkeypatch, tmp_path, ["a-one", "b-one"], {"alpha"})
    assert rc == 1
    assert [("skipped" in x) for x in summary] == [True, False]


def test_with_every_corpus_present_nothing_is_skipped(monkeypatch, tmp_path):
    rc, summary = _run(monkeypatch, tmp_path, ["--all-cases"], set())
    assert rc == 0
    assert len(summary) == 3 and not any("skipped" in x for x in summary)
