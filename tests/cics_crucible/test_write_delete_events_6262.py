"""#6262 (slice D): the Java leg's WRITE / DELETE events (SPEC 6.2 shape proposed here; the stub half is test_write_delete_stub_events_6262.py).

CicsTask.writeEvent / deleteEvent / deleteGenericEvent / deleteInvalidEvent / deleteHeldEvent / deleteTokenEvent record the
events; write / delete* , which every existing port calls, record none. IBM (CICS TS 6.x, EXEC CICS WRITE / DELETE): WRITE of
a key already there is DUPREC (no RESP2 stated); DELETE of a key that is not there is NOTFND RESP2 80; DELETE without RIDFLD
and no READ UPDATE before it is INVREQ RESP2 31; a generic DELETE whose KEYLENGTH is not shorter than the key is INVREQ RESP2
25; a planned NOTOPEN (RESP2 60) writes nothing. A DELETE of the held or the token's record has no RIDFLD, so no `ridfld`.
"""

import json
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402
import equivalence_cics as ec  # noqa: E402
import test_browse_events_6262 as java_leg  # noqa: E402
import test_cics_runtimes as rt  # noqa: E402

REC = java_leg.REC
NEW = {"K003": "K003CHARLIE 0030", "K004": "K004DELTA   0040", "K005": "K005ECHO    0050"}

# op (W WRITE, D DELETE, G DELETE GENERIC, I DELETE GENERIC KEYLENGTH 4 on a 4-byte key, H DELETE of the held record,
# U READ UPDATE (no event), K DELETE TOKEN of the record READ UPDATE TOKEN held) | key -> RESP/RESP2
_OPS = (
    ("W", "K003", "0/0"),
    ("W", "K003", "14/0"),  # DUPREC
    ("W", "K004", "19/60"),  # the planned NOTOPEN: nothing is written
    ("W", "K005", "0/0"),
    ("D", "K003", "0/0"),
    ("D", "K003", "13/80"),  # NOTFND
    ("G", "K001", "0/0"),
    ("I", "K002", "16/25"),
    ("H", "K002", "16/31"),  # nothing held
    ("U", "K002", "0/0"),
    ("H", "K002", "0/0"),
    ("U", "K005", "0/0"),  # held under a token
    ("K", "K005", "0/0"),
)
_PLAN = ec.fault_lines({"name": "s", "faults": [{"cmd": "WRITE", "file": "HCBR", "nth": 3, "resp": "NOTOPEN"}]})


def _w(key: str, **kv) -> dict:
    return {"event": "WRITE", "file": "HCBR", "ridfld": key, "data": java_leg._area(NEW.get(key)), **kv}


def _d(key: str | None, **kv) -> dict:
    return {"event": "DELETE", "file": "HCBR", **({} if key is None else {"ridfld": key}), **kv}


_EXPECTED = [
    _w("K003", resp="NORMAL"),
    _w("K003", resp="DUPREC"),
    _w("K004", resp="NOTOPEN", resp2=60),
    _w("K005", resp="NORMAL"),
    _d("K003", resp="NORMAL"),
    _d("K003", resp="NOTFND", resp2=80),
    _d("K001", generic=True, resp="NORMAL"),
    _d("K002", generic=True, resp="INVREQ", resp2=25),
    _d(None, resp="INVREQ", resp2=31),
    _d(None, resp="NORMAL"),
    _d(None, resp="NORMAL"),
]
_CTX = cc.Context(layouts={}, map_fields={})


def _verdict(actual: list[dict], expected: list[dict] | None = None) -> cc.Verdict:
    return cc.compare(java_leg._log(expected or _EXPECTED), java_leg._log(actual), runner.JAVA_CAPS, _CTX)


def _java(ops: str, seed: str, lines: str) -> str:
    return f"""
        java.util.function.Function<String, byte[]> hex = s -> java.util.HexFormat.of().parseHex(s);
        java.util.Map<String, byte[]> f = new java.util.TreeMap<>();
        {seed}
        CicsTask t = new CicsTask("T", "ENTER", null, null).withFaults(java.util.List.of({lines}), null);
        String[][] ops = {{{ops}}};
        int token = 0;
        for (String[] p : ops) {{
            String key = p[1];
            byte[] rid = hex.apply(p[2]);
            byte[] rec = hex.apply(p[3]);
            boolean there = f.containsKey(key);
            int resp = 0;
            switch (p[0]) {{
                case "W" -> resp = t.writeEvent("HCBR", rid, rec, there, () -> f.put(key, rec));
                case "D" -> resp = t.deleteEvent("HCBR", rid, there, () -> f.remove(key));
                case "G" -> resp = t.deleteGenericEvent("HCBR", rid, there, () -> f.remove(key));
                case "I" -> resp = t.deleteInvalidEvent("HCBR", rid, true, 25);
                case "H" -> resp = t.deleteHeldEvent("HCBR", () -> f.remove(key));
                case "U" -> {{
                    if (p[1].equals("K005")) token = t.holdToken("HCBR", rid);
                    else t.readForUpdate("HCBR", () -> java.util.Optional.ofNullable(f.get(key)));
                }}
                case "K" -> resp = t.deleteTokenEvent("HCBR", token, k -> f.remove(key));
                default -> throw new IllegalStateException(p[0]);
            }}
            System.out.println("R " + resp + "/" + t.resp2());
        }}
        System.out.println("F " + String.join(",", f.keySet()));
        int before = t.events().size();
        t.write("HCBR", false, () -> {{}});  // the event-free methods every port calls record nothing
        t.delete("HCBR", true, () -> {{}});
        t.deleteGeneric("HCBR", true, () -> {{}});
        t.deleteHeld("HCBR", () -> {{}});
        System.out.println("N " + (t.events().size() - before));
        for (java.util.Map<String, Object> e : t.events()) {{
            StringBuilder b = new StringBuilder("E {{");
            String sep = "";
            for (java.util.Map.Entry<String, Object> kv : e.entrySet()) {{
                Object v = kv.getValue();
                String s = v == null ? "null" : v instanceof byte[] d ? "\\"" + java.util.Base64.getEncoder().encodeToString(d) + "\\""
                        : v instanceof String str ? "\\"" + str + "\\"" : String.valueOf(v);
                b.append(sep).append("\\"").append(kv.getKey()).append("\\":").append(s);
                sep = ",";
            }}
            System.out.println(b.append("}}"));
        }}"""


@rt.needs_javac
def test_cics_task_records_each_write_and_delete_form_as_a_spec_event(tmp_path):
    seed = " ".join(f'f.put("{k}", hex.apply("{java_leg._hex(v)}"));' for k, v in REC.items())
    rows = []
    for op, key, _ in _OPS:
        text = NEW.get(key, REC.get(key, ""))
        rows.append(f'{{"{op}", "{key}", "{java_leg._hex(key)}", "{java_leg._hex(text)}"}}')
    lines = ", ".join(f'"{ln}"' for ln in _PLAN)
    out = rt._cics_task(tmp_path, _java(", ".join(rows), seed, lines)).splitlines()
    got = [ln[2:] for ln in out if ln.startswith("R ")]
    assert [g for g, (op, _, _w) in zip(got, _OPS, strict=True) if op != "U"] == [w for op, _, w in _OPS if op != "U"]
    assert next(ln for ln in out if ln.startswith("F ")) == "F "  # every record was written then deleted
    assert next(ln for ln in out if ln.startswith("N ")) == "N 0"
    raw = [json.loads(ln[2:]) for ln in out if ln.startswith("E ")]
    assert len(raw) == len(_EXPECTED)
    actual = [{"event": e["event"], **runner._java_file_event(e["event"], e)} for e in raw]
    v = _verdict(actual)
    assert v.status == "pass", v.reason


def _as_run(events: list[dict]) -> list[dict]:
    """An expected log as the actual side holds it: ridfld as EBCDIC bytes, data as an area."""
    out = []
    for e in events:
        e = dict(e)
        if "ridfld" in e:
            e["ridfld"] = e["ridfld"].encode(cc.EBCDIC)
        if e.get("data"):
            e["data"] = cc.RawArea(e["data"]["text"].encode(cc.EBCDIC), cc.EBCDIC)
        out.append(e)
    return out


def test_every_write_and_delete_key_is_compared():
    actual = _as_run(_EXPECTED)
    assert _verdict(actual).status == "pass"
    for i, key, bad in (
        (0, "data", cc.RawArea(NEW["K004"].encode(cc.EBCDIC), cc.EBCDIC)),
        (0, "ridfld", "K999".encode(cc.EBCDIC)),
        (1, "resp", "NORMAL"),
        (2, "resp2", 61),
        (6, "generic", None),
        (8, "resp2", 30),
    ):
        changed = [dict(e) for e in actual]
        if bad is None:
            del changed[i][key]
        else:
            changed[i][key] = bad
        assert _verdict(changed).status == "fail", (i, key)
    with_key = [dict(e) for e in actual]
    with_key[9]["ridfld"] = "K002".encode(cc.EBCDIC)  # a held-record DELETE has no RIDFLD
    assert _verdict(with_key).status == "fail"


def test_both_legs_support_the_write_and_delete_events():
    log = java_leg._log(_EXPECTED)
    assert cc.blockers(log, runner.JAVA_CAPS) == []
    assert cc.blockers(log, runner.COBOL_CAPS) == []
