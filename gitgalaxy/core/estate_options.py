# ==============================================================================
# GitGalaxy Core: an estate's compile and runtime options as one input (#4704)
#
# PURPOSE:
# "IBM is the reference" (#4702) means IBM's result under the options the estate actually uses. Those options come from
# three places, and the oracle (tests/tools/equivalence_common.py) and the det port each read them their own way:
# the compile step's PARM (a case's `compiler_options`), the program's CBL / PROCESS cards, IBM's defaults. This module
# is the one resolver both sides call, plus the estate options file that holds what the estate's own JCL, bind cards and
# region definitions say -- with the provenance of every value.
#
# THE FILE (tests/equivalence/estate_options/<corpus>.json, format gitgalaxy-estate-options/1; one per corpus in
# tests/cobol_mainframe/corpora.json):
#   compiler       product, version, installation_defaults (the shop's IGYCDOPT; a program with no PARM gets these)
#   parm           default (the PARM of the estate's compile step) and programs (a program built by another step
#                  has its own PARM: it replaces the default, as a different EXEC does)
#   le             Language Environment runtime options
#   db2            precompile and bind options
#   cics           translator, region (SIT) and program-definition options
# EVERY value is {"value", "source", "note"}; source is "<path in the corpus>:<line>" for a value found there (the
# schema test reads that line when the corpus is present) or "assumed: IBM default" / "assumed: owner decision" /
# "assumed: not stated in the corpus". Unknown is never blank: it is assumed, and says so.
#
# PRECEDENCE (IBM's order, lowest first): installation defaults < the compile step's PARM < the program's CBL / PROCESS
# cards (Enterprise COBOL for z/OS Programming Guide, "Compiler options", "Specifying compiler options under z/OS").
# A case's own `compiler_options` stand for a PARM the estate file does not hold and override the estate's PARM.
#
# A DECLARED DIFFERENCE: a PARM option may carry `applied_value` -- the value the proof runs under when the harness
# cannot honour the estate's (#4704 slice 1 so applied CBSA's TRUNC(OPT) as TRUNC(STD); #4706 honours OPT itself).
# The resolver applies `applied_value`, and lists the difference in `deviations` wherever it still shows in the
# program's final options, so no proof silently claims the estate's option.
#
# Slice 1 of #4704 (NUMPROC / TRUNC / ARITH / INTDATE, the options equivalence_common already honours).
# ==============================================================================
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gitgalaxy.core.compiler_options import (
    DEFAULTS,
    SEMANTIC_OPTIONS,
    compiler_options,
    effective,
    effective_with_defaults,
    rows_of,
)
from gitgalaxy.core.source_text import read_source

FORMAT = "gitgalaxy-estate-options/1"
ESTATE_OPTIONS_DIR = Path(__file__).resolve().parents[2] / "tests" / "equivalence" / "estate_options"
SECTIONS = ("compiler", "parm", "le", "db2", "cics")
ASSUMED = re.compile(r"^assumed: (IBM default|owner decision|not stated in the corpus)$")
FOUND = re.compile(r"^(?P<path>[^:\s][^:]*):(?P<line>[1-9][0-9]*)$")

# The shape of an estate options file, as a template to copy (and a schema test's input): every value has provenance.
TEMPLATE: dict[str, Any] = {
    "format": FORMAT,
    "estate": "<corpus name>",
    "corpus": "<corpus name>",
    "compiler": {
        "product": {
            "value": "Enterprise COBOL",
            "source": "path/in/corpus.jcl:7",
            "note": "where the build names IGYCRCTL",
        },
        "version": {"value": "6.3", "source": "assumed: IBM default", "note": "why"},
        "installation_defaults": {
            "TRUNC": {"value": "STD", "source": "assumed: IBM default", "note": "IGYCDOPT not seen"}
        },
    },
    "parm": {
        "default": [
            {
                "option": "TRUNC",
                "value": "OPT",
                "source": "path/in/corpus.jcl:7",
                "note": "the estate's compile PARM",
                "applied_value": "STD",
                "applied_note": "a value the harness cannot honour is applied as this, a declared difference",
            }
        ],
        "programs": {"PROGRAM": []},
    },
    "le": {"runtime_options": {"STORAGE": {"value": "NONE", "source": "assumed: IBM default", "note": "no CEEOPTS"}}},
    "db2": {},
    "cics": {},
}


def _text(option: str, value: Any) -> str:
    return option if value in (None, "") else f"{option}({value})"


def load_estate(corpus: str | None, directory: Path | None = None) -> dict[str, Any] | None:
    """The estate options file of a corpus, or None (a corpus without one: every option is IBM's default)."""
    if not corpus:
        return None
    path = (directory or ESTATE_OPTIONS_DIR) / f"{corpus}.json"
    if not path.is_file():
        return None
    return dict(json.loads(read_source(path).text))


@dataclass
class EffectiveOptions:
    """What one program is compiled and run under, before its own CBL / PROCESS cards (those come from the source,
    which the corpus pin fixes: `values` merges them in when the source text is given)."""

    estate: str | None
    program: str
    compiler: dict[str, str | None] = field(default_factory=dict)
    layers: list[str] = field(default_factory=list)  # PARM-level option texts, lowest first, `applied_value` applied
    declared: list[str] = field(default_factory=list)  # the same with the estate's own values
    sources: dict[str, str] = field(default_factory=dict)  # option -> where its value came from
    runtime: dict[str, dict[str, str | None]] = field(default_factory=dict)  # le / db2 / cics -> {name: value}

    def values(self, source_text: str = "") -> dict[str, str | None]:
        """{option: value} in force for the program: IBM's defaults under the layers under the program's cards."""
        return effective_with_defaults(self.layers, source_text)

    def deviations(self, source_text: str = "") -> list[dict[str, str | None]]:
        """The options whose final value in the estate's own terms is not the one applied: a declared difference."""
        applied = self.values(source_text)
        want = effective(rows_of(self.declared) + compiler_options(source_text))
        for option, default in DEFAULTS.items():
            want.setdefault(option, default)
        return [
            {"option": o, "declared": want[o], "applied": applied.get(o), "source": self.sources.get(o)}
            for o in sorted(want)
            if o in SEMANTIC_OPTIONS and str(want[o]).upper() != str(applied.get(o)).upper()
        ]

    def semantic(self, source_text: str = "") -> dict[str, str]:
        v = self.values(source_text)
        return {o: str(v.get(o) or "").upper() for o in SEMANTIC_OPTIONS if o in v}

    def fingerprint(self) -> dict[str, Any]:
        """The program's options as the evidence fingerprint hashes them: every value, no provenance (a changed note
        or source line is not a changed option), and not the program's own cards -- the corpus pin fixes those."""
        return {
            "estate": self.estate,
            "compiler": self.compiler,
            "parm": self.layers,
            "declared_parm": self.declared,
            "semantic": self.semantic(),
            "runtime": self.runtime,
        }


def _value(entry: Any) -> Any:
    return entry.get("value") if isinstance(entry, dict) else entry


def effective_options(
    case: dict[str, Any] | None, estate: dict[str, Any] | None = None, program: str | None = None
) -> EffectiveOptions:
    """The one resolver (#4704): the options `case`'s program is compiled under -- installation defaults < PARM < (the
    program's cards, added by .values(source)) -- with the provenance of the estate's values.

    `estate` is the estate options file (default: the case's corpus's file, if any); `case` may be None for a
    program of an estate with no case (then `program` names it). A case's `compiler` block (mortgage-mpmt's, the
    precedent) overrides the estate's compiler; its `compiler_options` are the last PARM layer."""
    case = case or {}
    if estate is None:
        estate = load_estate(case.get("corpus"))
    name = (program or case.get("program") or "").upper()
    est = estate or {}
    comp = est.get("compiler") or {}
    case_comp = case.get("compiler") or {}
    out = EffectiveOptions(
        estate=est.get("estate"),
        program=name,
        compiler={
            "product": case_comp.get("product") or _value(comp.get("product")),
            "version": case_comp.get("version") or _value(comp.get("version")),
        },
    )
    for option, entry in (comp.get("installation_defaults") or {}).items():
        out.layers.append(_text(option, _value(entry)))
        out.declared.append(_text(option, _value(entry)))
        out.sources[option] = str(entry.get("source")) if isinstance(entry, dict) else ""
    parm = est.get("parm") or {}
    programs = {k.upper(): v for k, v in (parm.get("programs") or {}).items()}
    for entry in programs.get(name, parm.get("default") or []):
        option, value = entry["option"], entry.get("value")
        out.declared.append(_text(option, value))
        out.layers.append(_text(option, entry.get("applied_value", value)))
        out.sources[option] = str(entry.get("source"))
    for text in case.get("compiler_options") or []:
        out.layers.append(text)
        out.declared.append(text)
    for section in ("le", "db2", "cics"):
        flat: dict[str, str | None] = {}
        for group, items in sorted((est.get(section) or {}).items()):
            for key, entry in sorted((items or {}).items()):
                flat[f"{group}.{key}"] = _value(entry)
        out.runtime[section] = flat
    return out


def validate(data: dict[str, Any]) -> list[str]:
    """Schema problems of one estate options file: a missing section, a value without provenance."""
    errs: list[str] = []
    if data.get("format") != FORMAT:
        errs.append(f"format is {data.get('format')!r}, not {FORMAT!r}")
    errs.extend(f"missing `{k}`" for k in ("estate", "corpus") if not data.get(k) or not isinstance(data[k], str))
    errs.extend(f"missing section `{s}`" for s in SECTIONS if s not in data)

    def check(entry: Any, where: str) -> None:
        if not isinstance(entry, dict) or "value" not in entry:
            errs.append(f"{where}: not a {{value, source, note}} entry")
            return
        src, note = entry.get("source"), entry.get("note")
        if not isinstance(src, str) or not (ASSUMED.match(src) or FOUND.match(src)):
            errs.append(f"{where}: source {src!r} is neither '<file>:<line>' nor 'assumed: ...'")
        if not isinstance(note, str) or not note.strip():
            errs.append(f"{where}: no note")
        if entry["value"] is None and not (isinstance(src, str) and src.startswith("assumed:")):
            errs.append(f"{where}: an unknown value (null) must be 'assumed'")
        if "applied_value" in entry and not entry.get("applied_note"):
            errs.append(f"{where}: applied_value without applied_note (a declared difference says why)")

    comp = data.get("compiler") or {}
    for key in ("product", "version"):
        check(comp.get(key), f"compiler.{key}")
    for opt, entry in (comp.get("installation_defaults") or {}).items():
        check(entry, f"compiler.installation_defaults.{opt}")
    parm = data.get("parm") or {}
    lists = {"parm.default": parm.get("default") or []}
    lists.update({f"parm.programs.{p}": v for p, v in (parm.get("programs") or {}).items()})
    for where, entries in lists.items():
        for i, entry in enumerate(entries):
            if not entry.get("option"):
                errs.append(f"{where}[{i}]: no option")
            check(entry, f"{where}[{i}] {entry.get('option')}")
    for section in ("le", "db2", "cics"):
        for group, items in (data.get(section) or {}).items():
            for key, entry in (items or {}).items():
                check(entry, f"{section}.{group}.{key}")
    return errs


def counts(data: dict[str, Any]) -> dict[str, int]:
    """{found, assumed} value counts of one estate file."""
    n = {"found": 0, "assumed": 0}

    def visit(o: Any) -> None:
        if isinstance(o, dict):
            if "value" in o and "source" in o:
                n["assumed" if str(o["source"]).startswith("assumed:") else "found"] += 1
            else:
                for v in o.values():
                    visit(v)
        elif isinstance(o, list):
            for v in o:
                visit(v)

    visit({k: v for k, v in data.items() if k in SECTIONS})
    return n
