"""#4443 (slice A0): the Java leg's READ / REWRITE / UNLOCK events (SPEC 6.2) and their comparison.

CicsTask.readInto / rewriteFrom / unlock record the events; read / readForUpdate / rewrite / unlockHeld, which every existing
port calls, record none (an equivalence proof compares a file as its final state, not as events). IBM (CICS TS 6.x, EXEC
CICS READ / REWRITE / UNLOCK): NOTFND RESP2 80; a record longer than INTO's LENGTH is LENGERR RESP2 11, LENGTH then the
record's; a REWRITE with no READ UPDATE before it INVREQ RESP2 30; a second READ UPDATE with nothing released INVREQ RESP2 28;
an UNLOCK with nothing held NORMAL. A LENGERR READ asserts its RESP only (SPEC section 2, Files).
"""

import base64
import json
import re
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


def _hex(text: str) -> str:
    return text.encode(E).hex()


# op | file key | INTO length -> the RESP / RESP2 the method returns. R: READ, U: READ UPDATE, W: REWRITE (FROM the
# key's record with 0099), L: UNLOCK, r / u / w / l: the event-free read / readForUpdate / rewrite / unlockHeld.
_OPS = (
    ("R", "K002", 8, "22/11"),  # LENGERR: the record is 16 bytes
    ("R", "K002", 16, "0/0"),
    ("R", "K009", 16, "13/80"),
    ("W", "K002", 16, "16/30"),  # nothing read for update
    ("L", "K002", 16, "0/0"),  # nothing held: NORMAL
    ("U", "K002", 16, "0/0"),
    ("U", "K001", 16, "16/28"),  # a second READ UPDATE, nothing released
    ("W", "K002", 16, "0/0"),
    ("R", "K002", 16, "0/0"),  # the rewritten record
    ("U", "K001", 16, "0/0"),
    ("L", "K001", 16, "0/0"),
    ("W", "K001", 16, "16/30"),  # the UNLOCK released it
    ("u", "K001", 16, "0/0"),
    ("r", "K001", 16, "0/0"),
    ("w", "K001", 16, "0/0"),
    ("l", "K001", 16, "0/0"),
    ("r", "K009", 16, "13/80"),
)

_JAVA = """
        java.util.function.Function<String, byte[]> hex = s -> java.util.HexFormat.of().parseHex(s);
        java.util.Map<String, byte[]> f = new java.util.HashMap<>();
        %(seed)s
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        String[][] ops = {%(ops)s};
        for (String[] p : ops) {
            String key = p[1];
            byte[] rid = hex.apply(p[3]);
            java.util.function.Supplier<java.util.Optional<byte[]>> look = () -> java.util.Optional.ofNullable(f.get(key));
            int n = Integer.parseInt(p[2]);
            byte[] from = hex.apply(p[4]);
            int resp;
            int resp2;
            switch (p[0]) {
                case "R", "U" -> {
                    CicsTask.FileRead<byte[]> r = t.readInto("HCUF", rid, p[0].equals("U"), n, look);
                    resp = r.resp();
                    resp2 = r.resp2();
                }
                case "r", "u" -> {
                    CicsTask.FileRead<byte[]> r = p[0].equals("u") ? t.readForUpdate("HCUF", look) : t.read("HCUF", look);
                    resp = r.resp();
                    resp2 = r.resp2();
                }
                case "W" -> {
                    resp = t.rewriteFrom("HCUF", from, () -> f.put(key, from));
                    resp2 = t.resp2();
                }
                case "w" -> {
                    resp = t.rewrite("HCUF", () -> f.put(key, from));
                    resp2 = t.resp2();
                }
                case "L" -> {
                    resp = t.unlock("HCUF");
                    resp2 = t.resp2();
                }
                default -> {
                    resp = t.unlockHeld("HCUF");
                    resp2 = t.resp2();
                }
            }
            System.out.println("R " + resp + "/" + resp2);
        }
        for (int[] bad : new int[][] {{1, 8}, {0, -1}}) {  // {update, LENGTH}: LENGERR on UPDATE; a negative LENGTH
            try {
                t.readInto("HCUF", hex.apply("%(k1)s"), bad[0] == 1, bad[1], () -> java.util.Optional.of(f.get("K001")));
                System.out.println("X read");
            } catch (UnsupportedOperationException e) {
                System.out.println("X refused " + e.getMessage());
            }
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


def _run(tmp_path: Path) -> tuple[list[str], list[str], list[dict]]:
    seed = " ".join(f'f.put("{k}", hex.apply("{_hex(v)}"));' for k, v in REC.items())
    ops = ", ".join(
        f'{{"{op}", "{key}", "{n}", "{_hex(key)}", "{_hex(REC.get(key, key.ljust(16))[:12] + "0099")}"}}'
        for op, key, n, _ in _OPS
    )
    out = _cics_task(tmp_path, _JAVA % {"seed": seed, "ops": ops, "k1": _hex("K001")}).splitlines()
    return (
        [ln[2:] for ln in out if ln.startswith("R ")],
        [ln[2:] for ln in out if ln.startswith("X ")],
        [json.loads(ln[2:]) for ln in out if ln.startswith("E ")],
    )


def _area(text: str | None) -> dict | None:
    return None if text is None else {"length": len(text), "text": text}


# the SPEC 6.2 events the recording ops above must give, in order (the event-free ops give none)
_EXPECTED = [
    {"event": "READ", "file": "HCUF", "ridfld": "K002", "resp": "LENGERR", "length": 16, "data": None},
    {"event": "READ", "file": "HCUF", "ridfld": "K002", "resp": "NORMAL", "length": 16, "data": _area(REC["K002"])},
    {"event": "READ", "file": "HCUF", "ridfld": "K009", "resp": "NOTFND", "resp2": 80, "data": None},
    {"event": "REWRITE", "file": "HCUF", "data": _area("K002BRAVO   0099"), "resp": "INVREQ", "resp2": 30},
    {"event": "UNLOCK", "file": "HCUF", "resp": "NORMAL"},
    {
        "event": "READ",
        "file": "HCUF",
        "ridfld": "K002",
        "update": True,
        "resp": "NORMAL",
        "length": 16,
        "data": _area(REC["K002"]),
    },
    {"event": "READ", "file": "HCUF", "ridfld": "K001", "update": True, "resp": "INVREQ", "resp2": 28, "data": None},
    {"event": "REWRITE", "file": "HCUF", "data": _area("K002BRAVO   0099"), "resp": "NORMAL"},
    {
        "event": "READ",
        "file": "HCUF",
        "ridfld": "K002",
        "resp": "NORMAL",
        "length": 16,
        "data": _area("K002BRAVO   0099"),
    },
    {
        "event": "READ",
        "file": "HCUF",
        "ridfld": "K001",
        "update": True,
        "resp": "NORMAL",
        "length": 16,
        "data": _area(REC["K001"]),
    },
    {"event": "UNLOCK", "file": "HCUF", "resp": "NORMAL"},
    {"event": "REWRITE", "file": "HCUF", "data": _area("K001ALPHA   0099"), "resp": "INVREQ", "resp2": 30},
]


def _task(events: list[dict]) -> dict:
    return {
        "seq": 1,
        "transid": "HC81",
        "program": "HCUNLK",
        "termid": "T001",
        "at": "2026-03-02T10:00:00",
        "trigger": {"kind": "terminal", "step": 0},
        "eibaid": "ENTER",
        "eibcalen": 0,
        "commarea": None,
        "events": events,
        "end": "normal",
    }


def _log(events: list[dict]) -> dict:
    return {"tasks": [_task(events)], "final": {}}


def _actual(raw: list[dict]) -> dict:
    return _log([{"event": e["event"], "program": "HCUNLK", **runner._java_file_event(e["event"], e)} for e in raw])


def _verdict(expected: list[dict], actual: dict, caps: cc.Capabilities = runner.JAVA_CAPS) -> cc.Verdict:
    exp = _log([{**e, "program": "HCUNLK"} for e in expected])
    return cc.compare(exp, actual, caps, cc.Context(layouts={}, map_fields={}))


@needs_javac
def test_cics_task_records_read_rewrite_unlock_as_spec_events_and_the_old_methods_none(tmp_path):
    resps, refused, raw = _run(tmp_path)
    assert resps == [w for *_, w in _OPS]
    assert refused == [
        "refused READ UPDATE LENGERR (whether the record is held): not modelled",
        "refused READ LENGTH -1 (negative): not modelled",
    ]
    # the LENGERR READ carries IBM's RESP2 11; the log leaves it out (SPEC section 2), as _java_file_event does
    assert raw[0]["resp2"] == 11 and raw[0]["data"] is None and raw[0]["length"] == 16
    assert raw[2]["length"] is None and raw[0]["update"] is None
    assert len(raw) == len(_EXPECTED)  # the event-free methods recorded nothing
    v = _verdict(_EXPECTED, _actual(raw))
    assert v.status == "pass", v.reason


def _b64(text: str) -> str:
    return base64.b64encode(text.encode(E)).decode()


def _raw(**kv) -> dict:
    return {
        "event": "READ",
        "file": "HCUF",
        "ridfld": _b64("K002"),
        "update": None,
        "resp": "NORMAL",
        "resp2": None,
        "length": 16,
        "data": _b64(REC["K002"]),
        **kv,
    }


def test_the_java_mapping_keeps_only_the_keys_the_command_carries():
    ev = runner._java_file_event("READ", _raw())
    assert ev["ridfld"] == "K002".encode(E) and ev["length"] == 16 and ev["data"].data == REC["K002"].encode(E)
    assert "update" not in ev and "resp2" not in ev
    assert runner._java_file_event("READ", _raw(update=True))["update"] is True
    assert "resp2" not in runner._java_file_event("READ", _raw(resp="LENGERR", resp2=11, data=None))
    nf = runner._java_file_event("READ", _raw(resp="NOTFND", resp2=80, length=None, data=None))
    assert nf["resp2"] == 80 and "length" not in nf and nf["data"] is None
    assert runner._java_file_event("UNLOCK", {"file": "HCUF", "resp": "NORMAL", "resp2": None}) == {
        "file": "HCUF",
        "resp": "NORMAL",
    }
    rw = runner._java_file_event("REWRITE", {"file": "HCUF", "data": None, "resp": "INVREQ", "resp2": 30})
    assert rw == {"file": "HCUF", "resp": "INVREQ", "data": None, "resp2": 30}


def _one(expected: dict, raw: dict) -> cc.Verdict:
    return _verdict([expected], _actual([raw]))


_READ = {"event": "READ", "file": "HCUF", "ridfld": "K002", "resp": "NORMAL", "length": 16, "data": _area(REC["K002"])}


def test_every_read_key_is_compared():
    assert _one(_READ, _raw()).status == "pass"
    for bad, kind in (
        ({"length": 8}, "length differs"),
        ({"ridfld": _b64("K001")}, "ridfld differs"),
        ({"resp": "NOTFND", "resp2": 80}, "resp differs"),
        ({"update": True}, "update unexpected"),
        ({"file": "OTHER"}, "file differs"),
    ):
        v = _one(_READ, _raw(**bad))
        assert (v.status, v.kind) == ("fail", f"{kind}" if "unexpected" not in kind else f"READ {kind}"), (bad, v)
    other = _b64("K002BRAVO   0099")
    assert _one(_READ, _raw(data=other)).status == "fail"
    assert _one({**_READ, "update": True}, _raw()).status == "fail"  # an UPDATE the side did not record
    nf = {"event": "READ", "file": "HCUF", "ridfld": "K002", "resp": "NOTFND", "resp2": 80, "data": None}
    assert _one(nf, _raw(resp="NOTFND", resp2=80, length=None, data=None)).status == "pass"
    assert _one(nf, _raw(resp="NOTFND", resp2=81, length=None, data=None)).status == "fail"
    assert (
        _one(nf, _raw(resp="NOTFND", resp2=80, length=16, data=None)).status == "fail"
    )  # a LENGTH NOTFND does not set


def test_rewrite_and_unlock_keys_are_compared():
    rw = {"event": "REWRITE", "file": "HCUF", "data": _area("K002BRAVO   0099"), "resp": "INVREQ", "resp2": 30}
    data = _b64("K002BRAVO   0099")
    raw = {"event": "REWRITE", "file": "HCUF", "data": data, "resp": "INVREQ", "resp2": 30}
    assert _one(rw, raw).status == "pass"
    assert _one(rw, {**raw, "resp2": 31}).status == "fail"
    assert _one(rw, {**raw, "data": _b64(" " * 16)}).status == "fail"
    ul = {"event": "UNLOCK", "file": "HCUF", "resp": "NORMAL"}
    assert _one(ul, {"event": "UNLOCK", "file": "HCUF", "resp": "NORMAL", "resp2": None}).status == "pass"
    assert _one(ul, {"event": "UNLOCK", "file": "HCUF", "resp": "INVREQ", "resp2": 47}).status == "fail"


def test_what_each_side_does_not_record_stays_unsupported():
    read_set = {**_READ, "set": True}
    del read_set["length"]
    assert "CicsTask: READ set" in cc.blockers(_log([{**read_set, "program": "HCUNLK"}]), runner.JAVA_CAPS)
    assert cc.blockers(_log([{**e, "program": "HCUNLK"} for e in _EXPECTED]), runner.JAVA_CAPS) == []
    # the stub (ggcics.c) records READ's file, key and RESP only, and no REWRITE or UNLOCK (#4443 slice A0b)
    stub = cc.blockers(_log([{**e, "program": "HCUNLK"} for e in _EXPECTED]), runner.COBOL_CAPS)
    assert stub == [
        "stub: READ length",
        "stub: READ data",
        "stub: READ resp2",
        "stub: REWRITE event",
        "stub: UNLOCK event",
        "stub: READ update",
    ]
    v = _verdict(
        [_READ],
        _log([{"event": "READ", "program": "HCUNLK", "file": "HCUF", "ridfld": "K002".encode(E), "resp": "NORMAL"}]),
        runner.COBOL_CAPS,
    )
    assert v.status == "unsupported" and "stub: READ length" in v.features


def test_the_forge_cics_task_holds_the_recording_methods():
    from gitgalaxy.tools.cobol_to_java import cics_task_filecontrol as tf

    for method in ("readInto", "rewriteFrom", "unlock"):
        assert re.search(rf"public \S+(?: \S+)? {method}\(", tf.FILECONTROL_JAVA), method
