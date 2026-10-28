"""DOOM per-subsystem plots (#6097): CSV read, colour scale, grey for a missing ratio, SVG well-formed, CLI output.

Synthetic CSV only (no DOOM code); the tool dir goes on sys.path and the module is imported as a bare name.
"""

import csv
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "doom_speedrun"))

import distribution  # noqa: E402
import subsystem_plot as sp  # noqa: E402


def write_csv(path, rows):
    fields = ["port", "other_pct", "subsystem", "n", "share", "cx10"] + [
        f"{f}_{k}" for f in distribution.FIELDS for k in ("med", "p90", "vs_linuxdoom")
    ]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


ROWS = [
    dict(port="gore", other_pct=12.5, subsystem="p_", complexity_vs_linuxdoom=2.0, loc_vs_linuxdoom=0.5),
    dict(port="gore", other_pct=12.5, subsystem="r_", complexity_vs_linuxdoom=""),
    dict(port="gore", other_pct=12.5, subsystem="other", complexity_vs_linuxdoom=1.0),
    dict(port="cssdoom", other_pct=0, subsystem="p_", complexity_vs_linuxdoom=0.25),
]


def test_colour_scale_is_symmetric_in_log_and_grey_when_missing():
    assert sp.colour(None) == sp.GREY
    assert sp.colour(1.0) == "rgb(255,255,255)"
    assert sp.colour(4.0) == "rgb(255,0,0)" and sp.colour(0.25) == "rgb(0,0,255)"
    assert sp.colour(100.0) == sp.colour(4.0) and sp.colour(0.0) != sp.GREY
    assert sp.colour(0.5).endswith(",255)")


def test_read_ratios_keeps_blank_as_none_and_other_share(tmp_path):
    write_csv(tmp_path / "s.csv", ROWS)
    ratios, other = sp.read_ratios(tmp_path / "s.csv", "complexity")
    assert ratios["gore"] == {"p_": 2.0, "r_": None, "other": 1.0}
    assert other == {"gore": 12.5, "cssdoom": 0.0}
    loc, _ = sp.read_ratios(tmp_path / "s.csv", "loc")
    assert loc["gore"]["p_"] == 0.5 and loc["cssdoom"]["p_"] is None


def test_missing_metric_column_is_refused(tmp_path):
    (tmp_path / "s.csv").write_text("port,other_pct,subsystem\ngore,0,p_\n")
    with pytest.raises(SystemExit, match="no column complexity_vs_linuxdoom"):
        sp.read_ratios(tmp_path / "s.csv", "complexity")


def test_svg_is_well_formed_one_row_per_port_other_last(tmp_path):
    write_csv(tmp_path / "s.csv", ROWS)
    ratios, other = sp.read_ratios(tmp_path / "s.csv", "complexity")
    root = ET.fromstring(sp.render(ratios, other, "complexity"))
    ns = "{http://www.w3.org/2000/svg}"
    rects = root.findall(f"{ns}rect")
    assert len(rects) == 2 * 3  # 2 ports x (p_, r_, other)
    fills = [r.get("fill") for r in rects]
    assert fills.count(sp.GREY) == 3  # gore r_, cssdoom r_ and cssdoom other: no ratio, not zero
    texts = [t.text for t in root.findall(f"{ns}text")]
    assert "other %" in texts and "12" in texts and "2.00" in texts


def test_cli_writes_the_svg_beside_the_csv(tmp_path):
    write_csv(tmp_path / "s.csv", ROWS)
    assert sp.main(["--csv", str(tmp_path / "s.csv"), "--metric", "loc"]) == 0
    assert (tmp_path / "subsystem_loc.svg").read_text().startswith("<svg")


def test_cli_without_a_csv_says_to_run_the_distribution_first(tmp_path):
    with pytest.raises(SystemExit, match="run subsystem_distribution.py first"):
        sp.main(["--work", str(tmp_path), "--sha", "abc"])


def test_cx10_is_an_absolute_share_on_a_linear_scale(tmp_path):
    rows = [
        dict(port="gore", other_pct=0, subsystem="p_", cx10=25.0),
        dict(port="gore", other_pct=0, subsystem="r_", cx10=0.0),
        dict(port="gore", other_pct=0, subsystem="s_", cx10=""),
    ]
    write_csv(tmp_path / "s.csv", rows)
    shares, _ = sp.read_ratios(tmp_path / "s.csv", "cx10")
    assert shares["gore"] == {"p_": 25.0, "r_": 0.0, "s_": None}
    assert sp.colour_share(0.0) == "rgb(255,255,255)" and sp.colour_share(sp.CX10_FULL) == "rgb(255,0,0)"
    assert sp.colour_share(500.0) == sp.colour_share(sp.CX10_FULL) and sp.colour_share(None) == sp.GREY
    root = ET.fromstring(sp.render(shares, {"gore": 0.0}, "cx10"))
    ns = "{http://www.w3.org/2000/svg}"
    fills = [r.get("fill") for r in root.findall(f"{ns}rect")]
    assert fills == ["rgb(255,128,128)", "rgb(255,255,255)", sp.GREY, sp.GREY]  # 0% white; s_ blank and the empty other column grey
    assert "25" in [t.text for t in root.findall(f"{ns}text")]
