"""
#3989: the pure half of the CICS crucible runner (tests/tools/cics_crucible.py) -- reading a
cics-crucible case (format `cics-crucible/1`, the crucible's SPEC.md) and comparing an actual
event log against the case's hand-written expected log, exactly as SPEC section 6 defines it.
Standard library only (plus equivalence_common for numeric decoding), so it is tested without
GnuCOBOL, Docker or Maven (tests/cics_crucible/test_cics_crucible_runner.py).

An *actual* log is shaped like an expected one -- `{"tasks": [{transid, program, ..., events,
end}], "final": {...}}` -- and is produced by one side of the harness: the COBOL program on the
stub runtime, or the generated Java through CicsTask. A side records only what it models, and
says so through its `Capabilities`: which task keys, which event types and which keys of each.
The comparison walks the expected log in order and stops at the first point that decides it:

* a modelled value that differs, a missing or extra event, a missing or extra task -> `fail`,
  with that first divergence;
* an expected event type or key the side does not model (or a value it marks `Unmodelled`)
  -> `unsupported`, naming the feature -- the harness cannot say either way;
* the end of the log with everything equal -> `pass`.

So a stub that records nothing fails at its first missing event, unless that event is one the
side cannot record at all, in which case the cell is honestly unsupported. Every verdict also
carries the full set of features the scenario needs that the side lacks (`blockers`), which is
what the report counts: how many cells each harness feature would unlock.

Values follow SPEC 6.1 exactly: text is EBCDIC (CCSID 037), right-padded with X'40' to the
area's known length (trailing blanks optional, embedded ones not); hex is exact bytes; a numeric
field is compared as a number. Areas are compared on their bytes: a side that holds real bytes
hands them over as a `RawArea` in its runtime's code page, transcoded here field by field
(DISPLAY fields through the page, COMP / COMP-3 bytes as they are); the Java side hands over
field values (`FieldArea`) with the length CicsTask recorded beside the DTO (#4009), or FULL when
the program passed it without a LENGTH: then it is its layout's whole record.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

CASE_FORMAT = "cics-crucible/case/1"
EXPECTED_FORMAT = "cics-crucible/expected/1"
EBCDIC = "cp037"  # SPEC section 2: every byte in every area is CCSID 037
# `java` runs the services as generated (the unported skeletons); `java-ported` lays each case's committed
# ports (tests/cics_crucible/ports/<case>/<PROGRAM>/, the porting loop's proven overlays) over them first.
# `java-facade` (#4343) runs that ported project again, each task entered through the program's deployed entry point
# (its Spring facade: handleTransaction, handleLink) rather than runTask.
SIDES = ("engine-facts", "forge-compile", "cobol-stub", "java", "java-ported", "java-facade")
CASE_SIDES = ("engine-facts", "forge-compile")  # one cell per case, scenario "*"
TASK_KEYS = ("transid", "program", "termid", "at", "trigger", "eibaid", "eibcalen", "commarea")

# SPEC 6.2: every key an event of each type may carry (besides `event`, `program` and `note`).
EVENT_KEYS: dict[str, tuple[str, ...]] = {
    "SEND-MAP": ("map", "mapset", "options", "cursor", "fields"),
    "SEND-TEXT": ("text", "length", "options"),
    "SEND-CONTROL": ("options",),
    "RECEIVE-MAP": ("map", "mapset", "resp"),
    "RECEIVE": ("resp", "length", "data"),
    "LINK": ("target", "length", "commarea", "resp", "resp2"),
    "XCTL": ("target", "length", "commarea", "resp", "resp2"),
    "RETURN": ("level", "transid", "commarea", "caller_commarea"),
    "START": ("transid", "termid", "interval", "time", "from", "reqid", "protect", "resp", "resp2", "expires"),
    "RETRIEVE": ("resp", "length", "data"),
    "CANCEL": ("reqid", "resp"),
    "READQ-TS": ("queue", "item", "resp", "length", "data"),
    "WRITEQ-TS": ("queue", "data", "resp", "item"),
    "READ": ("file", "ridfld", "resp"),
    "ABEND": ("abcode", "cause", "condition", "outcome", "exit"),
}
AREA_KEYS = frozenset({"commarea", "caller_commarea", "data", "from"})
FIELD_KEYS = ("attr", "attr_from", "data", "data_from", "color", "color_from", "hilight", "hilight_from")


class CaseError(Exception):
    """A case directory that is not a well-formed cics-crucible/1 case."""


# ---- reading a case ------------------------------------------------------------------------
def parse_csd(text: str) -> dict[str, Any]:
    """The DFHCSDUP input of a case: {"programs": set, "transactions": {transid: program},
    "mapsets": set}. Comment lines start with `*`; a DEFINE may continue on following lines."""
    programs: set[str] = set()
    mapsets: set[str] = set()
    transactions: dict[str, str] = {}
    body = " ".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("*"))
    for m in re.finditer(r"\bDEFINE\s+(\w+)\s*\(\s*([^)\s]+)\s*\)(.*?)(?=\bDEFINE\b|$)", body, re.I | re.S):
        kind, name, rest = m.group(1).upper(), m.group(2).upper(), m.group(3)
        if kind == "PROGRAM":
            programs.add(name)
        elif kind == "MAPSET":
            mapsets.add(name)
        elif kind == "TRANSACTION":
            prog = re.search(r"\bPROGRAM\s*\(\s*([^)\s]+)\s*\)", rest, re.I)
            if prog:
                transactions[name] = prog.group(1).upper()
    return {"programs": programs, "transactions": transactions, "mapsets": mapsets}


@dataclass
class Case:
    """One case: its case.json, its expected logs by scenario id, and its CSD."""

    dir: Path
    data: dict[str, Any]
    expected: dict[str, dict[str, Any]]
    csd: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.data["id"])

    @property
    def trap(self) -> str:
        return str(self.data["trap"])

    @property
    def scenarios(self) -> list[dict[str, Any]]:
        return list(self.data["scenarios"])

    @property
    def programs(self) -> list[str]:
        """PROGRAM-IDs, from the source file stems (SPEC 3: file stem = PROGRAM-ID)."""
        return [Path(p).stem.upper() for p in self.data["sources"]["cobol"]]


def load_case(case_dir: Path) -> Case:
    """A case directory -> Case. Refuses a format this runner does not read (a major bump)."""
    case_dir = Path(case_dir)
    path = case_dir / "case.json"
    if not path.is_file():
        raise CaseError(f"{case_dir}: no case.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != CASE_FORMAT:
        raise CaseError(f"{path}: format {data.get('format')!r}, this runner reads {CASE_FORMAT!r}")
    for key in ("id", "trap", "clock", "terminal", "sources", "layouts", "maps", "scenarios"):
        if key not in data:
            raise CaseError(f"{path}: no {key!r}")
    expected: dict[str, dict[str, Any]] = {}
    for sc in data["scenarios"]:
        ep = case_dir / "expected" / f"{sc['id']}.json"
        if not ep.is_file():
            raise CaseError(f"{case_dir}: scenario {sc['id']!r} has no expected/{sc['id']}.json")
        log = json.loads(ep.read_text(encoding="utf-8"))
        if log.get("format") != EXPECTED_FORMAT:
            raise CaseError(f"{ep}: format {log.get('format')!r}, this runner reads {EXPECTED_FORMAT!r}")
        if log.get("case") != data["id"] or log.get("scenario") != sc["id"]:
            raise CaseError(f"{ep}: names case {log.get('case')!r} / scenario {log.get('scenario')!r}")
        expected[sc["id"]] = log
    csd_text = "\n".join((case_dir / p).read_text(encoding="utf-8") for p in data["sources"]["csd"])
    return Case(case_dir, data, expected, parse_csd(csd_text))


def discover(root: Path, only: Optional[set[str]] = None) -> list[Path]:
    """Every case directory under a crucible checkout (cases/<trap>/<case-id>/), sorted by id."""
    dirs = sorted((p.parent for p in Path(root).glob("cases/*/*/case.json")), key=lambda p: p.name)
    return [d for d in dirs if only is None or d.name in only]


def cell_id(case: str, scenario: str, side: str) -> str:
    return f"{case}/{scenario}/{side}"


# ---- values ----------------------------------------------------------------------------------
class Unmodelled:
    """A value the side cannot produce here (e.g. a DTO's COMMAREA length when the log's is shorter)."""

    def __init__(self, feature: str) -> None:
        self.feature = feature

    def __repr__(self) -> str:
        return f"Unmodelled({self.feature!r})"


@dataclass
class RawArea:
    """An area's bytes as a runtime held them, in that runtime's code page (GnuCOBOL: latin-1)."""

    data: bytes
    encoding: str = EBCDIC


FULL = "full-record"  # a FieldArea's length when the side holds the whole record (a DTO)


@dataclass
class FieldArea:
    """An area as field values ({COBOL name: value}), the way a generated DTO holds it; `length` is an
    int, FULL (the DTO is the whole record) or Unmodelled."""

    fields: dict[str, Any]
    length: Any = FULL
    # #3989: the record's EBCDIC bytes, encoded from the fields by the DTO's layout -- how a log's text / hex
    # area is compared with a DTO (a one-byte `WS-CA PIC X` COMMAREA). None when a field cannot be encoded.
    data: Optional[bytes] = None
    known: int = 0  # how many leading bytes of `data` are known (a null field's are not)


_BINARY = ("COMP", "COMP-3", "COMP-4", "COMP-5", "BINARY", "PACKED-DECIMAL", "COMPUTATIONAL", "COMPUTATIONAL-3",
           "COMPUTATIONAL-4", "COMPUTATIONAL-5")  # fmt: skip


def _is_binary(f: dict[str, Any]) -> bool:
    return (f.get("usage") or "DISPLAY").upper() in _BINARY


def to_ebcdic(area: RawArea, layout: Optional[list[dict[str, Any]]] = None) -> bytes:
    """A RawArea's bytes in CCSID 037: DISPLAY bytes through the page, COMP / COMP-3 bytes as they
    are. Without a layout every byte is taken as DISPLAY (an area the log gives as text or hex)."""
    if area.encoding.replace("-", "").lower() in ("cp037", "ibm037"):
        return area.data
    # strict: the stub runtime's page is latin-1, which decodes every byte, and cp037 encodes every latin-1 character
    out = bytearray(area.data.decode(area.encoding).encode(EBCDIC))
    for f in layout or []:
        if _is_binary(f):
            end = min(f["offset"] + f["bytes"], len(area.data))
            out[f["offset"] : end] = area.data[f["offset"] : end]
    return bytes(out)


def expected_bytes(value: Any, length: Optional[int] = None) -> bytes:
    """A log's text or hex value as the EBCDIC bytes it means, text right-padded to `length`."""
    if isinstance(value, dict) and "hex" in value:
        return bytes.fromhex(value["hex"])
    data = str(value).encode(EBCDIC)
    if length is not None and len(data) < length:
        data += b"\x40" * (length - len(data))
    return data


def actual_bytes(value: Any, length: Optional[int] = None) -> bytes:
    """A side's text value as EBCDIC bytes: bytes are already EBCDIC; a string (a Java field, which
    holds text, not bytes) is encoded and padded like a log's text."""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return expected_bytes(str(value), length)


def _show(data: bytes) -> str:
    """Bytes for a message: the text when every byte is a printable EBCDIC character, else hex."""
    text = data.decode(EBCDIC)
    return repr(text) if text.isprintable() else f"X'{data.hex().upper()}'"


def _pair(want: bytes, got: bytes) -> tuple[str, str]:
    """Both sides in one form: text when both are printable, else both in hex."""
    a, b = _show(want), _show(got)
    if a.startswith("X'") != b.startswith("X'"):
        return f"X'{want.hex().upper()}'", f"X'{got.hex().upper()}'"
    return a, b


def _numeric_pic(pic: Optional[str]) -> bool:
    if not pic:
        return False
    p = re.sub(r"(.)\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), pic.upper())
    return bool(p) and not re.search(r"[^S9VP]", p)


def _as_decimal(value: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def _decode_number(raw: bytes, f: dict[str, Any]) -> Any:
    import equivalence_common as common

    return common.decode_field(raw, f["pic"], f.get("usage"), EBCDIC, bool(f.get("sign_separate")), EBCDIC)


# ---- capabilities ------------------------------------------------------------------------------
@dataclass
class Capabilities:
    """What one side of the harness records. `events` maps an event type to the keys it records (for
    SEND-MAP, `fields.<sub>` names the per-field keys, `fields.omission` that it omits fields BMS
    does not send). `layer` prefixes feature names (`stub`, `CicsTask`)."""

    layer: str
    task_keys: frozenset[str]
    events: dict[str, frozenset[str]]
    ts_queues: bool = False  # seeds a scenario's `initial` TS queues and reports the `final` ones
    start_tasks: bool = False


def feature_name(layer: str, event: Optional[str], key: Optional[str] = None) -> str:
    """A readable feature name for the report: `stub: SEND-MAP attribute bytes`, `CicsTask: LINK event`."""
    if event is None:
        return f"{layer}: task {key}"
    if key is None:
        return f"{layer}: {event} event"
    if event == "SEND-MAP" and key.startswith("fields."):
        sub = key.split(".", 1)[1]
        what = {"attr": "attribute bytes", "attr_from": "attribute bytes", "color": "extended attributes",
                "color_from": "extended attributes", "hilight": "extended attributes",
                "hilight_from": "extended attributes", "data_from": "data origin (program / map / none)",
                "data": "field data", "omission": "DATAONLY field omission"}.get(sub, sub)  # fmt: skip
        return f"{layer}: SEND-MAP {what}"
    return f"{layer}: {event} {key}"


def blockers(expected: dict[str, Any], caps: Capabilities, scenario: Optional[dict[str, Any]] = None) -> list[str]:
    """Every feature the expected log needs that the side does not model, in first-use order."""
    out: list[str] = []

    def need(feature: str) -> None:
        if feature not in out:
            out.append(feature)

    if scenario and (scenario.get("initial") or {}).get("ts_queues") and not caps.ts_queues:
        need(f"{caps.layer}: TS queue seeding")
    for task in expected["tasks"]:
        if task["trigger"]["kind"] == "start" and not caps.start_tasks:
            need(f"scheduler: START-triggered tasks ({caps.layer})")
        for key in TASK_KEYS:
            if key not in caps.task_keys:
                need(feature_name(caps.layer, None, key))
        for ev in task["events"]:
            kind = ev["event"]
            keys = caps.events.get(kind)
            if keys is None:
                need(feature_name(caps.layer, kind))
                continue
            for key in EVENT_KEYS[kind]:
                if key in ev and key not in keys:
                    need(feature_name(caps.layer, kind, key))
            if kind == "SEND-MAP" and "fields" in keys:
                for fo in ev["fields"].values():
                    for sub in FIELD_KEYS:
                        if sub in fo and f"fields.{sub}" not in keys:
                            need(feature_name(caps.layer, kind, f"fields.{sub}"))
                if "DATAONLY" in ev.get("options", []) and "fields.omission" not in keys:
                    need(feature_name(caps.layer, kind, "fields.omission"))
    if expected.get("final", {}).get("ts_queues") and not caps.ts_queues:
        need(f"{caps.layer}: TS queue final state")
    return out


# ---- the comparison ------------------------------------------------------------------------------
@dataclass
class Verdict:
    status: str  # pass | fail | unsupported
    reason: str = ""
    features: list[str] = field(default_factory=list)  # every blocker (unsupported), for the report
    kind: str = ""  # a short, groupable category of the reason (the report's "top failure reasons")
    detail: str = ""  # more than the reason's one line, when there is more (a port's compile errors)

    def as_dict(self) -> dict[str, Any]:
        d = {"status": self.status, "reason": self.reason, "features": self.features, "kind": self.kind}
        return {**d, "detail": self.detail} if self.detail else d


class _Decided(Exception):
    def __init__(self, verdict: Verdict) -> None:
        self.verdict = verdict


@dataclass
class Context:
    """What the comparison needs from the case: layouts by name (lists of {name, offset, bytes, pic,
    usage}), and each map's named output fields' lengths ({map: {field: bytes}})."""

    layouts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    map_fields: dict[str, dict[str, int]] = field(default_factory=dict)


class _Walk:
    def __init__(self, caps: Capabilities, ctx: Context) -> None:
        self.caps, self.ctx = caps, ctx
        self.pending: Optional[str] = None  # an unmodelled point met inside the current event
        self.stopped: Optional[str] = None  # why the side stopped running tasks, if it did

    def fail(self, where: str, detail: str, kind: str) -> None:
        raise _Decided(Verdict("fail", f"{where}: {detail}", kind=kind))

    def unsupported(self, feature: str) -> None:
        raise _Decided(Verdict("unsupported", feature, [feature], kind=feature))

    def later(self, feature: str) -> None:
        """An unmodelled key of the event being compared: decided only if its modelled keys agree."""
        self.pending = self.pending or feature

    # -- values
    def value(self, where: str, key: str, exp: Any, act: Any) -> None:
        if isinstance(act, Unmodelled):
            self.later(f"{self.caps.layer}: {act.feature}")
            return
        if key == "options":
            if sorted(exp or []) != sorted(act or []):
                self.fail(where, f"options {sorted(exp or [])} expected, got {sorted(act or [])}", f"{key} differ")
            return
        if exp != act:
            self.fail(where, f"{key} {exp!r} expected, got {act!r}", f"{key} differs")

    def text(self, where: str, key: str, exp: Any, act: Any, length: Optional[int]) -> None:
        if isinstance(act, Unmodelled):
            self.later(f"{self.caps.layer}: {act.feature}")
            return
        if exp is None or act is None:
            if exp is not act:
                self.fail(where, f"{key} {exp!r} expected, got {act!r}", f"{key} differs")
            return
        want, got = expected_bytes(exp, length), actual_bytes(act, length)
        if want != got:
            a, b = _pair(want, got)
            self.fail(where, f"{key} {a} expected, got {b}", f"{key} differs")

    def area(self, where: str, key: str, exp: Any, act: Any) -> None:
        if isinstance(act, Unmodelled):
            self.later(f"{self.caps.layer}: {act.feature}")
            return
        if exp is None or act is None:
            if exp is not act:
                self.fail(where, f"{key} {'none' if exp is None else 'an area'} expected, got "
                          f"{'none' if act is None else 'an area'}", f"{key} presence differs")  # fmt: skip
            return
        n = exp["length"]
        layout = self.ctx.layouts.get(exp["layout"]) if "layout" in exp else None
        if "layout" in exp and layout is None:
            raise KeyError(f"layout {exp['layout']!r} is not one of the case's layouts")
        if isinstance(act, FieldArea):
            self.field_area(where, key, exp, act, layout)
            return
        if not isinstance(act, RawArea):
            raise TypeError(f"{where}: {key} is a {type(act).__name__}, not an area")
        if len(act.data) != n:
            self.fail(where, f"{key} length {n} expected, got {len(act.data)}", f"{key} length differs")
        data = to_ebcdic(act, layout)
        if layout is None:
            want = expected_bytes(exp["text"] if "text" in exp else {"hex": exp["hex"]}, n)
            if data != want:
                at = next(i for i in range(max(len(want), len(data))) if want[i : i + 1] != data[i : i + 1])
                a, b = _pair(want[at : at + 16], data[at : at + 16])
                self.fail(where, f"{key} byte {at}: {a} expected, got {b}", f"{key} bytes differ")
            return
        by_name = {f["name"]: f for f in layout}
        for name, value in exp["fields"].items():
            f = by_name[name]
            raw = data[f["offset"] : f["offset"] + f["bytes"]]
            if isinstance(value, str) and _numeric_pic(f.get("pic")):
                got = _decode_number(raw, f)
                if not isinstance(got, Decimal) or got != _as_decimal(value):
                    self.fail(where, f"{key}.{name} {value} expected, got {got} ({_show(raw)})", f"{key} field differs")
            elif expected_bytes(value, f["bytes"]) != raw:
                a, b = _pair(expected_bytes(value, f["bytes"]), raw)
                self.fail(where, f"{key}.{name} {a} expected, got {b}", f"{key} field differs")

    def field_area(self, where: str, key: str, exp: dict[str, Any], act: FieldArea,
                   layout: Optional[list[dict[str, Any]]]) -> None:  # fmt: skip
        if act.data is not None and not isinstance(act.length, Unmodelled):
            # #3989: an area is bytes. A DTO whose record bytes are known is compared as them, through the log's
            # layout or text / hex -- a callee's DTO may name the bytes of a caller's area differently
            # (CA-EXT-FLAG where the caller has WS-AFTER-FLAG), and only the offsets say which is which.
            n = len(act.data) if act.length == FULL else act.length
            if n <= act.known:
                self.area(where, key, exp, RawArea(act.data[:n], EBCDIC))
                return
            if layout is None:  # #4009: a LENGTH past the record's end, or over a null field: unknown bytes
                self.later(f"{self.caps.layer}: {key} bytes past what its DTO holds")
                return
        if layout is None:
            self.later(f"{self.caps.layer}: {key} as bytes (the log gives it as text / hex)")
            return
        by_name = {f["name"]: f for f in layout}
        for name, value in exp["fields"].items():
            f = by_name[name]
            if name not in act.fields:
                self.fail(where, f"{key}.{name} {value!r} expected, the side has no such field", f"{key} field missing")
            got = act.fields[name]
            if isinstance(value, str) and _numeric_pic(f.get("pic")):
                if _as_decimal(got) != _as_decimal(value):
                    self.fail(where, f"{key}.{name} {value} expected, got {got!r}", f"{key} field differs")
            elif got is None or expected_bytes(value, f["bytes"]) != actual_bytes(got, f["bytes"]):
                self.fail(where, f"{key}.{name} {value!r} expected, got {got!r}", f"{key} field differs")
        size = max((f["offset"] + f["bytes"] for f in layout), default=0)
        if isinstance(act.length, Unmodelled):
            self.later(f"{self.caps.layer}: {act.length.feature}")
        elif act.length == FULL:  # #4009: passed without a LENGTH, so its record's; a shorter one is stated
            if exp["length"] != size:
                self.fail(where, f"{key} length {exp['length']} expected, got its whole record ({size} bytes, "
                          "no LENGTH given)", f"{key} length differs")  # fmt: skip
        elif act.length != exp["length"]:
            self.fail(where, f"{key} length {exp['length']} expected, got {act.length}", f"{key} length differs")

    def record_bytes(self, exp: Optional[dict[str, Any]]) -> Any:
        """#4009: the length of a COMMAREA a side passed as its whole record (FULL): its layout's."""
        layout = self.ctx.layouts.get(exp["layout"]) if exp and "layout" in exp else None
        if layout is None:
            return Unmodelled("task eibcalen of a whole record with no layout")
        return max((f["offset"] + f["bytes"] for f in layout), default=0)

    # -- events
    def fields(self, where: str, exp_ev: dict[str, Any], act: Any, keys: frozenset[str]) -> None:
        if isinstance(act, Unmodelled):
            self.later(f"{self.caps.layer}: {act.feature}")
            return
        act = act or {}
        lengths = self.ctx.map_fields.get(exp_ev["map"], {})
        for name, fo in exp_ev["fields"].items():
            if name not in act:
                self.fail(where, f"field {name} expected, not sent", "SEND-MAP field missing")
            got = act[name]
            for sub in FIELD_KEYS:
                if sub not in fo:
                    continue
                if f"fields.{sub}" not in keys:
                    self.later(feature_name(self.caps.layer, "SEND-MAP", f"fields.{sub}"))
                elif sub == "data":
                    self.text(f"{where} field {name}", "data", fo["data"], got.get("data"), lengths.get(name))
                else:
                    self.value(f"{where} field {name}", sub, fo[sub], got.get(sub))
        extra = sorted(set(act) - set(exp_ev["fields"]))
        if extra and "fields.omission" in keys:
            self.fail(where, f"fields {extra} sent, BMS sends none for them", "SEND-MAP extra fields")

    def event(self, where: str, exp: dict[str, Any], act: Optional[dict[str, Any]]) -> None:
        kind = exp["event"]
        keys = self.caps.events.get(kind)
        if keys is None:
            self.unsupported(feature_name(self.caps.layer, kind))
        assert keys is not None
        if act is None:
            self.fail(where, f"{kind} expected, the side recorded no further event", f"{kind} missing")
        assert act is not None
        if act["event"] != kind:
            self.fail(where, f"{kind} expected, got {act['event']}" + (f" ({act['message']})" if act.get("message") else ""),
                      f"{kind} expected, other event")  # fmt: skip
        self.value(where, "program", exp["program"], act.get("program"))
        self.pending = None
        for key in EVENT_KEYS[kind]:
            if key not in keys:
                if key in exp:
                    self.later(feature_name(self.caps.layer, kind, key))
                continue
            e, a = exp.get(key), act.get(key)
            if key not in exp and a is not None and not isinstance(a, Unmodelled):
                self.fail(where, f"{key} {a!r} not expected", f"{kind} {key} unexpected")
            if key not in exp:
                continue
            if key == "fields":
                self.fields(where, exp, a, keys)
            elif key in AREA_KEYS:
                self.area(where, key, e, a)
            elif key == "text":
                self.text(where, key, e, a, exp.get("length"))
            elif key == "ridfld":
                self.text(where, key, e, a, None)
            else:
                self.value(where, key, e, a)
        if self.pending:
            self.unsupported(self.pending)

    def task(self, exp: dict[str, Any], act: Optional[dict[str, Any]]) -> None:
        where = f"task {exp['seq']} ({exp['transid']})"
        if act is None:
            why = f" ({self.stopped})" if self.stopped else ""
            self.fail(where, f"expected a task running {exp['program']}, the side ran none{why}", "task missing")
        assert act is not None
        self.pending = None
        for key in TASK_KEYS:
            if key not in self.caps.task_keys:
                self.later(feature_name(self.caps.layer, None, key))
            elif key == "commarea":
                self.area(where, key, exp[key], act.get(key))
            elif key == "eibcalen" and act.get(key) == FULL:
                self.value(where, key, exp[key], self.record_bytes(exp.get("commarea")))
            else:
                self.value(where, key, exp[key], act.get(key))
        if self.pending:
            self.unsupported(self.pending)
        events = act.get("events", [])
        for i, ev in enumerate(exp["events"]):
            self.event(f"{where} event {i + 1}", ev, events[i] if i < len(events) else None)
        if len(events) > len(exp["events"]):
            extra = events[len(exp["events"])]
            self.fail(f"{where} event {len(exp['events']) + 1}", f"no further event expected, got {extra['event']}"
                      + (f" ({extra['message']})" if extra.get("message") else ""), "extra event")  # fmt: skip
        if "end" in self.caps.task_keys:
            self.value(where, "end", exp["end"], act.get("end"))

    def log(self, exp: dict[str, Any], act: dict[str, Any]) -> None:
        tasks = act.get("tasks", [])
        self.stopped = act.get("stopped")
        for i, t in enumerate(exp["tasks"]):
            self.task(t, tasks[i] if i < len(tasks) else None)
        if len(tasks) > len(exp["tasks"]):
            extra = tasks[len(exp["tasks"])]
            self.fail(f"task {len(exp['tasks']) + 1}", f"no further task expected, the side ran {extra.get('transid')}",
                      "extra task")  # fmt: skip
        final = exp.get("final", {}).get("ts_queues")
        if final:
            if not self.caps.ts_queues:
                self.unsupported(f"{self.caps.layer}: TS queue final state")
            got = act.get("final", {}).get("ts_queues", {})
            for q, items in final.items():
                have = got.get(q, [])
                if len(have) != len(items):
                    self.fail(
                        f"final TS queue {q}", f"{len(items)} items expected, got {len(have)}", "final TS differs"
                    )
                for n, (e, a) in enumerate(zip(items, have)):
                    # SPEC 6.1: a TS item's length is known -- its own -- so the log's text is blank-padded to it
                    # (trailing blanks optional); #4006 met the first items written from a longer area
                    known = len(a) if isinstance(a, (bytes, bytearray)) else None
                    self.text(f"final TS queue {q} item {n + 1}", "item", e, a, known)


def compare(expected: dict[str, Any], actual: dict[str, Any], caps: Capabilities, ctx: Context,
            scenario: Optional[dict[str, Any]] = None) -> Verdict:  # fmt: skip
    """The verdict of one side's actual log against the expected log (see the module docstring)."""
    needs = blockers(expected, caps, scenario)
    try:
        _Walk(caps, ctx).log(expected, actual)
    except _Decided as d:
        v = d.verdict
        v.features = needs if v.status == "fail" else list(dict.fromkeys(v.features + needs))
        return v
    return Verdict("pass", features=needs)


def not_run(features: list[str], needs: list[str], kind: Optional[str] = None) -> Verdict:
    """A cell the harness cannot run at all (a program it cannot translate, a seed it cannot load)."""
    feats = list(dict.fromkeys(features + needs))
    return Verdict("unsupported", "; ".join(features), feats, kind=kind or features[0])
