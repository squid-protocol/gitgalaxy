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
* DEFINE ALTERNATEINDEX (NAME(n) RELATE(base) KEYS(length offset) [UNIQUEKEY | NONUNIQUEKEY] [UPGRADE] RECORDSIZE(avg
  max) ...), DEFINE PATH (NAME(n) PATHENTRY(aix) [UPDATE | NOUPDATE]) and BLDINDEX INDATASET(base) OUTDATASET(aix)
  ("DEFINE ALTERNATEINDEX", "DEFINE PATH", "BLDINDEX"; SC23-6846-60). An alternate index is related to a cataloged
  KSDS or ESDS, its key inside the base's shortest record; DEFINE of a name already cataloged is code 12. BLDINDEX
  builds it (code 0): reading the base through the path (`path_records`, or REPRO INDATASET(path) as input) gives the
  base's records in alternate-key order, records sharing a key in the order the base holds them, which is how BLDINDEX
  sorts the pointers. DATA(NAME(n)) / INDEX(NAME(n)) components on a DEFINE are names only, and ERASE / NOERASE and
  a comma between operands are accepted.
* REPRO INFILE(dd) | INDATASET(cluster)  OUTFILE(dd) | OUTDATASET(cluster): copies every record, fixed length. A KSDS
  is read, and a sequential or ESDS source is loaded into an EMPTY KSDS, in ascending key order (a source out of order
  or holding a duplicate key is refused: IBM reports an error the model does not state); an ESDS is read in arrival
  order and appended to; a sequential output dataset is rewritten from its start.

Everything else is refused by name (Refused): NOUPGRADE, an alternate index whose RELATE or PATHENTRY is not in the
catalog, a path over anything but an alternate index, BLDINDEX by DD / of an empty base / of a built index / of UNIQUEKEY
over duplicate keys / whose busiest key's record overflows RECORDSIZE, reading a path whose index is not built, REPRO
onto a path or a base cluster that has an alternate index, DELETE of an alternate index, a path or a base that has an
index; every other command (ALTER, LISTCAT, PRINT, ...), DEFINE of anything but
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

# A comma separates operands like a blank (`RECORDSIZE(350,350)`, IBM "Continuing commands and comments" / the
# delimiter rules): it is never part of a token.
_TOKEN = re.compile(r"(>=|<=|\^=|" + chr(0xAC) + r"=|=|>|<|\(|\)|[^\s()=<>^," + chr(0xAC) + r"]+)")
_NAME = re.compile(r"[A-Z#@$][A-Z0-9#@$-]{0,7}(?:\.[A-Z#@$][A-Z0-9#@$-]{0,7})*$")
_COMPARE = {"=": "=", "EQ": "=", "^=": "!", "NE": "!", ">": ">", "GT": ">", ">=": "G", "GE": "G", "<": "<", "LT": "<",
            "<=": "L", "LE": "L"}  # fmt: skip
_COMPARE[chr(0xAC) + "="] = "!"
_MAX_SET = 16
_HANDLED = ("REPRO", "DELETE", "DEFINE", "SET", "IF", "BLDINDEX")
_KIND = {"AIX": "ALTERNATEINDEX"}
# DEFINE operands by entry kind: the ones that carry a value, and the flag groups (flag -> (group, canonical flag))
_VALUED = {"CLUSTER": ("NAME", "KEYS", "RECORDSIZE"), "ALTERNATEINDEX": ("NAME", "RELATE", "KEYS", "RECORDSIZE"),
           "PATH": ("NAME", "PATHENTRY")}  # fmt: skip
_ORG = "organisation"
_UNIQ = "key uniqueness"
_FLAGS = {
    "CLUSTER": {"INDEXED": (_ORG, "INDEXED"), "IXD": (_ORG, "INDEXED"),
                "NONINDEXED": (_ORG, "NONINDEXED"), "NIXD": (_ORG, "NONINDEXED")},
    "ALTERNATEINDEX": {"UNIQUEKEY": (_UNIQ, "UNIQUEKEY"), "UNQK": (_UNIQ, "UNIQUEKEY"),
                       "NONUNIQUEKEY": (_UNIQ, "NONUNIQUEKEY"), "NUNQK": (_UNIQ, "NONUNIQUEKEY"),
                       "UPGRADE": ("upgrade", "UPGRADE"), "UPG": ("upgrade", "UPGRADE"),
                       "NOUPGRADE": ("upgrade", "NOUPGRADE"), "NUPG": ("upgrade", "NOUPGRADE")},
    "PATH": {"UPDATE": ("update", "UPDATE"), "UPD": ("update", "UPDATE"), "NOUPDATE": ("update", "NOUPDATE"),
             "NUPD": ("update", "NOUPDATE")},
}  # fmt: skip
_BASE_PTR = 4  # an ESDS base is pointed at by its 4-byte RBA (a KSDS base by its primary key)
_AIX_HEADER = 5  # bytes ahead of the alternate key in an alternate index record (ASSUMED, register F6)
# DEFINE CLUSTER / ALTERNATEINDEX allocation: accepted, no effect the model reads (abbreviation -> keyword)
_ALLOC = {"VOLUMES": "VOLUMES", "VOL": "VOLUMES", "CYLINDERS": "CYLINDERS", "CYL": "CYLINDERS", "TRACKS": "TRACKS",
          "TRK": "TRACKS", "RECORDS": "RECORDS", "REC": "RECORDS", "MEGABYTES": "MEGABYTES", "MB": "MEGABYTES",
          "KILOBYTES": "KILOBYTES", "KB": "KILOBYTES", "SHAREOPTIONS": "SHAREOPTIONS", "SHR": "SHAREOPTIONS",
          "FREESPACE": "FREESPACE", "FSPC": "FREESPACE", "SPEED": "SPEED", "RECOVERY": "RECOVERY", "UNIQUE": "UNIQUE",
          "UNQ": "UNIQUE", "SUBALLOCATION": "SUBALLOCATION", "SUB": "SUBALLOCATION", "ERASE": "ERASE",
          "NOERASE": "NOERASE"}  # fmt: skip
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
class Aix:
    """An alternate index (DEFINE ALTERNATEINDEX) over the cluster `relate`. Its entries are derived from the base's
    records when it is read through a path, so only whether BLDINDEX has built it is state."""

    name: str
    relate: str
    key_len: int
    key_off: int
    avg: int
    max: int
    unique: bool
    upgrade: bool = True
    built: bool = False


@dataclass(frozen=True)
class Path:
    """A path (DEFINE PATH): reading it reads the base cluster's records in the alternate index's key order."""

    name: str
    aix: str
    update: bool = True


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
    catalog: dict[str, Cluster | Aix | Path]
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
    def __init__(self, catalog: dict[str, Cluster | Aix | Path], dds: dict[str, Sequential | Vsam]):
        self.catalog = copy.deepcopy(catalog)
        self.seqs: dict[str, Sequential] = {}
        self.vsam: dict[str, Cluster | Aix | Path] = {}
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
                {"DELETE": self.delete, "DEFINE": self.define, "REPRO": self.repro, "BLDINDEX": self.bldindex}[s.verb](
                    s.ops
                )

    # -- DELETE ------------------------------------------------------------------------------------------------
    def delete(self, ops: list[_Op]) -> None:
        if not ops or ops[0].args is not None or ops[0].name in ("CLUSTER", "PURGE", "NOPURGE", "ERASE", "NOERASE"):
            raise Refused("the IDCAMS DELETE without one entry name (an entry list is not modelled)")
        name = _entry(ops[0].name, "DELETE")
        for op in ops[1:]:
            if op.name not in ("CLUSTER", "PURGE", "NOPURGE", "ERASE", "NOERASE") or op.args is not None:
                raise Refused(f"the IDCAMS DELETE {op.name} parameter")
        ent = self.catalog.get(name)
        if ent is not None and not isinstance(ent, Cluster):
            raise Refused(f"the IDCAMS DELETE of {name}, an alternate index or path (its dependents are not modelled)")
        if ent is not None and any(isinstance(e, Aix) and e.relate == name for e in self.catalog.values()):
            raise Refused(f"the IDCAMS DELETE of {name}, a cluster with an alternate index related to it")
        if self.catalog.pop(name, None) is None:
            self.end(8, f"DELETE {name}: entry not found")
        else:
            self.end(0, f"DELETE {name}")

    # -- DEFINE CLUSTER / ALTERNATEINDEX / PATH ----------------------------------------------------------------
    def _components(self, ops: list[_Op], kind: str) -> list[str]:
        """The DATA / INDEX component names after the entry's own parenthesised group (naming only)."""
        names: list[str] = []
        seen: set[str] = set()
        for op in ops:
            if kind == "PATH" or op.name not in ("DATA", "INDEX"):
                raise Refused(
                    f"the IDCAMS DEFINE {kind} operand {op.name} outside {kind}(...) (only DATA / INDEX with "
                    "NAME(...) is modelled)"
                )
            if op.name in seen:
                raise Refused(f"the IDCAMS DEFINE {kind} {op.name} component stated twice")
            seen.add(op.name)
            inner = op.args or []
            if len(inner) != 1 or inner[0].name != "NAME" or inner[0].args is None or len(inner[0].args) != 1:
                raise Refused(f"the IDCAMS DEFINE {kind} {op.name} component operand (only NAME(one name) is modelled)")
            names.append(_entry(inner[0].args[0].name, f"DEFINE {kind} {op.name} NAME"))
        return names

    def _scan(self, kind: str, args: list[_Op]) -> tuple[dict[str, list[_Op]], dict[str, str]]:
        got: dict[str, list[_Op]] = {}
        flags: dict[str, str] = {}
        for op in args:
            key = _ALLOC.get(op.name, op.name)
            key = "RECORDSIZE" if key == "RECSZ" else key
            if key in _FLAGS[kind]:
                group, flag = _FLAGS[kind][key]
                if group in flags or op.args is not None:
                    raise Refused(f"the IDCAMS DEFINE {kind} {group} stated twice, or with a value")
                flags[group] = flag
            elif key in _VALUED[kind] and op.args is not None:
                if key in got:
                    raise Refused(f"the IDCAMS DEFINE {kind} {key} parameter twice")
                got[key] = op.args
            elif kind != "PATH" and key in _ALLOC.values():
                continue
            else:
                raise Refused(f"the IDCAMS DEFINE {kind} {op.name} parameter")
        if "NAME" not in got or len(got["NAME"]) != 1:
            raise Refused(f"the IDCAMS DEFINE {kind} without a single NAME")
        return got, flags

    def define(self, ops: list[_Op]) -> None:
        kind = _KIND.get(ops[0].name, ops[0].name) if ops else ""
        if kind not in _VALUED:
            raise Refused(
                f"the IDCAMS DEFINE {ops[0].name if ops else '(nothing)'} (only DEFINE CLUSTER, ALTERNATEINDEX and PATH "
                "are modelled)"
            )
        comps = self._components(ops[1:], kind)
        got, flags = self._scan(kind, ops[0].args or [])
        name = _entry(got["NAME"][0].name, f"DEFINE {kind} NAME")
        if kind == "PATH":
            self._define_path(name, got, flags)
            return
        if "RECORDSIZE" not in got:
            raise Refused(f"the IDCAMS DEFINE {kind} without RECORDSIZE (the default is not modelled)")
        avg, mx = _pair(got["RECORDSIZE"], "RECORDSIZE")
        if not 0 < avg <= mx:
            raise Refused(f"the IDCAMS DEFINE {kind} RECORDSIZE({avg} {mx}): the model needs 0 < average <= maximum")
        if kind == "ALTERNATEINDEX":
            self._define_aix(name, got, flags, avg, mx, comps)
            return
        indexed = flags.get(_ORG, "INDEXED") == "INDEXED"
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
        self._components_free(name, comps)
        self.catalog[name] = Cluster(name, indexed, key_len, key_off, avg, mx)
        self.end(0, f"DEFINE CLUSTER {name}")

    def _components_free(self, name: str, comps: list[str]) -> None:
        if len(set(comps)) != len(comps) or name in comps or any(c in self.catalog for c in comps):
            raise Refused(f"the IDCAMS DEFINE {name} component name is already an entry (its code is not stated)")

    def _define_aix(self, name: str, got: dict[str, list[_Op]], flags: dict[str, str], avg: int, mx: int,
                    comps: list[str]) -> None:  # fmt: skip
        if "RELATE" not in got or len(got["RELATE"]) != 1 or got["RELATE"][0].args is not None:
            raise Refused("the IDCAMS DEFINE ALTERNATEINDEX without a single RELATE")
        relate = _entry(got["RELATE"][0].name, "DEFINE ALTERNATEINDEX RELATE")
        if "KEYS" not in got:
            raise Refused("the IDCAMS DEFINE ALTERNATEINDEX without KEYS (the default is not modelled)")
        key_len, key_off = _pair(got["KEYS"], "KEYS")
        if flags.get("upgrade") == "NOUPGRADE":
            raise Refused("the IDCAMS DEFINE ALTERNATEINDEX NOUPGRADE (an alternate index left stale by the base)")
        if name in self.catalog:
            self.end(12, f"DEFINE ALTERNATEINDEX {name}: duplicate data set name")
            return
        base = self.catalog.get(relate)
        if base is None:
            raise Refused(
                f"the IDCAMS DEFINE ALTERNATEINDEX RELATE({relate}) is not in the catalog (its code is not stated)"
            )
        if not isinstance(base, Cluster):
            raise Refused(f"the IDCAMS DEFINE ALTERNATEINDEX RELATE({relate}) is not a cluster")
        if key_len < 1 or key_off + key_len > base.avg:
            raise Refused(
                f"the IDCAMS DEFINE ALTERNATEINDEX KEYS({key_len} {key_off}) is not inside the base's shortest record "
                f"({base.avg})"
            )
        self._components_free(name, comps)
        unique = flags.get(_UNIQ, "NONUNIQUEKEY") == "UNIQUEKEY"
        self.catalog[name] = Aix(name, relate, key_len, key_off, avg, mx, unique)
        self.end(0, f"DEFINE ALTERNATEINDEX {name}")

    def _define_path(self, name: str, got: dict[str, list[_Op]], flags: dict[str, str]) -> None:
        if "PATHENTRY" not in got or len(got["PATHENTRY"]) != 1 or got["PATHENTRY"][0].args is not None:
            raise Refused("the IDCAMS DEFINE PATH without a single PATHENTRY")
        entry = _entry(got["PATHENTRY"][0].name, "DEFINE PATH PATHENTRY")
        if name in self.catalog:
            self.end(12, f"DEFINE PATH {name}: duplicate data set name")
            return
        target = self.catalog.get(entry)
        if target is None:
            raise Refused(f"the IDCAMS DEFINE PATH PATHENTRY({entry}) is not in the catalog (its code is not stated)")
        if not isinstance(target, Aix):
            raise Refused(f"the IDCAMS DEFINE PATH PATHENTRY({entry}) is not an alternate index (a path over a cluster or "
                          "another path is not modelled)")  # fmt: skip
        self.catalog[name] = Path(name, entry, flags.get("update", "UPDATE") == "UPDATE")
        self.end(0, f"DEFINE PATH {name}")

    # -- BLDINDEX ----------------------------------------------------------------------------------------------
    def bldindex(self, ops: list[_Op]) -> None:
        ends: dict[str, str] = {}
        for op in ops:
            key = _REPRO.get(op.name)
            if key is None or op.args is None:
                raise Refused(f"the IDCAMS BLDINDEX {op.name} parameter")
            if not key.endswith("DATASET"):
                raise Refused(f"the IDCAMS BLDINDEX {key} (the DD form is not modelled; name the data sets)")
            if key in ends:
                raise Refused(f"the IDCAMS BLDINDEX names its {key} twice")
            if len(op.args) != 1 or op.args[0].args is not None:
                raise Refused(f"the IDCAMS BLDINDEX {key} value (one name, no password)")
            ends[key] = _entry(op.args[0].name, f"BLDINDEX {key}")
        if len(ends) != 2:
            raise Refused("the IDCAMS BLDINDEX without both INDATASET and OUTDATASET")
        base = self.catalog.get(ends["INDATASET"])
        aix = self.catalog.get(ends["OUTDATASET"])
        if not isinstance(base, Cluster):
            raise Refused(f"the IDCAMS BLDINDEX INDATASET({ends['INDATASET']}) is not a cluster in the catalog")
        if not isinstance(aix, Aix):
            raise Refused(
                f"the IDCAMS BLDINDEX OUTDATASET({ends['OUTDATASET']}) is not an alternate index in the catalog"
            )
        if aix.relate != base.name:
            raise Refused(f"the IDCAMS BLDINDEX of {aix.name} from {base.name}, which it is not related to")
        if aix.built:
            raise Refused(f"the IDCAMS BLDINDEX of {aix.name}, which is already built (its code is not stated)")
        if not base.records:
            raise Refused("the IDCAMS BLDINDEX of an empty base cluster (its condition code is not modelled)")
        pointer = base.key_len if base.indexed else _BASE_PTR
        groups: dict[bytes, int] = {}
        for r in base.records:
            k = r[aix.key_off : aix.key_off + aix.key_len]
            groups[k] = groups.get(k, 0) + 1
        if aix.unique and any(n > 1 for n in groups.values()):
            raise Refused(
                "the IDCAMS BLDINDEX of a UNIQUEKEY alternate index over duplicate keys (IBM's outcome is not stated)"
            )
        need = _AIX_HEADER + aix.key_len + pointer * max(groups.values())
        if need > aix.max:
            raise Refused(
                f"the IDCAMS BLDINDEX record for the busiest key needs {need} bytes, over RECORDSIZE maximum {aix.max} "
                "(IBM's outcome is not stated)"
            )
        aix.built = True
        self.end(0, f"BLDINDEX {aix.name}: {len(base.records)} records, {len(groups)} keys")

    # -- REPRO -------------------------------------------------------------------------------------------------
    def _endpoint(self, kind: str, name: str, side: str) -> Sequential | Cluster:
        if kind.endswith("FILE"):
            if name in self.seqs:
                return self.seqs[name]
            if name not in self.vsam:
                raise Refused(f"REPRO {kind}({name}) is not a dataset of the step")
            ent = self.vsam[name]
            if self.catalog.get(ent.name) is not ent:
                raise Refused(f"REPRO {kind}({name}): its cluster was deleted in the step (the allocation is stale)")
        else:
            if name not in self.catalog:
                raise Refused(
                    f"REPRO {kind}({name}) is not a cluster in the catalog (a cataloged sequential is not modelled)"
                )
            ent = self.catalog[name]
        if isinstance(ent, Aix):
            raise Refused(f"REPRO {kind}({name}) is an alternate index (its records are not modelled)")
        if isinstance(ent, Path):
            if side != "IN":
                raise Refused(f"REPRO {kind}({name}) writes through a path (not modelled)")
            return self._read_path(ent)
        if side == "OUT" and any(isinstance(e, Aix) and e.relate == ent.name for e in self.catalog.values()):
            raise Refused(
                f"REPRO {kind}({name}) onto a base cluster with an alternate index (its upgrade is not modelled)"
            )
        return ent

    def _read_path(self, path: Path) -> Sequential:
        recs = path_records(self.catalog, path.name)  # refuses a path that does not lead to a built index
        aix = self.catalog[path.aix]
        base = self.catalog[aix.relate] if isinstance(aix, Aix) else aix
        return Sequential(_reclen(base) if isinstance(base, Cluster) else 0, recs)

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
        src, dst = (self._endpoint(ends[s].split("\0")[0], ends[s].split("\0")[1], s) for s in sorted(ends))
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


def path_records(catalog: dict[str, Cluster | Aix | Path], path_name: str) -> list[bytes]:
    """The records read through a path: the base cluster's records in alternate-key order, records sharing a key in the
    order the base holds them (key order for a KSDS, arrival order for an ESDS), as BLDINDEX orders them. An alternate
    index BLDINDEX has not built is refused (reading it is not modelled)."""
    path = catalog.get(path_name)
    if not isinstance(path, Path):
        raise Refused(f"{path_name} is not a path in the catalog")
    aix = catalog[path.aix]
    base = catalog[aix.relate] if isinstance(aix, Aix) else None
    if not isinstance(aix, Aix) or not isinstance(base, Cluster):
        raise Refused(f"the path {path_name} does not lead to an alternate index over a cluster")
    if not aix.built:
        raise Refused(
            f"the path {path_name} reads {aix.name}, which BLDINDEX has not built (reading it is not modelled)"
        )
    return sorted(base.records, key=lambda r: r[aix.key_off : aix.key_off + aix.key_len])


def run(
    sysin: str, catalog: dict[str, Cluster | Aix | Path], dds: dict[str, Sequential | Vsam] | None = None
) -> Result:
    """Run the commands of `sysin`. `catalog` is the clusters that exist when the step starts and `dds` the step's DDs
    (a `Sequential` dataset, or a `Vsam` naming a catalog cluster). Neither argument is changed: the step's effect is
    in the `Result`, whose `rc` is the step's return code."""
    stmts = _parse(sysin)
    st = _Step(catalog, dds or {})
    st.run(stmts)
    return Result(st.maxcc, st.lastcc, st.maxcc, st.catalog, st.seqs, st.log)
