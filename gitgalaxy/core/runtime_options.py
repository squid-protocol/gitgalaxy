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
        "reason": "isolation only matters between concurrent units of work; a proof runs one"},
    "db2.bind.CURRENTDATA": {"kind": "value", "default": "NO", "honoured": None, "policy": None,
        "reason": "CURRENTDATA only decides lock avoidance between concurrent units of work"},
    "db2.bind.DYNAMICRULES": {"kind": "value", "default": "RUN", "honoured": None, "policy": None,
        "reason": "DYNAMICRULES decides authorization and the qualifier of dynamic SQL, not a computed value"},
    "db2.bind.VALIDATE": {"kind": "value", "default": "RUN", "honoured": None, "policy": None,
        "reason": "VALIDATE only decides when a missing object is reported"},
    "db2.bind.ACTION": {"kind": "value", "default": "REPLACE", "honoured": None, "policy": None,
        "reason": "ACTION is a bind administration choice"},
    "db2.bind.packages": {"kind": "value", "default": "none", "honoured": None, "policy": None,
        "reason": "the package list names where a bound program lives, not what it computes"},
    "db2.precompile.PARM": {"kind": "value", "default": "", "honoured": None, "policy": None,
        "reason": "the precompiler PARM (HOST, APOST, XREF ...) is read from the source it was given; the corpus pin "
                  "fixes that source"},
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


def _state(value: Any) -> str:
    return str(value if value is not None else "").strip().upper()


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
    if row["policy"] is None:
        return "no effect"
    hit = runtime_unhonoured({path.split(".", 1)[0]: {path.split(".", 1)[1]: value}}, None, code_page)
    return "honoured" if not hit else ("declared" if hit[0]["policy"] == "declare" else "refused")
