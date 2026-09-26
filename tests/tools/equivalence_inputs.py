"""
#3804: the equivalence harness's inputs, generated from record layouts.

Most estates ship no data, and one sample file reaches only the paths its records do. A
dataset whose case says `"input": "@generate"` is built from its copybook record instead --
the same layout the diff reads (equivalence.layout_fields) -- deterministically (a seed),
with each field's values chosen for its storage:

* text: letters and digits at full width, a short value, and blanks;
* numeric DISPLAY / COMP-3 / COMP: zero, one, the PICTURE's maximum and its negative
  where signed, the smallest fraction at its scale, and values in between;
* a date-shaped text field (named *DATE*, ten bytes): a valid YYYY-MM-DD.

A case steers what the program must meet:

    "generate": {"copybook": "app/cpy/CVACT01Y.cpy", "record": "ACCOUNT-RECORD", "records": 40, "seed": 7,
                 "fields": {"ACCT-GROUP-ID": {"values": ["A000000000", "DEFAULT"]},
                            "DIS-TRAN-TYPE-CD": {"values": ["01", "02"], "every": 3},
                            "XREF-ACCT-ID": {"from": "ACCTFILE.ACCT-ID", "miss": 0.1}}}

`from` draws a field from another dataset's values (generated first), so a join finds its
row -- and, with `miss`, sometimes does not, so the not-found path runs too. The primary key
(the case's first `keys` entry) is unique, and an indexed dataset is written in key order,
as a KSDS loads.
"""

from __future__ import annotations

import random
from decimal import Decimal
from pathlib import Path
from typing import Any


def _eq():
    """The batch harness, imported on use (it calls this module: a module-level import is a cycle)."""
    import equivalence

    return equivalence


def encode_field(value: Any, pic: str | None, usage: str | None, nbytes: int) -> bytes:
    """A value as the field stores it -- the inverse of equivalence.decode_field."""
    num = _eq()._pic_numeric(pic) if pic else None
    if num is None:
        return str(value).encode("latin-1")[:nbytes].ljust(nbytes, b" ")
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
        text = text[:-1] + ("}JKLMNOPQR"[last] if n < 0 else "{ABCDEFGHI"[last])
    return text.encode("latin-1")


def _numeric_value(rng: random.Random, signed: bool, digits: int, scale: int, row: int) -> Decimal:
    """Edge values first (zero, one, the maximum, its negative, the smallest fraction), then spread."""
    top = Decimal(10) ** (digits - scale) - Decimal(1).scaleb(-scale)  # 999.99 for 9(3)V99
    tiny = Decimal(1).scaleb(-scale) if scale else Decimal(1)
    edges = [Decimal(0), Decimal(1) if digits - scale > 0 else tiny, top, tiny]
    if signed:
        edges += [-top, -tiny]
    if row < len(edges):
        return edges[row]
    whole = rng.randint(0, 10 ** min(digits - scale, 9) - 1) if digits > scale else 0
    frac = Decimal(rng.randint(0, 10**scale - 1)).scaleb(-scale) if scale else Decimal(0)
    v = Decimal(whole) + frac
    return -v if signed and rng.random() < 0.3 else v


_TEXT = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _text_value(rng: random.Random, name: str, nbytes: int, row: int) -> str:
    if "DATE" in name.upper() and nbytes == 10:
        return f"{rng.randint(1990, 2030):04d}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
    if row % 7 == 3:
        return ""  # blanks: the field INITIALIZEd / never filled
    width = nbytes if row % 3 else max(1, nbytes // 2)
    return "".join(rng.choice(_TEXT) for _ in range(width))


def field_value(rng: random.Random, f: dict[str, Any], row: int) -> Any:
    num = _eq()._pic_numeric(f["pic"]) if f.get("pic") else None
    if num is None:
        return _text_value(rng, f["name"], f["bytes"], row)
    signed, digits, scale = num
    return _numeric_value(rng, signed, digits, scale, row)


def generate_dataset(
    name: str, spec: dict[str, Any], fields: list[dict[str, Any]], pools: dict[str, list[Any]]
) -> tuple[bytes, dict[str, list[Any]]]:
    """(the dataset's fixed-length records, {DD.FIELD: the values it holds} for later joins)."""
    gen = spec["generate"]
    rng = random.Random(f"{gen.get('seed', 0)}:{name}")
    rules = gen.get("fields", {})
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
        row, rec = len(rows), bytearray(b" " * reclen)
        chosen: dict[str, Any] = {}
        for f in fields:
            rule = rules.get(f["name"], {})
            if "values" in rule:  # `every` k: the value changes each k rows (a cartesian fill)
                v = rule["values"][(row // rule.get("every", 1)) % len(rule["values"])]
            elif "from" in rule:
                pool = pools.get(rule["from"])
                if not pool:
                    raise ValueError(f"{name}.{f['name']}: nothing generated yet for {rule['from']}")
                v = rng.choice(pool)
                if rng.random() < rule.get("miss", 0):
                    v = field_value(rng, f, len(pool) + attempts)  # a value the joined file does not hold
            elif f["name"] == "FILLER":
                v = ""  # unnamed padding: blanks, as the corpus files carry it
            elif key is not None and key["offset"] <= f["offset"] < key["offset"] + key["length"]:
                v = field_value(rng, f, 7 + row + attempts)  # a key part: never blank, never an edge repeat
                if isinstance(v, str):
                    v = "".join(rng.choice(_TEXT) for _ in range(f["bytes"]))
            else:
                v = field_value(rng, f, row if attempts == row + 1 else row + attempts)
            chosen[f["name"]] = v
            rec[f["offset"] : f["offset"] + f["bytes"]] = encode_field(v, f["pic"], f["usage"], f["bytes"])
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
        dd: {r["from"].split(".", 1)[0] for r in spec["generate"].get("fields", {}).values() if "from" in r}
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
    todo = {dd: spec for dd, spec in case["datasets"].items() if spec.get("input") == "@generate"}
    pools: dict[str, list[Any]] = {}
    out: dict[str, bytes] = {}
    for dd in _order(todo):
        spec = todo[dd]
        fields = _eq().layout_fields(corpus, spec["generate"]["copybook"], spec["generate"].get("record"))
        width = max(f["offset"] + f["bytes"] for f in fields)
        if width > spec["reclen"]:
            raise ValueError(f"{dd}: the layout is {width} bytes, wider than reclen {spec['reclen']}")
        out[dd], values = generate_dataset(dd, spec, fields, pools)
        pools.update(values)
    return out
