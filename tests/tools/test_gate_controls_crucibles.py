"""#7155: negative controls for the crucible gates. Each feeds the real --ci decision a planted regression and asserts red.

The measurement (a scan of the pinned corpus) is stubbed, so these prove the gate's logic, not the job around it.
"""

import copy
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import cics_crucible as cx  # noqa: E402
import estate_crucible_gate as eg  # noqa: E402
import unicode_gauntlet as ug  # noqa: E402

_CHANNEL = {"pass": 5, "fail": 0, "missing": 0, "phantom": 0, "unscored": 0}
_BASE = {
    "pinned_ref": "abc",
    "horrors": {"H1": "PASS", "H2": "FAIL"},
    "channels": {"copy": dict(_CHANNEL)},
    "not_passing": {"copy|M|f": "fail"},
}


def _now(**edit):
    now = copy.deepcopy(_BASE)
    for key, fn in edit.items():
        fn(now[key])
    return now


def test_estate_crucible_compare_goes_red_on_each_planted_regression():
    assert eg.compare(_BASE, copy.deepcopy(_BASE)) == ([], [])  # positive control: the baseline itself is green
    planted = {
        "a horror that passed now fails": _now(horrors=lambda h: h.update(H1="FAIL")),
        "a new horror that does not pass": _now(horrors=lambda h: h.update(H3="FAIL")),
        "a channel loses a pass": _now(channels=lambda c: c["copy"].update({"pass": 4})),
        "a channel gains a failure": _now(channels=lambda c: c["copy"].update({"fail": 1})),
        "a channel is gone": _now(channels=lambda c: c.clear()),
        "a new failing check": _now(not_passing=lambda n: n.update({"copy|M|g": "missing"})),
    }
    for what, now in planted.items():
        bad, _ = eg.compare(_BASE, now)
        assert bad, f"estate-crucible stayed green when {what}"
    bad, _ = eg.compare(_BASE, {**copy.deepcopy(_BASE), "pinned_ref": "other"})
    assert any("PINNED_REF" in m for m in bad)  # a baseline from another pin is refused
    _, good = eg.compare(_BASE, _now(horrors=lambda h: h.update(H2="PASS")))
    assert good  # an improvement is reported, never a failure


def test_estate_crucible_main_exits_1_on_a_regression_and_2_without_a_baseline(monkeypatch, tmp_path, capsys):
    crucible = tmp_path / "crucible"
    (crucible / "key").mkdir(parents=True)
    (crucible / "key" / "manifest.json").write_text("{}", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    now = {"value": copy.deepcopy(_BASE)}
    monkeypatch.setattr(eg.ec, "pin_mismatch", lambda c: None)
    monkeypatch.setattr(eg.ec, "scan", lambda c, t: None)
    monkeypatch.setattr(eg.ec, "score", lambda c, s: None)
    monkeypatch.setattr(eg, "snapshot", lambda sc, c: now["value"])
    argv = ["--crucible", str(crucible), "--baseline", str(baseline)]
    assert eg.main(argv) == 2  # no committed baseline fails closed
    baseline.write_text(json.dumps(_BASE), encoding="utf-8")
    assert eg.main(argv) == 0
    now["value"] = _now(horrors=lambda h: h.update(H1="FAIL"))
    assert eg.main(argv) == 1
    assert "horror H1: PASS -> FAIL" in capsys.readouterr().out


def _cells(**status):
    return {"cells": {cid: {"status": st, "reason": "r"} for cid, st in status.items()}}


def test_cics_crucible_ratchet_goes_red_on_a_new_failure_a_fixed_cell_and_a_lost_cell(monkeypatch, capsys):
    monkeypatch.setattr(cx, "read_baseline", lambda: {"cells": {"c2": {"status": "fail", "reason": "r"}}})
    monkeypatch.setattr(cx, "read_coverage", lambda: {"programs": {}})
    ok = _cells(c1="pass", c2="fail")
    assert cx.hold_ratchets(ok, set(), True, True) == 0  # positive control: exactly the ledgered state
    assert cx.hold_ratchets(_cells(c1="fail", c2="fail"), set(), True, True) == 1  # a cell that passed now fails
    assert "NEW FAIL: c1" in capsys.readouterr().out
    assert cx.hold_ratchets(_cells(c1="pass", c2="pass"), set(), True, True) == 1  # fixed but still ledgered
    assert "NOW PASSES" in capsys.readouterr().out
    assert cx.hold_ratchets(_cells(c1="pass"), set(), True, True) == 1  # a ledgered cell no longer measured
    assert "STALE: c2" in capsys.readouterr().out


def test_unicode_gauntlet_ci_fails_on_a_new_failing_cell_only(monkeypatch, tmp_path, capsys):
    results = {"cell-ok": {"diffs": []}, "cell-old": {"diffs": ["d"]}}
    monkeypatch.setattr(ug, "run", lambda *a, **k: results)
    monkeypatch.setattr(ug, "read_baseline", lambda: {"cell-old": "d"})
    argv = ["--corpus", str(tmp_path), "--ci"]
    assert ug.main(argv) == 0  # a baselined failure is not new
    results["cell-new"] = {"diffs": ["planted difference"]}
    assert ug.main(argv) == 1
    assert "NEW FAILING CELL cell-new" in capsys.readouterr().out
    monkeypatch.setattr(ug, "read_baseline", lambda: {})
    assert ug.main(argv) == 1  # no baseline: every failing cell is new
