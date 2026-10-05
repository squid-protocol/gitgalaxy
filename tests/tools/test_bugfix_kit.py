"""Tests for the pure parts of tests/tools/bugfix_kit.py: argument handling, the golden-diff
summarizer (on fixtures rendered through the real golden_store layout), the ledger / estate
deltas and the evidence markdown. Nothing here scans, builds a venv or touches git."""

from __future__ import annotations

import copy
import json
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bugfix_kit as kit
import golden_store

PARSED = golden_store.PARSED_FILES_KEY


def _audit() -> dict:
    return {
        "Audit Protocol": "GitGalaxy-Audit",
        "2. Global Ecosystem Summary": {"summary": {"files": 3, "loc": 120}},
        PARSED: {
            "cobol/app": {
                "Files": {
                    "cobol/app/A.cbl": {
                        "10. Mainframe System Facts": {"Call Sites": [{"Verb": "CALL", "Target": "B"}]},
                        "5. Function Analysis": {"functions": ["MAIN-PARA"]},
                    },
                    "cobol/app/B.cbl": {
                        "10. Mainframe System Facts": {"Call Sites": []},
                        "5. Function Analysis": {"functions": ["P1", "P2"]},
                    },
                },
                "file_count": 2,
            },
            "pli/x": {
                "Files": {"pli/x/C.pli": {"5. Function Analysis": {"functions": ["MAIN"]}}},
                "file_count": 1,
            },
        },
    }


def _changes(old: dict, new: dict) -> list:
    a, b = golden_store.render(old), golden_store.render(new)
    return [(rel, a.get(rel), b.get(rel)) for rel in sorted(set(a) | set(b)) if a.get(rel) != b.get(rel)]


# ----------------------------------------------------------------------------- argument handling


def test_parse_args_defaults_and_paths():
    a = kit.parse_args(["bless", "/w"])
    assert a.cmd == "bless" and a.worktree == Path("/w") and a.leg == "both" and not a.no_verify
    a = kit.parse_args(["evidence", "/w", "--base", "origin/v6-dev", "--template", "--venv-ledger", "/v"])
    assert a.base == "origin/v6-dev" and a.template and a.venv_ledger == Path("/v")
    a = kit.parse_args(["audit", "/w", "-k", "copybook", "tests/a/test_x.py"])
    assert a.keyword == "copybook" and a.tests == ["tests/a/test_x.py"]
    a = kit.parse_args(["audit", "/w", "tests/a/test_x.py", "tests/b", "-k", "z"])
    assert a.keyword == "z" and a.tests == ["tests/a/test_x.py", "tests/b"]


def test_parse_args_train_takes_several_branches():
    a = kit.parse_args(["train", "/t", "fix/a", "fix/b", "--ledger-per-step", "--no-final"])
    assert a.branches == ["fix/a", "fix/b"] and a.ledger_per_step and a.no_final


def test_parse_args_rejects_unknown_skip_step_and_missing_worktree(capsys):
    with pytest.raises(SystemExit):
        kit.parse_args(["all", "/w", "--skip", "bless,lint"])
    assert "unknown step" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        kit.parse_args(["bless"])
    with pytest.raises(SystemExit):
        kit.parse_args(["bless", "/w", "stray"])
    a = kit.parse_args(["all", "/w", "--skip", "estate,audit"])
    assert a.skip == "estate,audit"


def test_read_pin_and_workflow_python():
    assert kit.read_pin('x\nPINNED_TAG = "v1.7.0"\n', "PINNED_TAG") == "v1.7.0"
    assert kit.read_pin("PINNED_TAG = 'v1'\n", "PINNED_TAG") is None  # the workflows' sed needs double quotes
    assert kit.workflow_python("  python-version: '3.11'\n") == "3.11"
    assert kit.workflow_python('python-version: "3.12"') == "3.12"


def test_split_conflicts_only_generated_artifacts_resolve():
    gen, src = kit.split_conflicts(
        [
            "tests/golden_master_audit/6_parsed_files_scanned_artifacts/_groups.json",
            "tests/golden_master_zero_dep_audit/audit_protocol.json",
            "tests/cobol_mainframe/ground_truth_ledger.json",
            "gitgalaxy/core/detector.py",
            "tests/golden_master_audit_extra.py",
        ]
    )
    assert len(gen) == 3
    assert src == ["gitgalaxy/core/detector.py", "tests/golden_master_audit_extra.py"]


# ----------------------------------------------------------------------------- golden summarizer


def test_summarize_golden_unchanged_is_empty():
    s = kit.summarize_golden(_changes(_audit(), _audit()))
    assert s.empty and "unchanged" in kit.render_golden(s, "full")


def test_summarize_golden_attributes_per_file_channels():
    old, new = _audit(), _audit()
    files = new[PARSED]["cobol/app"]["Files"]
    files["cobol/app/B.cbl"]["10. Mainframe System Facts"]["Call Sites"] = [{"Verb": "CALL", "Target": "A"}]
    files["cobol/app/A.cbl"]["5. Function Analysis"]["functions"] = ["MAIN-PARA", "EXIT-PARA"]
    s = kit.summarize_golden(_changes(old, new))
    calls = s.channels["10. Mainframe System Facts / Call Sites"]
    assert calls.changed == {"cobol/app/B.cbl"} and not calls.added and not calls.removed
    funcs = s.channels["5. Function Analysis / functions"]
    assert funcs.changed == {"cobol/app/A.cbl"} and funcs.leaves == 1
    assert s.scanned_files() == {"cobol/app/A.cbl": 1, "cobol/app/B.cbl": 1}
    assert not s.newly_parsed and not s.errors


def test_summarize_golden_new_channel_and_parsed_set():
    old, new = _audit(), _audit()
    new[PARSED]["pli/x"]["Files"]["pli/x/D.pli"] = {"5. Function Analysis": {"functions": ["X"]}}
    new[PARSED]["pli/x"]["file_count"] = 2
    new[PARSED]["cobol/app"]["Files"]["cobol/app/A.cbl"]["13. New Facts"] = {"Thing": [1]}
    new["2. Global Ecosystem Summary"]["summary"]["files"] = 4
    s = kit.summarize_golden(_changes(old, new))
    assert s.newly_parsed == {"pli/x/D.pli"} and not s.no_longer_parsed
    assert s.channels["5. Function Analysis / functions"].added == {"pli/x/D.pli"}
    assert s.channels["13. New Facts / Thing"].note == "new channel"
    assert s.channels["2. Global Ecosystem Summary / summary"].leaves == 1
    assert s.channels["(parsed-file index: group stats)"].leaves == 1  # file_count 1 -> 2
    md = kit.render_golden(s, "full-precision")
    assert "| 13. New Facts / Thing *(new channel)* | 0 | 1 | 0 |" in md
    assert "+1 newly parsed `pli/x/D.pli`" in md
    assert "cobol 1" in md and "pli 1" in md


def test_summarize_golden_flags_conflict_markers_and_roundtrips_json():
    rel = "6_parsed_files_scanned_artifacts/_groups.json"
    s = kit.summarize_golden([(rel, b"{}", b"<<<<<<< HEAD\n{}\n=======\n")])
    assert s.errors and "merge-conflict" in s.errors[0]
    old, new = _audit(), copy.deepcopy(_audit())
    del new[PARSED]["cobol/app"]["Files"]["cobol/app/B.cbl"]
    s = kit.summarize_golden(_changes(old, new))
    assert s.no_longer_parsed == {"cobol/app/B.cbl"}
    again = kit.GoldenSummary.from_json(json.loads(json.dumps(s.to_json())))
    assert kit.render_golden(again, "x") == kit.render_golden(s, "x")


def test_render_golden_caps_rows():
    s = kit.GoldenSummary(docs_changed=30)
    for i in range(30):
        s.channels[f"ch{i}"] = kit.ChannelDelta(f"ch{i}", changed={f"cobol/p/{i}.cbl"}, leaves=1)
    md = kit.render_golden(s, "full", max_rows=5)
    assert "25 more channel(s)" in md and len(re.findall(r"^\| ch\d", md, re.M)) == 5


def test_count_leaf_diffs():
    assert kit.count_leaf_diffs({"a": 1, "b": [1, 2]}, {"a": 1, "b": [1, 2]}) == 0
    assert kit.count_leaf_diffs({"a": 1, "b": [1, 2]}, {"a": 2, "b": [1, 2, 3]}) == 2
    assert kit.count_leaf_diffs(None, {"a": {"b": 1, "c": 2}}) == 2


# ----------------------------------------------------------------------------- ledger / estate


def _ledger(mismatches: dict, tp: int) -> dict:
    return {
        "corpora": {
            "cbsa": {
                "mismatches": mismatches,
                "scoreboard": {"CALL USING": {"engine": {"got": 10, "tp": tp, "truth": 10}, "forge": None}},
            }
        }
    }


def test_ledger_delta_fixed_introduced_and_scoreboard():
    old = _ledger({"engine | f | P | v | fp": "c1", "engine | f | Q | v | fn": "c2"}, 8)
    new = _ledger({"engine | f | Q | v | fn": "c2", "engine | g | R | w | fp": "UNTRIAGED"}, 9)
    d = kit.ledger_delta(old, new)
    assert d["cbsa"]["fixed"] == ["engine | f | P | v | fp"]
    assert d["cbsa"]["introduced"] == {"engine | g | R | w | fp": "UNTRIAGED"}
    assert d["cbsa"]["scoreboard"] == ["CALL USING [engine] tp 8/got 10/truth 10 -> tp 9/got 10/truth 10"]
    md = kit.render_ledger(d)
    assert "1 mismatch(es) fixed, 1 introduced" in md and "1 UNTRIAGED" in md
    assert kit.ledger_delta(old, old) == {} and "no change" in kit.render_ledger({})


def _estate(verdicts: dict, passes: int) -> dict:
    return {
        "engine_commit": "abc",
        "channels": {"units": {"pass": passes, "fail": 5 - passes, "missing": 0, "phantom": 0, "unscored": 0}},
        "horrors": [
            {"id": h, "issue": 1, "title": f"t{h}", "verdict": v, "failing": [{}] * (v != "PASS")}
            for h, v in verdicts.items()
        ],
    }


def test_estate_delta_and_render():
    before = _estate({"H-0001": "FAIL", "H-0002": "PASS"}, 3)
    after = _estate({"H-0001": "PASS", "H-0002": "PASS"}, 4)
    d = kit.estate_delta(before, after)
    assert (d["pass_before"], d["pass_after"], d["n_horrors"]) == (1, 2, 2)
    assert [h["id"] for h in d["horrors"]] == ["H-0001"]
    md = kit.render_estate(d)
    assert "1/2 -> 2/2" in md and "| H-0001 | #1 | FAIL (1 not passing) | PASS |" in md
    assert "pass 3->4" in md and "| units | 3/2/0/0 | 4/1/0/0 |" in md
    assert "no base scorecard" in kit.render_estate(kit.estate_delta(None, after))
    assert "not scored" in kit.render_estate(kit.estate_delta(before, None))


# ----------------------------------------------------------------------------- evidence


def test_render_evidence_full_document_with_train():
    old, new = _audit(), _audit()
    new[PARSED]["cobol/app"]["Files"]["cobol/app/A.cbl"]["5. Function Analysis"]["functions"] = []
    g = {"full": kit.summarize_golden(_changes(old, new)), "zero": kit.summarize_golden([])}
    train = {
        "branch": "train/t",
        "base_sha": "0123456789abcdef",
        "steps": [
            {"branch": "fix/a", "sha": "aaaaaaaaaaaa", "golden": g["full"].to_json(), "notes": []},
            {"branch": "fix/b", "sha": "bbbbbbbbbbbb", "golden": kit.GoldenSummary().to_json(), "notes": ["n"]},
        ],
    }
    md = kit.render_evidence(g, "0123456789abcdef", {}, None, train, template=True)
    assert md.startswith("## What was broken")
    assert "## Golden masters (vs `0123456789ab`)" in md
    assert "zero-dependency (`tests/golden_master_zero_dep_audit`)**: unchanged" in md
    assert "| 1 | `fix/a` @ `aaaaaaaaaa` | 1 | 1 |" in md and "| 2 | `fix/b` @ `bbbbbbbbbb` | 0 | 0 |  | n |" in md
    assert "Ground-truth ledger: no change." in md and "Estate-crucible: not scored." in md


def test_fmt_secs():
    assert kit.fmt_secs(5) == "5s" and kit.fmt_secs(125) == "2m05s"


# ----------------------------------------------------------------------------- venv selection


def test_scope_leg_and_crucible_venv_python(tmp_path):
    assert [kit.scope_leg(m) for m in ("full", "both", "zero")] == ["full", "full", "zero"]
    assert kit.crucible_venv_python(tmp_path, "full") == tmp_path / ".crucible_venvs/full_precision/bin/python"
    assert kit.crucible_venv_python(tmp_path, "zero") == tmp_path / ".crucible_venvs/zero_dependency/bin/python"


def test_venv_env_drops_inherited_engine_and_prepends_bin(tmp_path):
    py = tmp_path / "wt" / ".crucible_venvs" / "full_precision" / "bin" / "python"
    base = {"PYTHONPATH": "/live/v6", "VIRTUAL_ENV": "/live/v6/.venv", "PYTHONHOME": "/x", "PATH": "/usr/bin", "K": "v"}
    env = kit.venv_env(base, py)
    assert "PYTHONPATH" not in env and "PYTHONHOME" not in env
    assert env["VIRTUAL_ENV"] == str(py.parent.parent)
    assert env["PATH"].split(os.pathsep)[:2] == [str(py.parent), "/usr/bin"] and env["K"] == "v"
    assert base["PYTHONPATH"] == "/live/v6"  # input untouched


def test_ensure_crucible_venv_errors_clearly_without_crucible_check(tmp_path):
    class FakeKit:
        wt = tmp_path

        def log(self, name):
            return tmp_path / f"{name}.log"

    with pytest.raises(kit.KitError, match="crucible_check.py is missing"):
        kit.ensure_crucible_venv(FakeKit(), "full")  # type: ignore[arg-type]
