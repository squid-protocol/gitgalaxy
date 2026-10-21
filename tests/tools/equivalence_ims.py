"""
IMS DL/I databases in the equivalence harness (#4893; see equivalence.py).

A batch case's `"ims"` section states the databases a DL/I program (IMS enters its ENTRY 'DLITCBL' with its PCBs; it
issues CALL 'CBLTDLI') runs against, and both sides run on the same stated content:

    "ims": {"dbd": ["<corpus path of a DBDGEN source>", ...], "psb": "<corpus path of the PSBGEN source>",
            "seed": {"<DBD>": {"unload": "<corpus path>"} | {"segments": [{"segment": S, "text" | "hex": ...}]}},
            "segments": {"<SEGM>": {"copybook": "<corpus path>", "record": "<01 name>"}},
            "compare": ["<DBD>", ...]}

The DBD and PSB sources are read by the engine's own macro reader (gitgalaxy/core/ims_gen.py); what this model does
not model is refused here by name (Unsupported): HDAM / PHDAM (the randomizer's root order), logical relationships,
variable-length segments, a non-unique or missing sequence field, an I/O PCB (CMPAT=YES, TYPE=TP: IMS TM), a GSAM PCB,
PROCSEQ (a secondary index), load mode (PROCOPT L / LS), segment-level PROCOPT and partial sensitivity.
`{"unload": ...}` reads an HD reorganization unload (DFSURGU0) of the corpus: its segments, EBCDIC, each laid out by
its copybook (`segments`) into the case's data page (text through CCSID 037, COMP / COMP-3 bytes as they are), its
trailer's segment counts checked.

Written for both sides into one directory (`stage`): dbd.cfg, psb.cfg and seed.<DBD> (tests/equivalence/ims/ggdli.c
documents the format); each side writes <DBD>.out, the database as the step left it, compared segment by segment
(`diff_db`) with every field of its segment's layout.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from gitgalaxy.core.ims_gen import ims_gen_macros  # noqa: E402

import equivalence_common as common  # noqa: E402

STUB = Path(__file__).resolve().parents[1] / "equivalence" / "ims" / "ggdli.c"
MASK = 36  # the DB PCB mask before its key feedback area (IMS Application Programming, "DB PCB mask")
AREA = 4096  # the area the COBOL driver passes per PCB: at least the PCB, and every byte a LINKAGE mask may name
ACCESS = ("HIDAM", "PHIDAM", "HISAM", "SHISAM")


class Unsupported(ValueError):
    """What the DL/I model does not model: the case is not runnable faithfully."""


def _keyed(attributes: str, key: str) -> str | None:
    m = re.search(rf"(?:^|,)\s*{key}\s*=\s*(\([^)]*\)+|[^,\s]+)", attributes or "", re.I)
    return m.group(1).upper() if m else None


def dbd(text: str, where: str) -> dict[str, Any]:
    """One DBD source: {name, segments: [{name, parent, bytes, fields: [{name, start, bytes, type, seq}]}]}."""
    rows = ims_gen_macros(text)
    db = next((r for r in rows if r["kind"] == "DBD"), None)
    if db is None:
        raise Unsupported(f"{where}: no DBD statement")
    access = (db["access"] or "").upper()
    if access not in ACCESS:
        raise Unsupported(f"{where}: ACCESS={access or '?'} (only {', '.join(ACCESS)}: the root sequence of an HDAM "
                          "database is its randomizer's, a GSAM / INDEX / LOGICAL database is no hierarchy here)")  # fmt: skip
    segs: list[dict[str, Any]] = []
    for r in rows:
        attrs = r["attributes"] or ""
        if r["kind"] == "SEGM":
            parent = (r["parent"] or "0").strip("()").split(",")[0].strip().upper() or "0"
            if _keyed(attrs, "SOURCE") or re.search(r"PARENT\s*=\s*\(\([^)]*\)\s*,\s*\(", attrs, re.I):
                raise Unsupported(f"{where}: SEGM {r['name']} has a logical relationship (not modelled)")
            if r["bytes"] is None or re.search(r"BYTES\s*=\s*\(\s*\d+\s*,", attrs, re.I):
                raise Unsupported(f"{where}: SEGM {r['name']}: a variable-length segment (not modelled)")
            segs.append({"name": r["name"].upper(), "parent": parent, "bytes": r["bytes"], "fields": []})
        elif r["kind"] == "FIELD" and segs:
            names = (_keyed(attrs, "NAME") or "").strip("()").split(",")
            seq = len(names) > 1 and names[1].strip() == "SEQ"
            if seq and (len(names) < 3 or names[2].strip() != "U"):
                raise Unsupported(f"{where}: FIELD {r['name']}: a non-unique sequence field (not modelled)")
            if r["start"] is None or r["bytes"] is None:
                raise Unsupported(f"{where}: FIELD {r['name']}: START / BYTES not literal")
            segs[-1]["fields"].append({"name": r["name"].upper(), "start": r["start"], "bytes": r["bytes"],
                                       "type": (_keyed(attrs, "TYPE") or "C")[0], "seq": seq})  # fmt: skip
    for s in segs:
        if not any(f["seq"] for f in s["fields"]):
            raise Unsupported(f"{where}: SEGM {s['name']} has no sequence field (twin order FIRST / LAST / HERE: "
                              "not modelled)")  # fmt: skip
    return {"name": db["name"].upper(), "segments": segs}


def psb(text: str, where: str, dbds: dict[str, dict[str, Any]], cics: bool = False) -> list[dict[str, Any]]:
    """The PSB's DB PCBs, in order: [{dbd, procopt, keylen}]; an I/O or GSAM PCB, or what else is not modelled,
    refused. `cics`: EXEC DLI numbers the DB PCBs from 1 (no I/O PCB first), so CMPAT=YES changes nothing (I5
    ASSUMPTION, no IBM text cited)."""
    rows = ims_gen_macros(text)
    gen = next((r for r in rows if r["kind"] == "PSBGEN"), None)
    if gen is None:
        raise Unsupported(f"{where}: no PSBGEN statement")
    if (_keyed(gen["attributes"], "CMPAT") or "NO") == "YES" and not cics:
        raise Unsupported(f"{where}: CMPAT=YES (IMS passes an I/O PCB first: IMS TM, not modelled)")
    pcbs: list[dict[str, Any]] = []
    for r in rows:
        attrs = r["attributes"] or ""
        if r["kind"] == "PCB":
            if (r["pcb_type"] or "").upper() != "DB":
                raise Unsupported(f"{where}: a TYPE={r['pcb_type']} PCB (an I/O, alternate or GSAM PCB: not modelled)")
            if _keyed(attrs, "PROCSEQ"):
                raise Unsupported(f"{where}: PCB {r['name']}: PROCSEQ (a secondary index) is not modelled")
            procopt = (r["procopt"] or "A").upper()
            if "L" in procopt:
                raise Unsupported(f"{where}: PCB {r['name']}: PROCOPT={procopt} (load mode) is not modelled")
            name = (r["dbd_name"] or "").upper()
            if name not in dbds:
                raise Unsupported(f"{where}: PCB {r['name']}: DBD {name} is not one of the case's DBDs")
            keylen = _keyed(attrs, "KEYLEN")
            if not (keylen or "").isdigit():
                raise Unsupported(f"{where}: PCB {r['name']}: KEYLEN not literal")
            pcbs.append({"dbd": name, "procopt": procopt[:4], "keylen": int(keylen or 0), "sensegs": []})
        elif r["kind"] == "SENSEG" and pcbs:
            if r["procopt"]:
                raise Unsupported(f"{where}: SENSEG {r['name']}: a segment-level PROCOPT is not modelled")
            pcbs[-1]["sensegs"].append((r["name"] or "").upper())
    for p in pcbs:
        every = [s["name"] for s in dbds[p["dbd"]]["segments"]]
        if sorted(p["sensegs"]) != sorted(every):
            raise Unsupported(f"{where}: a PCB on {p['dbd']} sensitive to {p['sensegs']}, not to every segment "
                              "(partial sensitivity is not modelled)")  # fmt: skip
    return pcbs


def definitions(
    case: dict[str, Any], corpus: Path, cics: bool = False
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    ims = case["ims"]
    dbds: dict[str, dict[str, Any]] = {}
    for rel in ims["dbd"]:
        d = dbd((corpus / rel).read_text(encoding="latin-1"), rel)
        dbds[d["name"]] = d
    return dbds, psb((corpus / ims["psb"]).read_text(encoding="latin-1"), ims["psb"], dbds, cics)


def _layout(case: dict[str, Any], corpus: Path, seg: str) -> list[dict[str, Any]] | None:
    spec = case["ims"].get("segments", {}).get(seg)
    if not spec:
        return None
    dirs = [corpus / d for d in case.get("copy_dirs", [])]
    return common.layout_fields(corpus, spec["copybook"], spec.get("record"), copy_dirs=[*dirs, corpus],
                                occurrences=True)  # fmt: skip


def _binary(f: dict[str, Any]) -> bool:
    return (f.get("usage") or "DISPLAY").upper() not in ("DISPLAY", "")


def from_ebcdic(data: bytes, layout: list[dict[str, Any]], enc: str) -> bytes:
    """A segment's EBCDIC bytes in the case's data page: text through CCSID 037, COMP / COMP-3 / POINTER bytes kept."""
    out = bytearray(data.decode("cp037").encode(enc))
    if len(out) != len(data):
        raise Unsupported(f"data page {enc} is not single-byte: a segment cannot be laid out")
    for f in layout:
        if _binary(f):
            out[f["offset"] : f["offset"] + f["bytes"]] = data[f["offset"] : f["offset"] + f["bytes"]]
    return bytes(out)


def unload(path: Path) -> list[tuple[str, bytes]]:
    """An HD reorganization unload (DFSURGU0, the corpus's own): [(segment, its EBCDIC data)] in hierarchic sequence.
    Each record: a halfword length, a halfword of zeros, the segment level and flag bytes, a halfword, the segment's
    length (halfword) and name (8 bytes, EBCDIC) at offset 8 / 10, its data the `length` bytes before the record's
    last byte. The first record (level 0) is the header, the last (level 0) the trailer: per segment type its name and,
    32 bytes on, a fullword count of its segments -- checked against what was read, so a misread layout is never
    seeded."""
    raw = path.read_bytes()
    recs, i = [], 0
    while i + 2 <= len(raw):
        n = int.from_bytes(raw[i : i + 2], "big")
        if n < 18 or i + n > len(raw):
            raise Unsupported(f"{path.name}: record at {i} has length {n}: not an HD unload")
        recs.append(raw[i : i + n])
        i += n
    if len(recs) < 2 or recs[0][4] != 0 or recs[-1][4] != 0:
        raise Unsupported(f"{path.name}: no header / trailer record: not an HD unload")
    segs = []
    for r in recs[1:-1]:
        length = int.from_bytes(r[8:10], "big")
        if length + 19 > len(r):
            raise Unsupported(f"{path.name}: a segment longer than its record")
        segs.append((r[10:18].decode("cp037").rstrip(), r[len(r) - length - 1 : len(r) - 1]))
    seen: dict[str, int] = {}
    for name, _ in segs:
        seen[name] = seen.get(name, 0) + 1
    trailer = recs[-1]
    for name, n in seen.items():
        at = trailer.find(name.ljust(8).encode("cp037"))
        count = int.from_bytes(trailer[at + 32 : at + 36], "big") if at >= 0 else None
        if count != n:
            raise Unsupported(f"{path.name}: {n} {name} segments read, the trailer counts {count}")
    return segs


def seed(case: dict[str, Any], corpus: Path, name: str, db: dict[str, Any]) -> bytes:
    """One database's seed, in the format both sides read (8-byte segment name, then its data)."""
    spec = case["ims"].get("seed", {}).get(name)
    if not spec:
        return b""
    enc = common.data_encoding(case)
    sizes = {s["name"]: s["bytes"] for s in db["segments"]}
    out = bytearray()
    if "unload" in spec:
        layouts: dict[str, list[dict[str, Any]]] = {}
        skip = set(spec.get("skip", []))  # record numbers left out (a root whose packed key is blank: GU would refuse)
        for n, (seg, data) in enumerate(unload(corpus / spec["unload"])):
            if n in skip:
                continue
            if seg not in sizes:
                raise Unsupported(f"{spec['unload']}: segment {seg} is not in DBD {name}")
            if seg not in layouts:
                lay = _layout(case, corpus, seg)
                if lay is None:
                    raise Unsupported(f"segment {seg}: no copybook to lay its EBCDIC bytes out by (ims.segments)")
                layouts[seg] = lay
            out += seg.ljust(8).encode("ascii") + from_ebcdic(data[: sizes[seg]].ljust(sizes[seg], b"\x40"),
                                                              layouts[seg], enc)  # fmt: skip
        return bytes(out)
    for s in spec["segments"]:
        size = sizes[s["segment"]]
        data = bytes.fromhex(s["hex"]) if "hex" in s else common.text_bytes(s["text"], size, enc)
        if len(data) != size:
            raise Unsupported(f"seed segment {s['segment']}: {len(data)} bytes, BYTES={size}")
        out += s["segment"].ljust(8).encode("ascii") + data
    return bytes(out)


def config(dbds: dict[str, dict[str, Any]], pcbs: list[dict[str, Any]]) -> tuple[str, str]:
    """dbd.cfg and psb.cfg (tests/equivalence/ims/ggdli.c, DetDli.load)."""
    lines = []
    for name, db in dbds.items():
        lines.append(f"DBD {name}")
        for s in db["segments"]:
            lines.append(f"SEGM {name} {s['name']} {s['parent']} {s['bytes']}")
        for s in db["segments"]:
            for f in s["fields"]:
                lines.append(f"FIELD {name} {s['name']} {f['name']} {f['start']} {f['bytes']} {f['type']} "
                             f"{'S' if f['seq'] else '-'}")  # fmt: skip
    return "\n".join(lines) + "\n", "".join(f"PCB {p['dbd']} {p['procopt']} {p['keylen']}\n" for p in pcbs)


def entry_using(source: str) -> list[str] | None:
    """The PCBs the program names at ENTRY 'DLITCBL' (IMS enters a COBOL DL/I program there), else None."""
    code = "\n".join(line[6:72] for line in source.splitlines() if len(line) > 6 and line[6] not in "*/")
    m = re.search(r"\bENTRY\s+['\"]DLITCBL['\"]\s*(?:USING\s+(.*?))?\.", code, re.I | re.S)
    if not m:
        return None
    words = [w.upper() for w in (m.group(1) or "").split()]
    return [w for w in words if w not in ("BY", "REFERENCE")]


def stage(case: dict[str, Any], corpus: Path, source: str, dest: Path) -> list[dict[str, Any]]:
    """Write dbd.cfg, psb.cfg and the seeds into `dest` (both sides read them); the PSB's DB PCBs."""
    dbds, pcbs = definitions(case, corpus)
    using = entry_using(source)
    if using is None:
        raise Unsupported(f"{case['program']}: no ENTRY 'DLITCBL' (a BMP / MPP or CICS DL/I program is not modelled)")
    if len(using) != len(pcbs):
        raise Unsupported(f"{case['program']}: ENTRY 'DLITCBL' names {len(using)} PCBs, the PSB has {len(pcbs)}")
    dest.mkdir(parents=True, exist_ok=True)
    dbd_cfg, psb_cfg = config(dbds, pcbs)
    (dest / "dbd.cfg").write_text(dbd_cfg, encoding="ascii")
    (dest / "psb.cfg").write_text(psb_cfg, encoding="ascii")
    for name, db in dbds.items():
        (dest / f"seed.{name}").write_bytes(seed(case, corpus, name, db))
    return pcbs


def cobol_driver(program_entry: str, pcbs: list[dict[str, Any]]) -> list[str]:
    """The driver's lines: each PCB an area of its own, bound (GGDLINIT), the program entered at `program_entry`
    with them, the databases written (GGDLIEND) -- the step's RETURN-CODE kept across that last CALL."""
    areas = [f"PCB-{i + 1}" for i in range(len(pcbs))]
    using = " ".join(areas)
    return [
        "IDENTIFICATION DIVISION.", "PROGRAM-ID. EQDRIVER.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
        *[f"01  {a} PIC X({AREA}) VALUE LOW-VALUES." for a in areas],
        "01  GG-RC PIC S9(9) COMP-5.",
        "PROCEDURE DIVISION.", f"    CALL 'GGDLINIT' USING {using}", f"    CALL '{program_entry}' USING {using}",
        "    MOVE RETURN-CODE TO GG-RC", "    CALL 'GGDLIEND'", "    MOVE GG-RC TO RETURN-CODE", "    STOP RUN.",
    ]  # fmt: skip


def split(data: bytes, sizes: dict[str, int]) -> list[tuple[str, bytes]]:
    """A database file (seed or output) as [(segment, data)]."""
    out, i = [], 0
    while i + 8 <= len(data):
        name = data[i : i + 8].decode("ascii").rstrip()
        n = sizes.get(name)
        if n is None:
            raise ValueError(f"segment {name!r} at {i}: not in the DBD")
        out.append((name, data[i + 8 : i + 8 + n]))
        i += 8 + n
    return out


def diff_db(case: dict[str, Any], corpus: Path, name: str, cobol: bytes, java: bytes) -> dict[str, Any]:
    """One database on both sides: its segments paired in hierarchic sequence, each one's fields (its segment's
    layout, else its bytes) compared."""
    dbds, _ = definitions(case, corpus)
    sizes = {s["name"]: s["bytes"] for s in dbds[name]["segments"]}
    left, right = split(cobol, sizes), split(java, sizes)
    diffs: list[dict[str, Any]] = []
    enc = common.data_encoding(case)
    for k in range(max(len(left), len(right))):
        a = left[k] if k < len(left) else None
        b = right[k] if k < len(right) else None
        if a is None or b is None or a[0] != b[0]:
            diffs.append({"segment": k + 1, "cobol": a[0] if a else None, "java": b[0] if b else None})
            continue
        if a[1] == b[1]:
            continue
        layout = _layout(case, corpus, a[0])
        if layout is None:
            diffs.append({"segment": k + 1, "name": a[0], "cobol": a[1].hex(), "java": b[1].hex()})
            continue
        d = common.diff_records(a[1], b[1], len(a[1]), layout, case.get("code_page", "cp037"), enc)
        diffs.append({"segment": k + 1, "name": a[0], "diffs": d["diffs"]})
    records = max(len(left), len(right))
    return {"records": records, "equal": records - len(diffs), "filler_differs": 0, "diffs": diffs}
