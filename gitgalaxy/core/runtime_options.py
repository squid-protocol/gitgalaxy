# ==============================================================================
# GitGalaxy Core: the LE / Db2 / CICS runtime option table (#4707, part of #4704)
#
# PURPOSE:
# The estate options file (estate_options.py) records Language Environment, Db2 and CICS options with provenance, and
# the evidence fingerprint hashes them; this table says what each one MEANS to a proof, the way
# compiler_options.OPTION_TABLE does for the compile options. Per option: (1) does it change results, (2) can cobc
# honour it, (3) what the det port does, (4) otherwise refused by name or a declared difference (#4702: IBM is the
# reference, GnuCOBOL the instrument).
#
# KEYS are "<section>.<group>.<name>", the file's own path (`le.runtime_options.STORAGE`). A key the table does not
# know is refused by name, so a new estate file cannot record an option nothing has judged. The text of every row is
# rendered into docs/language_status/register/C18.md; tests/cobol_mainframe/test_runtime_option_table.py pins it.
# ==============================================================================
import re
from typing import Any

# kind "value": compared upper case against `honoured`; kind "ccsid": honoured for the default CCSIDs or the CCSID of
# the case's data (as CODEPAGE is). policy None: no run result depends on it (the row says why).
RUNTIME_OPTION_TABLE: dict[str, dict[str, Any]] = {
    "le.runtime_options.STORAGE": {"kind": "value", "default": "NONE,NONE,NONE,0K", "honoured": ("NONE,NONE,NONE,0K",),
        "policy": "declare", "applied": "GnuCOBOL's initial storage (spaces; zeros in a numeric DISPLAY item)",
        "reason": "STORAGE(heap-init, stack-init, ...) decides what WORKING-STORAGE with no VALUE clause holds; a run "
                  "that reads none is IBM's, and one that does is register L3's assumption"},
    "le.runtime_options.TRAP": {"kind": "value", "default": "ON,SPIE", "honoured": ("ON,SPIE", "ON,NOSPIE", "ON"),
        "policy": "refuse",
        "reason": "TRAP(OFF) leaves a program exception untrapped (the run continues past it, undefined); the "
                  "oracle and the det port both end the run on one"},
    "le.runtime_options.ABTERMENC": {"kind": "value", "default": "ABEND", "honoured": ("ABEND",), "policy": "refuse",
        "reason": "ABTERMENC(RETCODE) ends an unhandled condition with a return code instead of an abend; the "
                  "harness compares the abend"},
    "le.source.CEEOPTS": {"kind": "value", "default": "", "honoured": None, "policy": None,
        "reason": "the CEEOPTS member is only a carrier: what it sets is read into the le.runtime_options rows, each judged"},
    "le.source.CEEUOPT": {"kind": "value", "default": "", "honoured": None, "policy": None,
        "reason": "the CEEUOPT module is only a carrier: what it sets is read into the le.runtime_options rows, each judged"},
    "le.source.CEEDOPT": {"kind": "value", "default": "", "honoured": None, "policy": None,
        "reason": "the CEEDOPT installation default is only a carrier: what it sets is read into the le.runtime_options rows, each judged"},
    "db2.format.DATE": {"kind": "value", "default": "ISO", "honoured": ("ISO",), "policy": "refuse",
        "reason": "DATE(USA|EUR|JIS|LOCAL) changes the string of every date a program fetches or compares; the Db2 "
                  "cases run in ISO"},
    "db2.format.TIME": {"kind": "value", "default": "ISO", "honoured": ("ISO",), "policy": "refuse",
        "reason": "TIME(USA|EUR|JIS|LOCAL) changes the string of every time a program fetches or compares; the Db2 "
                  "cases run in ISO"},
    "db2.format.DEC": {"kind": "value", "default": "15", "honoured": ("15",), "policy": "refuse",
        "reason": "DEC(31) widens the precision of decimal arithmetic in SQL; the Db2 cases run in DEC(15)"},
    "db2.format.DECPT": {"kind": "value", "default": ".", "honoured": (".",), "policy": "refuse",
        "reason": "DECPT(,) makes the decimal point of SQL literals a comma; the Db2 cases run with a period"},
    "db2.ccsid.EBCDIC_CCSID": {"kind": "ccsid", "default": "37", "honoured": ("37", "1140"), "policy": "declare",
        "applied": "data in the case's data_encoding",
        "reason": "the Db2 subsystem's EBCDIC CCSID is the code page of character columns; the proof runs the "
                  "case's data in its data_encoding"},
    "db2.ccsid.SQLCCSID": {"kind": "value", "default": "NO", "honoured": ("NO",), "policy": "refuse",
        "reason": "SQLCCSID(YES) passes SQL host text in the CCSID of the program's source; the harness does not "
                  "model the conversion"},
    "db2.bind.ISOLATION": {"kind": "value", "default": "CS", "honoured": None, "policy": None,
        "reason": "isolation only matters between concurrent units of work; a proof runs one (the value is judged, BIND_OPTIONS)"},
    "db2.bind.CURRENTDATA": {"kind": "value", "default": "NO", "honoured": None, "policy": None,
        "reason": "CURRENTDATA only decides lock avoidance between concurrent units of work (the value is judged, BIND_OPTIONS)"},
    "db2.bind.DYNAMICRULES": {"kind": "value", "default": "RUN", "honoured": None, "policy": None,
        "reason": "DYNAMICRULES decides authorization and the qualifier of dynamic SQL, not a computed value (the value is judged, BIND_OPTIONS)"},
    "db2.bind.VALIDATE": {"kind": "value", "default": "RUN", "honoured": None, "policy": None,
        "reason": "VALIDATE only decides when a missing object is reported (the value is judged, BIND_OPTIONS)"},
    "db2.bind.ACTION": {"kind": "value", "default": "REPLACE", "honoured": None, "policy": None,
        "reason": "ACTION is a bind administration choice"},
    "db2.bind.packages": {"kind": "value", "default": "none", "honoured": None, "policy": None,
        "reason": "the package list names where a bound program lives, not what it computes"},
    "db2.precompile.PARM": {"kind": "value", "default": "", "honoured": None, "policy": None,
        "reason": "the precompiler PARM is judged token by token (PRECOMPILE_OPTIONS): a listing or delimiter token "
                  "changes no result, one that changes SQL text, dates, decimals or code pages is refused by name"},
    "db2.precompile.coprocessor": {"kind": "value", "default": "", "honoured": None, "policy": None,
        "reason": "how SQL reaches the compiler (precompiler or integrated coprocessor) is a build route; the det "
                  "translator reads the SQL statements themselves"},
    "cics.region.LOCALCCSID": {"kind": "ccsid", "default": "37", "honoured": ("37", "1140"), "policy": "declare",
        "applied": "data in the case's data_encoding",
        "reason": "LOCALCCSID is the region's code page for EBCDIC <-> client conversion; the proof runs the case's "
                  "data in its data_encoding"},
    "cics.region.CICS_TS": {"kind": "value", "default": "", "honoured": None, "policy": None,
        "reason": "the CICS release is recorded for provenance; the command spec (X-series) states what is modelled"},
    "cics.region.DB2CONN": {"kind": "value", "default": "", "honoured": None, "policy": None,
        "reason": "whether the region connects to Db2 is a deployment fact; the Db2 cases name their own tables"},
    "cics.translator.options": {"kind": "value", "default": "", "honoured": None, "policy": None,
        "reason": "translator options (CICS, SP, EDF ...) are read from the source it was given; EXEC CICS commands "
                  "are refused or modelled by the CICS spec"},
    "cics.program_definition.CONCURRENCY": {"kind": "value", "default": "QUASIRENT", "honoured": None, "policy": None,
        "reason": "THREADSAFE only matters between concurrent tasks; a proof runs one"},
    "cics.program_definition.EXECKEY": {"kind": "value", "default": "USER", "honoured": None, "policy": None,
        "reason": "EXECKEY decides storage protection, not a computed value"},
}  # fmt: skip


# #4707: the CICS translator options, judged one by one (the options file records them as one string). policy None: the
# option changes the listing or the build, not the generated code a run executes; "refuse": it changes the generated
# code or data layout, which the harness does not model. A token with no row is refused by name.
TRANSLATOR_OPTIONS: dict[str, dict[str, Any]] = {
    "CICS": {"policy": None, "reason": "selects the translator's CICS command set; the default for a CICS program"},
    "SP": {"policy": None, "reason": "the system-programming command set is read from the source it was given"},
    "EDF": {"policy": None, "reason": "EDF only adds debugging-transaction hooks around each command"},
    "NOEDF": {"policy": None, "reason": "NOEDF removes the debugging-transaction hooks; no result depends on them"},
    "DEBUG": {"policy": None, "reason": "DEBUG only adds debugging-tool hooks"},
    "NODEBUG": {"policy": None, "reason": "NODEBUG removes debugging-tool hooks"},
    "FLAG": {"policy": None, "reason": "FLAG chooses which translator messages are listed"},
    "SOURCE": {"policy": None, "reason": "a listing option"},
    "NOSOURCE": {"policy": None, "reason": "a listing option"},
    "XREF": {"policy": None, "reason": "a listing option"},
    "NOXREF": {"policy": None, "reason": "a listing option"},
    "APOST": {"policy": None, "reason": "the delimiter the translator writes into its own generated text"},
    "QUOTE": {"policy": None, "reason": "the delimiter the translator writes into its own generated text"},
    "CPSM": {"policy": None, "reason": "adds the CICSPlex SM command set"},
    "COBOL2": {"policy": "refuse", "reason": "COBOL2 changes the layout of the generated working storage; not modelled"},
    "COBOL3": {"policy": "refuse", "reason": "COBOL3 changes the layout of the generated working storage; not modelled"},
    "GRAPHIC": {"policy": "refuse", "reason": "GRAPHIC changes how DBCS literals in commands are read; not modelled"},
    "NATLANG": {"policy": "refuse", "reason": "NATLANG changes the language of messages the generated code issues; not modelled"},
}  # fmt: skip
TRANSLATOR_OPTION = "cics.translator.options"
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]*")


def translator_tokens(value: Any) -> list[str]:
    """The upper-case option tokens of a recorded translator value (`CICS('SP,EDF') via the CBL card` is CICS, SP, EDF):
    the text before a ' via ' note, a token being letters and digits."""
    text = str(value if value is not None else "").split(" via ", 1)[0]
    return [t.upper() for t in _TOKEN.findall(text)]


def translator_rows() -> list[str]:
    """The TRANSLATOR_OPTIONS rows as the markdown table lines register C18 holds (tests pin the page to them)."""
    return [
        f"| `cics.translator.{key}` | {'no' if r['policy'] is None else 'yes'}: {r['reason']} | "
        f"{'recorded only' if r['policy'] is None else 'refused by name'} |"
        for key, r in TRANSLATOR_OPTIONS.items()
    ]


# #4707: the Db2 precompiler PARM, judged token by token (the options file records it as one string). A token is NAME or
# NAME(arg). policy None: no result depends on it. policy "refuse": it changes SQL text, dates, decimals or code pages,
# so it is refused by name unless its argument is in `honoured` (the IBM default the harness runs under). A token with
# no row is refused by name.
PRECOMPILE_OPTIONS: dict[str, dict[str, Any]] = {
    "HOST": {"policy": "refuse", "honoured": ("IBMCOB", "COBOL"),
        "reason": "HOST names the host language whose declarations the precompiler reads; only COBOL is modelled"},
    "APOST": {"policy": None, "reason": "the delimiter the precompiler writes into its own generated COBOL"},
    "QUOTE": {"policy": None, "reason": "the delimiter the precompiler writes into its own generated COBOL"},
    "XREF": {"policy": None, "reason": "a listing option"},
    "NOXREF": {"policy": None, "reason": "a listing option"},
    "SOURCE": {"policy": None, "reason": "a listing option"},
    "NOSOURCE": {"policy": None, "reason": "a listing option"},
    "FLAG": {"policy": None, "reason": "FLAG chooses which precompiler messages are listed"},
    "LINECOUNT": {"policy": None, "reason": "a listing option (lines per page)"},
    "ONEPASS": {"policy": None, "reason": "how many passes the precompiler makes over the source"},
    "TWOPASS": {"policy": None, "reason": "how many passes the precompiler makes over the source"},
    "APOSTSQL": {"policy": None, "reason": "the Db2 default: the apostrophe delimits an SQL string"},
    "QUOTESQL": {"policy": "refuse", "honoured": (),
        "reason": "QUOTESQL swaps the SQL string and delimited-identifier delimiters, so SQL text is read differently"},
    "DATE": {"policy": "refuse", "honoured": ("ISO",),
        "reason": "DATE decides the format of every date string; only ISO is modelled (db2.format.DATE)"},
    "TIME": {"policy": "refuse", "honoured": ("ISO",),
        "reason": "TIME decides the format of every time string; only ISO is modelled (db2.format.TIME)"},
    "DEC": {"policy": "refuse", "honoured": ("15", "15."),
        "reason": "DEC(31) changes decimal arithmetic precision; only DEC(15) is modelled (db2.format.DEC)"},
    "DECPT": {"policy": "refuse", "honoured": (".", "PERIOD"),
        "reason": "DECPT decides the decimal point of SQL literals; only the period is modelled (db2.format.DECPT)"},
    "CCSID": {"policy": "refuse", "honoured": ("37", "1140"),
        "reason": "CCSID decides the code page of SQL character data; see db2.ccsid.EBCDIC_CCSID"},
    "STDSQL": {"policy": "refuse", "honoured": ("NO",),
        "reason": "STDSQL(YES) changes SQLCODE / SQLSTATE handling and host-variable rules; not modelled"},
    "SQL": {"policy": "refuse", "honoured": ("DB2",),
        "reason": "SQL(ALL) changes which SQL statements the precompiler accepts; not modelled"},
    "GRAPHIC": {"policy": "refuse", "honoured": (),
        "reason": "GRAPHIC changes how DBCS literals in SQL are read; not modelled"},
}  # fmt: skip
PRECOMPILE_OPTION = "db2.precompile.PARM"
_PARM_TOKEN = re.compile(r"([A-Za-z][A-Za-z0-9]*)(?:\(([^)]*)\))?")


def precompile_tokens(value: Any) -> list[tuple[str, str | None]]:
    """The (NAME, arg) pairs of a recorded precompiler PARM (`HOST(IBMCOB),XREF,FLAG(I)` is HOST IBMCOB, XREF None,
    FLAG I): the text before a ' via ' note, a name upper-cased, an argument stripped and upper-cased."""
    text = str(value if value is not None else "").split(" via ", 1)[0]
    return [
        (m.group(1).upper(), None if m.group(2) is None else m.group(2).strip().upper())
        for m in _PARM_TOKEN.finditer(text)
    ]


def precompile_rows() -> list[str]:
    """The PRECOMPILE_OPTIONS rows as the markdown table lines register C18 holds (tests pin the page to them)."""
    return [
        f"| `db2.precompile.PARM.{key}` | {'no' if r['policy'] is None else 'yes'}: {r['reason']} | "
        f"{'recorded only' if r['policy'] is None else 'refused by name unless ' + (', '.join(r['honoured']) or 'never')} |"
        for key, r in PRECOMPILE_OPTIONS.items()
    ]


def _precompile_hits(path: str, value: Any, source: str | None) -> list[dict[str, Any]]:
    hits = []
    for name, arg in precompile_tokens(value):
        row = PRECOMPILE_OPTIONS.get(name)
        if row is not None and (row["policy"] is None or (arg is not None and arg in row["honoured"])):
            continue
        token = name if arg is None else f"{name}({arg})"
        why = row["reason"] if row else "no row in the precompiler PARM table"
        hits.append({"option": path, "declared": token, "policy": "refuse", "applied": None, "source": source,
                     "note": f"{path}={value}: {token}: {why} (#4707)"})  # fmt: skip
    return hits


# #4707: the Db2 bind options whose value is judged. The rows above stay policy None (no run result depends on a value
# the harness accepts, so a z/OS measurement need not state them); a value outside `values` is not one IBM accepts for
# that option (or, for DYNAMICRULES, takes a routine owner's context the harness does not model), so it is refused by name.
BIND_OPTIONS: dict[str, dict[str, Any]] = {
    "ISOLATION": {"values": ("CS", "UR", "RR", "RS"),
        "reason": "a proof runs one unit of work, and a program sees its own updates at every isolation level"},
    "CURRENTDATA": {"values": ("YES", "NO"),
        "reason": "CURRENTDATA only decides lock avoidance and block fetch between concurrent units of work"},
    "DYNAMICRULES": {"values": ("RUN", "BIND"),
        "reason": "RUN and BIND only change the authorization and qualifier of dynamic SQL, which no burned program "
                  "issues; DEFINE* and INVOKE* take a routine owner's context, which is not modelled"},
    "VALIDATE": {"values": ("RUN", "BIND"),
        "reason": "VALIDATE only decides when a missing object is reported; a program that ran found every object"},
}  # fmt: skip
BIND_PREFIX = "db2.bind."


def bind_rows() -> list[str]:
    """The BIND_OPTIONS rows as the markdown table lines register C18 holds (tests pin the page to them)."""
    return [
        f"| `{BIND_PREFIX}{key}` | no: {r['reason']} | recorded only for {', '.join(r['values'])}; any other value "
        "refused by name |"
        for key, r in BIND_OPTIONS.items()
    ]


def _bind_hits(path: str, value: Any, source: str | None) -> list[dict[str, Any]]:
    row = BIND_OPTIONS.get(path[len(BIND_PREFIX) :])
    state = _state(value)
    if row is None or state in row["values"]:
        return []
    return [{"option": path, "declared": state, "policy": "refuse", "applied": None, "source": source,
             "note": f"{path}={value}: not a value the harness runs under ({', '.join(row['values'])}): "
                     f"{row['reason']} (#4707)"}]  # fmt: skip


# #4707: the Language Environment options whose value is judged for syntax. The rows above keep their policy (a
# well-formed value is honoured, declared or refused exactly as before); a value that is not LE syntax at all is not
# one IBM accepts, so it is refused by name instead of being declared or blamed on TRAP(OFF) / RETCODE.
# `normal` returns the value with omitted fields filled in, or None if malformed (only used to judge syntax: the outcome
# of a well-formed value is still decided on the spelling the file records).
LE_PREFIX = "le.runtime_options."
_STORAGE_DEFAULT = ("NONE", "NONE", "NONE", "0K")


def _normal_storage(state: str) -> str | None:
    fields = [f.strip() for f in state.split(",")]
    if len(fields) > 4 or fields == [""]:
        return None
    out = list(_STORAGE_DEFAULT)
    for i, field in enumerate(fields):
        if not field:
            continue  # an omitted positional field keeps the IBM default
        if i < 3 and (field == "NONE" or re.fullmatch(r"[0-9A-F]{2}", field)):
            out[i] = field
        elif i == 3 and (m := re.fullmatch(r"(\d+)(K?)", field)):
            out[i] = "0K" if int(m.group(1)) == 0 else field
        else:
            return None
    return ",".join(out)


def _normal_trap(state: str) -> str | None:
    fields = [f.strip() for f in state.split(",")]
    if fields[0] in ("ON", "OFF") and (len(fields) == 1 or (len(fields) == 2 and fields[1] in ("SPIE", "NOSPIE"))):
        return ",".join(fields)
    return None


LE_OPTIONS: dict[str, dict[str, Any]] = {
    "STORAGE": {"normal": _normal_storage,
        "grammar": "up to four comma-separated fields: allocated-storage init, freed-storage init, stack init (each NONE "
                   "or a two-digit hex byte), reserve size (digits, optional K); an omitted field is allowed"},
    "TRAP": {"normal": _normal_trap, "grammar": "ON or OFF, optionally followed by SPIE or NOSPIE"},
    "ABTERMENC": {"normal": lambda state: state if state in ("ABEND", "RETCODE") else None,
        "grammar": "ABEND or RETCODE"},
}  # fmt: skip


def le_rows() -> list[str]:
    """The LE_OPTIONS rows as the markdown table lines register C18 holds (tests pin the page to them)."""
    return [
        f"| `{LE_PREFIX}{key}` | {r['grammar']} | a value outside this syntax is refused by name; a well-formed one "
        "is judged by the row above |"
        for key, r in LE_OPTIONS.items()
    ]


def _le_hits(path: str, value: Any, source: str | None) -> list[dict[str, Any]]:
    row = LE_OPTIONS.get(path[len(LE_PREFIX) :]) if path.startswith(LE_PREFIX) else None
    if row is None or row["normal"](_state(value)) is not None:
        return []
    return [{"option": path, "declared": _state(value), "policy": "refuse", "applied": None, "source": source,
             "note": f"{path}={value}: not Language Environment syntax ({row['grammar']}) (#4707)"}]  # fmt: skip


# #4707: the Db2 format and CCSID options whose value is judged for syntax, the same way as the LE rows: a well-formed
# value keeps its outcome (ISO honoured, USA refused, a CCSID declared), one that is not Db2 syntax is refused by name.
DB2_PREFIX = "db2."


def _one_of(*names: str) -> Any:
    return lambda state: state if state in names else None


def _normal_ccsid(state: str) -> str | None:
    return state if re.fullmatch(r"\d{1,5}", state) and int(state) > 0 else None


DB2_OPTIONS: dict[str, dict[str, Any]] = {
    "format.DATE": {"normal": _one_of("ISO", "USA", "EUR", "JIS", "LOCAL"), "grammar": "ISO, USA, EUR, JIS or LOCAL"},
    "format.TIME": {"normal": _one_of("ISO", "USA", "EUR", "JIS", "LOCAL"), "grammar": "ISO, USA, EUR, JIS or LOCAL"},
    "format.DEC": {"normal": _one_of("15", "31", "15.", "31."), "grammar": "15 or 31, optionally followed by a period"},
    "format.DECPT": {"normal": _one_of(".", ",", "PERIOD", "COMMA"), "grammar": "a period or a comma, or PERIOD or COMMA"},
    "ccsid.SQLCCSID": {"normal": _one_of("YES", "NO"), "grammar": "YES or NO"},
    "ccsid.EBCDIC_CCSID": {"normal": _normal_ccsid, "grammar": "a CCSID: one to five digits, not zero"},
}  # fmt: skip


def db2_rows() -> list[str]:
    """The DB2_OPTIONS rows as the markdown table lines register C18 holds (tests pin the page to them)."""
    return [
        f"| `{DB2_PREFIX}{key}` | {r['grammar']} | a value outside this syntax is refused by name; a well-formed one "
        "is judged by the row above |"
        for key, r in DB2_OPTIONS.items()
    ]


def _db2_hits(path: str, value: Any, source: str | None) -> list[dict[str, Any]]:
    row = DB2_OPTIONS.get(path[len(DB2_PREFIX) :]) if path.startswith(DB2_PREFIX) else None
    if row is None or row["normal"](_state(value)) is not None:
        return []
    return [{"option": path, "declared": _state(value), "policy": "refuse", "applied": None, "source": source,
             "note": f"{path}={value}: not Db2 syntax ({row['grammar']}) (#4707)"}]  # fmt: skip


# #4707: the CICS region and program-definition options whose value is judged for syntax, the same way: a well-formed
# value keeps its outcome (LOCALCCSID 37 honoured, another CCSID declared), one that is not CICS syntax is refused by name.
CICS_PREFIX = "cics."

CICS_OPTIONS: dict[str, dict[str, Any]] = {
    "region.LOCALCCSID": {"normal": _normal_ccsid, "grammar": "a CCSID: one to five digits, not zero"},
    "region.DB2CONN": {"normal": _one_of("YES", "NO"), "grammar": "YES or NO"},
    "region.CICS_TS": {"normal": lambda s: s if re.fullmatch(r"\d{1,2}(\.\d{1,2}){0,2}", s) else None,
                       "grammar": "a release number: digits and periods, such as 4.2 or 5.6"},
    "program_definition.CONCURRENCY": {"normal": _one_of("QUASIRENT", "THREADSAFE", "REQUIRED"),
                                       "grammar": "QUASIRENT, THREADSAFE or REQUIRED"},
    "program_definition.EXECKEY": {"normal": _one_of("USER", "CICS"), "grammar": "USER or CICS"},
}  # fmt: skip


def cics_rows() -> list[str]:
    """The CICS_OPTIONS rows as the markdown table lines register C18 holds (tests pin the page to them)."""
    return [
        f"| `{CICS_PREFIX}{key}` | {r['grammar']} | a value outside this syntax is refused by name; a well-formed one "
        "is judged by the row above |"
        for key, r in CICS_OPTIONS.items()
    ]


def _cics_hits(path: str, value: Any, source: str | None) -> list[dict[str, Any]]:
    row = CICS_OPTIONS.get(path[len(CICS_PREFIX) :]) if path.startswith(CICS_PREFIX) else None
    if row is None or row["normal"](_state(value)) is not None:
        return []
    return [{"option": path, "declared": _state(value), "policy": "refuse", "applied": None, "source": source,
             "note": f"{path}={value}: not CICS syntax ({row['grammar']}) (#4707)"}]  # fmt: skip


# #4707: which burned estates exercise each judged option (policy refuse or declare): the corpora whose source holds the
# construct the row says the option changes. An empty list says no burned program depends on the assumed value, so a
# refusal there protects a customer's estate only. The test greps the corpora for each pattern (STORAGE rests on
# register L3's two named programs instead).
RUNTIME_USED_BY: dict[str, list[str]] = {
    "le.runtime_options.STORAGE": ["aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa"],
    "le.runtime_options.TRAP": ["aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa", "cics-genapp", "dbb-mortgage-application", "zecs"],
    "le.runtime_options.ABTERMENC": ["aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa", "cics-genapp", "dbb-mortgage-application"],
    "db2.format.DATE": ["aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa"],
    "db2.format.TIME": [],
    "db2.format.DEC": [],
    "db2.format.DECPT": [],
    "db2.ccsid.EBCDIC_CCSID": ["aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa", "cics-genapp", "dbb-mortgage-application"],
    "db2.ccsid.SQLCCSID": ["aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa", "cics-genapp", "dbb-mortgage-application"],
    "cics.region.LOCALCCSID": ["aws-mainframe-modernization-carddemo", "cics-async-api-credit-card-application-example", "cics-banking-sample-application-cbsa", "cics-genapp", "dbb-mortgage-application", "zecs"],
}  # fmt: skip


def used_by_rows() -> list[str]:
    """The RUNTIME_USED_BY rows as the markdown table lines register C18 holds (tests pin the page to them)."""
    return [
        f"| `{path}` | {', '.join(corpora) or 'none: no burned program depends on it'} |"
        for path, corpora in RUNTIME_USED_BY.items()
    ]


def _state(value: Any) -> str:
    return str(value if value is not None else "").strip().upper()


def _translator_hits(path: str, value: Any, source: str | None) -> list[dict[str, Any]]:
    hits = []
    for token in translator_tokens(value):
        row = TRANSLATOR_OPTIONS.get(token)
        if row is None or row["policy"]:
            why = row["reason"] if row else "no row in the translator option table"
            hits.append({"option": path, "declared": token, "policy": "refuse", "applied": None, "source": source,
                         "note": f"{path}={value}: {token}: {why} (#4707)"})  # fmt: skip
    return hits


def runtime_unhonoured(
    runtime: dict[str, dict[str, Any]],
    sources: dict[str, str] | None = None,
    code_page: str | None = None,
) -> list[dict[str, Any]]:
    """The runtime options in `runtime` ({section: {"group.name": value}}, EffectiveOptions.runtime) the harness cannot
    honour, in file order: [{option, declared, policy, applied, note, source}], `policy` "refuse" (the proof stops by
    name) or "declare" (proven under `applied`, a declared difference). An option the table does not know is refused.
    `code_page`: the CCSID of the case's data, which a "ccsid" row is honoured against."""
    out = []
    for section, items in runtime.items():
        for key, value in items.items():
            path = f"{section}.{key}"
            row = RUNTIME_OPTION_TABLE.get(path)
            state = _state(value)
            if row is None:
                out.append({"option": path, "declared": state, "policy": "refuse", "applied": None, "source": (sources or {}).get(path),
                            "note": f"{path}={value}: no row in the runtime option table (#4707)"})  # fmt: skip
                continue
            if row["kind"] == "ccsid":
                state = state.lstrip("0")  # 037 is 37
            src = (sources or {}).get(path)
            if bad := _le_hits(path, value, src) or _db2_hits(path, value, src) or _cics_hits(path, value, src):
                out.extend(bad)
                continue
            if path == TRANSLATOR_OPTION:
                out.extend(_translator_hits(path, value, (sources or {}).get(path)))
            elif path == PRECOMPILE_OPTION:
                out.extend(_precompile_hits(path, value, (sources or {}).get(path)))
            elif path.startswith(BIND_PREFIX):
                out.extend(_bind_hits(path, value, (sources or {}).get(path)))
            if row["policy"] is None or state in row["honoured"] or (row["kind"] == "ccsid" and state == code_page):
                continue
            out.append({"option": path, "declared": state, "policy": row["policy"], "source": (sources or {}).get(path),
                        "applied": row.get("applied") if row["policy"] == "declare" else None,
                        "note": f"{path}={value}: {row['reason']}"})  # fmt: skip
    return out


def runtime_effect(path: str, value: Any, code_page: str | None = None) -> str:
    """How one runtime value stands against the table: "no effect", "honoured", "declared", "refused" or "unjudged"."""
    row = RUNTIME_OPTION_TABLE.get(path)
    if row is None:
        return "unjudged"
    hit = runtime_unhonoured({path.split(".", 1)[0]: {path.split(".", 1)[1]: value}}, None, code_page)
    if row["policy"] is None:
        return "refused" if hit else "no effect"  # a recorded-only row still refuses a value that is not its syntax
    return "honoured" if not hit else ("declared" if hit[0]["policy"] == "declare" else "refused")


def calibration_problems(under: Any) -> list[str]:
    """The problems of the runtime options a z/OS measurement says it was taken under (#4702 part 2): `under` is
    {"le.runtime_options.TRAP": "ON,SPIE", ...}. A measured IBM result only calibrates a proof run under the same
    effective options, so every option the table judges (policy refuse or declare) must be stated, a key the table does
    not know is refused, and a value the harness cannot honour is named (the measurement does not transfer to it)."""
    if not isinstance(under, dict) or not under:
        return ["calibrated_under is a non-empty {option path: value} object"]
    probs = [f"{path}: no row in the runtime option table" for path in under if path not in RUNTIME_OPTION_TABLE]
    probs += [
        f"{path}: judged by the table (policy {row['policy']}) and not stated"
        for path, row in RUNTIME_OPTION_TABLE.items()
        if row["policy"] and path not in under
    ]
    known: dict[str, dict[str, Any]] = {}
    for path, value in under.items():
        if path in RUNTIME_OPTION_TABLE:
            section, _, key = path.partition(".")
            known.setdefault(section, {})[key] = value
    probs += [
        f"{hit['option']}={hit['declared']}: measured under a value the harness cannot honour ({hit['policy']})"
        for hit in runtime_unhonoured(known)
        if hit["option"] in RUNTIME_OPTION_TABLE
    ]
    return probs


# #4707: the CICS conventions a result depends on that no options file records: the EIB fields a program reads and
# the abend conventions. Same four answers as the option rows. `register`: the entries that state it (an empty list
# is a gap, named in `note`). `used_by`: the burned corpora whose COBOL names the field (a test greps them).
CICS_CONVENTIONS: dict[str, dict[str, Any]] = {
    "EIBCALEN": {"changes": "yes: the length of the COMMAREA the task started with; programs branch on 0", "cobc": "the stub's WS-LEN",
        "det": "the runner-stated COMMAREA length", "otherwise": "a reference past EIBCALEN is refused by name",
        "register": ["X23", "X10"], "used_by": ["aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa", "cics-genapp", "dbb-mortgage-application"]},
    "EIBAID": {"changes": "yes: the key pressed selects the screen path", "cobc": "the case's AID name, moved by the stub",
        "det": "the case's AID name; HANDLE AID reads it", "otherwise": "a task started without a terminal has none (IBM is silent): not read",
        "register": ["X16", "X27"], "used_by": ["aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa", "dbb-mortgage-application"]},
    "EIBRESP": {"changes": "yes: the numeric condition of the last command", "cobc": "the stub's GG-RESP",
        "det": "the runtime's response code", "otherwise": "a command or condition IBM leaves open is refused by name",
        "register": ["X28", "X21"], "used_by": ["aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa", "zecs"]},
    "EIBRESP2": {"changes": "yes: the reason code of the last command", "cobc": "the stub's GG-RESP2",
        "det": "the runtime's reason code", "otherwise": "a reason code IBM does not document is refused by name",
        "register": ["X28", "X21"], "used_by": ["cics-banking-sample-application-cbsa", "cics-genapp", "zecs"]},
    "EIBTASKN": {"changes": "yes when a program stores or compares it", "cobc": "the stub's $GGCICS_TASKN",
        "det": "the runner-stated task number", "otherwise": "DIFFERS from z/OS in value, both sides agree (declared)",
        "register": ["X21"], "used_by": ["cics-banking-sample-application-cbsa", "cics-genapp", "zecs"]},
    "EIBTRNID": {"changes": "yes: the transaction id a program routes on", "cobc": "the case's transid, moved by the stub",
        "det": "task.transid()", "otherwise": "the case's transid, ASSUMED to be the region's; not validated (X68)",
        "register": ["X68"], "used_by": ["cics-banking-sample-application-cbsa", "cics-genapp", "zecs"]},
    "EIBTRMID": {"changes": "yes when a program starts a task at its own terminal", "cobc": "the case's termid, moved by the stub",
        "det": "task.termid(), blanks for a task with none", "otherwise": "ASSUMED",
        "register": ["X18"], "used_by": ["cics-banking-sample-application-cbsa", "cics-genapp"]},
    "EIBDS": {"changes": "yes when a program reads the last data set referred to", "cobc": "set before a file control command",
        "det": "set before a file control command, only in a program that reads it", "otherwise": "ASSUMED",
        "register": ["X64"], "used_by": ["zecs"]},
    "EIBRCODE": {"changes": "yes: the six-byte response code", "cobc": "none", "det": "none",
        "otherwise": "unmodelled: a program that reads it is refused by name", "register": ["X64"],
        "used_by": ["cics-banking-sample-application-cbsa", "zecs"]},
    "EIBFN": {"changes": "yes: the code of the last command", "cobc": "none", "det": "none",
        "otherwise": "unmodelled: a program that reads it is refused by name", "register": ["X64"], "used_by": ["zecs"]},
    "ABEND.ABCODE": {"changes": "yes: the four-character abend code is compared", "cobc": "the stub's abend code",
        "det": "the runtime's abend code", "otherwise": "a code IBM does not state (an unknown mapset: ABM0) is ASSUMED",
        "register": ["X31", "X5"], "used_by": []},
    "ABEND.HANDLE_ABEND": {"changes": "yes: a handled abend continues in the program's routine", "cobc": "modelled by the stub",
        "det": "modelled by the runtime", "otherwise": "forms IBM leaves open are refused by name",
        "register": ["X16", "X5"], "used_by": []},
    "ABEND.UNHANDLED": {"changes": "yes: the task ends with the abend", "cobc": "the harness compares the abend",
        "det": "the harness compares the abend", "otherwise": "ABTERMENC(RETCODE) is refused by name (le.runtime_options.ABTERMENC)",
        "register": ["C18"], "used_by": []},
}  # fmt: skip


def conventions_rows() -> list[str]:
    """The CICS_CONVENTIONS rows as the markdown table lines register C18 holds (tests pin the page to them)."""
    return [
        f"| `cics.convention.{key}` | {r['changes']} | {r['cobc']} | {r['det']} | {r['otherwise']} | "
        f"{', '.join(r['register']) or 'none (gap)'} |"
        for key, r in CICS_CONVENTIONS.items()
    ]
