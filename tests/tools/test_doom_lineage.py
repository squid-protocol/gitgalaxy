"""DOOM study lineage (#5620): name / body survival vs the baseline, subsystems, stated parents, divergence, landmarks.

Synthetic sources only (no DOOM code); each fake port is a git-tracked source tree plus a minimal scan DB. The tool
dir goes on sys.path and the module is imported as a bare name (tests/ has no __init__.py).
"""

import csv
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "doom_speedrun"))

import lineage  # noqa: E402

SHA = "abc123def"

TICKER = """void P_Ticker (void)
{
    int i;
    for (i = 0; i < MAXPLAYERS; i++)
        if (playeringame[i])
            P_PlayerThink (&players[i]);
    P_RunThinkers ();
}
"""
DRAW = """void R_DrawColumn (void)
{
    int count;
    count = dc_yh - dc_yl;
    if (count < 0)
        return;
    while (count--)
        *dest = dc_colormap[dc_source[(frac >> FRACBITS) & 127]];
}
"""
MENU = """boolean M_Responder (event_t* ev)
{
    if (ev->type != ev_keydown)
        return false;
    if (menuactive == 0)
        return false;
    M_StartControlPanel ();
    return true;
}
"""
STUB = "void I_Stub (void)\n{\n    return;\n}\n"


def make_port(work, name, files, funcs, languages=None):
    """files: {rel: source}; funcs: [(rel, name, start_line, loc, args, complexity)]. The tree is git-tracked."""
    repo = work / "repos" / name
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    scan = work / "scans" / SHA / name
    scan.mkdir(parents=True)
    con = sqlite3.connect(scan / f"{name}_galaxy_master.db")
    con.execute("create table file_data (id integer primary key, file_path text, language text)")
    con.execute(
        "create table function_data (file_id integer, func_name text, start_line integer, loc integer, "
        "args integer, complexity integer)"
    )
    ids = {}
    for rel in files:
        lang = (languages or {}).get(rel, "c")
        ids[rel] = con.execute("insert into file_data (file_path, language) values (?, ?)", (rel, lang)).lastrowid
    for rel, fname, start, loc, args, cx in funcs:
        con.execute("insert into function_data values (?, ?, ?, ?, ?, ?)", (ids[rel], fname, start, loc, args, cx))
    con.commit()
    con.close()
    return repo


def nlines(src):
    return len(src.splitlines())


@pytest.fixture
def work(tmp_path):
    base_files = {
        "linuxdoom-1.10/p_tick.c": TICKER,
        "linuxdoom-1.10/r_draw.c": DRAW,
        "linuxdoom-1.10/m_menu.c": MENU,
        "linuxdoom-1.10/i_system.c": STUB,
    }
    make_port(
        tmp_path, "linuxdoom", base_files,
        [("linuxdoom-1.10/p_tick.c", "P_Ticker", 1, nlines(TICKER), 0, 3),
         ("linuxdoom-1.10/r_draw.c", "R_DrawColumn", 1, nlines(DRAW), 0, 3),
         ("linuxdoom-1.10/m_menu.c", "M_Responder", 1, nlines(MENU), 1, 3),
         ("linuxdoom-1.10/i_system.c", "I_Stub", 1, nlines(STUB), 0, 1)],
    )  # fmt: skip
    # A descendant: P_Ticker reformatted with a comment (still exact), R_DrawColumn edited (near), M_Responder gone.
    ticker = TICKER.replace("int i;", "int i; /* loop */").replace("    P_RunThinkers", "\n\n  P_RunThinkers")
    draw = DRAW.replace("& 127", "& 255")
    make_port(
        tmp_path, "chocolate-doom", {"src/doom/p_tick.c": ticker, "src/doom/r_draw.c": draw},
        [("src/doom/p_tick.c", "P_Ticker", 1, nlines(ticker), 0, 3),
         ("src/doom/r_draw.c", "R_DrawColumn", 1, nlines(draw), 0, 3)],
    )  # fmt: skip
    # A child of the descendant that renamed everything into a class: names survive, bodies do not.
    cs = "class Game {\n    public void PTicker() { Players.Think(); Thinkers.Run(); }\n}\n"
    make_port(
        tmp_path, "crispy-doom", {"Game.cs": cs}, [("Game.cs", "Game::PTicker", 2, 1, 0, 1)],
        languages={"Game.cs": "csharp"},
    )  # fmt: skip
    return tmp_path


ROWS = [
    {"name": "linuxdoom", "lineage": "(root) id Software 1997 release"},
    {"name": "chocolate-doom", "lineage": "linuxdoom-1.10 (vanilla-accurate port)"},
    {"name": "crispy-doom", "lineage": "Chocolate Doom"},
]


def test_names_tokens_and_subsystems():
    assert lineage.norm_name("Game::P_Ticker") == lineage.norm_name("game.p_ticker") == "pticker"
    assert lineage.tokens("void f(int a) { x = 1; /* c */ // d\n }", "c") == ["{", "x", "=", "1", ";", "}"]
    assert "#" in lineage.tokens("def f():\n    x = 1  # c", "python")  # no C comments outside C-style languages
    assert lineage.subsystem("linuxdoom-1.10/r_draw.c") == "renderer"
    assert lineage.subsystem("linuxdoom-1.10/i_net.c") == "netcode"
    assert lineage.subsystem("sndserv/soundsrv.c") == "sound"
    assert lineage.subsystem("linuxdoom-1.10/info.c") == "data-tables"
    assert lineage.subsystem("linuxdoom-1.10/qmus2mid.c") == "other"


@pytest.mark.parametrize(
    ("exact", "best", "named", "cls"),
    [(True, 1.0, True, "exact"), (False, 0.9, True, "near"), (False, 0.6, True, "derived"),
     (False, 0.59, True, "name-only"), (False, 0.0, False, "gone")],
)  # fmt: skip
def test_classify_thresholds_are_inclusive(exact, best, named, cls):
    assert lineage.classify(exact, best, named) == cls


@pytest.mark.parametrize(
    ("text", "parent"),
    [("linuxdoom-1.10 (vanilla-accurate port)", "linuxdoom"), ("Chocolate Doom (terminal renderer)", "chocolate-doom"),
     ("Chocolate Doom codebase (inferred ...)", "chocolate-doom"), ("PrBoom+", "prboom-plus"),
     ("PrBoom (single-header port)", ""), ("WinMBF <- MBF <- Boom", ""), ("(root) id Software 1997 release", ""),
     ("Go rewrite (linuxdoom lineage)", ""), ("Woof engine (own lineage)", "")],
)  # fmt: skip
def test_parent_is_the_first_manifest_port_the_lineage_names(text, parent):
    names = ["linuxdoom", "chocolate-doom", "crispy-doom", "prboom-plus", "woof", "gore"]
    assert lineage.parent_of(text, names, own="woof") == parent


def test_survival_per_function_subsystem_and_parent(work):
    out, skipped = lineage.run(ROWS, work, SHA, vendor_test=lambda repo: lambda rel: False)
    assert skipped == []
    fn = {(r["variant"], r["func"]): r for r in out["survival_functions.csv"]}
    assert "I_Stub" not in {r["func"] for r in out["survival_functions.csv"]}  # under MIN_TOKENS
    assert fn["chocolate-doom", "P_Ticker"]["cls"] == "exact"  # comments and whitespace do not count
    assert fn["chocolate-doom", "R_DrawColumn"]["cls"] == "near"
    assert fn["chocolate-doom", "M_Responder"]["cls"] == "gone"
    assert fn["crispy-doom", "P_Ticker"]["cls"] == "name-only"  # renamed into a class: the name survives
    summary = {r["variant"]: r for r in out["survival.csv"]}
    choc = summary["chocolate-doom"]
    assert (choc["base_funcs"], choc["pct_name"], choc["pct_exact_body"], choc["pct_near_ge_0_9"]) == (
        3,
        66.7,
        33.3,
        66.7,
    )
    assert (choc["parent"], choc["exact_vs_parent"]) == ("linuxdoom", -66.7)
    crispy = summary["crispy-doom"]
    assert (crispy["parent"], crispy["pct_name"], crispy["pct_exact_body"]) == ("chocolate-doom", 33.3, 0.0)
    assert crispy["exact_vs_parent"] == -33.3
    subs = {(r["variant"], r["subsystem"]): r for r in out["survival_subsystem.csv"]}
    assert subs["chocolate-doom", "renderer"]["pct_near_ge_0_9"] == 100.0
    assert subs["chocolate-doom", "misc"]["pct_name"] == 0.0
    stems = {r["variant"]: r for r in out["filename_survival.csv"]}
    assert stems["chocolate-doom"]["missing"] == "i_system m_menu"
    assert "| chocolate-doom | linuxdoom-1.10 (vanilla-accurate port) | linuxdoom | 66.7 |" in out["lineage.md"]


def test_divergence_and_landmarks_skip_vendored_code(work):
    vendored = {"crispy-doom": lambda rel: rel == "Game.cs"}
    out, _ = lineage.run(ROWS, work, SHA, vendor_test=lambda repo: vendored.get(repo.name, lambda rel: False))
    names = {r["variant"]: r for r in out["divergence_names.csv"]}
    assert names["linuxdoom"]["chocolate-doom"] == 0.5  # {pticker, rdrawcolumn} of the four linuxdoom names
    assert names["linuxdoom"]["crispy-doom"] == 0.0  # crispy's only function is vendored
    core = {r["variant"]: r for r in out["divergence_core.csv"]}
    assert core["chocolate-doom"]["chocolate-doom"] == 1.0 and core["chocolate-doom"]["crispy-doom__n"] == 1
    landmark = {(r["variant"], r["function"]): r for r in out["canonical_functions.csv"]}
    assert (landmark["linuxdoom", "M_Responder"]["complexity"], landmark["linuxdoom", "M_Responder"]["loc"]) == (3, 9)
    assert landmark["crispy-doom", "R_DrawColumn"]["found_as"] == ""


def _fn(name, loc, file="src/a.c"):
    return dict(name=name, nname=lineage.norm_name(name), file=file, loc=loc, complexity=loc // 2)


def test_landmarks_match_a_dropped_prefix_only_when_the_bare_name_is_specific():
    fns = [_fn("UseSpecialLine", 30), _fn("draw_column", 12), _fn("Ticker", 50), _fn("Responder", 40),
           _fn("DamageMobj", 20, "heretic/a.c")]  # fmt: skip
    got = lineage.canonical(fns, lambda rel: False)
    assert got["P_UseSpecialLine"]["found_as"] == "UseSpecialLine" and got["P_UseSpecialLine"]["loc"] == 30
    assert got["R_DrawColumn"]["found_as"] == "draw_column"
    assert got["M_Responder"]["found_as"] == "Responder"
    assert got["G_Ticker"]["found_as"] == ""  # "Ticker" is every subsystem's
    assert got["P_DamageMobj"]["found_as"] == ""  # another game's tree
    # a function keeping the full name wins over a bigger prefix-less one
    fns = [_fn("draw_column", 90), _fn("R_DrawColumn", 10)]
    assert lineage.canonical(fns, lambda rel: False)["R_DrawColumn"]["found_as"] == "R_DrawColumn"
    assert lineage.canonical(fns, lambda rel: True)["R_DrawColumn"]["found_as"] == ""


def test_main_refuses_unlicensed_ports_and_writes_results(work, monkeypatch, capsys):
    with pytest.raises(SystemExit, match="not-a-licensed-port"):
        lineage.main(["--only", "not-a-licensed-port", "--work", str(work), "--sha", SHA])
    manifest = work / "manifest.csv"
    with open(manifest, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["name", "upstream", "sha", "branch", "languages", "lineage"])
        w.writeheader()
        w.writerows({"upstream": "", "sha": "", "branch": "", "languages": "", **r} for r in ROWS)
    monkeypatch.setattr(lineage, "_engine_vendor_test", lambda repo: lambda rel: False)
    args = ["--only", "chocolate-doom,doomretro", "--work", str(work), "--sha", SHA, "--manifest", str(manifest)]
    assert lineage.main(args) == 0
    dest = work / "results" / SHA / "lineage"
    assert {p.name for p in dest.iterdir()} >= {"survival.csv", "survival_functions.csv", "lineage.md"}
    with open(dest / "survival.csv", newline="") as fh:
        assert [r["variant"] for r in csv.DictReader(fh)] == ["chocolate-doom"]  # crispy not asked for
    assert "chocolate-doom" in capsys.readouterr().out
