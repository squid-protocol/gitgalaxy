# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4726: what `gitgalaxy assess` may write, and the one function that writes it.

The raw inventory (`inventory.scan_estate`) is built from source text and can carry some: a parser's message quoting
a line, a sequence-area number read as a CICS command word, a word after FUNCTION that is a data name. `project` is
the only path from it to a report, and it lets through only:

  counts and integers (eras, totals);
  feature names from closed vocabularies -- the CICS command spec's words, the COBOL statement and intrinsic function
    names, the SQL statement forms, the data types, the semantic compile options, the refusal families, the era
    tells. A key outside its vocabulary is counted under `other` (how many keys, occurrences, programs), never
    written;
  program names (estate-relative paths) and copybook member names, or under redaction their keyed-hash labels;
  statuses and reasons from fixed sets (an exception's class name, never its message).

`validate` re-checks a report against those rules, so a later change to `project` cannot widen it unnoticed.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections import defaultdict
from typing import Any

from gitgalaxy.core.cics_macro_level import FAMILIES
from gitgalaxy.core.compiler_options import SEMANTIC_OPTIONS
from gitgalaxy.tools.readiness.era_tags import TELLS

SCHEMA = "gitgalaxy-assess/1"
CATEGORIES = (
    "statements",
    "data_types",
    "cics_commands",
    "cics_options",
    "sql_forms",
    "intrinsic_functions",
    "compile_options",
    "refusal_families",
)
UNKNOWN = "unknown"  # the inventory's own word: a construct the parser could not read
PARSED, UNPARSED, REFUSED = "parsed", "unparsed", "refused by family"
STATUSES = (PARSED, UNPARSED, REFUSED)
MISSING_COPYBOOK = "missing copybook"
KINDS = ("cobol", "assembler")

# COBOL statements as the det parser and the census fallback name them: IBM Enterprise COBOL verbs, plus the parser's
# own kinds (ARITH for ADD / SUBTRACT / MULTIPLY / DIVIDE, GOTO, the SET forms, HOLE).
STATEMENTS = frozenset({
    "ACCEPT", "ADD", "ALLOCATE", "ALTER", "ARITH", "CALL", "CANCEL", "CLOSE", "COMPUTE", "CONTINUE", "DELETE",
    "DISPLAY", "DIVIDE", "ENTRY", "EVALUATE", "EXEC", "EXHIBIT", "EXIT", "FREE", "GO", "GOBACK", "GOTO", "HOLE",
    "IF", "INITIALIZE", "INSPECT", "INVOKE", "JSON", "MERGE", "MOVE", "MULTIPLY", "NEXT-SENTENCE", "OPEN",
    "PERFORM", "READ", "RELEASE", "RETURN", "REWRITE", "SEARCH", "SET", "SET-ADDRESS", "SET-BY", "SET-NULL",
    "SET-POINTER", "SET-TO", "SET-TRUE", "SORT", "START", "STOP", "STRING", "SUBTRACT", "UNSTRING", "WRITE",
    "XML",
})  # fmt: skip
DATA_TYPES = frozenset({
    "BINARY", "COMP-1", "COMP-2", "COMP-3", "COMP-5", "EDITED", "NATIONAL", "P-SCALED", "PACKED",
})  # fmt: skip
SQL_FORMS = frozenset({
    "ALLOCATE", "ALTER", "ASSOCIATE", "BEGIN", "CALL", "CLOSE", "COMMENT", "COMMIT", "CONNECT", "CREATE",
    "DECLARE", "DECLARE CURSOR", "DELETE", "DESCRIBE", "DROP", "DYNAMIC", "END", "EXECUTE", "EXPLAIN", "FETCH",
    "FREE", "GET", "GRANT", "HOLD", "INCLUDE", "INSERT", "LABEL", "LOCK", "MERGE", "OPEN", "PREPARE", "REFRESH",
    "RELEASE", "RENAME", "REVOKE", "ROLLBACK", "SAVEPOINT", "SELECT", "SET", "SIGNAL", "STATIC", "TRUNCATE",
    "UPDATE", "VALUES", "WHENEVER",
})  # fmt: skip
# IBM Enterprise COBOL for z/OS 6.4 intrinsic functions
INTRINSIC_FUNCTIONS = frozenset({
    "ABS", "ACOS", "ANNUITY", "ASIN", "ATAN", "BIT-OF", "BIT-TO-CHAR", "BYTE-LENGTH", "CHAR",
    "COMBINED-DATETIME", "COS", "CURRENT-DATE", "DATE-OF-INTEGER", "DATE-TO-YYYYMMDD", "DAY-OF-INTEGER",
    "DAY-TO-YYYYDDD", "DISPLAY-OF", "E", "EXP", "EXP10", "FACTORIAL", "FORMATTED-CURRENT-DATE",
    "FORMATTED-DATE", "FORMATTED-DATETIME", "FORMATTED-TIME", "HEX-OF", "HEX-TO-CHAR", "INTEGER",
    "INTEGER-OF-DATE", "INTEGER-OF-DAY", "INTEGER-OF-FORMATTED-DATE", "INTEGER-PART", "LENGTH", "LOG", "LOG10",
    "LOWER-CASE", "MAX", "MEAN", "MEDIAN", "MIDRANGE", "MIN", "MOD", "NATIONAL-OF", "NUMVAL", "NUMVAL-C",
    "NUMVAL-F", "ORD", "ORD-MAX", "ORD-MIN", "PI", "PRESENT-VALUE", "RANDOM", "RANGE", "REM", "REVERSE",
    "SECONDS-FROM-FORMATTED-TIME", "SECONDS-PAST-MIDNIGHT", "SIGN", "SIN", "SQRT", "STANDARD-DEVIATION", "SUM",
    "TAN", "TEST-DATE-YYYYMMDD", "TEST-DAY-YYYYDDD", "TEST-FORMATTED-DATETIME", "TEST-NUMVAL", "TEST-NUMVAL-C",
    "TEST-NUMVAL-F", "TRIM", "ULENGTH", "UPOS", "UPPER-CASE", "USUBSTR", "USUPPLEMENTARY", "UUID4", "UVALID",
    "UWIDTH", "VARIANCE", "WHEN-COMPILED", "YEAR-TO-YYYY",
})  # fmt: skip
TELL_NAMES = frozenset(t[0] for t in TELLS)
ROW_KEYS = frozenset(
    {
        "name",
        "kind",
        "status",
        "reason",
        "copybook",
        "era",
        "earliest",
        "mixed",
        "program_era",
        "copybook_skipped",
        "tells",
        "translation",
        "refusal",
        "statements",
        "translated_statements",
        "holes",
    }
)
TRANSLATIONS = ("whole", "holes", "refused")  # dryrun.TRANSLATIONS
TRANSLATION_INTS = ("statements", "translated_statements", "holes")
_OPTION_VALUE = re.compile(r"^-?[A-Z0-9]{1,10}$")
_MEMBER = re.compile(r"^[A-Za-z0-9@#$_-]{1,30}$")
_EXC_CLASS = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,60}$")
_LABEL = re.compile(r"^[PC]-[0-9a-f]{12}$")
_cics_words: frozenset[str] | None = None


def cics_words() -> frozenset[str]:
    """Every word of the CICS command spec: its command keys' words and every option it honours or refuses."""
    global _cics_words
    if _cics_words is None:
        from gitgalaxy.standards.cics import COMMANDS

        words: set[str] = set()
        for key, cmd in COMMANDS.items():
            words.update(key.split())
            words.update(cmd.options)
            words.update(cmd.refused)
        _cics_words = frozenset(words)
    return _cics_words


def _cics_command(key: str) -> bool:
    words = key.split(" ")
    return 1 <= len(words) <= 3 and all(w in cics_words() for w in words)


def known(category: str, key: str) -> bool:
    """Whether `key` is a feature name `category` may print (UNKNOWN is the inventory's own word)."""
    if key == UNKNOWN:
        return True
    if category == "statements":
        return key in STATEMENTS
    if category == "data_types":
        return key in DATA_TYPES
    if category == "sql_forms":
        return key in SQL_FORMS
    if category == "intrinsic_functions":
        return key in INTRINSIC_FUNCTIONS
    if category == "refusal_families":
        return key in FAMILIES
    if category == "cics_commands":
        return _cics_command(key)
    if category == "cics_options":
        verb, sep, opt = key.partition(": ")
        return bool(sep) and _cics_command(verb) and opt in cics_words()
    if category == "compile_options":
        opt, sep, value = key.partition(": ")
        return bool(sep) and opt in SEMANTIC_OPTIONS and bool(_OPTION_VALUE.match(value))
    return False


class Namer:
    """Program and copybook names as written, or (`key` given) their keyed-hash labels: `P-` / `C-` and 12 hex digits
    of HMAC-SHA256 over the name. The same key gives the same labels, so two runs compare; without it no one can map
    a label back."""

    def __init__(self, key: bytes | None = None) -> None:
        self.key = key

    def _label(self, prefix: str, name: str, key: bytes) -> str:
        return prefix + hmac.new(key, name.encode("utf-8"), hashlib.sha256).hexdigest()[:12]

    def program(self, name: str) -> str:
        return name if self.key is None else self._label("P-", name, self.key)

    def member(self, name: str) -> str:
        return name if self.key is None else self._label("C-", name, self.key)


def _reason(text: str) -> tuple[str, str | None]:
    """(reason, missing copybook member or None) of an inventory `unparsed_programs` reason -- never its message."""
    if text.startswith("CopyNotFound:"):
        m = re.match(r"CopyNotFound: COPY (\S+)$", text)
        return MISSING_COPYBOOK, (m.group(1) if m and _MEMBER.match(m.group(1)) else None)
    cls = text.split(" - ", 1)[0]
    return (cls if _EXC_CLASS.match(cls) else "unreadable"), None


def _tag(tag: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {k: tag.get(k) for k in ("era", "earliest", "mixed")}
    if "program_era" in tag:
        out["program_era"] = tag["program_era"]
    if tag.get("copybook_skipped") and _EXC_CLASS.match(
        str(tag["copybook_skipped"])
    ):  # #5195: a reason code, no message
        out["copybook_skipped"] = tag["copybook_skipped"]
    out["tells"] = [
        {
            "tell": t["tell"],
            "era": t["era"],
            "count": t["count"],
            **({"via_copybook": True} if t.get("via_copybook") else {}),
        }
        for t in tag.get("tells", [])
        if t.get("tell") in TELL_NAMES
    ]
    return out


def _translation(t: dict[str, Any]) -> dict[str, Any]:
    """The dry run's outcome of one program, reduced to its closed fields: a status, three counts, a refusal's class."""
    out: dict[str, Any] = {"translation": t.get("translation")}
    for k in TRANSLATION_INTS:
        if isinstance(t.get(k), int):
            out[k] = t[k]
    if t.get("translation") == "refused" and _EXC_CLASS.match(str(t.get("refusal"))):
        out["refusal"] = t["refusal"]
    return out


def project(
    inv: dict[str, Any],
    redact_key: bytes | None = None,
    tool_version: str = "unknown",
    translation: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The assess report of one raw inventory: the only function that builds one. `translation` (dryrun.dry_run):
    each program's translate-only outcome; only a parsed program's is kept, and none is written when it is None."""
    names = Namer(redact_key)
    features: dict[str, dict[str, Any]] = {}
    other: dict[str, dict[str, int]] = {}
    for cat in CATEGORIES:
        kept: dict[str, Any] = {}
        off: dict[str, Any] = {"keys": 0, "count": 0, "programs": set()}
        for key, v in sorted(inv.get(cat, {}).items()):
            if not v.get("count") and not v.get("programs"):
                continue
            if known(cat, key):
                kept[key] = {"count": v["count"], "programs": sorted(names.program(p) for p in v["programs"])}
            else:
                off["keys"] += 1
                off["count"] += v["count"]
                off["programs"].update(v["programs"])
        if kept:
            features[cat] = kept
        if off["keys"]:
            other[cat] = {"keys": off["keys"], "count": off["count"], "programs": len(off["programs"])}

    gaps: dict[str | None, set[str]] = defaultdict(set)
    for key, v in inv.get("copybook_resolution_gaps", {}).items():
        if key == UNKNOWN:
            continue
        m = re.match(r"COPY (\S+)$", key)
        gaps[m.group(1) if m and _MEMBER.match(m.group(1)) else None].update(v["programs"])

    families: dict[str, str] = {}
    for fam, v in inv.get("refusal_families", {}).items():
        for p in v["programs"]:
            if fam in FAMILIES:
                families[p] = fam
    unparsed = {u["program"]: u["reason"] for u in inv.get("unparsed_programs", [])}
    tags = inv.get("eras", {}).get("programs", {})
    asm_tags = inv.get("eras", {}).get("assembler", {})  # #5195: the era tags of assembler members

    programs = []
    for p in sorted(set(tags) | set(families)):
        row: dict[str, Any] = {"name": names.program(p), "kind": "cobol" if p in tags else "assembler"}
        if p in families:
            row["status"], row["reason"] = REFUSED, families[p]
        elif p in unparsed:
            reason, member = _reason(unparsed[p])
            row["status"], row["reason"] = UNPARSED, reason
            if member is not None:
                row["copybook"] = names.member(member)
        else:
            row["status"] = PARSED
            if translation is not None and p in translation:
                row.update(_translation(translation[p]))
        if p in tags:
            row.update(_tag(tags[p]))
        elif p in asm_tags:
            row.update(_tag(asm_tags[p]))
        programs.append(row)
    programs.sort(key=lambda r: r["name"])

    cobol = [r for r in programs if r["kind"] == "cobol"]
    totals = {
        "programs": len(cobol),
        "parsed": sum(r["status"] == PARSED for r in cobol),
        "unparsed": sum(r["status"] == UNPARSED for r in cobol),
        "refused_by_family": sum(r["status"] == REFUSED for r in programs),
        "assembler_members": len(programs) - len(cobol),
    }
    if translation is not None:
        kinds = [r["translation"] for r in cobol if "translation" in r]
        totals["translation"] = {t: kinds.count(t) for t in TRANSLATIONS}
    summary = inv.get("eras", {}).get("summary", {})
    eras = {
        k: summary[k] for k in ("programs", "by_era", "mixed", "raised_by_copybook", "copybook_skipped") if k in summary
    }
    eras["tells"] = {t: n for t, n in summary.get("tells", {}).items() if t in TELL_NAMES}
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "tool_version": tool_version,
        "redacted": redact_key is not None,
        "totals": totals,
        "eras": eras,
        "features": features,
        "other": other,
        "copybook_gaps": sorted(
            (
                {"name": names.member(m) if m is not None else None, "programs": sorted(names.program(p) for p in ps)}
                for m, ps in gaps.items()
            ),
            key=lambda g: (g["name"] is None, g["name"] or ""),
        ),
        "programs": programs,
    }
    return report


def _ints(node: Any, where: str, problems: list[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if not re.match(r"^[a-z0-9_]{1,24}$", str(k)):
                problems.append(f"{where}: key {k!r}")
            _ints(v, f"{where}.{k}", problems)
    elif not (isinstance(node, int) or node is None):
        problems.append(f"{where}: {type(node).__name__} where a count belongs")


def validate(report: dict[str, Any]) -> list[str]:
    """Every rule `project` keeps, checked again on the finished report: [] when it holds."""
    p: list[str] = []
    expected = {
        "schema",
        "tool_version",
        "redacted",
        "totals",
        "eras",
        "features",
        "other",
        "copybook_gaps",
        "programs",
    }
    if set(report) != expected:
        p.append(f"top-level keys {sorted(set(report) ^ expected)}")
        return p
    if report["schema"] != SCHEMA or not re.match(r"^[A-Za-z0-9.+_-]{1,64}$", str(report["tool_version"])):
        p.append("schema / tool_version")
    redacted = report["redacted"] is True
    names = {r.get("name") for r in report["programs"]}

    def name_ok(n: Any, prefix: str) -> bool:
        if redacted:
            return isinstance(n, str) and bool(_LABEL.match(n)) and n.startswith(prefix)
        return isinstance(n, str) and 0 < len(n) <= 512 and "\n" not in n

    _ints(report["totals"], "totals", p)
    _ints({k: v for k, v in report["eras"].items() if k != "tells"}, "eras", p)
    for t, n in report["eras"].get("tells", {}).items():
        if t not in TELL_NAMES or not isinstance(n, int):
            p.append(f"eras.tells {t!r}")
    for cat, keys in report["features"].items():
        if cat not in CATEGORIES:
            p.append(f"features category {cat!r}")
            continue
        for key, v in keys.items():
            if not known(cat, key):
                p.append(f"features.{cat}: {key!r} is not in its vocabulary")
            if set(v) != {"count", "programs"} or not isinstance(v["count"], int):
                p.append(f"features.{cat}.{key}: shape")
            p.extend(f"features.{cat}.{key}: program {n!r}" for n in v.get("programs", []) if n not in names)
    for cat, v in report["other"].items():
        if cat not in CATEGORIES:
            p.append(f"other category {cat!r}")
        _ints(v, f"other.{cat}", p)
    for g in report["copybook_gaps"]:
        if set(g) != {"name", "programs"} or not (g["name"] is None or name_ok(g["name"], "C-")):
            p.append(f"copybook_gaps entry {g.get('name')!r}")
        p.extend(f"copybook_gaps: program {n!r}" for n in g.get("programs", []) if n not in names)
    for r in report["programs"]:
        if not name_ok(r.get("name"), "P-") or r.get("kind") not in KINDS or r.get("status") not in STATUSES:
            p.append(f"program row {r.get('name')!r}")
        reason = r.get("reason")
        if r.get("status") == REFUSED and reason not in FAMILIES:
            p.append(f"program {r.get('name')!r}: reason {reason!r}")
        if r.get("status") == UNPARSED and not (
            reason in (MISSING_COPYBOOK, "unreadable") or (isinstance(reason, str) and _EXC_CLASS.match(reason))
        ):
            p.append(f"program {r.get('name')!r}: reason {reason!r}")
        if r.get("status") == PARSED and reason is not None:
            p.append(f"program {r.get('name')!r}: a parsed program has no reason")
        if "translation" in r:
            if r["translation"] not in TRANSLATIONS or r.get("status") != PARSED:
                p.append(f"program {r.get('name')!r}: translation {r['translation']!r}")
            if "refusal" in r and not (r["translation"] == "refused" and _EXC_CLASS.match(str(r["refusal"]))):
                p.append(f"program {r.get('name')!r}: refusal")
            p.extend(
                f"program {r.get('name')!r}: {k}"
                for k in TRANSLATION_INTS
                if k in r and not (isinstance(r[k], int) and not isinstance(r[k], bool) and r[k] >= 0)
            )
        elif {"refusal", *TRANSLATION_INTS} & set(r):
            p.append(f"program {r.get('name')!r}: translation fields without a status")
        if "copybook" in r and not name_ok(r["copybook"], "C-"):
            p.append(f"program {r.get('name')!r}: copybook {r['copybook']!r}")
        extra = set(r) - ROW_KEYS
        if extra:
            p.append(f"program {r.get('name')!r}: keys {sorted(extra)}")
        _ints({k: r[k] for k in ("era", "earliest", "program_era") if k in r}, f"program {r.get('name')!r}", p)
        if "copybook_skipped" in r and not _EXC_CLASS.match(str(r["copybook_skipped"])):
            p.append(f"program {r.get('name')!r}: copybook_skipped")
        p.extend(
            f"program {r.get('name')!r}: tell {t.get('tell')!r}"
            for t in r.get("tells", [])
            if t.get("tell") not in TELL_NAMES or set(t) - {"tell", "era", "count", "via_copybook"}
        )
    return p
