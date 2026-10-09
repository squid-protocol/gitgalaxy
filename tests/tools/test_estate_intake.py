"""estate_intake: assumed values and missing copybooks become a confirmation list; deterministic, fixture files only."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import estate_intake as ei

ESTATE = {
    "compiler": {
        "product": {"value": "Enterprise COBOL", "source": "a/b.jcl:7", "note": "n"},
        "installation_defaults": {"TRUNC": {"value": "STD", "source": "assumed: IBM default", "note": "n"}},
    },
    "parm": {"default": [{"option": "NUMPROC", "value": "PFD", "source": "assumed: owner decision", "note": "n"}]},
    "le": {"runtime_options": {"STORAGE": {"value": "NONE", "source": "assumed: not stated in the corpus"}}},
    "db2": {"format": {"DATE": {"value": "ISO", "source": "assumed: IBM default", "note": "n"}}},
    "cics": {"region": {"LOCALCCSID": {"value": "037", "source": "assumed: IBM default", "note": "n"}}},
}
REPORT = {
    "programs": [
        {"program": "src/B.cbl", "residual": {"refused": "missing copybook CEEIGZCT"}},
        {"program": "src/A.cbl", "residual": {"refused": "missing copybook CEEIGZCT"}},
        {"program": "src/C.cbl", "residual": {"refused": None}},
    ]
}


def test_found_values_are_not_listed():
    rows = ei.assumed_values(ESTATE)
    assert "compiler.product" not in [r["where"] for r in rows]
    assert [r["option"] for r in rows] == ["TRUNC", "NUMPROC", "STORAGE", "DATE", "LOCALCCSID"]


def test_sections_route_to_the_checklist():
    rows = {r["option"]: r for r in ei.assumed_values(ESTATE)}
    assert [rows[o]["section"] for o in ("TRUNC", "NUMPROC", "STORAGE", "DATE", "LOCALCCSID")] == [
        "2",
        "1",
        "3",
        "4",
        "5",
    ]
    assert rows["NUMPROC"]["basis"] == "owner decision"


def test_missing_copybooks_group_programs():
    assert ei.missing_copybooks(REPORT) == {"CEEIGZCT": ["src/A.cbl", "src/B.cbl"]}


def test_render_is_deterministic_markdown():
    text = ei.render("x", ESTATE, REPORT)
    assert text == ei.render("x", ESTATE, REPORT)
    assert "## Assumed options (5)" in text and "| `CEEIGZCT` | src/A.cbl, src/B.cbl | section 7 |" in text
    assert "None" in ei.render("x", {}, None).split("## Assumed options (0)")[1]


def test_main_reads_files(tmp_path, capsys):
    (tmp_path / "c.json").write_text(json.dumps(ESTATE))
    rpt = tmp_path / "r.json"
    rpt.write_text(json.dumps(REPORT))
    assert ei.main(["c", "--options-dir", str(tmp_path), "--report", str(rpt)]) == 0
    assert "LOCALCCSID" in capsys.readouterr().out
    assert ei.main(["nope", "--options-dir", str(tmp_path)]) == 2


def test_committed_estates_render():
    for path in sorted(ei.OPTIONS_DIR.glob("*.json")):
        text = ei.render(path.stem, json.loads(path.read_text()), None)
        assert text.startswith(f"# Estate intake: {path.stem}")
