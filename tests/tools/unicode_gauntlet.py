#!/usr/bin/env python3
"""
The Unicode Gauntlet (#3812, epic #3811): every read GitGalaxy makes is assumed wrong until a
metamorphic test proves it right.

A SEED is an estate whose facts we trust. A TRANSFORM rewrites it -- its unit names get a suffix in
another script (only where the language allows that script in an identifier), the files are
re-encoded (UTF-8 with a BOM, UTF-16, cp1252, Shift-JIS, GB18030), line endings become CRLF. The
engine scans the seed and every variant, and each variant's facts must equal the seed's facts with
the same transform applied:

    facts(T(seed)) == T(facts(seed))

Facts are read from the master DB: every file with its integer signals (LOC, counts; not the
naming-style counters, which a new name changes by design), its units with their lines, its call
edges, and the mainframe channels (call sites, datasets, CSD and CICS resources, record items,
job flow), each keyed by path, names mapped. A CELL is one (seed language, script, encoding)
variant; it passes when nothing differs.

A Shift-JIS or GB18030 estate is scanned with its code page declared (`--source-encoding`), as a
real one is (#3878). Neither can be told from cp1252 by its bytes -- GB18030 decodes almost any
byte string -- so the engine never guesses one; a cell that scanned them undeclared would test a
case the engine rules out by design, and hide whether the declared path works. cp1252 cells stay
undeclared: that fallback is what they test.

The mainframe seed is also written as raw EBCDIC (#3816): each file a fixed-block download in one of
the Western European pages or the mixed CJK host pages (cp930 / cp939 / cp935 / cp937 / cp933), every
line padded to an 80-byte card image and no line ends at all, as a binary transfer of a PDS member
arrives. Those estates declare their page too, and the engine must
read the same facts out of them as out of the UTF-8 seed. Nordic names go into cp277 / cp278 and
German names into cp273, the pages whose `@ # $` positions carry those letters.

Seeds:
  rosetta     keyword-rosetta's corpus (every language's planted probes; ../keyword-rosetta)
  mainframe   tests/unicode_gauntlet/mainframe/ -- PL/I, COBOL, JCL, CSD, HLASM, CICS with every
              channel named from a placeholder (the #3810 probe)

    python tests/tools/unicode_gauntlet.py --report [--out DIR]   # the matrix, report.md + chart.svg
    python tests/tools/unicode_gauntlet.py --ci                   # fail on a cell not in the baseline
    python tests/tools/unicode_gauntlet.py --update-baseline      # record today's failing cells

The baseline (tests/unicode_gauntlet/baseline.txt) is a ratchet: known failing cells are listed
with their first difference, a new failing cell fails CI, and a fix removes cells from it. It is one
line per cell with no counts, and git merges it as a UNION (.gitattributes): two PRs that each fix
cells merge without a conflict, and a line left for a cell that now passes is harmless (--ci reports
it as "lower the baseline", never as a failure). The rosetta commit the cells were measured at is
tests/unicode_gauntlet/rosetta_ref.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

from gitgalaxy.core.ebcdic_codecs import register as register_ebcdic_codecs

register_ebcdic_codecs()  # #3816: cp277 / cp278 / cp297 / cp1047 are not in Python's codec table

REPO_ROOT = Path(__file__).resolve().parents[2]
HERE = REPO_ROOT / "tests" / "unicode_gauntlet"
BASELINE = HERE / "baseline.txt"
ROSETTA_REF = HERE / "rosetta_ref"
_BASELINE_HEADER = (
    "# #3812: the Unicode Gauntlet's known failing cells -- a ratchet. CI fails on a failing cell not listed\n"
    "# here; a fix removes cells (--update-baseline). One `cell<TAB>first difference` per line, sorted; git\n"
    "# merges this file as a union, so a stale line is possible and harmless. Cells were measured at the\n"
    "# keyword-rosetta commit in rosetta_ref.\n"
)


def read_baseline() -> dict[str, str]:
    """{cell: its first difference} of the committed baseline (empty without one)."""
    if not BASELINE.is_file():
        return {}
    rows = (line.split("\t", 1) for line in BASELINE.read_text(encoding="utf-8").splitlines())
    return {r[0]: (r[1] if len(r) > 1 else "") for r in rows if r[0] and not r[0].startswith("#")}


def write_baseline(failing: dict[str, str]) -> None:
    def one_line(diff: str) -> str:  # a difference may quote multi-line source: keep it on its line
        return " ".join(diff.split())[:240]

    body = "".join(f"{cid}\t{one_line(d)}\n" for cid, d in sorted(failing.items()))
    BASELINE.write_text(_BASELINE_HEADER + body, encoding="utf-8")


LEGALITY = json.loads((HERE / "legality.json").read_text(encoding="utf-8"))

# A word per script, appended to a unit name. Each exercises a failure class: ß upper-cases to SS
# (a length change), İ/ı fold oddly, Devanagari and Tamil carry combining marks (Mn / Mc) that
# `\w` does not match, a ZWJ sits inside a word, NFD splits é into two code points, RTL scripts
# reorder on display, CJK and Hangul are outside every Latin code page.
SCRIPTS: dict[str, str] = {
    "german": "ÄÖÜß",
    "nordic": "ÆØÅ",
    "french": "éèç",
    "turkish": "İı",
    "greek": "αβγ",
    "cyrillic": "жзи",
    "devanagari": "नाम",
    "devanagari_zwj": "क्‍ष",
    "tamil": "பெயர்",
    "arabic": "اسم",
    "hebrew": "שם",
    "han": "名前",
    "kana": "なまえ",
    "hangul": "이름",
    "nfd": unicodedata.normalize("NFD", "é"),
}
# National characters: on Nordic / German EBCDIC code pages @ # $ are the bytes that show as
# these letters, so mainframe identifiers carry them -- upper case only, one byte each.
NATIONAL = {"nordic": "ÆØÅ", "german": "ÄÖÜ"}

ENCODINGS = ["utf-8", "utf-8-sig", "utf-16", "utf-16-be", "cp1252", "shift_jis", "gb18030", "crlf"]
# Code pages an estate must declare (see the module docstring): the scan of a `<script>__<codec>`
# estate passes `--source-encoding <codec>` for these.
# #3816: raw EBCDIC, for the mainframe seed only (a Python file in EBCDIC is not a real estate).
# The mixed CJK pages (part 3a) hold the seed in their single-byte half, read through the byte-level
# record split that a Kanji comment or N-literal also goes through.
EBCDIC = ["cp037", "cp273", "cp277", "cp278", "cp297", "cp1047", "cp930", "cp939", "cp935", "cp937", "cp933"]
# the pages each national script is tested in: the ones whose national positions hold its letters
EBCDIC_SCRIPTS = {"nordic": ["cp277", "cp278"], "german": ["cp273"]}
FB_LRECL = 80  # a card image: the record length of a source PDS
DECLARED = {"shift_jis", "gb18030", *EBCDIC}
# #3815: the mainframe seed's national names with the FILE NAMES written decomposed (NFD), as a macOS
# export or zip writes them; the content stays UTF-8 NFC. The engine stores paths in NFC, so the facts
# must equal the NFC estate's -- and `%INCLUDE INCAÄÖÜ` must still find the NFD-named INCAÄÖÜ.inc.
NFD_PATHS = "nfd-paths"

# Counters a new name changes by design (a suffix changes the case style and the length) and the
# token mass (a different script tokenises differently). Everything else must not move.
NAME_STYLE = {"struct_camel_case", "struct_snake_case", "struct_pascal_case", "struct_upper_case",
              "struct_short_vars", "struct_long_vars", "token_mass"}  # fmt: skip
# Unit names that are the language's own (renaming them changes meaning, not just a name).
KEEP = {"main", "init", "__init__", "new", "constructor", "entry", "run", "setup", "teardown"}
CHANNELS = ["function_data", "fcall_data", "call_site_data", "dataset_data", "csd_resource_data",
            "cics_resource_data", "record_data", "job_flow_data"]  # fmt: skip


# ---- the transforms ---------------------------------------------------------------------
def fixed_block(text: str, codec: str, lrecl: int = FB_LRECL) -> bytes | None:
    """#3816: `text` as a raw fixed-block EBCDIC download -- every line padded to `lrecl` bytes (0x40,
    the EBCDIC space), back to back, no line ends. Bytes, not characters: on a mixed CJK page a
    double-byte character is two bytes and its shifts one each. None when a line is longer than a
    record or a character is not in the page."""
    lines = text.replace("\r\n", "\n").split("\n")
    if lines[-1] == "":
        lines.pop()
    try:
        records = [line.encode(codec) for line in lines]
    except UnicodeEncodeError:
        return None
    if any(len(record) > lrecl for record in records):
        return None
    return b"".join(record.ljust(lrecl, b"\x40") for record in records)


def encode(text: str, encoding: str) -> bytes | None:
    """The file's bytes in `encoding`, or None when the text cannot be written in it."""
    if encoding in EBCDIC:
        return fixed_block(text, encoding)
    if encoding == NFD_PATHS:
        return text.encode("utf-8")
    if encoding == "crlf":
        return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    if encoding == "utf-16-be":
        return b"\xfe\xff" + text.encode("utf-16-be")
    try:
        return text.encode(encoding)
    except UnicodeEncodeError:
        return None


def _joiner(name: str) -> str:
    return "_" if "_" in name else "-" if "-" in name else ""


def variant_name(name: str, suffix: str, max_len: int | None) -> str:
    joined = f"{name}{_joiner(name)}{suffix}"
    if max_len and len(joined) > max_len:
        joined = name[: max_len - len(suffix)] + suffix
    return joined


def renamer(mapping: dict[str, str], id_chars: str):
    """Whole-word replacement of every mapped name (longest first), `id_chars` being the
    characters that continue a name in this language."""
    if not mapping:
        return lambda text: text
    alt = "|".join(re.escape(n) for n in sorted(mapping, key=len, reverse=True))
    word = re.compile(rf"(?<![{id_chars}])({alt})(?![{id_chars}])")
    return lambda text: word.sub(lambda m: mapping[m.group(1)], text)


def legality(language: str) -> dict[str, Any]:
    """{scripts: which scripts an identifier may carry, max_len, id_chars} for a language."""
    for rule in LEGALITY["rules"]:
        if language in rule["languages"]:
            return {"scripts": rule["scripts"], "max_len": rule.get("max_len", {}).get(language),
                    "id_chars": rule.get("id_chars", "A-Za-z0-9_")}  # fmt: skip
    return {"scripts": [], "max_len": None, "id_chars": "A-Za-z0-9_"}


# ---- scanning and facts -----------------------------------------------------------------
def scan(estate: Path, out: Path) -> Path:
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db

    # set for the scan only: a process-wide GITGALAXY_DISABLE_GIT_HISTORY outlives it and silently
    # turns git off for every later test in a pytest session (it once broke test_chronometer)
    keys = ("GITGALAXY_LICENSE_KEY", "GITGALAXY_DISABLE_GIT_HISTORY")
    saved = {k: os.environ.get(k) for k in keys}
    os.environ.setdefault("GITGALAXY_LICENSE_KEY", "COMMUNITY_FREE_TIER")
    os.environ["GITGALAXY_DISABLE_GIT_HISTORY"] = "1"
    codec = estate.name.rpartition("__")[2]
    try:
        return scan_to_db(estate, out, extra_args=("--source-encoding", codec) if codec in DECLARED else ())
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _columns(cur: sqlite3.Cursor, table: str) -> list[tuple[str, str]]:
    return [(r[1], (r[2] or "").upper()) for r in cur.execute(f"PRAGMA table_info({table})")]  # noqa: S608


def facts(db: Path) -> dict[str, dict[str, Any]]:
    """{file path: {"ints": {...}, channel: sorted rows}} from a master DB. File ids become paths;
    other ids and the repo / commit stamps are dropped."""
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    paths = {fid: p for fid, p in cur.execute("SELECT id, file_path FROM file_data")}
    out: dict[str, dict[str, Any]] = {}
    ints = [c for c, t in _columns(cur, "file_data") if t == "INTEGER" and c != "id" and c not in NAME_STYLE]
    for row in cur.execute(f"SELECT file_path, language, {', '.join(ints)} FROM file_data"):  # noqa: S608
        out[row[0]] = {
            "language": row[1],
            "ints": dict(zip(ints, row[2:], strict=False)),
            **{c: [] for c in CHANNELS},
        }  # reason: length may differ
    tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table in CHANNELS:
        if table not in tables:
            continue
        cols = _columns(cur, table)
        owner = next((c for c, _ in cols if c in ("file_id", "src_file_id")), None)
        if owner is None:
            continue
        keep = [c for c, t in cols if not (c == "id" or c.endswith("_id") or c in ("repo_name", "commit_hash")
                                             or c in NAME_STYLE or t == "REAL")]  # fmt: skip
        extra = "dst_file_id" if any(c == "dst_file_id" for c, _ in cols) else None
        sel = [owner, *keep] + ([extra] if extra else [])
        for r in cur.execute(f"SELECT {', '.join(sel)} FROM {table}"):  # noqa: S608
            path = paths.get(r[0])
            if path not in out:
                continue
            vals = list(r[1 : 1 + len(keep)])
            if extra:
                vals.append(paths.get(r[-1]))
            out[path][table].append(vals)
    conn.close()
    return out


def _norm(v: Any) -> Any:
    """Case-folded text; a JSON-valued column (calls_out_to) compared as data, not as escapes."""
    if isinstance(v, str) and v[:1] in "[{":
        try:
            return json.dumps(json.loads(v), ensure_ascii=False, sort_keys=True).casefold()
        except ValueError:
            pass
    return v.casefold() if isinstance(v, str) else v


def expected(control: dict[str, Any], rename, prefix_from: str, prefix_to: str) -> dict[str, Any]:
    """The control's facts with the transform applied: paths moved to the variant's folder,
    every text value renamed."""

    def path(p: str | None) -> str | None:
        if p is None or not p.startswith(prefix_from):
            return p
        # #3815: the engine stores paths in NFC (a renamed path carrying the `nfd` word included)
        return _nfc(rename(prefix_to + p[len(prefix_from) :]))

    out = {}
    for p, f in control.items():
        if not p.startswith(prefix_from):
            continue
        g = {"language": f["language"], "ints": dict(f["ints"])}
        for c in CHANNELS:
            g[c] = sorted((tuple(_norm(rename(v)) if isinstance(v, str) and not (v or "").startswith(prefix_from)
                                 else _norm(path(v)) if isinstance(v, str) else v for v in row)
                           for row in f[c]), key=repr)  # fmt: skip
        out[path(p)] = g
    return out


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def actual(variant: dict[str, Any], prefix: str) -> dict[str, Any]:
    out = {}
    for p, f in variant.items():
        if not p.startswith(prefix):
            continue
        g = {"language": f["language"], "ints": dict(f["ints"])}
        for c in CHANNELS:
            g[c] = sorted((tuple(_norm(v) for v in row) for row in f[c]), key=repr)
        out[p] = g
    return out


def diff_cell(want: dict[str, Any], got: dict[str, Any]) -> list[str]:
    """What differs between the expected and the scanned facts of one variant (first few, readable)."""
    out: list[str] = []
    for p in sorted(set(want) | set(got)):
        w, g = want.get(p), got.get(p)
        if w is None or g is None:
            out.append(f"{p}: {'missing' if g is None else 'unexpected'} file")
            continue
        if w["language"] != g["language"]:
            out.append(f"{p}: language {w['language']} -> {g['language']}")
        for k in sorted(set(w["ints"]) | set(g["ints"])):
            if w["ints"].get(k) != g["ints"].get(k):
                out.append(f"{p}: {k} {w['ints'].get(k)} -> {g['ints'].get(k)}")
        for c in CHANNELS:
            if w[c] != g[c]:
                missing = [r for r in w[c] if r not in g[c]][:2]
                extra = [r for r in g[c] if r not in w[c]][:2]
                out.append(f"{p}: {c} missing {missing} extra {extra}")
    return out


# ---- the seeds --------------------------------------------------------------------------
def rosetta_seeds(corpus: Path) -> dict[str, Path]:
    """{language: its folder} of keyword-rosetta's corpus, plus the mainframe channel seed."""
    data = corpus / "data"
    seeds = (
        {p.name: p for p in sorted(data.iterdir()) if (p / "expected_signals.json").is_file()} if data.is_dir() else {}
    )
    seeds["mainframe"] = HERE / "mainframe"  # needs no corpus: it lives here
    return seeds


def ascii_twin(word: str) -> str:
    """An ASCII word of the same shape: X for an upper-case letter, x otherwise. A script cell is
    compared with its twin, not with the untouched seed, so a heuristic that reads names (rosetta
    plants `probe_safety`; `test_` marks a test; Make's `clean`) sees the same kind of name on
    both sides and only the script differs."""
    return "".join("X" if c.isupper() else "x" for c in word if not unicodedata.combining(c)) or "x"


def _write(folder: Path, dest: Path, rename, enc: str) -> bool:
    """The folder's files, renamed (content and path: `%INCLUDE INCA` resolves to INCA.inc) and
    re-encoded under `dest`; False when a file cannot be written in `enc`."""
    for src in folder.rglob("*"):
        if not src.is_file() or src.name in ("expected_signals.json", "names.json"):
            continue
        raw = src.read_bytes()
        try:
            text = raw.decode("utf-8")
            # #3814: Perl takes Unicode names only under `use utf8`; the seed gets it too, so both sides match
            if src.suffix in (".pl", ".pm", ".t") and "use utf8;" not in text:
                text = "use utf8;\n" + text
            data = encode(rename(text), enc)
        except UnicodeDecodeError:  # not text we can transform (an image, a legacy file): as it is
            data = raw
        if data is None:
            return False
        out = dest / rename(src.relative_to(folder).as_posix())
        if enc == NFD_PATHS:
            out = dest / unicodedata.normalize("NFD", rename(src.relative_to(folder).as_posix()))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    return True


def _mapping(units: list[str], word: str, max_len: Any) -> dict[str, str] | None:
    """{name: its renamed form}; `max_len` is the language's name limit, or {name: limit}."""
    limit = (lambda u: max_len.get(u)) if isinstance(max_len, dict) else (lambda u: max_len)
    mapping = {u: variant_name(u, word, limit(u)) for u in units}
    if len(set(mapping.values())) != len(mapping) and isinstance(max_len, int):
        # a name limit (JCL's 8) truncated two names to one: keep them apart with a number
        room = max_len - len(word) - 2
        mapping = {u: f"{u[:room]}{k:02d}{word}" for k, u in enumerate(units)}
    return mapping if len(set(mapping.values())) == len(mapping) else None


def build(seeds: dict[str, Path], seed_facts: dict[str, Any], root: Path, full: bool) -> list[dict[str, Any]]:
    """Write every estate under `root`: per script a `twin__<script>` reference (the seed renamed
    with the script's ASCII twin) and per (script, encoding) a cell; `ascii` cells are the seed
    itself re-encoded. Each estate holds every seed language, the seed's shape exactly."""
    cells: list[dict[str, Any]] = []
    for lang, folder in seeds.items():
        rule = legality(lang)
        names_file = folder / "names.json"
        if names_file.is_file():  # a seed that says what to rename, and each name's limit
            rule["max_len"] = json.loads(names_file.read_text(encoding="utf-8"))["names"]
            units = sorted(rule["max_len"])
        else:
            units = sorted({row[0] for p, f in seed_facts.items() if p.startswith(f"{lang}/")
                            for row in f["function_data"] if isinstance(row[0], str)})  # fmt: skip
            units = [u for u in units if len(u) >= 3 and u.lower() not in KEEP]
        scripts = [sc for sc in rule["scripts"] if sc in SCRIPTS or sc in NATIONAL]
        plan = [("ascii", e) for e in ENCODINGS if e not in ("cp1252", "shift_jis", "gb18030")]
        for i, sc in enumerate(scripts):
            encs = ENCODINGS if full else ["utf-8", ENCODINGS[1 + i % (len(ENCODINGS) - 1)]]
            plan += [(sc, e) for e in encs]
        if lang == "mainframe":  # #3816: every EBCDIC cell, in the sampled plan too, so CI runs them
            plan += [("ascii", e) for e in EBCDIC]
            plan += [(sc, e) for sc in scripts for e in EBCDIC_SCRIPTS.get(sc, [])]
            plan += [(sc, NFD_PATHS) for sc in scripts]  # #3815: file names decomposed
        twins_done: set[str] = set()
        for script, enc in plan:
            if script == "ascii":
                if _write(folder, root / f"ascii__{enc}" / lang, lambda t: t, enc):
                    cells.append({"id": f"{lang}|ascii|{enc}", "language": lang, "script": "ascii", "encoding": enc,
                                  "estate": f"ascii__{enc}", "reference": "seed", "mapping": {}, "id_chars": rule["id_chars"]})  # fmt: skip
                continue
            word = NATIONAL[script] if rule["scripts"] == ["nordic", "german"] else SCRIPTS[script]
            twin_map = _mapping(units, ascii_twin(word), rule["max_len"])
            var_map = _mapping(units, word, rule["max_len"])
            if twin_map is None or var_map is None:
                continue
            if script not in twins_done:
                _write(folder, root / f"twin__{script}" / lang, renamer(twin_map, rule["id_chars"]), "utf-8")
                twins_done.add(script)
            if not _write(folder, root / f"{script}__{enc}" / lang, renamer(var_map, rule["id_chars"]), enc):
                shutil.rmtree(root / f"{script}__{enc}" / lang, ignore_errors=True)
                continue
            cells.append({"id": f"{lang}|{script}|{enc}", "language": lang, "script": script, "encoding": enc,
                          "estate": f"{script}__{enc}", "reference": f"twin__{script}",
                          "mapping": {twin_map[u]: var_map[u] for u in units}, "id_chars": rule["id_chars"]})  # fmt: skip
    _complete_ebcdic_estates(cells, root)
    return cells


def _complete_ebcdic_estates(cells: list[dict[str, Any]], root: Path) -> None:
    """An EBCDIC estate holds only the mainframe seed's variant, but the engine reads a file in its
    project's context (an ambiguous `.inc` is resolved by the languages around it, #3867): give it
    every other language exactly as its reference estate holds them, so the one thing that differs
    from the reference is the mainframe files' encoding."""
    for cell in cells:
        estate, reference = root / cell["estate"], root / cell["reference"]
        if cell["encoding"] not in EBCDIC or not reference.is_dir():
            continue
        for lang_dir in reference.iterdir():
            if lang_dir.is_dir() and not (estate / lang_dir.name).exists():
                shutil.copytree(lang_dir, estate / lang_dir.name)


def _scan_facts(args: tuple[str, str]) -> dict[str, Any]:
    """One estate scanned in its own process (the engine's scan is process-global)."""
    estate, out = args
    return facts(scan(Path(estate), Path(out)))


def run(
    corpus: Path,
    only: set[str] | None,
    full: bool,
    work: Path,
    jobs: int = 4,
    cells_out: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Every estate is scanned on its own and holds every seed language (sibling variants in one
    scan would make `import a` ambiguous between forty `a.py`). `cells_out`, when given, receives
    the planned cells (estate, reference, mapping): the tree-sitter comparison
    (unicode_gauntlet_vs_treesitter.py) reads the same estates and scans under `work`."""
    from concurrent.futures import ProcessPoolExecutor

    seeds = rosetta_seeds(corpus)
    if only:
        seeds = {k: v for k, v in seeds.items() if k in only}
    root = work / "estates"
    for lang, folder in seeds.items():
        _write(folder, root / "seed" / lang, lambda t: t, "utf-8")
    seed_facts = facts(scan(root / "seed", work / "scans" / "seed"))
    cells = build(seeds, seed_facts, root, full)
    if cells_out is not None:
        cells_out.extend(cells)
    estates = sorted({c["estate"] for c in cells} | {c["reference"] for c in cells} - {"seed"})
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        scanned = dict(
            zip(
                estates,
                pool.map(_scan_facts, [(str(root / e), str(work / "scans" / e)) for e in estates]),
                strict=False,
            )
        )  # reason: length may differ
    scanned["seed"] = seed_facts
    results = {}
    for cell in cells:
        lang = cell["language"]
        rename = renamer({k.casefold(): v for k, v in cell["mapping"].items()} | cell["mapping"], cell["id_chars"])
        want = expected(scanned[cell["reference"]], rename, f"{lang}/", f"{lang}/")
        got = actual(scanned[cell["estate"]], f"{lang}/")
        results[cell["id"]] = {**{k: cell[k] for k in ("language", "script", "encoding")}, "seed": "rosetta",
                               "diffs": diff_cell(want, got)}  # fmt: skip
    return results


# ---- report, chart, baseline ------------------------------------------------------------
def summary(results: dict[str, Any]) -> dict[str, Any]:
    by_lang: dict[str, dict[str, list[int]]] = {}
    for r in results.values():
        cell = by_lang.setdefault(r["language"], {}).setdefault(r["script"], [0, 0])
        cell[1] += 1
        cell[0] += not r["diffs"]
    return by_lang


def report_md(results: dict[str, Any]) -> str:
    s = summary(results)
    scripts = ["ascii", *SCRIPTS]
    passed = sum(not r["diffs"] for r in results.values())
    lines = ["# Unicode Gauntlet", "",
             f"{passed}/{len(results)} cells pass. A cell is one (language, script, encoding) variant of a trusted "
             "seed; it passes when its scanned facts equal the seed's with the same renaming applied.", "",
             "| language | " + " | ".join(scripts) + " |", "|---|" + "---|" * len(scripts)]  # fmt: skip
    for lang in sorted(s):
        row = [f"{s[lang][sc][0]}/{s[lang][sc][1]}" if sc in s[lang] else "" for sc in scripts]
        lines.append(f"| {lang} | " + " | ".join(row) + " |")
    lines += ["", "## Failing cells", ""]
    for cid, r in sorted(results.items()):
        if r["diffs"]:
            lines.append(
                f"- `{cid}`: {r['diffs'][0]}" + (f" (+{len(r['diffs']) - 1} more)" if len(r["diffs"]) > 1 else "")
            )
    return "\n".join(lines) + "\n"


def chart_svg(results: dict[str, Any]) -> str:
    """A heat map: language x script, the share of the cell's encodings that pass."""
    s = summary(results)
    scripts = ["ascii", *SCRIPTS]
    langs = sorted(s)
    cw, ch, left, top = 34, 16, 110, 110
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{left + cw * len(scripts) + 20}" '
             f'height="{top + ch * len(langs) + 20}" font-family="sans-serif" font-size="10">',
             '<rect width="100%" height="100%" fill="#ffffff"/>']  # fmt: skip
    for j, sc in enumerate(scripts):
        x = left + j * cw + cw / 2
        parts.append(f'<text transform="translate({x},{top - 6}) rotate(-60)">{sc}</text>')
    for i, lang in enumerate(langs):
        y = top + i * ch
        parts.append(f'<text x="{left - 6}" y="{y + 12}" text-anchor="end">{lang}</text>')
        for j, sc in enumerate(scripts):
            if sc not in s[lang]:
                continue
            ok, tot = s[lang][sc]
            share = ok / tot
            color = "#2e7d32" if share == 1 else "#f9a825" if share > 0 else "#c62828"
            parts.append(f'<rect x="{left + j * cw}" y="{y}" width="{cw - 2}" height="{ch - 2}" fill="{color}">'
                         f"<title>{lang} {sc}: {ok}/{tot}</title></rect>")  # fmt: skip
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--corpus",
        type=Path,
        default=Path(os.environ.get("KEYWORD_ROSETTA_PATH", REPO_ROOT.parent / "keyword-rosetta")),
    )
    ap.add_argument("--only", nargs="*", help="seed languages to run (default: all)")
    ap.add_argument("--full", action="store_true", help="every encoding for every script (default: two each)")
    ap.add_argument("--out", type=Path, help="write report.md, chart.svg and results.json here")
    ap.add_argument("--work", type=Path, help="keep the estates and scans here")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4, help="cells scanned in parallel")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--ci", action="store_true", help="fail when a cell fails that the baseline does not list")
    ap.add_argument("--update-baseline", action="store_true")
    args = ap.parse_args(argv)
    work = args.work or Path(tempfile.mkdtemp(prefix="unicode_gauntlet_"))
    results = run(args.corpus, set(args.only) if args.only else None, args.full, work, args.jobs)
    failing = {cid: r["diffs"][0] for cid, r in sorted(results.items()) if r["diffs"]}
    print(f"Unicode Gauntlet: {len(results) - len(failing)}/{len(results)} cells pass")
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "report.md").write_text(report_md(results), encoding="utf-8")
        (args.out / "chart.svg").write_text(chart_svg(results), encoding="utf-8")
        (args.out / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    if args.update_baseline:
        import subprocess

        ref = subprocess.run(["git", "-C", str(args.corpus), "rev-parse", "HEAD"], capture_output=True, text=True,  # noqa: S603, S607
                             check=False).stdout.strip() or None  # fmt: skip
        write_baseline(failing)
        if ref:
            ROSETTA_REF.write_text(ref + "\n", encoding="utf-8")
        print(f"baseline: {len(failing)} failing cells recorded")
        return 0
    if args.ci:
        known = read_baseline()
        new = sorted(set(failing) - set(known))
        fixed = sorted(set(known) - set(failing) & set(results))
        for cid in new:
            print(f"NEW FAILING CELL {cid}: {failing[cid]}")
        if fixed:
            print(f"{len(fixed)} baseline cells now pass -- lower the baseline (--update-baseline): {fixed[:10]}")
        return 1 if new else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
