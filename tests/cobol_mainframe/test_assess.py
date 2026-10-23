"""#4726 `gitgalaxy assess`: no source text in the report over every burned estate, redaction, the read-only and
offline guarantees, and the command end to end.

The fast tests project each burned estate's committed raw inventory (tests/fixtures/feature_inventory/, the same
`scan_estate` output the command projects) and, where the corpora are on disk, hold the report against the estate's own
source. The command itself runs as a subprocess only: in-process it would install the network guard in pytest."""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")  # the det parser; the ground-truth CI job has no translator extra

from gitgalaxy.tools.readiness import offline
from gitgalaxy.tools.readiness import schema as SC

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures" / "feature_inventory"
OPTIONS = REPO / "tests" / "equivalence" / "estate_options"
CORPORA = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", REPO / ".mainframe_corpora"))
BURNED = sorted(p.stem for p in FIXTURES.glob("*.json"))  # the six burned estates' corpus directories
TEXT_SUFFIXES = {".cbl", ".cob", ".cobol", ".cpy", ".copy", ".bms", ".asm", ".mac", ".jcl", ".prc", ".proc", ".sql", ""}


def _env() -> dict[str, str]:
    return dict(os.environ, PYTHONPATH=str(REPO), GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER")


def test_every_burned_estate_has_an_inventory():
    assert len(BURNED) == 6, BURNED  # estate4_draw.BURNED_NAMES: CardDemo, CBSA, GenApp, zECS, DBB, async credit card


def _inventory(estate: str) -> dict:
    return json.loads((FIXTURES / f"{estate}.json").read_text())


def _strings(node, out: set[str]) -> set[str]:
    """Every string in a report, keys included."""
    if isinstance(node, dict):
        for k, v in node.items():
            out.add(str(k))
            _strings(v, out)
    elif isinstance(node, list):
        for v in node:
            _strings(v, out)
    elif isinstance(node, str):
        out.add(node)
    return out


def _tokens(report: dict) -> set[str]:
    return {t for s in _strings(report, set()) for t in re.split(r"[\s:/.]+", s) if t}


def _source_files(estate_dir: Path):
    for p in sorted(estate_dir.rglob("*")):
        if p.is_file() and ".git" not in p.parts and p.suffix.lower() in TEXT_SUFFIXES and p.stat().st_size < 4_000_000:
            yield p


_LITERAL = re.compile(r"'([^'\n]{6,})'|\"([^\"\n]{6,})\"")
_DATA_NAME = re.compile(r"^\s*\d{1,2}\s+([A-Za-z0-9][A-Za-z0-9-]{5,})", re.M)
_PARAGRAPH = re.compile(r"^ {7}([A-Za-z0-9][A-Za-z0-9-]{5,})\.\s*$", re.M)


def source_text(estate_dir: Path) -> tuple[set[str], set[str]]:
    """(fragments, user names) of an estate: every string literal of 6+ characters, comment body and code line of 24+
    (fixed form: columns 8-72; the sequence area as well), and every data and paragraph name of 6+ characters."""
    fragments: set[str] = set()
    names: set[str] = set()
    for p in _source_files(estate_dir):
        text = p.read_bytes().decode("latin-1")
        fragments.update(a or b for a, b in _LITERAL.findall(text))
        names.update(_DATA_NAME.findall(text))
        names.update(_PARAGRAPH.findall(text))
        for ln in text.splitlines():
            body = ln[7:72].strip() if len(ln) > 7 else ln.strip()
            if len(body) >= 24:
                fragments.add(body)
            seq = ln[72:80].strip()
            if len(seq) >= 6:
                fragments.add(seq)
    return fragments, names


# the report's own field names and fixed values: a source word equal to one (a comment saying "features") is no leak
STRUCTURE = {
    *SC.CATEGORIES, *SC.STATUSES, *SC.KINDS, SC.UNKNOWN, SC.MISSING_COPYBOOK, "unreadable", "schema", "tool_version",
    "redacted", "totals", "eras", "features", "other", "copybook_gaps", "programs", "parsed", "unparsed",
    "refused_by_family", "assembler_members", "by_era", "mixed", "tells", "count", "keys", "name", "kind", "status",
    "reason", "copybook", "era", "earliest", "program_era", "via_copybook", "tell", "none", "raised_by_copybook",
    "copybook_skipped",
}  # fmt: skip


def _vocabulary() -> set[str]:
    words = SC.STATEMENTS | SC.DATA_TYPES | SC.SQL_FORMS | SC.INTRINSIC_FUNCTIONS | SC.TELL_NAMES | SC.cics_words()
    words |= set(SC.FAMILIES) | STRUCTURE
    return {w for k in words for w in re.split(r"[\s:/.]+", k) if w} | set(SC.SEMANTIC_OPTIONS)


def assert_no_source_text(report: dict, estate_dir: Path, allowed_names: set[str]) -> None:
    text = json.dumps(report)
    fragments, names = source_text(estate_dir)
    # a fragment made only of program / copybook names (CardDemo writes its program name in the sequence area and in
    # literals) or of feature words (a literal 'DELETE') is a name the report may print, not the estate's text
    allowed = allowed_names | _vocabulary()
    toks = _tokens(report)
    leaked = sorted(
        f
        for f in fragments
        if (f in toks if re.fullmatch(r"\S+", f) else f in text)  # one word: as a whole token, never a substring
        and not set(re.split(r"[\s/.]+", f.strip())) <= allowed
    )
    assert not leaked, leaked[:10]
    named = sorted(n for n in names if n in toks and n.upper() not in allowed and n not in allowed_names)
    assert not named, named[:10]


def _program_names(inv: dict) -> set[str]:
    """The estate's program paths and their parts, and its copybook member names: a plain report may print them."""
    out: set[str] = set()
    for p in inv["eras"]["programs"]:
        out.update(re.split(r"[/.]", p))
    for v in inv.get("refusal_families", {}).values():
        for p in v["programs"]:
            out.update(re.split(r"[/.]", p))
    for key in inv.get("copybook_resolution_gaps", {}):
        out.update(key.split())
    return out


@pytest.mark.parametrize("estate", BURNED)
def test_projection_holds_its_schema(estate):
    """Every burned estate: the plain and the redacted report pass `validate`, and nothing off-vocabulary is printed."""
    inv = _inventory(estate)
    for key in (None, b"k"):
        report = SC.project(inv, redact_key=key)
        assert SC.validate(report) == []
        for cat, keys in report["features"].items():
            assert all(SC.known(cat, k) for k in keys)


@pytest.mark.parametrize("estate", BURNED)
def test_no_source_text_in_the_report(estate):
    """Every burned estate's report against its own source: no literal, comment, code line, sequence number, data or
    paragraph name appears; only program and copybook names do (and under redaction, not those)."""
    estate_dir = CORPORA / estate
    if not estate_dir.is_dir():
        pytest.skip("no mainframe corpora (mainframe_corpus.py fetch)")
    inv = _inventory(estate)
    assert_no_source_text(SC.project(inv), estate_dir, _program_names(inv))
    assert_no_source_text(SC.project(inv, redact_key=b"k"), estate_dir, set())


def test_the_checker_catches_the_raw_inventory():
    """The source-text check is not vacuous: the CardDemo inventory with a sequence-number key planted (what the stale
    fixture held before #5235) fails it."""
    estate_dir = CORPORA / "aws-mainframe-modernization-carddemo"
    if not estate_dir.is_dir():
        pytest.skip("no mainframe corpora (mainframe_corpus.py fetch)")
    inv = json.loads(json.dumps(_inventory("aws-mainframe-modernization-carddemo")))
    inv["cics_commands"]["ASKTIME 03430012"] = {"count": 1, "programs": [next(iter(inv["eras"]["programs"]))]}
    with pytest.raises(AssertionError):
        assert_no_source_text(inv, estate_dir, _program_names(inv))


def test_carddemo_sequence_numbers_never_reach_the_report():
    """A raw inventory that carried sequence-area numbers as CICS command words (the stale CardDemo fixture before
    #5235) is planted into the current one; the report counts them under `other` and prints none."""
    inv = json.loads(json.dumps(_inventory("aws-mainframe-modernization-carddemo")))
    planted = ["02750012 029200", "ASKTIME 03430012"]
    for k in planted:
        inv["cics_commands"][k] = {"count": 1, "programs": [next(iter(inv["eras"]["programs"]))]}
    report = SC.project(inv)
    text = json.dumps(report)
    assert not any(w in text for k in planted for w in k.split() if w.isdigit())
    assert report["other"]["cics_commands"]["keys"] >= len(planted)


def _names(inv: dict) -> set[str]:
    out = set(inv["eras"]["programs"])
    for v in inv.get("refusal_families", {}).values():
        out.update(v["programs"])
    return out


def _shape(report: dict) -> dict:
    """The report with every program / copybook name blanked: what redaction must leave unchanged."""
    r = json.loads(json.dumps(report))
    for cat in r["features"].values():
        for v in cat.values():
            v["programs"] = len(v["programs"])
    for g in r["copybook_gaps"]:
        g["name"], g["programs"] = g["name"] is not None, len(g["programs"])
    r["copybook_gaps"].sort(key=lambda g: (g["name"], g["programs"]))
    rows = []
    for p in r["programs"]:
        p["name"] = None
        if "copybook" in p:
            p["copybook"] = True
        rows.append(json.dumps(p, sort_keys=True))
    r["programs"] = sorted(rows)
    r["redacted"] = None
    return r


@pytest.mark.parametrize("estate", BURNED)
def test_redaction(estate):
    """Every burned estate: no program path, file name or stem, and no copybook member name, appears redacted; the
    labels are stable under one key and change with it; every count is the plain report's."""
    inv = _inventory(estate)
    plain = SC.project(inv)
    red = SC.project(inv, redact_key=b"key-1")
    text = json.dumps(red)
    toks = _tokens(red)
    for p in _names(inv):
        assert p not in text
        stem = Path(p).stem
        assert Path(p).name not in text and stem not in toks
    for g in plain["copybook_gaps"]:
        if g["name"]:
            assert g["name"] not in toks
    assert red["redacted"] is True and all(re.match(r"^P-[0-9a-f]{12}$", r["name"]) for r in red["programs"])
    assert SC.project(inv, redact_key=b"key-1") == red
    other = SC.project(inv, redact_key=b"key-2")
    assert {r["name"] for r in other["programs"]}.isdisjoint({r["name"] for r in red["programs"]})
    assert _shape(red) == _shape(plain)


def test_an_unparsed_reason_prints_its_class_never_its_message():
    inv = {
        "eras": {"programs": {"A.cbl": {"era": None, "earliest": None, "mixed": False, "tells": []}}, "summary": {}},
        "unparsed_programs": [{"program": "A.cbl", "reason": "NotCobol - MOVE SECRET-FIELD TO 'PASSWORD 1234'"}],
    }
    report = SC.project(inv)
    assert report["programs"][0]["reason"] == "NotCobol"
    assert "SECRET" not in json.dumps(report) and SC.validate(report) == []
    inv["unparsed_programs"][0]["reason"] = "MOVE X TO Y - quoted"
    assert SC.project(inv)["programs"][0]["reason"] == "unreadable"


def test_a_skipped_copybook_pass_prints_its_reason_code_never_a_message():
    """#5195: `copybook_skipped` reaches the report as a class-like code on a COBOL row and on an assembler member's row."""
    tag = {"era": None, "earliest": None, "mixed": False, "tells": [], "copybook_skipped": "CopyNotFound"}
    asm = {"era": 0, "earliest": 0, "mixed": False, "tells": [], "copybook_skipped": "CopyCycle"}
    inv = {
        "eras": {"programs": {"A.cbl": tag}, "assembler": {"M.asm": asm}, "summary": {"copybook_skipped": 1}},
        "refusal_families": {"macro-level CICS": {"count": 1, "programs": ["M.asm"]}},
        "unparsed_programs": [],
    }
    report = SC.project(inv)
    rows = {r["kind"]: r for r in report["programs"]}
    assert rows["cobol"]["copybook_skipped"] == "CopyNotFound" and rows["assembler"]["copybook_skipped"] == "CopyCycle"
    assert report["eras"]["copybook_skipped"] == 1 and SC.validate(report) == []
    tag["copybook_skipped"] = "MOVE SECRET TO X"
    clean = SC.project(inv)
    assert "copybook_skipped" not in {k for r in clean["programs"] if r["kind"] == "cobol" for k in r}
    clean["programs"][0]["copybook_skipped"] = "MOVE SECRET TO X"
    assert any("copybook_skipped" in p for p in SC.validate(clean))


def test_validate_refuses_a_widened_report():
    report = SC.project(_inventory("zecs"))
    report["features"]["statements"]["MOVE WS-PASSWORD TO OUT"] = {"count": 1, "programs": []}
    report["programs"][0]["source"] = "MOVE A TO B"
    problems = SC.validate(report)
    assert any("vocabulary" in p for p in problems) and any("keys ['source']" in p for p in problems)


# --- the command end to end, on an estate built to leak -------------------------------------------------------------

MARK = "ZQX"  # in every planted text below; never in a program or copybook name


def _fixed(code: str, seq: str = "") -> str:
    return "\n".join(f"{ln:<72}{seq}" if seq and len(ln) <= 72 else ln for ln in code.splitlines()) + "\n"


PLANTED = {
    "PLANT1.cbl": _fixed(
        """       ID DIVISION.
       PROGRAM-ID. PLANT1.
      * ZQX COMMENT TEXT THAT MUST NEVER LEAVE THE SITE
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-ZQX-CUSTOMER-NAME PIC X(30)
              VALUE 'ZQX LITERAL CUSTOMER DATA'.
       PROCEDURE DIVISION.
       ZQX-MAIN-PARAGRAPH.
           EXEC CICS SEND TEXT FROM(WS-ZQX-CUSTOMER-NAME) END-EXEC.
           MOVE FUNCTION UPPER-CASE(WS-ZQX-CUSTOMER-NAME)
             TO WS-ZQX-CUSTOMER-NAME.
           GOBACK.""",
        "ZQX00001",
    ),
    # a missing copybook: the census falls back to a raw-text parse, sequence area and all
    "PLANT2.cbl": _fixed(
        """       ID DIVISION.
       PROGRAM-ID. PLANT2.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY MISSBOOK.
       PROCEDURE DIVISION.
           EXEC CICS ASKTIME ABSTIME(WS-ZQX-TIME) END-EXEC.
           MOVE FUNCTION ZQXNOTAFUNCTION(WS-ZQX-TIME)
             TO WS-ZQX-TIME.
           EXEC SQL SELECT ZQXCOL INTO :WS-ZQX-TIME
             FROM ZQXTABLE END-EXEC.
           GOBACK.""",
        "ZQXSEQ01",
    ),
    # holes whose own text quotes the program: a file, a key, a data name (the dry run's `hole_texts`)
    "PLANT4.cbl": _fixed(
        """       ID DIVISION.
       PROGRAM-ID. PLANT4.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-ZQX-REC PIC X(10).
       PROCEDURE DIVISION.
           EXEC CICS WRITE FILE('ZQXFILE') FROM(WS-ZQX-REC)
             RIDFLD(WS-ZQX-REC) KEYLENGTH(ZQXLEN) END-EXEC.
           MOVE ZQX-UNDECLARED TO WS-ZQX-REC.
           GOBACK.""",
        "ZQX00004",
    ),
    "PLANT3.cbl": "ZQX THIS FILE IS NOT COBOL AT ALL 'ZQX QUOTED'\n<html>ZQX</html>\n",
}


def _without_translation(report: dict) -> dict:
    """The report as the inventory alone projects it: the dry run's fields (#4726) removed."""
    out = json.loads(json.dumps(report))
    out["totals"].pop("translation", None)
    for row in out["programs"]:
        for k in ("translation", "refusal", "statements", "translated_statements", "holes"):
            row.pop(k, None)
    out.pop("rules", None)
    return out


def _snapshot(root: Path) -> dict[str, tuple[int, int, str]]:
    return {
        str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(root.rglob("*"))
        if p.is_file()
    } | {str(p.relative_to(root)) + "/": (0, 0, "") for p in root.rglob("*") if p.is_dir()}


def _assess(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "gitgalaxy.cli", "assess", *args],
        capture_output=True,
        text=True,
        env=_env(),
        check=False,
        timeout=600,
    )


@pytest.fixture(scope="module")
def planted(tmp_path_factory):
    """(estate, snapshot before, plain report, redacted report, snapshot after): two runs of the real command."""
    base = tmp_path_factory.mktemp("assess")
    estate = base / "estate"
    estate.mkdir()
    for name, text in PLANTED.items():
        (estate / name).write_text(text)
    before = _snapshot(estate)
    key = base / "key"
    key.write_bytes(b"a site key")
    runs = []
    for extra in ((), ("--redact", "--redact-key-file", str(key))):
        out = base / f"report{len(runs)}.json"
        res = _assess(str(estate), "--out", str(out), *extra)
        assert res.returncode == 0, res.stderr[-3000:]
        runs.append(json.loads(out.read_text()))
    return estate, before, runs[0], runs[1], _snapshot(estate)


@pytest.mark.slow(reason="#4726: planted fixture runs two subprocess gitgalaxy assess scans (#5240)")
def test_planted_text_never_reaches_the_report(planted):
    _estate, _before, plain, red, _after = planted
    for report in (plain, red):
        assert SC.validate(report) == []
        assert MARK not in json.dumps(report)
    assert {r["name"] for r in plain["programs"]} == set(PLANTED)
    assert plain["totals"]["programs"] == 4
    rules = {r["rule"] for r in plain["rules"]["ranked"]}  # the new field is in the marker scan above
    assert {"EXEC CICS WRITE: key length not known", "MOVE: no such item"} <= rules
    assert all(SC._rule_known(r["rule"]) for r in plain["rules"]["ranked"])
    rows = {r["name"]: r for r in plain["programs"]}
    assert (rows["PLANT2.cbl"]["status"], rows["PLANT2.cbl"]["reason"]) == ("unparsed", "missing copybook")
    assert plain["other"]["intrinsic_functions"]["keys"] == 1  # FUNCTION ZQXNOTAFUNCTION: counted, never printed
    assert (
        "SEND TEXT" in plain["features"]["cics_commands"] and "UPPER-CASE" in plain["features"]["intrinsic_functions"]
    )
    assert [g["name"] for g in plain["copybook_gaps"]] == ["MISSBOOK"]
    red_text = json.dumps(red)
    assert not any(w in red_text for w in ("PLANT", "MISSBOOK"))


@pytest.mark.slow(reason="#4726: planted fixture runs two subprocess gitgalaxy assess scans (#5240)")
def test_the_estate_is_read_only(planted):
    _estate, before, _plain, _red, after = planted
    assert after == before  # no file written, changed or touched; no directory (.gitgalaxy) created


@pytest.mark.slow(reason="#4726: planted fixture runs two subprocess gitgalaxy assess scans (#5240)")
def test_out_inside_the_estate_is_refused(planted):
    estate = planted[0]
    res = _assess(str(estate), "--out", str(estate / "report.json"))
    assert res.returncode == 2 and "read only" in res.stderr
    assert not (estate / "report.json").exists()


def test_jcl_and_options_together_are_refused_by_name(tmp_path):
    res = _assess(str(tmp_path), "--jcl", str(tmp_path), "--options", str(tmp_path / "o.json"))
    assert res.returncode == 2 and "--jcl and --options" in res.stderr


# --- the network guard -------------------------------------------------------------------------------------------------

_PROBE = """
import socket, sys
from gitgalaxy.tools.readiness.offline import OfflineViolation
results = []
for attempt in (lambda: socket.create_connection(("127.0.0.1", 9), timeout=1),
                lambda: socket.getaddrinfo("example.com", 443),
                lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("127.0.0.1", 9)),
                lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b"x", ("127.0.0.1", 9))):
    try:
        attempt()
        results.append("allowed")
    except OfflineViolation:
        results.append("refused")
    except OSError:
        results.append("allowed")  # reached the network stack: the guard did not stop it
a, b = socket.socketpair()  # AF_UNIX: multiprocessing's local channel
a.sendall(b"ok")
results.append(b.recv(2).decode())
print(" ".join(results))
"""


def test_the_guard_refuses_the_network_and_keeps_local_sockets():
    code = "from gitgalaxy.tools.readiness.offline import install; install(); install()\n" + _PROBE
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=_env(), check=False)  # noqa: S603
    assert res.stdout.split() == ["refused"] * 4 + ["ok"], res.stderr[-2000:]


def test_the_guard_exempts_only_socketpair_loopback():
    """The Windows socketpair emulation (AF_INET loopback connect) must work; a direct loopback connect must not."""
    code = (
        "import socket\n"
        "from gitgalaxy.tools.readiness import offline\n"
        "from gitgalaxy.tools.readiness.offline import OfflineViolation, install\n"
        "install()\n"
        "srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(1)\n"
        "port = srv.getsockname()[1]\n"
        "out = []\n"
        "for exempt in (False, True, False):\n"
        "    try:\n"
        "        if exempt:\n"
        "            with offline._allow_local():\n"
        "                socket.socket().connect(('127.0.0.1', port))\n"
        "        else:\n"
        "            socket.socket().connect(('127.0.0.1', port))\n"
        "        out.append('ok' if exempt else 'allowed')\n"
        "    except OfflineViolation:\n"
        "        out.append('refused')\n"
        "a, b = socket.socketpair(); a.sendall(b'x'); out.append(b.recv(1).decode())\n"
        "print(' '.join(out))\n"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=_env(), check=False)  # noqa: S603
    assert res.stdout.split() == ["refused", "ok", "refused", "x"], res.stderr[-2000:]


def test_the_scan_child_runs_under_the_guard(tmp_path):
    """BOOTSTRAP installs the guard before galaxyscope's code runs: the same bootstrap, pointed at a probe module."""
    (tmp_path / "probe_mod.py").write_text(_PROBE)
    code = offline.BOOTSTRAP.replace("gitgalaxy.galaxyscope", "probe_mod")
    assert code != offline.BOOTSTRAP
    env = dict(_env(), PYTHONPATH=os.pathsep.join([str(tmp_path), str(REPO)]))
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=False)  # noqa: S603
    assert res.stdout.split() == ["refused"] * 4 + ["ok"], res.stderr[-2000:]


def _spawned_probe(offline_flag):
    """Runs in a spawn-start worker: the real scan initializer, then a network attempt (#5235)."""
    import socket

    from gitgalaxy import galaxyscope

    try:
        galaxyscope._init_worker(str(REPO), {}, {}, 30, set(), set(), offline_flag)
    except Exception:  # noqa: BLE001 -- a bare config may not warm everything; the guard installs before any of it
        pass
    try:
        socket.create_connection(("127.0.0.1", 9), timeout=1)
    except offline.OfflineViolation:
        return "refused"
    except OSError:
        return "allowed"
    return "allowed"


@pytest.mark.parametrize(("flag", "expected"), [(True, "refused"), (False, "allowed")])
def test_a_spawn_start_scan_worker_runs_under_the_guard(flag, expected):
    """A spawn worker is a fresh interpreter: only `_init_worker(offline=True)` can install the guard there."""
    import concurrent.futures
    import multiprocessing

    with concurrent.futures.ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn")) as pool:
        assert pool.submit(_spawned_probe, flag).result(timeout=120) == expected


def test_the_scan_child_asks_its_workers_for_the_guard(monkeypatch, tmp_path):
    seen = {}

    def fake_run(argv, env=None, **_kw):
        seen["env"] = env
        raise RuntimeError("stop")

    monkeypatch.setattr(offline.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="stop"):
        offline.guarded_scan(tmp_path, tmp_path / "out")
    assert seen["env"][offline.OFFLINE_ENV] == "1"


# --- every burned estate, the command end to end ---------------------------------------------------------------------


_NIGHTLY = pytest.mark.skipif(
    not os.environ.get("GITGALAXY_NIGHTLY"), reason="nightly (~40 s, five estates): set GITGALAXY_NIGHTLY=1"
)
# --- #4726 slice 2: the ranked rules ---------------------------------------------------------------------------

# the shapes of real holes (CardDemo, CBSA, GenApp, DBB), each with a planted marker where the program's text sits
HOLES = {
    "line 191: EXEC EXEC SQL: no generated Db2 repository method for the statement at line 191": "EXEC SQL: no generated Db2 repository method",
    "line 9: EXEC EXEC CICS: no generated screen for map ZQXMAP": "EXEC CICS: no generated screen for map",
    "line 9: EXEC EXEC CICS: no generated DTO for COMMAREA ZQX-AREA": "EXEC CICS: no generated DTO for COMMAREA",
    "line 1: EXEC EXEC CICS: WRITE KEYLENGTH(ZQX-LEN): not a known length on a known file, so maybe not the full key": "EXEC CICS WRITE: key length not known",
    "line 1: EXEC EXEC CICS: EXEC CICS SOAPFAULT CREATE not modelled (web services are not)": "EXEC CICS SOAPFAULT CREATE: not modelled",
    "line 4: OPEN ZQX-FILE: the generated project has no batch package (CobolFiles) to run files through": "OPEN: no batch package",
    "line 7: CALL ZQXPROG: no program of that name with a CALL entry in the estate": "CALL: no program of that name",
    "line 8: MOVE ZQX-FIELD: no such item": "MOVE: no such item",
    "line 8: COMPUTE FUNCTION ANNUITY (IBM defines arg-1 but not the bits)": "COMPUTE",
    "line 3: ZQX-DATA ADDRESS OF ZQX-X: not an item of ZQX-Y or LINKAGE (not modelled)": "other",
    "line 3: EXEC EXEC CICS: ZQXVERB ZQXOPT(1): odd": "EXEC CICS",
}


@pytest.mark.parametrize("hole,expected", HOLES.items())
def test_a_hole_reduces_to_a_closed_gap_class(hole, expected):
    got = SC.gap_class(hole)
    assert got == expected
    assert MARK not in got and SC._rule_known(got)


def test_the_rules_rank_as_the_census_does():
    rows = [({"A"}, "1"), ({"A"}, "1"), ({"A"}, "none"), ({"B"}, "2"), ({"A", "B"}, "1"), ({"A", "B", "C"}, "1")]
    rules = SC.rules_to_land(rows)
    assert rules["classes"] == 3
    by = {r["rule"]: r for r in rules["ranked"]}
    assert (by["A"]["only"], by["A"]["one_away"], by["A"]["touched"]) == (3, 1, 5)
    assert by["A"]["only_by_era"] == {"1": 2, "none": 1}
    assert (by["B"]["only"], by["B"]["one_away"], by["B"]["touched"]) == (1, 1, 3)
    assert (by["C"]["only"], by["C"]["one_away"]) == (0, 0)
    assert [r["rule"] for r in rules["ranked"]] == ["A", "B", "C"]
    assert SC.rules_to_land([]) == {"classes": 0, "ranked": []}


def test_project_ranks_a_refusal_and_holes_by_class_never_by_text():
    inv = _inventory("zecs")
    progs = sorted(inv["eras"]["programs"])[:3]
    tr = {
        progs[0]: {"translation": "whole", "statements": 4, "translated_statements": 4, "holes": 0, "gap_classes": []},
        progs[1]: {
            "translation": "holes",
            "statements": 5,
            "translated_statements": 3,
            "holes": 2,
            "gap_classes": ["MOVE: no such item", "MOVE ZQX-A: no such item", "ZQX"],
        },
        progs[2]: {"translation": "refused", "refusal": "CopyNotFound"},
    }
    report = SC.project(inv, translation=tr)
    assert SC.validate(report) == []
    ranked = {r["rule"]: r for r in report["rules"]["ranked"]}
    # a class outside the closed set (what a later change to dryrun could let through) is not printed: it is `other`
    assert set(ranked) == {"MOVE: no such item", "other", "refused: CopyNotFound"}
    assert ranked["MOVE: no such item"]["only"] == 0 and ranked["MOVE: no such item"]["one_away"] == 1
    assert MARK not in json.dumps(report)
    assert "rules" not in SC.project(inv)  # no dry run, no rules


def test_validate_refuses_a_rule_off_the_closed_classes():
    report = SC.project(_inventory("zecs"), translation={})
    report["rules"] = {
        "classes": 1,
        "ranked": [{"rule": "MOVE: ZQX", "only": 1, "one_away": 0, "touched": 1, "only_by_era": {"1": 1}}],
    }
    assert any("closed gap class" in p for p in SC.validate(report))
    for bad in ("MOVE WS-PASSWORD", "EXEC CICS ZQXVERB", "refused: not a class!", "ZQX: not modelled"):
        report["rules"]["ranked"][0]["rule"] = bad
        assert any("closed gap class" in p for p in SC.validate(report)), bad
    report["rules"]["ranked"][0].update(rule="MOVE", only_by_era={"1": 2})
    assert any("only_by_era" in p for p in SC.validate(report))
    report["rules"]["ranked"][0].update(only_by_era={"1": 1}, source="x")
    assert any("entry shape" in p for p in SC.validate(report))


# zECS (3 s, and the one with assembler members refused by family) on every run; the rest nightly, beside
# test_feature_inventory_cli_check, which re-scans the same estates against the same fixtures
E2E = [e if e == "zecs" else pytest.param(e, marks=[pytest.mark.nightly, _NIGHTLY]) for e in BURNED]


@pytest.mark.slow(reason="#4726: a full engine scan of each burned estate (CBSA alone is 73 MB)")
@pytest.mark.parametrize("estate", E2E)
def test_assess_every_burned_estate(estate, tmp_path):
    """The real command on the real estate: exit 0, the estate unchanged, no source text, and the report equal to the
    projection of the committed inventory (the moved scan core and the guarded scan change nothing)."""
    estate_dir = CORPORA / estate
    if not estate_dir.is_dir():
        pytest.skip("no mainframe corpora (mainframe_corpus.py fetch)")
    before = _snapshot(estate_dir)
    out = tmp_path / "report.json"
    res = _assess(str(estate_dir), "--options", str(OPTIONS / f"{estate}.json"), "--out", str(out))
    assert res.returncode == 0, res.stderr[-3000:]
    report = json.loads(out.read_text())
    assert _snapshot(estate_dir) == before
    assert SC.validate(report) == []
    inv = _inventory(estate)
    assert _without_translation(report) == SC.project(inv, tool_version=report["tool_version"])
    assert report["totals"]["translation"]["whole"] > 0 or estate != "zecs"
    assert_no_source_text(report, estate_dir, _program_names(inv))
