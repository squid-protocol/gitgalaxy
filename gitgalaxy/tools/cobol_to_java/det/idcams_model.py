"""An IDCAMS step as a model, for a job case (#8880, part of #8878 / #4890): the commands a step's SYSIN holds, run
against a catalog of VSAM clusters and the step's sequential datasets, ending in the step's condition code.
GnuCOBOL has no IDCAMS, so this is the oracle's own model; `det/idcams.py` stays the one-REPRO copy the batch forge
lowers onto COBOL, and this module is what a job case compares a step's datasets and condition code against.

    run(sysin, catalog, dds) -> Result        (a command or operand the model does not cover raises Refused, by name)

The model (IBM z/OS DFSMS Access Method Services Commands, SC23-6846-60: "REPRO", "DELETE", "DEFINE CLUSTER", "SET",
"IF-THEN-ELSE command sequence", "Condition codes", "Modal commands", "Continuing commands and comments"):

* Condition codes. Each command ends with a code (0 ok, 8 a problem the command could not finish, 12 a serious
  error); LASTCC is the code of the last command run, MAXCC the highest so far, and the step ends with MAXCC as its
  return code. `SET MAXCC = n` replaces MAXCC (the idiom after a DELETE that may find nothing). `IF LASTCC|MAXCC op n THEN
  cmd | DO ... END [ELSE cmd | DO ... END]` (op = EQ NE GT GE LT LE or = ^= > >= < <=) runs the branch the code selects;
  testing changes no code. A failing command does not stop the commands after it (the DELETE-then-DEFINE idiom).
* DELETE entryname [CLUSTER] [PURGE | NOPURGE] [ERASE | NOERASE]: removes the cluster and its records (code 0); an
  entry not in the catalog is code 8 (entry not found). The model has no retention period, so PURGE / NOPURGE change
  nothing, and ERASE overwrites data nothing can read afterwards.
* DEFINE CLUSTER (NAME(n) RECORDSIZE(avg max) [KEYS(length offset)] [INDEXED | NONINDEXED] ...): INDEXED (the
  default) is a KSDS, NONINDEXED an ESDS. A name already in the catalog is code 12 (duplicate data set name) and the
  catalog is unchanged. Allocation (VOLUMES, CYLINDERS, TRACKS, RECORDS, MEGABYTES, KILOBYTES, SHAREOPTIONS, FREESPACE,
  SPEED, RECOVERY, UNIQUE, SUBALLOCATION) always succeeds and has no effect the model reads.
* REPRO INFILE(dd) | INDATASET(cluster)  OUTFILE(dd) | OUTDATASET(cluster): copies every record, fixed length. A KSDS
  is read, and a sequential or ESDS source is loaded into an EMPTY KSDS, in ascending key order (a source out of order
  or holding a duplicate key is refused: IBM reports an error the model does not state); an ESDS is read in arrival
  order and appended to; a sequential output dataset is rewritten from its start.

Everything else is refused by name (Refused): every other command (ALTER, LISTCAT, PRINT, ...), DEFINE of anything but
a CLUSTER, a DATA / INDEX / CATALOG component, a NUMBERED / LINEAR / REUSE / SPANNED cluster, INDEXED without KEYS, no
RECORDSIZE, a key outside the shortest record, DELETE of an entry list, a password or quoted string, `SET LASTCC`, a
value over 16, REPRO FROMKEY / TOKEY / SKIP / COUNT / REPLACE / REUSE and the other parameters, REPRO of variable-length
records, of zero records, onto a non-empty KSDS, or between two datasets of different record length, a DD that is not
a dataset of the step or whose cluster was deleted in the step, and DISP=MOD on an output.

The oracle is this model, not z/OS: the register entry (docs/language_status/register/) lists what it assumes.
"""

from __future__ import annotations

import copy
import itertools
import re
from dataclasses import dataclass, field

from .dfsort import Refused
from .idcams import _REFUSED, _commands

_TOKEN = re.compile(r"(>=|<=|\^=|" + chr(0xAC) + r"=|=|>|<|\(|\)|[^\s()=<>^" + chr(0xAC) + r"]+)")
_NAME = re.compile(r"[A-Z#@$][A-Z0-9#@$-]{0,7}(?:\.[A-Z#@$][A-Z0-9#@$-]{0,7})*$")
_COMPARE = {"=": "=", "EQ": "=", "^=": "!", "NE": "!", ">": ">", "GT": ">", ">=": "G", "GE": "G", "<": "<", "LT": "<",
            "<=": "L", "LE": "L"}  # fmt: skip
_COMPARE[chr(0xAC) + "="] = "!"
_MAX_SET = 16
_HANDLED = ("REPRO", "DELETE", "DEFINE", "SET", "IF")
# DEFINE CLUSTER allocation: accepted, no effect the model reads (abbreviation -> keyword)
_ALLOC = {"VOLUMES": "VOLUMES", "VOL": "VOLUMES", "CYLINDERS": "CYLINDERS", "CYL": "CYLINDERS", "TRACKS": "TRACKS",
          "TRK": "TRACKS", "RECORDS": "RECORDS", "REC": "RECORDS", "MEGABYTES": "MEGABYTES", "MB": "MEGABYTES",
          "KILOBYTES": "KILOBYTES", "KB": "KILOBYTES", "SHAREOPTIONS": "SHAREOPTIONS", "SHR": "SHAREOPTIONS",
          "FREESPACE": "FREESPACE", "FSPC": "FREESPACE", "SPEED": "SPEED", "RECOVERY": "RECOVERY", "UNIQUE": "UNIQUE",
          "UNQ": "UNIQUE", "SUBALLOCATION": "SUBALLOCATION", "SUB": "SUBALLOCATION"}  # fmt: skip
_REPRO = {"INFILE": "INFILE", "IFILE": "INFILE", "OUTFILE": "OUTFILE", "OFILE": "OUTFILE", "INDATASET": "INDATASET",
          "IDS": "INDATASET", "OUTDATASET": "OUTDATASET", "ODS": "OUTDATASET"}  # fmt: skip


@dataclass
class Cluster:
    """A VSAM cluster in the catalog. A KSDS holds its records in key order, an ESDS in arrival order."""

    name: str
    indexed: bool
    key_len: int
    key_off: int
    avg: int
    max: int
    records: list[bytes] = field(default_factory=list)

    def key(self, rec: bytes) -> bytes:
        return rec[self.key_off : self.key_off + self.key_len]


@dataclass
class Sequential:
    """A sequential dataset of fixed-length records (a DD of the step). `disp` is the DD's DISP status."""

    lrecl: int
    records: list[bytes] = field(default_factory=list)
    disp: str = "OLD"


@dataclass(frozen=True)
class Vsam:
    """A DD of the step that names a cluster already in the catalog when the step starts."""

    name: str


@dataclass
class Result:
    rc: int  # the step's return code: MAXCC at its end
    lastcc: int
    maxcc: int
    catalog: dict[str, Cluster]
    datasets: dict[str, Sequential]  # the step's sequential DDs after the step
    log: list[str] = field(default_factory=list)


@dataclass
class _Op:
    name: str
    args: list[_Op] | None = None


@dataclass
class _Cmd:
    verb: str
    ops: list[_Op]


@dataclass
class _Set:
    value: int


@dataclass
class _If:
    var: str
    cmp: str
    num: int
    then: list[object]
    els: list[object]


def _toks(line: str) -> list[str]:
    if "'" in line or '"' in line:
        raise Refused("an IDCAMS quoted string")
    return _TOKEN.findall(line)


def _ops(toks: list[str], pos: int, nested: bool) -> tuple[list[_Op], int]:
    out: list[_Op] = []
    while pos < len(toks):
        t = toks[pos]
        if t == ")":
            if not nested:
                raise Refused("an unbalanced ) in an IDCAMS command")
            return out, pos + 1
        if t == "(":
            if not out or out[-1].args is not None:
                raise Refused("an IDCAMS ( with no keyword before it")
            out[-1].args, pos = _ops(toks, pos + 1, True)
            continue
        out.append(_Op(t.upper()))
        pos += 1
    if nested:
        raise Refused("an unbalanced ( in an IDCAMS command")
    return out, pos


def _num(text: str, what: str) -> int:
    if not text.isdigit():
        raise Refused(f"{what} value ({text[:20]}) is not a number")
    return int(text)


def _parse_one(lines: list[str], i: int) -> tuple[object, int]:
    toks = _toks(lines[i])
    verb = toks[0].upper()
    if verb == "IF":
        return _parse_if(lines, i, toks)
    if verb in ("END", "ELSE", "THEN", "DO"):
        raise Refused(f"the IDCAMS {verb} with no IF-THEN before it")
    if verb == "SET":
        if len(toks) != 4 or toks[2] != "=":
            raise Refused("an IDCAMS SET that is not 'SET MAXCC = n'")
        if toks[1].upper() != "MAXCC":
            raise Refused(f"the IDCAMS SET {toks[1].upper()} (only SET MAXCC is modelled)")
        value = _num(toks[3], "the IDCAMS SET")
        if value > _MAX_SET:
            raise Refused(f"the IDCAMS SET value {value} (the model covers 0 to {_MAX_SET})")
        return _Set(value), i + 1
    if verb not in _HANDLED:
        raise Refused(f"the IDCAMS {verb} command ({_REFUSED.get(verb, 'a command the oracle has no model of')})")
    ops, _ = _ops(toks, 1, False)
    return _Cmd(verb, ops), i + 1


def _parse_body(lines: list[str], i: int) -> tuple[list[object], int]:
    if i >= len(lines):
        raise Refused("an IDCAMS THEN / ELSE with no command after it")
    if [t.upper() for t in _toks(lines[i])] == ["DO"]:
        body: list[object] = []
        i += 1
        while True:
            if i >= len(lines):
                raise Refused("an IDCAMS DO with no END")
            if [t.upper() for t in _toks(lines[i])] == ["END"]:
                return body, i + 1
            stmt, i = _parse_one(lines, i)
            body.append(stmt)
    stmt, i = _parse_one(lines, i)
    return [stmt], i


def _parse_if(lines: list[str], i: int, toks: list[str]) -> tuple[object, int]:
    up = [t.upper() for t in toks]
    if "THEN" not in up:
        raise Refused("an IDCAMS IF with no THEN")
    t = up.index("THEN")
    cond = up[1:t]
    if len(cond) != 3 or cond[0] not in ("LASTCC", "MAXCC") or cond[1] not in _COMPARE:
        raise Refused("an IDCAMS IF condition that is not 'LASTCC|MAXCC op number'")
    num = _num(cond[2], "the IDCAMS IF")
    lines = lines[:]
    rest = " ".join(toks[t + 1 :])
    if rest:
        lines[i] = rest
        j = i
    else:
        j = i + 1
    then, j = _parse_body(lines, j)
    els: list[object] = []
    if j < len(lines):
        nxt = _toks(lines[j])
        if nxt and nxt[0].upper() == "ELSE":
            tail = " ".join(nxt[1:])
            if tail:
                lines[j] = tail
            els, j = _parse_body(lines, j if tail else j + 1)
    return _If(cond[0], _COMPARE[cond[1]], num, then, els), j


def _parse(sysin: str) -> list[object]:
    lines = _commands(sysin)
    if not lines:
        raise Refused("no IDCAMS command")
    out: list[object] = []
    i = 0
    while i < len(lines):
        stmt, i = _parse_one(lines, i)
        out.append(stmt)
    return out


class _Step:
    def __init__(self, catalog: dict[str, Cluster], dds: dict[str, Sequential | Vsam]):
        self.catalog = copy.deepcopy(catalog)
        self.seqs: dict[str, Sequential] = {}
        self.vsam: dict[str, Cluster] = {}
        for dd, d in dds.items():
            if isinstance(d, Vsam):
                if d.name not in self.catalog:
                    raise Refused(
                        f"DD {dd} names cluster {d.name}, which is not in the catalog (a JCL allocation error)"
                    )
                self.vsam[dd] = self.catalog[d.name]
            else:
                if any(len(r) != d.lrecl for r in d.records):
                    raise ValueError(f"DD {dd}: a record is not {d.lrecl} bytes")
                self.seqs[dd] = copy.deepcopy(d)
        self.lastcc = 0
        self.maxcc = 0
        self.log: list[str] = []

    def end(self, cc: int, note: str) -> None:
        self.lastcc = cc
        self.maxcc = max(self.maxcc, cc)
        self.log.append(f"{note}: condition code {cc}")

    def run(self, stmts: list[object]) -> None:
        for s in stmts:
            if isinstance(s, _Set):
                self.maxcc = s.value
                self.log.append(f"SET MAXCC = {s.value}")
            elif isinstance(s, _If):
                have = self.lastcc if s.var == "LASTCC" else self.maxcc
                hit = {"=": have == s.num, "!": have != s.num, ">": have > s.num, "G": have >= s.num,
                       "<": have < s.num, "L": have <= s.num}[s.cmp]  # fmt: skip
                self.run(s.then if hit else s.els)
            elif isinstance(s, _Cmd):
                {"DELETE": self.delete, "DEFINE": self.define, "REPRO": self.repro}[s.verb](s.ops)

    # -- DELETE ------------------------------------------------------------------------------------------------
    def delete(self, ops: list[_Op]) -> None:
        if not ops or ops[0].args is not None or ops[0].name in ("CLUSTER", "PURGE", "NOPURGE", "ERASE", "NOERASE"):
            raise Refused("the IDCAMS DELETE without one entry name (an entry list is not modelled)")
        name = _entry(ops[0].name, "DELETE")
        for op in ops[1:]:
            if op.name not in ("CLUSTER", "PURGE", "NOPURGE", "ERASE", "NOERASE") or op.args is not None:
                raise Refused(f"the IDCAMS DELETE {op.name} parameter")
        if self.catalog.pop(name, None) is None:
            self.end(8, f"DELETE {name}: entry not found")
        else:
            self.end(0, f"DELETE {name}")

    # -- DEFINE CLUSTER ----------------------------------------------------------------------------------------
    def define(self, ops: list[_Op]) -> None:
        if not ops or ops[0].name != "CLUSTER":
            raise Refused(f"the IDCAMS DEFINE {ops[0].name if ops else '(nothing)'} (only DEFINE CLUSTER is modelled)")
        if len(ops) > 1:
            raise Refused(f"the IDCAMS DEFINE CLUSTER operand {ops[1].name} outside CLUSTER(...) (DATA / INDEX / CATALOG "
                          "components are not modelled)")  # fmt: skip
        got: dict[str, list[_Op]] = {}
        org = None
        for op in ops[0].args or []:
            key = _ALLOC.get(op.name, op.name)
            if key in ("INDEXED", "IXD", "NONINDEXED", "NIXD"):
                if org or op.args is not None:
                    raise Refused("the IDCAMS DEFINE CLUSTER organisation stated twice, or with a value")
                org = key[0] != "N"
            elif key in ("NAME", "KEYS", "RECORDSIZE", "RECSZ") and op.args is not None:
                key = "RECORDSIZE" if key == "RECSZ" else key
                if key in got:
                    raise Refused(f"the IDCAMS DEFINE CLUSTER {key} parameter twice")
                got[key] = op.args
            elif key in _ALLOC.values():
                continue
            else:
                raise Refused(f"the IDCAMS DEFINE CLUSTER {op.name} parameter")
        if "NAME" not in got or len(got["NAME"]) != 1:
            raise Refused("the IDCAMS DEFINE CLUSTER without a single NAME")
        name = _entry(got["NAME"][0].name, "DEFINE CLUSTER NAME")
        if "RECORDSIZE" not in got:
            raise Refused("the IDCAMS DEFINE CLUSTER without RECORDSIZE (the default is not modelled)")
        avg, mx = _pair(got["RECORDSIZE"], "RECORDSIZE")
        if not 0 < avg <= mx:
            raise Refused(f"the IDCAMS DEFINE CLUSTER RECORDSIZE({avg} {mx}): the model needs 0 < average <= maximum")
        indexed = True if org is None else org
        key_len = key_off = 0
        if indexed:
            if "KEYS" not in got:
                raise Refused("the IDCAMS DEFINE CLUSTER INDEXED without KEYS (the default is not modelled)")
            key_len, key_off = _pair(got["KEYS"], "KEYS")
            if key_len < 1 or key_off + key_len > avg:
                raise Refused(
                    f"the IDCAMS DEFINE CLUSTER KEYS({key_len} {key_off}) is not inside the shortest record ({avg})"
                )
        elif "KEYS" in got:
            raise Refused("the IDCAMS DEFINE CLUSTER NONINDEXED with KEYS")
        if name in self.catalog:
            self.end(12, f"DEFINE CLUSTER {name}: duplicate data set name")
            return
        self.catalog[name] = Cluster(name, indexed, key_len, key_off, avg, mx)
        self.end(0, f"DEFINE CLUSTER {name}")

    # -- REPRO -------------------------------------------------------------------------------------------------
    def _endpoint(self, kind: str, name: str) -> Sequential | Cluster:
        if kind.endswith("FILE"):
            if name in self.seqs:
                return self.seqs[name]
            if name in self.vsam:
                if self.catalog.get(self.vsam[name].name) is not self.vsam[name]:
                    raise Refused(
                        f"REPRO {kind}({name}): its cluster was deleted in the step (the allocation is stale)"
                    )
                return self.vsam[name]
            raise Refused(f"REPRO {kind}({name}) is not a dataset of the step")
        if name not in self.catalog:
            raise Refused(
                f"REPRO {kind}({name}) is not a cluster in the catalog (a cataloged sequential is not modelled)"
            )
        return self.catalog[name]

    def repro(self, ops: list[_Op]) -> None:
        ends: dict[str, str] = {}
        for op in ops:
            key = _REPRO.get(op.name)
            if key is None or op.args is None:
                raise Refused(f"the IDCAMS REPRO {op.name} parameter")
            side = "IN" if key.startswith("IN") else "OUT"
            if side in ends:
                raise Refused(f"the IDCAMS REPRO names its {side.lower()}put twice")
            if len(op.args) != 1 or op.args[0].args is not None or "/" in op.args[0].name:
                raise Refused(f"the IDCAMS REPRO {key} value (one name, no password)")
            nm = op.args[0].name
            if not (_NAME.match(nm) if key.endswith("DATASET") else re.match(r"[A-Z#@$][A-Z0-9#@$]{0,7}$", nm)):
                raise Refused(f"the IDCAMS REPRO {key} value ({nm[:20]}) is not a name")
            ends[side] = key + "\0" + nm
        if len(ends) != 2:
            raise Refused("the IDCAMS REPRO without both an input and an output")
        src, dst = (self._endpoint(*ends[s].split("\0")) for s in sorted(ends))
        if src is dst:
            raise Refused("the IDCAMS REPRO of a dataset onto itself")
        recs = list(src.records)
        n, m = _reclen(src), _reclen(dst)
        if n != m:
            raise Refused(f"the IDCAMS REPRO between record lengths {n} and {m}")
        if not recs:
            raise Refused("the IDCAMS REPRO of zero records (its condition code is not modelled)")
        if isinstance(dst, Sequential):
            if dst.disp not in ("OLD", "NEW"):
                raise Refused(f"the IDCAMS REPRO onto a DD with DISP={dst.disp}")
            dst.records = recs
        elif dst.indexed:
            if dst.records:
                raise Refused("the IDCAMS REPRO onto a non-empty KSDS (insert mode and its duplicate-key codes)")
            keys = [dst.key(r) for r in recs]
            if any(a >= b for a, b in itertools.pairwise(keys)):
                raise Refused("the IDCAMS REPRO into a KSDS from a source out of key order or with a duplicate key")
            dst.records = recs
        else:
            dst.records = dst.records + recs
        self.end(0, f"REPRO {len(recs)} records")


def _reclen(d: Sequential | Cluster) -> int:
    if isinstance(d, Sequential):
        return d.lrecl
    if d.avg != d.max:
        raise Refused(f"the IDCAMS REPRO of variable-length records (cluster {d.name} RECORDSIZE({d.avg} {d.max}))")
    return d.max


def _entry(text: str, what: str) -> str:
    if "/" in text or not _NAME.match(text):
        raise Refused(f"the IDCAMS {what} name ({text[:20]}) is not a plain data set name (no password)")
    return text


def _pair(args: list[_Op], what: str) -> tuple[int, int]:
    if len(args) != 2 or any(a.args is not None for a in args):
        raise Refused(f"the IDCAMS {what} value is not two numbers")
    return _num(args[0].name, what), _num(args[1].name, what)


def run(sysin: str, catalog: dict[str, Cluster], dds: dict[str, Sequential | Vsam] | None = None) -> Result:
    """Run the commands of `sysin`. `catalog` is the clusters that exist when the step starts and `dds` the step's DDs
    (a `Sequential` dataset, or a `Vsam` naming a catalog cluster). Neither argument is changed: the step's effect is
    in the `Result`, whose `rc` is the step's return code."""
    stmts = _parse(sysin)
    st = _Step(catalog, dds or {})
    st.run(stmts)
    return Result(st.maxcc, st.lastcc, st.maxcc, st.catalog, st.seqs, st.log)
