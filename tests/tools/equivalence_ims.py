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
variable-length segments, a non-unique or missing sequence field, an I/O PCB (CMPAT=YES, TYPE=TP: IMS TM), PROCSEQ (a
secondary index), a PROCOPT with L beside other options, segment-level PROCOPT and partial sensitivity. A DB PCB with PROCOPT L / LS
(#5233) is load mode: ISRT only, into an empty database no other PCB shares. A GSAM database
(#5233) is modelled as a load-mode output only: ACCESS=(GSAM,..) with fixed RECORD=(n), a TYPE=GSAM PCB with PROCOPT
LS, and ISRT; it takes `"gsam": {"<DBD>": {"copybook": ..., "record": ...}}` to compare its records by field.
`{"unload": ...}` reads an HD reorganization unload (DFSURGU0) of the corpus: its segments, EBCDIC, each laid out by
its copybook (`segments`) into the case's data page (text through CCSID 037, COMP / COMP-3 bytes as they are), its
trailer's segment counts checked.

A CICS scenario may state its own `"ims_seed": {"<DBD>": {"insert": [{"after": N, "segment": S, "fields": {F: v}}]}}`
(#6072): a segment of the DBD's unload seed inserted after its Nth record (the record numbers of the unload), a copy of
the `like` record (default: the one it follows) with the fields stated encoded by their PIC / USAGE. The sequence key
must stay unique and ascending among its neighbours; everything else is refused by name. The Java side then stages
that scenario's database in its own directory (`dli-<scenario>`).
A batch case's `faults` entry may state the same `ims_seed` (#6967): that run's COBOL side stages its own
`dli` directory and the Java run reads those very files.

Written for both sides into one directory (`stage`): dbd.cfg, psb.cfg and seed.<DBD> (tests/equivalence/ims/ggdli.c
documents the format); each side writes <DBD>.out, the database as the step left it, compared segment by segment
(`diff_db`) with every field of its segment's layout; a GSAM database's .out is its records, compared record by record.
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
import equivalence_inputs  # noqa: E402

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
    if access == "GSAM":  # #5233: a sequential file of fixed-length records, no hierarchy
        sets = [r for r in rows if r["kind"] == "DATASET"]
        rec = _keyed(sets[0]["attributes"], "RECORD") if len(sets) == 1 else None
        n = (rec or "").strip("()").split(",")[0]
        if not n.isdigit() or int(n) == 0 or (_keyed(sets[0]["attributes"], "RECFM") or "F") != "F":
            raise Unsupported(f"{where}: a GSAM database needs one DATASET with RECORD=(n) and RECFM=F (variable and "
                              "blocked formats are not modelled)")  # fmt: skip
        return {"name": db["name"].upper(), "gsam": int(n), "segments": []}
    if access not in ACCESS:
        raise Unsupported(f"{where}: ACCESS={access or '?'} (only {', '.join(ACCESS)}: the root sequence of an HDAM "
                          "database is its randomizer's, a GSAM / INDEX / LOGICAL database is no hierarchy here)")  # fmt: skip
    if re.search(r"(?im)^(?!\*)[^\s]*\s+XDFLD\s", text):  # ims_gen_macros drops XDFLD: read it off the source
        raise Unsupported(f"{where}: XDFLD (a secondary index) is not modelled")
    segs: list[dict[str, Any]] = []
    for r in rows:
        attrs = r["attributes"] or ""
        if r["kind"] == "LCHILD" and not re.search(r"POINTER\s*=\s*\(?\s*INDX?\b", attrs, re.I):
            raise Unsupported(
                f"{where}: LCHILD {r['name']} is not a primary index (a logical relationship: not modelled)"
            )
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


def psb(
    text: str, where: str, dbds: dict[str, dict[str, Any]], bmp: bool = False, cics: bool = False
) -> list[dict[str, Any]]:
    """The PSB's DB PCBs, in order: [{dbd, procopt, keylen}]; an I/O PCB, or what else is not modelled,
    refused. `bmp`: the program is a BMP (#5857), which IMS enters with the I/O PCB first (CMPAT=YES): required then,
    and refused otherwise. `cics`: EXEC DLI numbers the DB PCBs from 1 (no I/O PCB first), so CMPAT=YES changes nothing
    (I5 ASSUMPTION, no IBM text cited)."""
    rows = ims_gen_macros(text)
    gen = next((r for r in rows if r["kind"] == "PSBGEN"), None)
    if gen is None:
        raise Unsupported(f"{where}: no PSBGEN statement")
    compat = (_keyed(gen["attributes"], "CMPAT") or "NO") == "YES"
    if compat and not bmp and not cics:
        raise Unsupported(f"{where}: CMPAT=YES (IMS passes an I/O PCB first: only a BMP entered USING its I/O PCB "
                          "is modelled)")  # fmt: skip
    if bmp and not compat:
        raise Unsupported(f"{where}: a BMP is entered with the I/O PCB first, which needs CMPAT=YES")
    pcbs: list[dict[str, Any]] = []
    for r in rows:
        attrs = r["attributes"] or ""
        if r["kind"] == "PCB":
            if (r["pcb_type"] or "").upper() == "GSAM":  # #5233: load mode (LS), ISRT only
                name = (r["dbd_name"] or "").upper()
                if not dbds.get(name, {}).get("gsam"):
                    raise Unsupported(f"{where}: PCB {r['name']}: GSAM DBD {name} is not one of the case's DBDs")
                if (r["procopt"] or "").upper() != "LS":
                    raise Unsupported(f"{where}: PCB {r['name']}: GSAM PROCOPT={r['procopt']} (only LS, load mode, "
                                      "is modelled: reading a GSAM file is not)")  # fmt: skip
                pcbs.append({"dbd": name, "procopt": "LS", "keylen": 0, "gsam": dbds[name]["gsam"], "sensegs": []})
                continue
            if (r["pcb_type"] or "").upper() != "DB":
                raise Unsupported(f"{where}: a TYPE={r['pcb_type']} PCB (an I/O or alternate PCB: not modelled)")
            if _keyed(attrs, "PROCSEQ"):
                raise Unsupported(f"{where}: PCB {r['name']}: PROCSEQ (a secondary index) is not modelled")
            procopt = (r["procopt"] or "A").upper()
            if "L" in procopt and procopt not in ("L", "LS"):
                raise Unsupported(f"{where}: PCB {r['name']}: PROCOPT={procopt} (load mode with another option is not "
                                  "modelled: only L / LS alone)")  # fmt: skip
            if "L" in procopt and cics:
                raise Unsupported(f"{where}: PCB {r['name']}: PROCOPT={procopt} (load mode under CICS is not modelled)")
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
        if p.get("gsam"):
            continue
        if p["procopt"] in ("L", "LS") and sum(q.get("dbd") == p["dbd"] for q in pcbs) > 1:
            raise Unsupported(f"{where}: a load-mode PCB on {p['dbd']} beside another PCB on it (the database is "
                              "empty until the load ends: not modelled)")  # fmt: skip
        every = [s["name"] for s in dbds[p["dbd"]]["segments"]]
        if sorted(p["sensegs"]) != sorted(every):
            raise Unsupported(f"{where}: a PCB on {p['dbd']} sensitive to {p['sensegs']}, not to every segment "
                              "(partial sensitivity is not modelled)")  # fmt: skip
    return pcbs


def dbd_definitions(case: dict[str, Any], corpus: Path) -> dict[str, dict[str, Any]]:
    """The case's DBDs by name (the PSB, which depends on how the program is entered, not read)."""
    dbds: dict[str, dict[str, Any]] = {}
    for rel in case["ims"]["dbd"]:
        d = dbd((corpus / rel).read_text(encoding="latin-1"), rel)
        dbds[d["name"]] = d
    return dbds


def definitions(
    case: dict[str, Any], corpus: Path, bmp: bool = False, cics: bool = False
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    ims = case["ims"]
    dbds = dbd_definitions(case, corpus)
    return dbds, psb((corpus / ims["psb"]).read_text(encoding="latin-1"), ims["psb"], dbds, bmp, cics)


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


def _insert(
    entries: list[tuple[int, str, bytes]],
    ins: dict[str, Any],
    case: dict[str, Any],
    corpus: Path,
    db: dict[str, Any],
    sizes: dict[str, int],
    enc: str,
) -> None:
    """#6072: one scenario-stated segment, placed in `entries` ((unload record number, segment, data)) after record
    `after`. It is the record `like` (default `after`) with the `fields` stated, each written as its PICTURE says
    (a digit field wants a number, a text field text). Refused by name when the place or a field is not there, or
    when its sequence key would not stay unique and ascending among the neighbours of its own type."""
    seg = ins["segment"]
    if seg not in sizes:
        raise Unsupported(f"ims_seed: segment {seg} is not in DBD {db['name']}")
    at = next((i for i, e in enumerate(entries) if e[0] == ins["after"]), None)
    if at is None:
        raise Unsupported(f"ims_seed: no unload record {ins['after']} to insert after (a skipped record has none)")
    src = next((e for e in entries if e[0] == ins.get("like", ins["after"])), None)
    if src is None or src[1] != seg:
        raise Unsupported(f"ims_seed: the record to copy ({ins.get('like', ins['after'])}) is not a {seg} segment")
    layout = {f["name"]: f for f in (_layout(case, corpus, seg) or [])}
    data = bytearray(src[2])
    for fname, value in ins.get("fields", {}).items():
        f = layout.get(fname)
        if f is None:
            raise Unsupported(f"ims_seed: segment {seg} has no field {fname} in its copybook")
        data[f["offset"] : f["offset"] + f["bytes"]] = equivalence_inputs.encode_field(
            value, f["pic"], f["usage"], f["bytes"], common.sign_page(enc), enc)  # fmt: skip
    key = next((f for f in next(s for s in db["segments"] if s["name"] == seg)["fields"] if f["seq"]), None)
    if key is not None:

        def k(b: bytes) -> bytes:
            return b[key["start"] - 1 : key["start"] - 1 + key["bytes"]]

        before = entries[at][2] if entries[at][1] == seg else None
        after = entries[at + 1][2] if at + 1 < len(entries) and entries[at + 1][1] == seg else None
        if (before is not None and k(bytes(data)) <= k(before)) or (after is not None and k(bytes(data)) >= k(after)):
            raise Unsupported(f"ims_seed: the {seg} sequence key {key['name']} would not stay unique and ascending "
                              f"after record {ins['after']}")  # fmt: skip
    entries.insert(at + 1, (-1 - len(entries), seg, bytes(data)))


def check_seed_names(scenario: dict[str, Any] | None, dbds: dict[str, dict[str, Any]]) -> None:
    """#6967: an `ims_seed` naming a DBD the case does not have would be ignored: refused by name instead."""
    for name in (scenario or {}).get("ims_seed") or {}:
        if name not in dbds:
            raise Unsupported(f"ims_seed: DBD {name} is not in the case (it has {sorted(dbds)})")


def seed(case: dict[str, Any], corpus: Path, name: str, db: dict[str, Any],
         scenario: dict[str, Any] | None = None) -> bytes:  # fmt: skip
    """One database's seed, in the format both sides read (8-byte segment name, then its data). #6072: a scenario's
    `"ims_seed": {"<DBD>": {"insert": [{"after": N, "segment": S, "like": M, "fields": {...}}]}}` adds segments to an
    unload seed (N, M: unload record numbers, as `skip` counts them), for the task of that scenario only."""
    spec = case["ims"].get("seed", {}).get(name)
    over = ((scenario or {}).get("ims_seed") or {}).get(name)
    if not spec:
        if over:
            raise Unsupported(f"ims_seed: DBD {name} has no seed to add to")
        return b""
    enc = common.data_encoding(case)
    sizes = {s["name"]: s["bytes"] for s in db["segments"]}
    out = bytearray()
    if "unload" in spec:
        layouts: dict[str, list[dict[str, Any]]] = {}
        skip = set(spec.get("skip", []))  # record numbers left out (a root whose packed key is blank: GU would refuse)
        entries: list[tuple[int, str, bytes]] = []
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
            entries.append((n, seg, from_ebcdic(data[: sizes[seg]].ljust(sizes[seg], b"\x40"), layouts[seg], enc)))
        for ins in (over or {}).get("insert", []):
            _insert(entries, ins, case, corpus, {**db, "name": name}, sizes, enc)
        for _, seg, data in entries:
            out += seg.ljust(8).encode("ascii") + data
        return bytes(out)
    if over:
        raise Unsupported(f"ims_seed: DBD {name}'s seed is stated segments, not an unload: nothing to insert into")
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
        if db.get("gsam"):  # no hierarchy: only its PCB's GSAM line names it
            continue
        lines.append(f"DBD {name}")
        for s in db["segments"]:
            lines.append(f"SEGM {name} {s['name']} {s['parent']} {s['bytes']}")
        for s in db["segments"]:
            for f in s["fields"]:
                lines.append(f"FIELD {name} {s['name']} {f['name']} {f['start']} {f['bytes']} {f['type']} "
                             f"{'S' if f['seq'] else '-'}")  # fmt: skip
    return "\n".join(lines) + "\n", "".join(
        f"GSAM {p['dbd']} {p['procopt']} {p['gsam']}\n"
        if p.get("gsam")
        else f"PCB {p['dbd']} {p['procopt']} {p['keylen']}\n"
        for p in pcbs
    )


def entry_using(source: str) -> list[str] | None:
    """The PCBs the program names at ENTRY 'DLITCBL' (IMS enters a COBOL DL/I program there), else None."""
    code = "\n".join(line[6:72] for line in source.splitlines() if len(line) > 6 and line[6] not in "*/")
    m = re.search(r"\bENTRY\s+['\"]DLITCBL['\"]\s*(?:USING\s+(.*?))?\.", code, re.I | re.S)
    if not m:
        return None
    words = [w.upper() for w in (m.group(1) or "").split()]
    return [w for w in words if w not in ("BY", "REFERENCE")]


def _code(source: str) -> str:
    return "\n".join(line[6:72] for line in source.splitlines() if len(line) > 6 and line[6] not in "*/")


def bmp_using(source: str) -> list[str] | None:
    """#5857 (register I5): the items of a BMP's PROCEDURE DIVISION USING (the I/O PCB first, then the DB PCBs) -- a
    program that issues EXEC DLI or CALL 'CBLTDLI' and has no ENTRY 'DLITCBL', or (#5233, PAUDBLOD) whose ENTRY lists
    exactly the header's USING minus the leading I/O PCB (IMS enters a BMP at the header) -- else None."""
    code = _code(source)
    if not re.search(r"\bEXEC\s+DLI\b|\bCALL\s+['\"]CBLTDLI['\"]", code, re.I):
        return None
    m = re.search(r"\bPROCEDURE\s+DIVISION\s+USING\s+(.*?)\.", code, re.I | re.S)
    if not m:
        return None
    head = [w for w in (x.upper() for x in m.group(1).split()) if w not in ("BY", "REFERENCE")]
    entry = entry_using(source)
    if entry is not None and not (entry and len(head) == len(entry) + 1 and head[1:] == entry):
        return None
    return head


def stage(case: dict[str, Any], corpus: Path, source: str, dest: Path,
          scenario: dict[str, Any] | None = None) -> list[dict[str, Any]]:  # fmt: skip
    """Write dbd.cfg, psb.cfg and the seeds into `dest` (both sides read them); the PSB's DB PCBs. #6967: a batch
    run (a fault entry) may state its own `ims_seed`, as a CICS scenario does."""
    bmp = bmp_using(source)
    dbds, pcbs = definitions(case, corpus, bmp is not None)
    check_seed_names(scenario, dbds)
    using = entry_using(source) if bmp is None else bmp[1:]
    if using is None or (bmp is not None and len(bmp) < 2):
        raise Unsupported(f"{case['program']}: no ENTRY 'DLITCBL' and not a BMP entered USING its I/O PCB and DB "
                          "PCBs (an MPP or CICS DL/I program is not modelled)")  # fmt: skip
    if len(using) != len(pcbs):
        raise Unsupported(f"{case['program']}: {'PROCEDURE DIVISION USING' if bmp else 'ENTRY DLITCBL'} names "
                          f"{len(using)} DB PCBs, the PSB has {len(pcbs)}")  # fmt: skip
    dest.mkdir(parents=True, exist_ok=True)
    dbd_cfg, psb_cfg = config(dbds, pcbs)
    (dest / "dbd.cfg").write_text(dbd_cfg, encoding="ascii")
    (dest / "psb.cfg").write_text(psb_cfg, encoding="ascii")
    for name, db in dbds.items():
        if db.get("gsam"):  # load mode: nothing to seed
            continue
        (dest / f"seed.{name}").write_bytes(seed(case, corpus, name, db, scenario))
    return pcbs


def cobol_driver(program_entry: str, pcbs: list[dict[str, Any]], io: bool = False) -> list[str]:
    """The driver's lines: each PCB an area of its own, bound (GGDLINIT), the program entered at `program_entry`
    with them, the databases written (GGDLIEND) -- the step's RETURN-CODE kept across that last CALL. `io` (#5857): a
    BMP, its I/O PCB's area first (GGDLIBMP binds the DB PCBs after it)."""
    areas = [f"PCB-{i + 1}" for i in range(len(pcbs))]
    if io:
        areas.insert(0, "PCB-IO")
    using = " ".join(areas)
    return [
        "IDENTIFICATION DIVISION.", "PROGRAM-ID. EQDRIVER.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
        *[f"01  {a} PIC X({AREA}) VALUE LOW-VALUES." for a in areas],
        "01  GG-RC PIC S9(9) COMP-5.",
        "PROCEDURE DIVISION.", f"    CALL '{'GGDLIBMP' if io else 'GGDLINIT'}' USING {using}", f"    CALL '{program_entry}' USING {using}",
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
    dbds = dbd_definitions(case, corpus)
    if dbds[name].get("gsam"):
        return diff_gsam(case, corpus, name, dbds[name]["gsam"], cobol, java)
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


def diff_gsam(case: dict[str, Any], corpus: Path, name: str, reclen: int, cobol: bytes, java: bytes) -> dict[str, Any]:
    """#5233: a GSAM database's .out is its fixed-length records, in the order ISRT appended them; paired by position,
    each compared by its copybook's fields when the case names one (`ims.gsam`), else by bytes."""
    if len(cobol) % reclen or len(java) % reclen:
        raise Unsupported(f"GSAM {name}: output is not a whole number of {reclen}-byte records")
    left = [cobol[i : i + reclen] for i in range(0, len(cobol), reclen)]
    right = [java[i : i + reclen] for i in range(0, len(java), reclen)]
    spec = case["ims"].get("gsam", {}).get(name)
    layout = None
    if spec:
        dirs = [corpus / d for d in case.get("copy_dirs", [])]
        layout = common.layout_fields(corpus, spec["copybook"], spec.get("record"), copy_dirs=[*dirs, corpus],
                                      occurrences=True)  # fmt: skip
    diffs: list[dict[str, Any]] = []
    enc = common.data_encoding(case)
    for k in range(max(len(left), len(right))):
        a = left[k] if k < len(left) else None
        b = right[k] if k < len(right) else None
        if a is None or b is None:
            diffs.append({"segment": k + 1, "cobol": a.hex() if a else None, "java": b.hex() if b else None})
        elif a != b:
            if layout is None:
                diffs.append({"segment": k + 1, "cobol": a.hex(), "java": b.hex()})
            else:
                d = common.diff_records(a, b, reclen, layout, case.get("code_page", "cp037"), enc)
                diffs.append({"segment": k + 1, "diffs": d["diffs"]})
    records = max(len(left), len(right))
    return {"records": records, "equal": records - len(diffs), "filler_differs": 0, "diffs": diffs}


def rewrite_bmp(source: str) -> str:
    """#5857 (register I5): a BMP's EXEC DLI -> the CALLs of ggdli.c (GGDLIX as under CICS, GGDLICHKP for CHKP
    ID(area)), IBM's DIB (DIBSTAT only) supplied. Any other form is refused by name, as the det translator does."""
    import equivalence_cics as ec

    from gitgalaxy.tools.cobol_to_java.det import dli
    from gitgalaxy.tools.cobol_to_java.det.gen import Untranslatable

    lines = source.splitlines()
    out: list[str] = []
    problems: list[str] = []
    at = 0
    try:
        blocks = list(ec._exec_blocks(lines))
    except ec.Unsupported as e:
        raise Unsupported(str(e)) from e
    for i, j, prefix, body, suffix in blocks:
        out += lines[at:i]
        at = j + 1
        if prefix.strip():
            out.append(lines[i][:7] + prefix.rstrip())
        text = body[len(ec._DLI_TAG) :].strip() if body.startswith(ec._DLI_TAG) else ""
        try:
            if not text:
                raise Unsupported("EXEC CICS in a batch program")
            if text.split()[0].upper() == "CHKP":
                try:
                    cl = dli._clauses(text.split(None, 1)[1] if len(text.split()) > 1 else "")
                except Untranslatable as e:
                    raise Unsupported(str(e)) from None
                ident = cl[0][1].strip() if len(cl) == 1 and cl[0][0] == "ID" else ""
                if not re.fullmatch(r"[A-Za-z0-9-]*[A-Za-z][A-Za-z0-9-]*", ident):
                    raise Unsupported("EXEC DLI CHKP: only ID(data name) is modelled (register I5)")
                stmts = ["CALL 'GGDLICHKP' USING BY REFERENCE DIBSTAT",
                         f"    BY REFERENCE {ident}",
                         f"    BY VALUE LENGTH OF {ident}"]  # fmt: skip
            else:
                try:
                    stmts = ec.translate_dli(text)
                except ec.Unsupported as e:
                    raise Unsupported(str(e)) from None
        except Unsupported as e:
            problems.append(f"line {i + 1}: {e}")
            stmts = []
        for s in stmts:
            if len(ec._AREA_B) + len(s) > 72:
                raise Unsupported(f"line {i + 1}: generated statement too long: {s}")
            out.append(ec._AREA_B + s)
        if suffix.strip():
            out.append(ec._AREA_B + suffix.strip())
    out += lines[at:]
    if problems:
        raise Unsupported("; ".join(problems))
    text = "\n".join(out) + "\n"
    text, n = re.subn(r"^(.{6} +WORKING-STORAGE\s+SECTION\.[^\n]*\n)", lambda m: m.group(1) + ec._DIB, text,
                      count=1, flags=re.M | re.I)  # fmt: skip
    if n != 1:
        raise Unsupported("no WORKING-STORAGE SECTION to hold the DIB")
    return text
