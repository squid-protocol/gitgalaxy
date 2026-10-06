"""
#3804: the equivalence harness's inputs, generated from record layouts.

Most estates ship no data, and one sample file reaches only the paths its records do. A
dataset whose case says `"input": "@generate"` is built from its copybook record instead --
the same layout the diff reads (equivalence.layout_fields) -- deterministically (a seed),
with each field's values chosen for its storage:

* text: letters and digits at full width, a short value, and blanks; #3821: with
  `"alphabet": "mixed"`, also lower case, national letters and punctuation -- the keys and
  values whose order and comparisons differ between collations and locales;
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
                            "XREF-ACCT-ID": {"from": "ACCTFILE.ACCT-ID", "miss": 0.1},
                            "KTO-DATUM": {"date": "DD.MM.YYYY"}}}

`"digits": true` fills a text field with digits only -- a card number, an account id kept as text -- which its
PICTURE (X) cannot say. `date` (#3829) gives a field valid dates in a shape -- YYYY, YY, MM and DD, anything else literal --
text or numeric (`PIC 9(8)` as DDMMYYYY), whatever the field is called; its width must be the field's.
`from` draws a field from another dataset's values (generated first), so a join finds its
row -- and, with `miss`, sometimes does not, so the not-found path runs too. The primary key
(the case's first `keys` entry) is unique, and an indexed dataset is written in key order,
as a KSDS loads.

CICS cases (#3804; prepare_cics_case): a dataset `@generate`d takes its record length and key from the
program's CICS file, and a `scenario_generate` block makes scenarios whose COMMAREA and map input come from the
same layouts -- a typed account id that is on file, is not, or is not a number at all.
"""

from __future__ import annotations

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
    num = common._pic_numeric(f["pic"]) if f.get("pic") else None
    if num is None:
        return _text_value(rng, f["name"], f["bytes"], row, alphabet)
    signed, digits, scale = num
    return _numeric_value(rng, signed, digits, scale, row)


def generate_dataset(
    name: str,
    spec: dict[str, Any],
    fields: list[dict[str, Any]],
    pools: dict[str, list[Any]],
    code_page: str = "cp037",
    data_encoding: str = common.DEFAULT_DATA_ENCODING,
) -> tuple[bytes, dict[str, list[Any]]]:
    """(the dataset's fixed-length records, {DD.FIELD: the values it holds} for later joins)."""
    gen = spec["generate"]
    rng = random.Random(f"{gen.get('seed', 0)}:{name}")
    rules = gen.get("fields", {})
    alphabet = {"upper": _TEXT, "mixed": _MIXED}[gen.get("alphabet", "upper")]  # #3821
    reclen = spec["reclen"]
    key = (spec.get("keys") or [None])[0]
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
            else:
                v = field_value(rng, f, row if attempts == row + 1 else row + attempts, alphabet)
            chosen[f["name"]] = v
            rec[f["offset"] : f["offset"] + f["bytes"]] = encode_field(
                v, f["pic"], f["usage"], f["bytes"], code_page, data_encoding
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
        rows.sort(key=lambda r: r[key["offset"] : key["offset"] + key["length"]])
    return b"".join(rows), values


def _order(datasets: dict[str, dict[str, Any]]) -> list[str]:
    """Generated datasets, each after the ones its `from` rules draw on."""
    deps = {
        dd: {r["from"].rsplit(".", 1)[0] for r in spec["generate"].get("fields", {}).values() if "from" in r}
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
    pools: dict[str, list[Any]] = {}
    out: dict[str, bytes] = {}
    for dd in _order(todo):
        spec = todo[dd]
        fields = common.layout_fields(corpus, spec["generate"]["copybook"], spec["generate"].get("record"))
        width = max(f["offset"] + f["bytes"] for f in fields)
        if width > spec["reclen"]:
            raise ValueError(f"{dd}: the layout is {width} bytes, wider than reclen {spec['reclen']}")
        out[dd], values = generate_dataset(
            dd, spec, fields, pools, case.get("code_page", "cp037"), common.data_encoding(case)
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
        sc: dict[str, Any] = {"name": name, "aid": gen.get("aid", "DFHENTER"), "generated": True}
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
            receive[m] = {}
            for fname, rule in typed.items():
                if fname not in layout:
                    raise ValueError(f"{name}: map {m} has no input field {fname}")
                rule = rule if isinstance(rule, dict) else {"values": [rule]}
                receive[m][fname] = _typed(rng, rule, layout[fname]["bytes"], pools.get(rule.get("from", ""), []), i)
        if receive:
            sc["receive"] = receive
        scenarios.append(sc)
    return {**case, "scenarios": [*case.get("scenarios", []), *scenarios]}
