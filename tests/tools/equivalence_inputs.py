"""
#3804: the equivalence harness's inputs, generated from record layouts.

Most estates ship no data, and one sample file reaches only the paths its records do. A
dataset whose case says `"input": "@generate"` is built from its copybook record instead --
the same layout the diff reads (equivalence.layout_fields) -- deterministically (a seed),
with each field's values chosen for its storage:

* text: letters and digits at full width, a short value, and blanks; #3821: with
  `"alphabet": "mixed"`, also lower case, national letters and punctuation -- the keys and
  values whose order and comparisons differ between collations and locales;
* #4035: with `"collation": true` in a dataset's `generate`, a text field the program compares as alphanumeric (an
  alphanumeric relation condition from relation_facts, or a level-88 THRU range over it; collation_operands) takes
  values on the EBCDIC / ASCII disagreement (boundary_values): digit against letter, lower against upper case, trailing
  blanks, LOW- / HIGH-VALUES and the literals it is compared with, so a `String.compareTo` port fails the diff;
* numeric DISPLAY / COMP-3 / COMP: zero, one, the PICTURE's maximum and its negative
  where signed, the smallest fraction at its scale, exact halves (2.5, 0.5, 0.05 ...: the ties
  where ROUNDED modes differ, #3825), and values in between;
* a date-shaped text field (named *DATE*, ten bytes): a valid YYYY-MM-DD; #3829: a field whose name
  has a date word in another language as one of its parts (DATUM, FECHA, DATA, DATO, TARIKH ...),
  or an English DATE part, of eight or six bytes: a valid YYYYMMDD / YYMMDD.

A case steers what the program must meet:

    "generate": {"copybook": "app/cpy/CVACT01Y.cpy", "record": "ACCOUNT-RECORD", "records": 40, "seed": 7,
                 "fields": {"ACCT-GROUP-ID": {"values": ["A000000000", "DEFAULT"]},
                            "DIS-TRAN-TYPE-CD": {"values": ["01", "02"], "every": 3},
                            "ROOT-SEG-KEY": {"hex": ["10000000001C", "1000000000AC"]},   # raw bytes, a COMP-3 not NUMERIC
                            "XREF-ACCT-ID": {"from": "ACCTFILE.ACCT-ID", "miss": 0.1},
                            "KTO-DATUM": {"date": "DD.MM.YYYY"}}}

`"digits": true` fills a text field with digits only -- a card number, an account id kept as text -- which its
PICTURE (X) cannot say. `date` (#3829) gives a field valid dates in a shape -- YYYY, YY, MM and DD, anything else literal --
text or numeric (`PIC 9(8)` as DDMMYYYY), whatever the field is called; its width must be the field's.
`hex` (#6072) writes a field's raw bytes, cycled as `values` (with `every`): a value no PICTURE can say, such as
a COMP-3 with a bad digit nibble for an IS NUMERIC false arm; each must be the field's width.
`from` draws a field from another dataset's values (generated first), so a join finds its
row -- and, with `miss`, sometimes does not, so the not-found path runs too. The primary key
(the case's first `keys` entry) is unique, and an indexed dataset is written in key order,
as a KSDS loads.

CICS cases (#3804; prepare_cics_case): a dataset `@generate`d takes its record length and key from the
program's CICS file, and a `scenario_generate` block makes scenarios whose COMMAREA and map input come from the
same layouts -- a typed account id that is on file, is not, or is not a number at all.
"""

from __future__ import annotations

import functools
import random
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import equivalence_common as common


def encode_field(
    value: Any,
    pic: str | None,
    usage: str | None,
    nbytes: int,
    code_page: str = "cp037",
    data_encoding: str = common.DEFAULT_DATA_ENCODING,
) -> bytes:
    """A value as the field stores it -- the inverse of equivalence.decode_field. #3815: text and zoned
    digits in `data_encoding` (the zoned sign from `code_page`'s table, as the generated CobolRecords)."""
    if (usage or "").upper() == "POINTER" and not pic:  # #4270 (C9): NULL only -- an address is not portable
        if value is None or str(value).strip() in ("", common.POINTER_NULL):
            return bytes(nbytes)
        raise ValueError(
            f"a POINTER can only be given as {common.POINTER_NULL!r} (an address is not portable): {value!r}"
        )
    num = common._pic_numeric(pic) if pic else None
    if num is None:
        return common.text_bytes(str(value), nbytes, data_encoding)
    signed, digits, scale = num
    n = int((Decimal(str(value)) * (Decimal(10) ** scale)).to_integral_value())
    u = (usage or "DISPLAY").upper()
    if u in ("COMP-3", "PACKED-DECIMAL", "COMPUTATIONAL-3"):
        body = f"{abs(n):0{nbytes * 2 - 1}d}"[-(nbytes * 2 - 1) :]
        return bytes.fromhex(body + ("d" if n < 0 else ("c" if signed else "f")))
    if u in ("COMP", "COMP-4", "COMP-5", "BINARY", "COMPUTATIONAL", "COMPUTATIONAL-4", "COMPUTATIONAL-5"):
        return n.to_bytes(nbytes, "big", signed=signed)
    text = f"{abs(n):0{digits}d}"[-digits:]
    if signed:
        last = int(text[-1])
        from gitgalaxy.tools.cobol_to_java.java_target import zoned_sign_characters

        pos, neg = zoned_sign_characters(code_page)
        text = text[:-1] + (neg[last] if n < 0 else pos[last])
    return text.encode(data_encoding)


def _numeric_value(rng: random.Random, signed: bool, digits: int, scale: int, row: int) -> Decimal:
    """Edge values first (zero, one, the maximum, its negative, the smallest fraction), then spread."""
    top = Decimal(10) ** (digits - scale) - Decimal(1).scaleb(-scale)  # 999.99 for 9(3)V99
    tiny = Decimal(1).scaleb(-scale) if scale else Decimal(1)
    edges = [Decimal(0), Decimal(1) if digits - scale > 0 else tiny, top, tiny]
    if signed:
        edges += [-top, -tiny]
    # #3825: exact halves, so a ROUNDED result meets a tie -- half away from zero (3 / -3) and banker's
    # rounding (2 / -2) part company only there: 2.5 and 0.5 at the whole-number digit, 5 at the last one
    ties = [t for t in (Decimal("2.5"), Decimal("0.5"), Decimal(5).scaleb(-scale)) if scale and t <= top]
    edges += [v for t in dict.fromkeys(ties) for v in ((t, -t) if signed else (t,))]
    if row < len(edges):
        return edges[row]
    whole = rng.randint(0, 10 ** min(digits - scale, 9) - 1) if digits > scale else 0
    frac = Decimal(rng.randint(0, 10**scale - 1)).scaleb(-scale) if scale else Decimal(0)
    v = Decimal(whole) + frac
    return -v if signed and rng.random() < 0.3 else v


_TEXT = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
# #3821: `"alphabet": "mixed"` -- what makes key order and comparisons culture-sensitive: lower case, national
# letters (ISO-8859-1, as the inputs are written by default; #3815: in the case's data_encoding) and
# punctuation, beside the upper case and digits
_MIXED = _TEXT + "abcdefghijklmnopqrstuvwxyz" + "ÆØÅæøåÄÖÜäöüßÉéÑñÇç" + " -.&/#@$"
# #3829: "date" in the languages mainframe estates are written in -- de/nl/sv/no, es, pt/it/pl, da/no, ms/hi,
# ja (romanised), vi -- matched as a whole part of a hyphenated name (WS-FECHA-ALTA, DATUM-VON), never inside
# a word (CANDIDATE, UPDATE-FLAG, KDATO)
_DATE_WORDS = frozenset({"DATE", "DATUM", "FECHA", "DATA", "DATO", "TARIKH", "HIZUKE", "NGAY"})
_DATE_SHAPES = {10: "YYYY-MM-DD", 8: "YYYYMMDD", 6: "YYMMDD"}
_DATE_TOKEN = re.compile(r"YYYY|YY|MM|DD")


def date_value(rng: random.Random, fmt: str) -> str:
    """#3829: a valid date in `fmt` (YYYY, YY, MM, DD; any other character is literal), days 1-28."""
    y, m, d = rng.randint(1990, 2030), rng.randint(1, 12), rng.randint(1, 28)
    parts = {"YYYY": f"{y:04d}", "YY": f"{y % 100:02d}", "MM": f"{m:02d}", "DD": f"{d:02d}"}
    return _DATE_TOKEN.sub(lambda t: parts[t.group(0)], fmt)


def _date_shape(name: str, nbytes: int) -> str | None:
    """The date shape a text field's name and width imply, or None."""
    upper = name.upper()
    if "DATE" in upper and nbytes == 10:  # the English rule of old, kept byte-identical (#3804)
        return _DATE_SHAPES[10]
    if nbytes in _DATE_SHAPES and _DATE_WORDS & set(upper.split("-")):
        return _DATE_SHAPES[nbytes]
    return None


def _text_value(rng: random.Random, name: str, nbytes: int, row: int, alphabet: str = _TEXT) -> str:
    shape = _date_shape(name, nbytes)
    if shape:
        return date_value(rng, shape)
    if row % 7 == 3:
        return ""  # blanks: the field INITIALIZEd / never filled
    width = nbytes if row % 3 else max(1, nbytes // 2)
    return "".join(rng.choice(alphabet) for _ in range(width))


def field_value(rng: random.Random, f: dict[str, Any], row: int, alphabet: str = _TEXT) -> Any:
    if f.get("usage") == "POINTER" and not f.get("pic"):  # #4270 (C9): NULL, the only value both sides can hold
        return common.POINTER_NULL
    num = common._pic_numeric(f["pic"]) if f.get("pic") else None
    if num is None:
        return _text_value(rng, f["name"], f["bytes"], row, alphabet)
    signed, digits, scale = num
    return _numeric_value(rng, signed, digits, scale, row)


def _cp037(ch: str) -> bytes:
    try:
        return ch.encode("cp037")
    except UnicodeEncodeError:
        return b"\x6f"  # '?'


def ibm_key_order(key: bytes, data_encoding: str) -> tuple[bytes, bytes]:
    """#4876: the sort key of a record key held in `data_encoding`: its characters in code page 037 (z/OS's order, the
    letters before the digits); a character cp037 lacks is its '?', the bytes themselves break such a tie."""
    text = key.decode(data_encoding, errors="surrogateescape")  # lossless: a byte the page lacks stays a surrogate
    return b"".join(_cp037(ch) for ch in text), key


# ---- #4035: collation boundary values ---------------------------------------------------------------------------
# COBOL compares alphanumerics by the collating sequence (EBCDIC: lower case < upper < digits, LOW-VALUES lowest,
# HIGH-VALUES highest) after padding the shorter operand with spaces; String.compareTo orders them by UTF-16 units. A
# generated value rarely lands where the two disagree, so a field the program compares gets values on that boundary.
_COPY_NAME = re.compile(r"(?<![A-Z0-9-])COPY\s+([A-Z0-9#@$-]{1,64})", re.I)
_QUOTED = re.compile(r"""^[XxZz]?(['"])(.*)\1$""")


def _members(case: dict[str, Any], corpus: Path) -> dict[str, Path]:
    """{MEMBER: file} of the case's copy_dirs, the member name upper-case and without its suffix."""
    found: dict[str, Path] = {}
    for d in case.get("copy_dirs", []):
        for p in sorted((corpus / d).iterdir()):
            if p.is_file() and p.suffix.lower() != ".bms":
                found.setdefault(p.stem.upper(), p)
    return found


def collation_operands(case: dict[str, Any], corpus: Path) -> dict[str, list[str]]:
    """{FIELD: the literals it is compared with} for every field the program compares as alphanumeric: an
    alphanumeric relation condition (relation_facts) naming it, and the level-88 THRU range endpoints over it.
    The program's COPY members (and theirs) give the operands their classes."""
    from gitgalaxy.core.relation_facts import condition_ranges, relation_facts

    text = common.read_program(case, corpus / case["program_source"])[0]
    members, books, seen, todo = _members(case, corpus), [], set(), [text]
    while todo and len(seen) < 500:
        for name in {m.group(1).upper() for m in _COPY_NAME.finditer(todo.pop())} - seen:
            seen.add(name)
            if name in members:
                books.append(common.read_program(case, members[name])[0])
                todo.append(books[-1])
    out: dict[str, list[str]] = {}

    def add(field: str, literal: str | None) -> None:
        lits = out.setdefault(field.upper(), [])
        if literal is not None and literal not in lits:
            lits.append(literal)

    def literal(operand: str) -> str | None:
        m = _QUOTED.match(operand.strip())
        return m.group(2) if m else None

    for r in relation_facts(text, books):
        if r["kind"] != "alphanumeric":
            continue
        for me, other in (("left", "right"), ("right", "left")):
            word = re.match(r"[A-Za-z0-9#@$-]+", r[me])
            if word and literal(r[me]) is None and r[me + "_class"] == "alphanumeric":
                add(word.group(0), literal(r[other]))
    for c in condition_ranges(text, books):
        for rng in c["ranges"]:
            for end in (rng["lo"], rng["hi"]):
                add(c["parent"], literal(end or ""))
    return out


def _edge_char(enc: str, byte: int) -> str | None:
    """The character `enc` stores as the single byte `byte` (HIGH-VALUES x'FF', LOW-VALUES x'00'), or None."""
    for code in (byte, 0x9F if byte == 0xFF else byte):
        ch = chr(code)
        try:
            if ch.encode(enc) == bytes([byte]):
                return ch
        except UnicodeEncodeError:
            continue
    return None


def boundary_values(nbytes: int, literals: list[str], enc: str = common.DEFAULT_DATA_ENCODING) -> list[str]:
    """Values for a text field of `nbytes` on the EBCDIC / ASCII disagreement: a digit and a letter in the same
    place, lower and upper case, a short value (the trailing blanks it is padded with), a blank field, LOW- and
    HIGH-VALUES, and for each literal compared with it the literal itself, its case swaps, a trailing blank, the
    next shorter prefix and its last character made a digit / a letter / a lower-case letter."""
    cands = ["A", "a", "Z", "z", "0", "1", "9", "A1", "1A", "Aa", "aA", "A" * nbytes, "a" * nbytes, "0" * nbytes,
             "9" * nbytes, "Z" * nbytes, "9" + "Z" * nbytes, "Z" + "9" * nbytes, ""]  # fmt: skip
    for byte in (0x00, 0xFF):
        edge = _edge_char(enc, byte)
        if edge:
            cands += [edge * nbytes, "A" + edge * nbytes]
    for lit in literals:
        cands += [lit, lit.lower(), lit.upper(), lit + " ", lit[:-1]]
        for tail in ("0", "9", "A", "Z", "a"):
            cands.append(lit[:-1] + tail)
            cands.append(lit + tail)
    out: list[str] = []
    for c in cands:
        try:
            padded = common.text_bytes(c, nbytes, enc)
        except UnicodeEncodeError:
            continue
        v = padded.decode(enc)  # one value per stored bytes (a cut-off or padded duplicate drops)
        if v not in out:
            out.append(v)
    return out


def generate_dataset(
    name: str,
    spec: dict[str, Any],
    fields: list[dict[str, Any]],
    pools: dict[str, list[Any]],
    code_page: str = "cp037",
    data_encoding: str = common.DEFAULT_DATA_ENCODING,
    collation: dict[str, list[str]] | None = None,
) -> tuple[bytes, dict[str, list[Any]]]:
    """(the dataset's fixed-length records, {DD.FIELD: the values it holds} for later joins). #4035 `collation`
    ({FIELD: literals} from collation_operands; only with the dataset's `"collation": true`): a text field in it,
    not a key part and with no rule of the case's, takes boundary_values by row."""
    gen = spec["generate"]
    rng = random.Random(f"{gen.get('seed', 0)}:{name}")
    rules = gen.get("fields", {})
    alphabet = {"upper": _TEXT, "mixed": _MIXED}[gen.get("alphabet", "upper")]  # #3821
    reclen = spec["reclen"]
    key = (spec.get("keys") or [None])[0]
    boundary = {
        f["name"]: boundary_values(f["bytes"], collation[f["name"].upper()], data_encoding)
        for f in fields
        if gen.get("collation") and collation and f["name"].upper() in collation and f["name"] != "FILLER"
        and (not f.get("pic") or common._pic_numeric(f["pic"]) is None)
        and not _date_shape(f["name"], f["bytes"])  # a date keeps its valid shape (the `date` rule's job)
    }  # fmt: skip
    rows: list[bytes] = []
    seen: set[bytes] = set()
    values: dict[str, list[Any]] = {f"{name}.{f['name']}": [] for f in fields}
    attempts = 0
    while len(rows) < gen.get("records", 20):
        attempts += 1
        if attempts > gen.get("records", 20) * 50:
            raise ValueError(f"{name}: cannot make {gen.get('records')} records with a unique key")
        row, rec = len(rows), bytearray(" ".encode(data_encoding) * reclen)  # #3815: the page's space
        chosen: dict[str, Any] = {}
        for f in fields:
            rule = rules.get(f["name"], {})
            if "values" in rule:  # `every` k: the value changes each k rows (a cartesian fill)
                v = rule["values"][(row // rule.get("every", 1)) % len(rule["values"])]
            elif (
                "hex" in rule
            ):  # #6072: raw bytes (an invalid packed value for an IS NUMERIC test), `every` as `values`
                v = rule["hex"][(row // rule.get("every", 1)) % len(rule["hex"])]
                if len(bytes.fromhex(v)) != f["bytes"]:
                    raise ValueError(f"{name}.{f['name']}: hex {v!r} is not the field's {f['bytes']} bytes")
            elif rule.get("digits"):  # a text field that holds a number (a card number): digits only
                v = "".join(rng.choice("0123456789") for _ in range(f["bytes"]))
            elif "date" in rule:
                v = date_value(rng, rule["date"])
                if len(v) != f["bytes"]:
                    raise ValueError(f"{name}.{f['name']}: date format {rule['date']!r} is {len(v)} characters, "
                                     f"the field {f['bytes']} bytes")  # fmt: skip
                if f.get("pic") and common._pic_numeric(f["pic"]) is not None:
                    if not v.isdigit():
                        raise ValueError(f"{name}.{f['name']}: a numeric field takes digits only, not {rule['date']!r}")
                    v = Decimal(v)  # a numeric date field (PIC 9(8)): the digits as its number
            elif "from" in rule:
                pool = pools.get(rule["from"])
                if not pool:
                    raise ValueError(f"{name}.{f['name']}: nothing generated yet for {rule['from']}")
                v = rng.choice(pool)
                if rng.random() < rule.get("miss", 0):
                    v = field_value(rng, f, len(pool) + attempts, alphabet)  # a value the joined file does not hold
            elif f["name"] == "FILLER":
                v = ""  # unnamed padding: blanks, as the corpus files carry it
            elif key is not None and key["offset"] <= f["offset"] < key["offset"] + key["length"]:
                v = field_value(rng, f, 7 + row + attempts, alphabet)  # a key part: never blank, never an edge repeat
                if isinstance(v, str):
                    v = "".join(rng.choice(alphabet) for _ in range(f["bytes"]))
            elif f["name"] in boundary:  # #4035: the values the collating sequence orders differently
                v = boundary[f["name"]][(attempts - 1 + 3 * len(chosen)) % len(boundary[f["name"]])]
            else:
                v = field_value(rng, f, row if attempts == row + 1 else row + attempts, alphabet)
            chosen[f["name"]] = v
            rec[f["offset"] : f["offset"] + f["bytes"]] = (
                bytes.fromhex(v)
                if "hex" in rule
                else encode_field(v, f["pic"], f["usage"], f["bytes"], code_page, data_encoding)
            )
        if key is not None:
            k = bytes(rec[key["offset"] : key["offset"] + key["length"]])
            if k in seen:
                continue
            seen.add(k)
        rows.append(bytes(rec))
        for fname, v in chosen.items():
            values[f"{name}.{fname}"].append(v)
    if key is not None and spec.get("organization") == "indexed":
        # #4876: loaded in IBM's key order (cp037 of the key's characters), not the data page's byte order: GnuCOBOL's BDB
        # keeps a non-unique alternate key's duplicates in the order they are loaded (and orders its primary key by
        # bytes whatever the collating sequence), VSAM returns them in prime-key order, EBCDIC's. D1.
        rows.sort(key=lambda r: ibm_key_order(r[key["offset"] : key["offset"] + key["length"]], data_encoding))
    return b"".join(rows), values


def _order(datasets: dict[str, dict[str, Any]]) -> list[str]:
    """Generated datasets, each after the ones its `from` rules draw on."""
    deps = {
        dd: {r["from"].rsplit(".", 1)[0] for r in spec["generate"].get("fields", {}).values() if "from" in r}
        & set(datasets)  # (#4507: a `from` naming a generated Db2 column is no dataset to wait for)
        for dd, spec in datasets.items()
    }
    out: list[str] = []
    while len(out) < len(deps):
        ready = [dd for dd in deps if dd not in out and deps[dd] <= set(out)]
        if not ready:
            raise ValueError(f"generated inputs depend on each other in a cycle: {sorted(set(deps) - set(out))}")
        out += sorted(ready)
    return out


def generate_inputs(case: dict[str, Any], corpus: Path) -> dict[str, bytes]:
    """{dd: fixed-length records} for every dataset whose input is `@generate`."""
    return generate_all(case, corpus)[0]


def generate_all(case: dict[str, Any], corpus: Path) -> tuple[dict[str, bytes], dict[str, list[Any]]]:
    """(generate_inputs, {DD.FIELD: the values it holds}) -- the values a scenario's keys are drawn from."""
    todo = {dd: spec for dd, spec in case["datasets"].items() if spec.get("input") == "@generate"}
    import equivalence_db2

    # #4507: a dataset's `from` may name a generated Db2 column (SCHEMA.TABLE.COLUMN): a batch input that keys the table
    pools: dict[str, list[Any]] = dict(equivalence_db2.generated_pools(case, corpus)) if todo else {}
    # #4035: the fields the program compares as alphanumeric, read only when a dataset asks for their boundary values
    collation = collation_operands(case, corpus) if any(x["generate"].get("collation") for x in todo.values()) else None
    out: dict[str, bytes] = {}
    for dd in _order(todo):
        spec = todo[dd]
        # #5233: a COPY inside the record (PAUDBLOD's CIPAUSMY) resolves in the case's copy_dirs, after the file's own directory
        dirs = [
            (corpus / spec["generate"]["copybook"]).parent,
            *(corpus / d for d in case.get("copy_dirs", [])),
            corpus,
        ]
        fields = common.layout_fields(
            corpus, spec["generate"]["copybook"], spec["generate"].get("record"), copy_dirs=dirs
        )
        width = max(f["offset"] + f["bytes"] for f in fields)
        if width > spec["reclen"]:
            raise ValueError(f"{dd}: the layout is {width} bytes, wider than reclen {spec['reclen']}")
        out[dd], values = generate_dataset(
            dd, spec, fields, pools, case.get("code_page", "cp037"), common.data_encoding(case), collation
        )
        pools.update(values)
    return out, pools


# ---- CICS cases (#3804): files and scenarios generated from the layouts -------------------------------------
# what a user types into a field the program reads as a number, when it is not one
_BAD_TEXT = ("ABC", "1A2", "", "   ", "1 2", "-1", "1.5", "0", "*", "A", "00", "12345678901234567890", "O", "1,0")


def _typed(rng: random.Random, rule: dict[str, Any], width: int, pool: list[Any], i: int) -> str:
    """One generated line of typed map input: a value the file holds, one it does not, or not a number."""
    r = rng.random()
    if "values" in rule:
        return str(rule["values"][i % len(rule["values"])])
    if r < rule.get("bad", 0):
        bad = _BAD_TEXT[(i + int(r * 1000)) % len(_BAD_TEXT)]
        return bad[:width]
    numeric = all(isinstance(v, Decimal) for v in pool) if pool else True
    held = {str(int(v)) if isinstance(v, Decimal) else str(v).strip() for v in pool}
    if r < rule.get("bad", 0) + rule.get("miss", 0) or not pool:
        for _ in range(100):
            v = "".join(rng.choice("0123456789" if numeric else _TEXT) for _ in range(width))
            if (str(int(v)) if numeric else v.strip()) not in held:
                return v
        raise ValueError(f"no value of {width} characters is missing from the file")
    v = rng.choice(pool)
    return f"{int(v):0{width}d}" if isinstance(v, Decimal) else str(v)


_PICTURE_RUN = re.compile(r"([9X])(?:\((\d+)\))?")


def _picture(picin: str | None) -> tuple[int, bool] | None:
    """(width, digits only) of a DFHMDF PICIN such as `9(5)`, `999` or `X(10)`; None for no PICIN or one this does not
    read (V, S, Z, ... a picture the symbolic map's field then takes as plain text)."""
    text = (picin or "").strip().strip("'").upper()
    runs = list(_PICTURE_RUN.finditer(text))
    if not runs or "".join(r.group(0) for r in runs) != text:
        return None
    width = sum(int(r.group(2) or 1) for r in runs)
    return width, all(r.group(1) == "9" for r in runs)


@functools.lru_cache(maxsize=64)
def bms_input_fields(corpus: Path, map_name: str) -> dict[str, dict[str, Any]]:
    """#4506: {symbolic input field (<name>I): {"length", "numeric", "picture", "mdt"}} of the fields a user can type into on a
    BMS map, read from the corpus's BMS source (the engine's own reading, gitgalaxy.core.bms_screen_fields). Typable:
    named, not protected, and not repeated. A field with no ATTRB is ASKIP (the forge's `_attrs`, IBM DFHMDF), so is
    never typed; `mdt` is FSET (the map sends the field with its modified-data tag on, so a terminal always transmits it); ASKIP and PROT fields cannot be keyed into; an OCCURS field is not typed (`map_input` refuses it by
    name, "BMS OCCURS input"). A NUM field takes digits, and so does a PICIN of 9s (`_picture`), its length the
    narrower of the two."""
    from gitgalaxy.core.bms_screen_fields import bms_screen_fields
    from gitgalaxy.core.source_text import read_source
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_screen_forge import _attrs

    out: dict[str, dict[str, Any]] = {}
    for p in sorted(corpus.rglob("*.bms")):
        if ".git" in p.parts:
            continue
        rows = bms_screen_fields(read_source(p).text)
        maps = {r["ordinal"] for r in rows if r["kind"] == "map" and (r["name"] or "").upper() == map_name.upper()}
        for r in rows:
            if r["kind"] != "field" or r["parent_ordinal"] not in maps or not r["name"]:
                continue
            attrs = _attrs(r)
            if attrs & {"ASKIP", "PROT"} or (r.get("occurs") or 1) > 1 or not r.get("length"):
                continue
            pic = _picture(r.get("picin"))
            length = min(r["length"], pic[0]) if pic else r["length"]
            out[r["name"].upper() + "I"] = {"length": length, "numeric": "NUM" in attrs or bool(pic and pic[1]),
                                            "picture": r.get("picin"), "mdt": "FSET" in attrs}  # fmt: skip
    if not out:
        raise ValueError(f"{map_name}: no typable field in the BMS sources under {corpus}")
    return out


def _bms_value(rng: random.Random, f: dict[str, Any], i: int, bad: float) -> str:
    """One typed value for a BMS field (`bms_input_fields`): full width, short, or a random length in turn; digits for a
    NUM / 9-picture field, letters and digits otherwise; with share `bad`, text that is not a number."""
    width = f["length"]
    if rng.random() < bad:
        return _BAD_TEXT[(i + int(rng.random() * 1000)) % len(_BAD_TEXT)][:width]
    n = (width, max(1, width // 2), rng.randint(1, width))[i % 3]
    return "".join(rng.choice("0123456789" if f["numeric"] else _TEXT) for _ in range(n))


def _left_alone(rng: random.Random, rule: dict[str, Any], bms: dict[str, dict], fname: str) -> bool:
    """#4506: a field rule's `empty` share: the user left the field alone (an FSET field is then sent with length 0, any other
    omitted: X'00', length 0). The random draw is made only when the rule asks, so a rule without `empty` keeps its input."""
    return bool(rule.get("empty")) and bool(bms) and fname in bms and rng.random() < rule["empty"]


def _bms_receive(rng: random.Random, name: str, spec: Any, layout: dict[str, dict[str, Any]], bms: dict[str, dict],
                 pools: dict[str, list[Any]], i: int) -> dict[str, str]:  # fmt: skip
    """#4506: the map input of `"MAP": "@bms"` / `"MAP": {"@bms": {"bad": .., "empty": ..}, "FIELDI": rule}`: every typable
    BMS field gets a value, except an `empty` share of the scenarios (the user left it alone: no data, length 0; an unmodified
    field is not transmitted, so RECEIVE MAP leaves it X'00' with length 0 and flag X'00', but an FSET field's MDT is on, so
    it is transmitted with length 0: ASSUMED, X54);
    a field rule beside `@bms` (or None, never typed) replaces the generated one, as any `receive` rule does."""
    opts = (spec.get("@bms") or {}) if isinstance(spec, dict) else {}
    explicit = {k: v for k, v in spec.items() if k != "@bms"} if isinstance(spec, dict) else {}
    out: dict[str, str] = {}
    for fname, f in bms.items():
        if fname not in layout:  # the generated symbolic map does not hold it
            continue
        f = {**f, "length": min(f["length"], layout[fname]["bytes"])}
        if fname in explicit:
            continue
        value = _bms_value(rng, f, i, opts.get("bad", 0))
        if rng.random() >= opts.get("empty", 0):
            out[fname] = value
        elif f.get("mdt"):
            out[fname] = ""  # MDT on (FSET): transmitted though left alone, with no data (length 0)
    for fname, rule in explicit.items():
        if fname not in layout:
            raise ValueError(f"{name}: map has no input field {fname}")
        if rule is None:
            continue
        rule = rule if isinstance(rule, dict) else {"values": [rule]}
        if _left_alone(rng, rule, bms, fname):
            if bms.get(fname, {}).get("mdt"):
                out[fname] = ""
            continue
        out[fname] = _typed(rng, rule, layout[fname]["bytes"], pools.get(rule.get("from", ""), []), i)
    return out


def _missing(rng: random.Random, pool: list[Any], field: dict[str, Any] | None) -> Any:
    """#4507: a value like the pool's (digits when they are all digits; the field's width) that it does not hold."""
    held = {str(v).strip() for v in pool}
    numeric = all(isinstance(v, (int, Decimal)) or str(v).strip().isdigit() for v in pool)
    width = max(len(str(v)) for v in pool)
    if field is not None and field.get("bytes"):
        width = min(width, field["bytes"]) if not numeric else field["bytes"]
    for _ in range(200):
        v = "".join(rng.choice("0123456789" if numeric else _TEXT) for _ in range(width))
        if v.strip() not in held and (not numeric or str(int(v)) not in {str(int(h)) for h in held if h.isdigit()}):
            return v
    raise ValueError(f"no value of {width} characters is missing from the pool")


def prepare_cics_case(case: dict[str, Any], corpus: Path, files: list[dict[str, Any]]) -> dict[str, Any]:
    """A CICS case with its generated parts made concrete. A dataset whose input is `@generate` takes its
    record length and key from the program's CICS file (the stub's `files`); a `scenario_generate` block adds
    `count` scenarios whose COMMAREA and map input are generated the same way:

        "scenario_generate": {"seed": 7, "count": 16, "aid": "DFHENTER",
            "commarea": {"CDEMO-FROM-TRANID": "CAVW", "CDEMO-PGM-CONTEXT": 1},
            "receive": {"CACTVWA": {"ACCTSIDI": {"from": "AWS.ACCTDATA.ACCT-ID", "miss": 0.2, "bad": 0.25}}}}

    `"aid"` may be a list of keys, used in turn (#4506: PF3 / PF4 / an unassigned key reach the program's other branches).
    `"receive": {"MAP": "@bms"}` (#4506) types into every unprotected field the map's BMS source defines, by its length, NUM
    and PICIN (`{"@bms": {"bad": 0.2, "empty": 0.3}, "FIELDI": rule}` steers it; a rule beside it wins).
    A map field's rule gives what the user typed: a value `from` the generated file's field, one it does not hold
    (`miss`), or not a number (`bad`: letters, blanks, signs, a decimal point ...) -- as a share of the scenarios;
    or `values`, in turn. A COMMAREA field's rule is `values` / `edge` (the PICTURE's edge values, in turn) / `from` (it is a typed record: the port's DTO
    holds numbers there, so no non-numeric text). #4507: `from` may name a generated Db2 table's column
    (SCHEMA.TABLE.COLUMN, equivalence_db2.generate_rows), with `miss` (a share of values it does not hold) and
    `turn` (its values in turn)."""
    by_base = {f["base"]: f for f in files}
    datasets = {}
    for dd, spec in case.get("datasets", {}).items():
        if spec.get("input") == "@generate":
            f = by_base.get(dd)
            if f is None:
                raise ValueError(f"{dd}: generated, but the program has no CICS file with that dataset name")
            keyed = f["key_length"] > 0  # an ESDS has no key: its records are in arrival order
            spec = {"organization": "indexed" if keyed else "sequential", "reclen": f["reclen"],
                    "keys": [{"offset": f["key_offset"], "length": f["key_length"]}] if keyed else [], **spec}  # fmt: skip
        datasets[dd] = spec
    case = {**case, "datasets": datasets}
    gen = case.get("scenario_generate")
    if not gen:
        return case
    import equivalence_cics as cx

    _, pools = generate_all(case, corpus)
    import equivalence_db2

    pools = {**pools, **equivalence_db2.generated_pools(case, corpus)}  # #4507: a generated table's columns too
    ca_layout = {f["name"]: f for f in cx.commarea_fields(corpus, case)} if gen.get("commarea") else {}
    scenarios = []
    for i in range(gen.get("count", 12)):
        name = f"{gen.get('prefix', 'generated')}-{i + 1:02d}"
        rng = random.Random(f"{gen.get('seed', 0)}:{name}")
        aid = gen.get("aid", "DFHENTER")
        sc: dict[str, Any] = {
            "name": name,
            "aid": aid[i % len(aid)] if isinstance(aid, list) else aid,
            "generated": True,
        }
        if gen.get("commarea") is not None:
            commarea: dict[str, Any] = {}
            for fname, v in gen["commarea"].items():
                if isinstance(v, dict):
                    if "values" in v:
                        v = v["values"][i % len(v["values"])]
                    elif v.get("edge"):  # the field's own edge values by its PICTURE, in turn (field_value)
                        v = field_value(rng, ca_layout[fname], i)
                    elif "from" in v:
                        pool = pools.get(v["from"])
                        if not pool:
                            raise ValueError(f"{name}.{fname}: nothing generated for {v['from']}")
                        # #4507: `miss`, that share of the time a value the source does not hold (+100 for a
                        # SELECT / UPDATE / DELETE by it, -530 for an INSERT naming it as a parent); otherwise one
                        # it does (a duplicate key, -803, for an INSERT); `turn`: the source's values in turn (each
                        # generated row reached), not at random
                        if rng.random() < v.get("miss", 0):
                            v = _missing(rng, pool, ca_layout.get(fname))
                        else:
                            v = pool[i % len(pool)] if v.get("turn") else rng.choice(pool)
                    else:
                        raise ValueError(
                            f"{name}.{fname}: a COMMAREA rule is `values`, `edge` or `from`, not {sorted(v)}"
                        )
                commarea[fname] = str(v) if isinstance(v, Decimal) else v  # JSON: the report writes the scenario
            sc["commarea"] = commarea
        receive: dict[str, dict[str, str]] = {}
        for m, typed in (gen.get("receive") or {}).items():
            layout = {f["name"]: f for f in cx.screen_fields(corpus, case, m, "input")}
            if typed == "@bms" or (isinstance(typed, dict) and "@bms" in typed):  # #4506: from the BMS source
                receive[m] = _bms_receive(rng, f"{name} map {m}", typed, layout, bms_input_fields(corpus, m), pools, i)
                continue
            receive[m] = {}
            for fname, rule in typed.items():
                if fname not in layout:
                    raise ValueError(f"{name}: map {m} has no input field {fname}")
                rule = rule if isinstance(rule, dict) else {"values": [rule]}
                bms = bms_input_fields(corpus, m) if rule.get("empty") else {}
                if _left_alone(rng, rule, bms, fname):  # #4506: the user left the field alone
                    if bms[fname]["mdt"]:
                        receive[m][fname] = ""
                    continue
                receive[m][fname] = _typed(rng, rule, layout[fname]["bytes"], pools.get(rule.get("from", ""), []), i)
        if receive:
            sc["receive"] = receive
        scenarios.append(sc)
    return {**case, "scenarios": [*case.get("scenarios", []), *scenarios]}
