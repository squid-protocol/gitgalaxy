"""#6262 (READPREV event): the key-form READPREV shapes, run on the Java leg and the C stub and held to one SPEC 6.2 log.

IBM (CICS TS 6.x, EXEC CICS READPREV, "Conditions"): right after STARTBR the STARTBR key must name a record (NOTFND RESP2
80 when it does not); a RIDFLD of X'FF's after STARTBR reads the last record; each READPREV with RIDFLD left as the last
read returns the previous record, ENDFILE RESP2 90 before the first; a READPREV after a READNEXT repositions to RIDFLD
and reads that record again; with no browse INVREQ RESP2 34. test_browse_events_6262 holds one READPREV (after a READNEXT)
to a SPEC log and test_cics_runtimes the rest as RESP only: this holds every shape to the event, key by key, on both legs.
"""

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402
import test_browse_events_6262 as java_leg  # noqa: E402
import test_browse_stub_events_6262 as stub_leg  # noqa: E402
import test_cics_runtimes as rt  # noqa: E402

REC = {"K001": "K001ALPHA   0010", "K002": "K002BRAVO   0020", "K003": "K003CHARL   0030"}
HV = "*"  # HIGH-VALUES: four X'FF' bytes

# op | key on entry | INTO length -> RESP/RESP2. S: STARTBR GTEQ, Q: STARTBR EQUAL, N: READNEXT, P: READPREV, X: ENDBR.
_OPS = (
    ("S", "K002", 16, "0/0"),
    ("P", "K002", 16, "0/0"),  # right after STARTBR: the STARTBR's record
    ("P", "K002", 16, "0/0"),  # RIDFLD as the last read left it: the previous record
    ("P", "K001", 16, "20/90"),  # before the first
    ("X", "K001", 16, "0/0"),
    ("S", "K000", 16, "0/0"),  # GTEQ positions on K001
    ("P", "K000", 16, "13/80"),  # right after STARTBR the key must exist
    ("X", "K000", 16, "0/0"),
    ("S", HV, 16, "0/0"),
    ("P", HV, 16, "0/0"),  # the last record
    ("P", "K003", 16, "0/0"),  # the one before
    ("P", "K002", 16, "0/0"),
    ("P", "K001", 16, "20/90"),
    ("X", "K001", 16, "0/0"),
    ("S", "K002", 16, "0/0"),
    ("N", "K002", 16, "0/0"),
    ("P", "K002", 16, "0/0"),  # after a READNEXT: K002 again
    ("N", "K002", 16, "0/0"),  # after a READPREV: repositions on RIDFLD, K002 again
    ("N", "K002", 16, "0/0"),  # K003
    ("P", "K001", 16, "0/0"),  # RIDFLD changed: repositions, reads K001
    ("X", "K001", 16, "0/0"),
    ("S", HV, 16, "0/0"),
    ("P", HV, 8, "22/11"),  # the record does not fit INTO
    ("X", HV, 16, "0/0"),
    ("P", "K001", 16, "16/34"),  # no browse
    ("Q", "K009", 16, "13/80"),
    ("P", "K009", 16, "16/34"),  # the STARTBR failed: still no browse
)


def _key(key: str) -> str:
    return (b"\xff" * 4).decode(cc.EBCDIC) if key == HV else key


def _ev(kind: str, key: str, **kv) -> dict:
    base = {"event": kind, "file": "HCBR"}
    if kind != "ENDBR":
        base["ridfld"] = _key(key)
    if kind == "STARTBR":
        base["mode"] = "GTEQ"
    return {**base, **kv}


def _got(kind: str, key: str, rec: str, **kv) -> dict:
    return _ev(kind, key, resp="NORMAL", length=16, data=java_leg._area(rec), **kv)


def _none(kind: str, key: str, resp: str, resp2: int, **kv) -> dict:
    return _ev(kind, key, resp=resp, resp2=resp2, data=None, **kv)


_EXPECTED = [
    _ev("STARTBR", "K002", resp="NORMAL"),
    _got("READPREV", "K002", REC["K002"]),
    _got("READPREV", "K002", REC["K001"]),
    _none("READPREV", "K001", "ENDFILE", 90),
    _ev("ENDBR", "", resp="NORMAL"),
    _ev("STARTBR", "K000", resp="NORMAL"),
    _none("READPREV", "K000", "NOTFND", 80),
    _ev("ENDBR", "", resp="NORMAL"),
    _ev("STARTBR", HV, resp="NORMAL"),
    _got("READPREV", HV, REC["K003"]),
    _got("READPREV", "K003", REC["K002"]),
    _got("READPREV", "K002", REC["K001"]),
    _none("READPREV", "K001", "ENDFILE", 90),
    _ev("ENDBR", "", resp="NORMAL"),
    _ev("STARTBR", "K002", resp="NORMAL"),
    _got("READNEXT", "K002", REC["K002"]),
    _got("READPREV", "K002", REC["K002"]),
    _got("READNEXT", "K002", REC["K002"]),
    _got("READNEXT", "K002", REC["K003"]),
    _got("READPREV", "K001", REC["K001"]),
    _ev("ENDBR", "", resp="NORMAL"),
    _ev("STARTBR", HV, resp="NORMAL"),
    _ev("READPREV", HV, resp="LENGERR", length=16, data=None),
    _ev("ENDBR", "", resp="NORMAL"),
    _none("READPREV", "K001", "INVREQ", 34),
    _ev("STARTBR", "K009", resp="NOTFND", resp2=80, mode="EQUAL"),
    _none("READPREV", "K009", "INVREQ", 34),
]


def _hex(key: str) -> str:
    return "ff" * 4 if key == HV else java_leg._hex(key)


def _run_java(tmp_path: Path) -> tuple[list[str], list[dict]]:
    seed = " ".join(f'f.put("{k}", hex.apply("{java_leg._hex(v)}"));' for k, v in REC.items())
    jkey = lambda k: "\\u00ff" * 4 if k == HV else k  # noqa: E731
    ops = ", ".join(f'{{"{op}", "{jkey(key)}", "{n}", "{_hex(key)}"}}' for op, key, n, _ in _OPS)
    java = java_leg._JAVA % {"seed": seed, "ops": ops, "k1": java_leg._hex("K001")}
    out = rt._cics_task(tmp_path, java).splitlines()
    import json

    return (
        [ln[2:] for ln in out if ln.startswith("R ")],
        [json.loads(ln[2:]) for ln in out if ln.startswith("E ")],
    )


def _verdict(expected: list[dict], actual: dict, caps) -> cc.Verdict:
    return cc.compare(java_leg._log(expected), actual, caps, cc.Context(layouts={}, map_fields={}))


@rt.needs_javac
def test_the_java_leg_records_every_readprev_shape(tmp_path):
    resps, raw = _run_java(tmp_path)
    assert resps == [w for *_, w in _OPS]
    assert len(raw) == len(_EXPECTED)
    v = _verdict(_EXPECTED, java_leg._actual(raw), runner.JAVA_CAPS)
    assert v.status == "pass", v.reason


@rt.needs_cc
def test_the_stub_records_every_readprev_shape(tmp_path):
    (tmp_path / "hcbr.dat").write_bytes(b"".join(r.encode("latin-1") for r in REC.values()))
    (tmp_path / "files.cfg").write_text(f"HCBR {tmp_path / 'hcbr.dat'} 16 0 4\n", encoding="ascii")
    main = stub_leg._MAIN.replace(
        "memcpy(rid, argv[i] + 2, 4);",
        "memcpy(rid, argv[i] + 2, 4);\n        if (argv[i][2] == '*') memset(rid, 0xFF, 4);",
    )
    ops = [f"{op}:{HV * 4 if key == HV else key}:{n:02d}" for op, key, n, _ in _OPS]
    rt._run_stub(rt._stub(tmp_path, main), tmp_path, *ops)
    events = runner._cobol_events(tmp_path / "out", "HCBR")
    assert len(events) == len(_EXPECTED)
    v = _verdict(_EXPECTED, java_leg._log(events), runner.COBOL_CAPS)
    assert v.status == "pass", v.reason


def _as_actual(e: dict) -> dict:
    """An expected event as a leg reports it: the key as EBCDIC bytes, the data as a raw area."""
    out = {**e}
    if isinstance(e.get("ridfld"), str):
        out["ridfld"] = e["ridfld"].encode(cc.EBCDIC)
    if e.get("data") is not None:
        out["data"] = cc.RawArea(e["data"]["text"].encode(cc.EBCDIC), cc.EBCDIC)
    return out


def test_the_readprev_keys_are_compared():
    actual = [_as_actual(e) for e in _EXPECTED]
    jc = runner.JAVA_CAPS
    assert _verdict(_EXPECTED, java_leg._log(actual), jc).status == "pass"
    for i, change in (
        (1, {"ridfld": "K003".encode(cc.EBCDIC)}),
        (1, {"data": cc.RawArea(REC["K001"].encode(cc.EBCDIC), cc.EBCDIC)}),
        (3, {"resp2": 80}),
        (6, {"resp": "ENDFILE", "resp2": 90}),
        (9, {"ridfld": "K003".encode(cc.EBCDIC)}),
        (22, {"length": 8}),
        (24, {"resp2": 35}),
    ):
        bad = [{**e, **change} if n == i else e for n, e in enumerate(actual)]
        assert _verdict(_EXPECTED, java_leg._log(bad), jc).status == "fail", (i, change)


def test_both_legs_support_the_readprev_events():
    log = java_leg._log(_EXPECTED)
    assert cc.blockers(log, runner.JAVA_CAPS) == []
    assert cc.blockers(log, runner.COBOL_CAPS) == []


def test_a_logged_high_values_key_stays_x_ff_and_text_goes_to_ebcdic():
    assert runner._key_ebcdic("ffffffff") == b"\xff" * 4
    assert runner._key_ebcdic("4b303031".upper()) == "K001".encode(cc.EBCDIC)
