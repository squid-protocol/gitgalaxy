"""#6262 (slice B): the Java leg's STARTBR / READNEXT / READPREV / ENDBR events (SPEC 6.2) and their comparison.

CicsTask.startbrEvent / readnextInto / readprevInto / endbrEvent record the events; startbr / readnext / readprev / endbr,
which every existing port calls, record none. IBM (CICS TS 6.x, EXEC CICS STARTBR / READNEXT / READPREV / ENDBR): a second
STARTBR on a file INVREQ RESP2 33; NOTFND RESP2 80 for a STARTBR EQUAL with no such key; ENDFILE RESP2 90 past the last
record; READNEXT / READPREV with no browse INVREQ RESP2 34; ENDBR with none INVREQ RESP2 35. A LENGERR read asserts its
RESP only (SPEC section 2, Files).
"""

import base64
import json
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402
from test_cics_runtimes import _cics_task, needs_javac  # noqa: E402

E = cc.EBCDIC
REC = {"K001": "K001ALPHA   0010", "K002": "K002BRAVO   0020"}

# op | key on entry | INTO length -> RESP/RESP2. S: STARTBR GTEQ, Q: STARTBR EQUAL, N: READNEXT, P: READPREV, X: ENDBR;
# s / n / p / x: the event-free startbr / readnext / readprev / endbr.
_OPS = (
    ("S", "K001", 16, "0/0"),
    ("S", "K001", 16, "16/33"),  # a browse is active
    ("N", "K001", 16, "0/0"),  # the record STARTBR positioned on
    ("N", "K001", 16, "0/0"),  # the next one
    ("N", "K002", 16, "20/90"),  # past the last
    ("P", "K002", 16, "0/0"),  # reads K002 again
    ("N", "K002", 8, "22/11"),  # the record does not fit INTO
    ("X", "K001", 16, "0/0"),
    ("X", "K001", 16, "16/35"),  # no browse
    ("N", "K001", 16, "16/34"),  # no browse
    ("Q", "K009", 16, "13/80"),
    ("S", "K000", 16, "0/0"),  # GTEQ, no such key: positions on the first greater one, RIDFLD stays as given
    ("X", "K000", 16, "0/0"),
    ("S", "K999", 16, "13/80"),  # GTEQ past the last key
    ("Q", "K002", 16, "0/0"),  # EQUAL on a present key
    ("X", "K002", 16, "0/0"),
    ("s", "K001", 16, "0/0"),
    ("n", "K001", 16, "0/0"),
    ("p", "K001", 16, "0/0"),
    ("x", "K001", 16, "0/0"),
)

_JAVA = """
        java.util.function.Function<String, byte[]> hex = s -> java.util.HexFormat.of().parseHex(s);
        java.util.Map<String, byte[]> f = new java.util.TreeMap<>();
        %(seed)s
        java.util.function.Supplier<java.util.NavigableSet<String>> keys = () -> new java.util.TreeSet<>(f.keySet());
        java.util.function.Function<String, java.util.Optional<byte[]>> look = k -> java.util.Optional.ofNullable(f.get(k));
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        String[][] ops = {%(ops)s};
        for (String[] p : ops) {
            byte[] rid = hex.apply(p[3]);
            int n = Integer.parseInt(p[2]);
            int resp;
            int resp2;
            switch (p[0]) {
                case "S", "Q" -> {
                    resp = t.startbrEvent("HCBR", rid, p[1], p[0].equals("Q"), keys);
                    resp2 = t.resp2();
                }
                case "N", "P" -> {
                    CicsTask.Browsed b = p[0].equals("N") ? t.readnextInto("HCBR", rid, p[1], n, look)
                            : t.readprevInto("HCBR", rid, p[1], n, look);
                    resp = b.resp();
                    resp2 = b.resp2();
                }
                case "X" -> {
                    resp = t.endbrEvent("HCBR");
                    resp2 = t.resp2();
                }
                case "s" -> {
                    resp = t.startbr("HCBR", p[1], false, keys);
                    resp2 = t.resp2();
                }
                case "n", "p" -> {
                    CicsTask.Browsed b = p[0].equals("n") ? t.readnext("HCBR", p[1]) : t.readprev("HCBR", p[1]);
                    resp = b.resp();
                    resp2 = b.resp2();
                }
                default -> {
                    resp = t.endbr("HCBR");
                    resp2 = t.resp2();
                }
            }
            System.out.println("R " + resp + "/" + resp2);
        }
        try {
            t.readnextInto("HCBR", hex.apply("%(k1)s"), "K001", -1, look);
            System.out.println("X read");
        } catch (UnsupportedOperationException e) {
            System.out.println("X refused " + e.getMessage());
        }
        for (java.util.Map<String, Object> e : t.events()) {
            StringBuilder b = new StringBuilder("E {");
            String sep = "";
            for (java.util.Map.Entry<String, Object> kv : e.entrySet()) {
                Object v = kv.getValue();
                String s = v == null ? "null" : v instanceof byte[] d ? "\\"" + java.util.Base64.getEncoder().encodeToString(d) + "\\""
                        : v instanceof String str ? "\\"" + str + "\\"" : String.valueOf(v);
                b.append(sep).append("\\"").append(kv.getKey()).append("\\":").append(s);
                sep = ",";
            }
            System.out.println(b.append("}"));
        }"""


def _hex(text: str) -> str:
    return text.encode(E).hex()


def _run(tmp_path: Path) -> tuple[list[str], list[str], list[dict]]:
    seed = " ".join(f'f.put("{k}", hex.apply("{_hex(v)}"));' for k, v in REC.items())
    ops = ", ".join(f'{{"{op}", "{key}", "{n}", "{_hex(key)}"}}' for op, key, n, _ in _OPS)
    out = _cics_task(tmp_path, _JAVA % {"seed": seed, "ops": ops, "k1": _hex("K001")}).splitlines()
    return (
        [ln[2:] for ln in out if ln.startswith("R ")],
        [ln[2:] for ln in out if ln.startswith("X ")],
        [json.loads(ln[2:]) for ln in out if ln.startswith("E ")],
    )


def _area(text: str | None) -> dict | None:
    return None if text is None else {"length": len(text), "text": text}


def _rd(kind: str, key: str, text: str | None, **kv) -> dict:
    return {"event": kind, "file": "HCBR", "ridfld": key, "resp": "NORMAL", "length": 16, "data": _area(text), **kv}


_EXPECTED = [
    {"event": "STARTBR", "file": "HCBR", "ridfld": "K001", "mode": "GTEQ", "resp": "NORMAL"},
    {"event": "STARTBR", "file": "HCBR", "ridfld": "K001", "mode": "GTEQ", "resp": "INVREQ", "resp2": 33},
    _rd("READNEXT", "K001", REC["K001"]),
    _rd("READNEXT", "K001", REC["K002"]),
    {"event": "READNEXT", "file": "HCBR", "ridfld": "K002", "resp": "ENDFILE", "resp2": 90, "data": None},
    _rd("READPREV", "K002", REC["K002"]),
    {"event": "READNEXT", "file": "HCBR", "ridfld": "K002", "resp": "LENGERR", "length": 16, "data": None},
    {"event": "ENDBR", "file": "HCBR", "resp": "NORMAL"},
    {"event": "ENDBR", "file": "HCBR", "resp": "INVREQ", "resp2": 35},
    {"event": "READNEXT", "file": "HCBR", "ridfld": "K001", "resp": "INVREQ", "resp2": 34, "data": None},
    {"event": "STARTBR", "file": "HCBR", "ridfld": "K009", "mode": "EQUAL", "resp": "NOTFND", "resp2": 80},
    {"event": "STARTBR", "file": "HCBR", "ridfld": "K000", "mode": "GTEQ", "resp": "NORMAL"},
    {"event": "ENDBR", "file": "HCBR", "resp": "NORMAL"},
    {"event": "STARTBR", "file": "HCBR", "ridfld": "K999", "mode": "GTEQ", "resp": "NOTFND", "resp2": 80},
    {"event": "STARTBR", "file": "HCBR", "ridfld": "K002", "mode": "EQUAL", "resp": "NORMAL"},
    {"event": "ENDBR", "file": "HCBR", "resp": "NORMAL"},
]


def _log(events: list[dict]) -> dict:
    task = {
        "seq": 1,
        "transid": "HC82",
        "program": "HCBR",
        "termid": "T001",
        "at": "2026-03-02T10:00:00",
        "trigger": {"kind": "terminal", "step": 0},
        "eibaid": "ENTER",
        "eibcalen": 0,
        "commarea": None,
        "events": [{**e, "program": "HCBR"} for e in events],
        "end": "normal",
    }
    return {"tasks": [task], "final": {}}


def _actual(raw: list[dict]) -> dict:
    return _log([{"event": e["event"], **runner._java_file_event(e["event"], e)} for e in raw])


def _verdict(expected: list[dict], actual: dict) -> cc.Verdict:
    return cc.compare(_log(expected), actual, runner.JAVA_CAPS, cc.Context(layouts={}, map_fields={}))


@needs_javac
def test_cics_task_records_browse_commands_as_spec_events_and_the_old_methods_none(tmp_path):
    resps, refused, raw = _run(tmp_path)
    assert resps == [w for *_, w in _OPS]
    assert refused == ["refused READNEXT LENGTH -1 (negative): not modelled"]
    assert len(raw) == len(_EXPECTED)  # the event-free methods recorded nothing
    assert raw[6]["resp2"] == 11 and raw[6]["data"] is None  # the log leaves a LENGERR's RESP2 out, as READ's
    v = _verdict(_EXPECTED, _actual(raw))
    assert v.status == "pass", v.reason


def _b64(text: str) -> str:
    return base64.b64encode(text.encode(E)).decode()


def _raw(kind: str, **kv) -> dict:
    base = {"event": kind, "file": "HCBR", "ridfld": _b64("K001"), "resp": "NORMAL", "resp2": None}
    if kind == "STARTBR":
        base["mode"] = "GTEQ"
    elif kind != "ENDBR":
        base.update(length=16, data=_b64(REC["K001"]))
    return {**base, **kv}


def test_the_java_mapping_keeps_only_the_keys_the_command_carries():
    sb = runner._java_file_event("STARTBR", _raw("STARTBR"))
    assert sb == {"file": "HCBR", "resp": "NORMAL", "ridfld": "K001".encode(E), "mode": "GTEQ"}
    rn = runner._java_file_event("READNEXT", _raw("READNEXT"))
    assert rn["length"] == 16 and rn["data"].data == REC["K001"].encode(E) and "resp2" not in rn
    for kind in ("READNEXT", "READPREV"):
        assert "resp2" not in runner._java_file_event(kind, _raw(kind, resp="LENGERR", resp2=11, data=None))
        eof = runner._java_file_event(kind, _raw(kind, resp="ENDFILE", resp2=90, length=None, data=None))
        assert eof["resp2"] == 90 and "length" not in eof and eof["data"] is None
    assert runner._java_file_event("ENDBR", _raw("ENDBR")) == {"file": "HCBR", "resp": "NORMAL"}


def test_every_browse_key_is_compared():
    for kind, exp in (("STARTBR", _EXPECTED[0]), ("READNEXT", _EXPECTED[2]), ("ENDBR", _EXPECTED[7])):
        assert _verdict([exp], _actual([_raw(kind)])).status == "pass", kind
    start, nxt = _EXPECTED[0], _EXPECTED[2]
    assert _verdict([start], _actual([_raw("STARTBR", mode="EQUAL")])).status == "fail"
    assert _verdict([start], _actual([_raw("STARTBR", ridfld=_b64("K002"))])).status == "fail"
    assert _verdict([nxt], _actual([_raw("READNEXT", length=8)])).status == "fail"
    assert _verdict([nxt], _actual([_raw("READNEXT", data=_b64(REC["K002"]))])).status == "fail"
    assert _verdict([nxt], _actual([_raw("READNEXT", resp="ENDFILE", resp2=90)])).status == "fail"
    assert _verdict([_EXPECTED[7]], _actual([_raw("ENDBR", resp="INVREQ", resp2=35)])).status == "fail"


def test_the_java_leg_supports_the_browse_events():
    assert cc.blockers(_log(_EXPECTED), runner.JAVA_CAPS) == []  # the stub's half: test_browse_stub_events_6262.py
