#!/usr/bin/env python3
"""SOP-001 rigorous keyword-family decoy runner (#8863).

Implements SOP-001-v1 (`docs/agents/decoy-testing-protocol.md`) for every code
language without a parser oracle (or `--all-langs` to also cover unscored
non-oracle families on parser-backed languages).

Six-gate battery run through the real `Prism` + `StructuralExtractor` pipeline:
  G1  Positive control       bare idiomatic snippet MUST fire `equations[family] >= 1`
  G2  Primary comment        full-line comment in the language's own syntax -> 0 hits
  G3  Block comment          multi-line / secondary block comment (when supported) -> 0 hits
  G4  Inline comment         trailing comment after code on the same line -> 0 hits
  G5  Identifier boundary    pure-word trigger embedded in `my_<kw>_val` -> 0 hits
  G6a String literal         trigger inside a string literal -> recorded honestly (#2535)
  G6b String-comment edge    `"http://x"` followed by a real comment -> 0 hits

Usage:
    python tests/tools/family_decoy_runner.py                       # dry-run summary (parserless langs)
    python tests/tools/family_decoy_runner.py --all-langs           # include unscored families on parser langs
    python tests/tools/family_decoy_runner.py --lang zig ada        # specific languages only
    python tests/tools/family_decoy_runner.py --write               # merge into tests/family_validity_baseline.json
    python tests/tools/family_decoy_runner.py --audit-superficial   # list cells missing SOP-001-v1 coverage
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from gitgalaxy.core.detector import StructuralExtractor  # noqa: E402
from gitgalaxy.core.prism import Prism  # noqa: E402
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS  # noqa: E402
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402
from tests.tools import family_validity_chart as fvc  # noqa: E402

BASELINE = fvc.BASELINE
CORPUS_LABEL = "decoy-suite"
PROTOCOL_VERSION = "SOP-001-v1"

# Families that intentionally inspect comments, prose, security strings, or
# structural unit boundaries rather than code-stream keyword equations.
NON_DECOY_FAMILIES = frozenset(
    {
        "doc",
        "ownership",
        "dead_code",
        "planned_debt",
        "fragile_debt",
        "spec_exposure",
        "calls_out",
        "args",
        "func_start",
        "class_start",
        "structural_boundaries",
        "hardcoded_secrets",
        "lit_code_blocks",
        "lit_diagrams",
        "lit_headers",
        "lit_links",
    }
)


@dataclass(frozen=True)
class LangSyntax:
    """Idiomatic comment and string wrappers for a language under SOP-001."""

    comment: str  # G2: full-line primary comment with `{kw}`
    string: str | None  # G6a: string literal with `{kw}`, or None if stringless
    block_comment: str | None = None  # G3: multi-line / secondary block comment with `{kw}`
    inline_comment: str | None = None  # G4: code + trailing comment with `{kw}`
    string_comment: str | None = None  # G6b: string literal + trailing comment with `{kw}`


def _c_like(
    string: str | None = 'const s = "{kw}";\n',
    *,
    has_block: bool = True,
    inline_prefix: str = "x = 1",
    str_prefix: str = 'x = "http://example.com"',
) -> LangSyntax:
    return LangSyntax(
        comment="// {kw}\n",
        string=string,
        block_comment="/*\n{kw}\n*/\n" if has_block else None,
        inline_comment=f"{inline_prefix} // {{kw}}\n",
        string_comment=f"{str_prefix} // {{kw}}\n" if string is not None else None,
    )


def _hash_like(
    string: str | None = 's = "{kw}"\n',
    *,
    block_comment: str | None = None,
    has_inline: bool = True,
    inline_prefix: str = "x = 1",
    str_prefix: str = 'x = "http://example.com"',
) -> LangSyntax:
    return LangSyntax(
        comment="# {kw}\n",
        string=string,
        block_comment=block_comment,
        inline_comment=f"{inline_prefix} # {{kw}}\n" if has_inline else None,
        string_comment=f"{str_prefix} # {{kw}}\n" if (has_inline and string is not None) else None,
    )


def _dash_like(
    string: str | None = "SELECT '{kw}';\n",
    *,
    block_comment: str | None = "/*\n{kw}\n*/\n",
    inline_prefix: str = "SELECT 1",
    str_prefix: str = "SELECT 'http://example.com'",
) -> LangSyntax:
    return LangSyntax(
        comment="-- {kw}\n",
        string=string,
        block_comment=block_comment,
        inline_comment=f"{inline_prefix} -- {{kw}}\n",
        string_comment=f"{str_prefix} -- {{kw}}\n" if string is not None else None,
    )


# Idiomatic comment and string syntax per language. Comments use each language's
# real syntax (never a foreign syntax just to make Prism pass), so any missing
# comment rule in Prism surfaces honestly as `"leak"`.
LANG_SYNTAX: dict[str, LangSyntax] = {
    "abap": LangSyntax("* {kw}\n", "lv_s = '{kw}'.\n", inline_comment='lv_x = 1. " {kw}\n'),
    "acs": _c_like('str s = "{kw}";\n'),
    "ada": _dash_like(
        'S : constant String := "{kw}";\n', block_comment=None, inline_prefix="X := 1;", str_prefix='S := "http://x";'
    ),
    "agc_assembly": _hash_like(None, has_inline=True, inline_prefix="CA ZERO"),
    "apex": _c_like("String s = '{kw}';\n", str_prefix="String x = 'http://x';"),
    "assembly": LangSyntax(
        "; {kw}\n", '.asciz "{kw}"\n', block_comment="/*\n{kw}\n*/\n", inline_comment="nop ; {kw}\n"
    ),
    "batch": LangSyntax("REM {kw}\n", None),
    "bms": LangSyntax("* {kw}\n", None),
    "c": _c_like('const char *s = "{kw}";\n'),
    "clist": LangSyntax("/* {kw} */\n", "SET &S = '{kw}'\n", block_comment="/*\n{kw}\n*/\n"),
    "cobol": LangSyntax("      * {kw}\n", "       MOVE '{kw}' TO WS-S.\n"),
    "cpp": _c_like('const char *s = "{kw}";\n'),
    "crystal": _hash_like('s = "{kw}"\n'),
    "csd": LangSyntax("* {kw}\n", None),
    "csharp": _c_like('var s = "{kw}";\n'),
    "css": LangSyntax("/* {kw} */\n", 'a {{ content: "{kw}"; }}\n', block_comment="/*\n{kw}\n*/\n"),
    "dart": _c_like('var s = "{kw}";\n'),
    "db2_sql": _dash_like("SELECT '{kw}' FROM SYSIBM.SYSDUMMY1;\n"),
    "dockerfile": _hash_like('ENV S="{kw}"\n', has_inline=False),
    "easytrieve": LangSyntax("* {kw}\n", "WS-S = '{kw}'\n"),
    "elixir": _hash_like('s = "{kw}"\n'),
    "embedded_python": _hash_like('s = "{kw}"\n'),
    "erlang": LangSyntax(
        "% {kw}\n", 'S = "{kw}".\n', inline_comment="X = 1, % {kw}\n", string_comment='X = "http://x", % {kw}\n'
    ),
    "fortran": LangSyntax(
        "! {kw}\n", "s = '{kw}'\n", inline_comment="x = 1 ! {kw}\n", string_comment="s = 'http://x' ! {kw}\n"
    ),
    "fsharp": LangSyntax(
        comment="// {kw}\n",
        string='let s = "{kw}"\n',
        block_comment="(*\n{kw}\n*)\n",
        inline_comment="let x = 1 // {kw}\n",
        string_comment='let x = "http://example.com" // {kw}\n',
    ),
    "glsl": _c_like(None),
    "go": _c_like('s := "{kw}"\n'),
    "groovy": _c_like('def s = "{kw}"\n'),
    "haskell": _dash_like(
        's = "{kw}"\n', block_comment="{{-\n{kw}\n-}}\n", inline_prefix="x = 1", str_prefix='x = "http://x"'
    ),
    "hcl": _hash_like('s = "{kw}"\n', block_comment="/*\n{kw}\n*/\n"),
    "hlasm": LangSyntax("* {kw}\n", None),
    "hlo": _c_like(None),
    "html": LangSyntax("<!-- {kw} -->\n", None, block_comment="<!--\n{kw}\n-->\n"),
    "java": _c_like('String s = "{kw}";\n'),
    "javascript": _c_like('const s = "{kw}";\n'),
    "jcl": LangSyntax("//* {kw}\n", None),
    "julia": _hash_like('s = "{kw}"\n', block_comment="#=\n{kw}\n=#\n"),
    "kotlin": _c_like('val s = "{kw}"\n'),
    "livecode": _dash_like('put "{kw}" into s\n', inline_prefix="put 1 into x", str_prefix='put "http://x" into x'),
    "lua": _dash_like(
        'local s = "{kw}"\n',
        block_comment="--[[\n{kw}\n]]\n",
        inline_prefix="local x = 1",
        str_prefix='local x = "http://x"',
    ),
    "m4": LangSyntax("dnl {kw}\n", None),
    "makefile": _hash_like('S := "{kw}"\n', inline_prefix="X := 1", str_prefix='X := "http://x"'),
    "matlab": LangSyntax(
        "% {kw}\n",
        "s = '{kw}';\n",
        block_comment="%{{\n{kw}\n%}}\n",
        inline_comment="x = 1; % {kw}\n",
        string_comment="x = 'http://x'; % {kw}\n",
    ),
    "mlir": _c_like('"{kw}"\n', has_block=False),
    "nim": _hash_like('let s = "{kw}"\n', block_comment="#[\n{kw}\n]#\n"),
    "objective-c": _c_like('NSString *s = @"{kw}";\n'),
    "ocaml": LangSyntax(
        "(* {kw} *)\n",
        'let s = "{kw}"\n',
        block_comment="(*\n{kw}\n*)\n",
        inline_comment="let x = 1 (* {kw} *)\n",
        string_comment='let x = "http://x" (* {kw} *)\n',
    ),
    "perl": _hash_like('my $s = "{kw}";\n', inline_prefix="my $x = 1;", str_prefix='my $x = "http://x";'),
    "php": _c_like('$s = "{kw}";\n', inline_prefix="$x = 1;", str_prefix='$x = "http://x";'),
    "pli": LangSyntax(
        "/* {kw} */\n",
        "S = '{kw}';\n",
        block_comment="/*\n{kw}\n*/\n",
        inline_comment="X = 1; /* {kw} */\n",
        string_comment="X = 'http://x'; /* {kw} */\n",
    ),
    "postgresql": _dash_like("SELECT '{kw}';\n"),
    "powershell": _hash_like(
        '$s = "{kw}"\n', block_comment="<#\n{kw}\n#>\n", inline_prefix="$x = 1", str_prefix='$x = "http://x"'
    ),
    "python": _hash_like('s = "{kw}"\n'),
    "r": _hash_like('s <- "{kw}"\n', inline_prefix="x <- 1", str_prefix='x <- "http://x"'),
    "rexx": LangSyntax(
        "/* {kw} */\n",
        "s = '{kw}'\n",
        block_comment="/*\n{kw}\n*/\n",
        inline_comment="x = 1 /* {kw} */\n",
        string_comment="x = 'http://x' /* {kw} */\n",
    ),
    "ruby": _hash_like('s = "{kw}"\n', block_comment="=begin\n{kw}\n=end\n"),
    "rust": _c_like('let s = "{kw}";\n'),
    "scala": _c_like('val s = "{kw}"\n'),
    "scheme": LangSyntax(
        "; {kw}\n",
        '(define s "{kw}")\n',
        block_comment="#|\n{kw}\n|#\n",
        inline_comment="(define x 1) ; {kw}\n",
        string_comment='(define x "http://x") ; {kw}\n',
    ),
    "shell": _hash_like('s="{kw}"\n', inline_prefix="x=1", str_prefix='x="http://x"'),
    "solidity": _c_like('string s = "{kw}";\n'),
    "sqlite": _dash_like("SELECT '{kw}';\n"),
    "swift": _c_like('let s = "{kw}"\n'),
    "tcl": _hash_like('set s "{kw}"\n', inline_prefix="set x 1;", str_prefix='set x "http://x";'),
    "typescript": _c_like('const s = "{kw}";\n'),
    "yacc": _c_like('const char *s = "{kw}";\n'),
    "yaml": _hash_like('s: "{kw}"\n', inline_prefix="x: 1", str_prefix='x: "http://x"'),
    "zig": _c_like('const s = "{kw}";\n', has_block=False),
    "zscript": _c_like('string s = "{kw}";\n'),
}

# Pattern-source literal scraper (bounded, ReDoS-safe).
_BOUNDARY_ESC = re.compile(r"\\(?:[bBAZz]|[wWdD][+*?]?|[nrt])")
_SPACE_CLASS = re.compile(r"\[[ \t\\rn]{1,16}\][+*?]?")
_SOURCE_SPACE = re.compile(r"\\s[+*?]?")
_SIMPLE_ALT = re.compile(r"\(\?:([A-Za-z0-9_.\- ]{1,48})\|[^()]{1,200}\)")
_CHARCLASS = re.compile(r"\[(?:\\.|[^\]\\]){0,256}\][+*?]?")
_CANDIDATE = re.compile(r"[@#$%!'/]?[A-Za-z_][A-Za-z0-9_]{0,63}(?:(?:\\\.|::|->|=|[-/ ])[A-Za-z0-9_]{1,63}){0,4}=?")
_PURE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{1,63}$")
_META = frozenset({"b", "B", "s", "S", "w", "W", "d", "D", "n", "t", "r", "A", "Z", "P", "x", "i", "m", "s"})

# Operator / symbolic probes for rules whose regexes match punctuation rather than words.
_FAMILY_PROBES: dict[str, tuple[str, ...]] = {
    "bitwise_ops": (
        "a << 1",
        "a >> 1",
        "a | b",
        "a & b",
        "a ^ b",
        "~a",
        "a |= 1",
        "a &= 1",
        "a ^= 1",
        "a <<= 1",
        "a >>= 1",
        "a >>> 1",
        "a &&& b",
        "a ||| b",
        "a ^^^ b",
        "a <<< 1",
        "a band b",
        "a bor b",
        "a bxor b",
        "a bsl 1",
        "a bsr 1",
        "a land b",
        "a lor b",
        "a lxor b",
        "a lsl 1",
        "a lsr 1",
        "a shl 1",
        "a shr 1",
        "BITAND(a, b)",
    ),
    "short_circuit": (
        "a && b",
        "a || b",
        "a and b",
        "a or b",
        "a andalso b",
        "a orelse b",
        "a ?? b",
        "a ?. b",
        "a ? b : c",
        "a .AND. b",
        "a .OR. b",
        "AND THEN",
        "OR ELSE",
    ),
    "closures": (
        "x => x + 1",
        "(x) => x",
        "|x| x + 1",
        "\\x -> x",
        "fn x -> x end",
        "fun(X) -> X end",
        "fun x -> x",
        "lambda x: x",
        "proc { |x| x }",
        "{ x -> x }",
        "^(int x) { return x; }",
        "function(x) { return x; }",
        "sub { shift }",
    ),
    "generics": (
        "List<int>",
        "Vec<T>",
        "Option<T>",
        "Array[Int]",
        "List[T]",
        "Map<String, Int>",
        "template <typename T>",
        "generic",
    ),
    "decorators": (
        "@deprecated",
        "@Override",
        "#[inline]",
        "[Serializable]",
        "[[nodiscard]]",
        "@spec",
    ),
    "state_mutation": (
        "x = 1",
        "x := 1",
        "x += 1",
        "x -= 1",
        "x <- 1",
        "x++",
        "SET x = 1",
        "mut x",
    ),
    "pointer_math": (
        "*ptr",
        "&x",
        "ptr->field",
        "*(p + 1)",
        "ptr++",
    ),
    "comprehensions": (
        "[x for x in xs]",
        "for x <- xs, do: x",
        "[X || X <- Xs]",
        "xs.map(f)",
        "map(f, xs)",
    ),
    "ternary_ops": (
        "a ? b : c",
        "a ?? b",
    ),
    "macros": (
        "#define FOO 1",
        "defmacro foo",
        "macro_rules! foo",
        "define(`FOO', `1')",
        "MACRO",
    ),
}


def scrape_candidates(pattern_source: str, family: str) -> list[str]:
    """Extract literal token candidates from a regex pattern source plus symbolic probes."""
    seen: list[str] = []
    seen_set: set[str] = set()

    def _add(tok: str) -> None:
        t = tok.strip()
        if len(t) >= 2 and t not in _META and t not in seen_set and "\n" not in t and '"' not in t and "'" not in t:
            seen_set.add(t)
            seen.append(t)

    normalised = _SOURCE_SPACE.sub(" ", _SPACE_CLASS.sub(" ", _BOUNDARY_ESC.sub(" ", pattern_source)))
    for _ in range(2):
        normalised = _SIMPLE_ALT.sub(r"\1", normalised)
    normalised = _CHARCLASS.sub(" ", normalised)
    for m in _CANDIDATE.finditer(normalised):
        raw = m.group(0).replace("\\.", ".")
        _add(raw)
        if " " in raw:
            for part in raw.split():
                _add(part)

    for probe in _FAMILY_PROBES.get(family, ()):
        if probe not in seen_set and "\n" not in probe:
            seen_set.add(probe)
            seen.append(probe)

    return seen


def _contexts(token: str) -> tuple[str, ...]:
    """Single-line code contexts in which a token might match a language rule."""
    return (
        token,
        f" {token} ",
        f"{token}()",
        f"{token}(x)",
        f"{token}(x, y)",
        f"x = {token}(y)",
        f"{token} x",
        f"a {token} b",
        f"{token};",
        f"{token}:",
        f"  {token}",
    )


def _fire_count(prism: Prism, extractor: StructuralExtractor, lang: str, family: str, src: str) -> int:
    """Run `src` through the real Prism + StructuralExtractor pipeline and return `equations[family]`."""
    ref = prism.split_streams(src, lang)
    res = extractor.splice(
        code_stream=ref["code_stream"],
        comment_stream=ref["comment_stream"],
        raw_content=src,
    )
    return int((res.get("equations") or {}).get(family, 0))


def find_trigger(
    prism: Prism,
    extractor: StructuralExtractor,
    lang: str,
    family: str,
    rule: re.Pattern[str],
    preferred_keyword: str | None = None,
) -> str | None:
    """G1: Find a single-line trigger snippet that fires `family` through the real pipeline."""
    candidates: list[str] = []
    if preferred_keyword and "\n" not in preferred_keyword:
        candidates.append(preferred_keyword)
    candidates.extend(scrape_candidates(rule.pattern, family))

    tried_ctx: set[str] = set()
    for tok in candidates:
        for ctx in _contexts(tok):
            if ctx in tried_ctx:
                continue
            tried_ctx.add(ctx)
            try:
                if not rule.search(ctx + "\n"):
                    continue
            except Exception:
                continue
            if _fire_count(prism, extractor, lang, family, ctx + "\n") > 0:
                return ctx
    return None


def test_cell(
    prism: Prism,
    extractor: StructuralExtractor,
    lang: str,
    family: str,
    rule: re.Pattern[str],
    syntax: LangSyntax,
    preferred_keyword: str | None = None,
) -> dict[str, Any] | None:
    """Run the 6-gate SOP-001-v1 battery for one `(lang, family)` cell."""
    # G1: Positive control
    trigger = find_trigger(prism, extractor, lang, family, rule, preferred_keyword=preferred_keyword)
    if trigger is None:
        return None

    kw = trigger.strip()

    # G2: Primary full-line comment decoy
    comment_hits = _fire_count(prism, extractor, lang, family, syntax.comment.format(kw=trigger))
    comment_verdict = "pass" if comment_hits == 0 else "leak"

    # G3: Secondary / multi-line block comment decoy
    block_verdict: str | None = None
    if syntax.block_comment is not None:
        block_hits = _fire_count(prism, extractor, lang, family, syntax.block_comment.format(kw=trigger))
        block_verdict = "pass" if block_hits == 0 else "leak"

    # G4: Inline trailing comment decoy (subtract any hits from the dummy prefix itself, e.g. `state_mutation` on `x = 1`)
    inline_verdict: str | None = None
    if syntax.inline_comment is not None:
        base_inline = _fire_count(prism, extractor, lang, family, syntax.inline_comment.format(kw="SENTINEL_NOOP"))
        inline_hits = _fire_count(prism, extractor, lang, family, syntax.inline_comment.format(kw=trigger))
        inline_verdict = "pass" if inline_hits <= base_inline else "leak"

    # G5: Identifier-substring boundary decoy (pure alphabetic/word triggers only)
    ident_verdict: str | None = None
    if _PURE_IDENT.match(kw):
        embedded = f"MY_{kw}_VAL\n" if kw.isupper() else f"my_{kw}_val\n"
        ident_hits = _fire_count(prism, extractor, lang, family, embedded)
        ident_verdict = "pass" if ident_hits == 0 else "leak"

    # G6a: String literal decoy
    string_counts: bool | None = None
    if syntax.string is not None:
        delim = "'" if "'" in syntax.string and '"' not in syntax.string else '"'
        if delim not in trigger:
            string_hits = _fire_count(prism, extractor, lang, family, syntax.string.format(kw=trigger))
            string_counts = string_hits > 0

    # G6b: String-to-comment boundary decoy (subtract any hits from the dummy prefix itself)
    str_cmt_verdict: str | None = None
    if syntax.string_comment is not None:
        base_sc = _fire_count(prism, extractor, lang, family, syntax.string_comment.format(kw="SENTINEL_NOOP"))
        sc_hits = _fire_count(prism, extractor, lang, family, syntax.string_comment.format(kw=trigger))
        str_cmt_verdict = "pass" if sc_hits <= base_sc else "leak"

    return {
        "comment": comment_verdict,
        "block_comment": block_verdict,
        "inline_comment": inline_verdict,
        "ident_boundary": ident_verdict,
        "string_counts": string_counts,
        "string_comment_boundary": str_cmt_verdict,
        "keyword": kw,
        "corpus": CORPUS_LABEL,
        "protocol": PROTOCOL_VERSION,
    }


def run_decoys(
    target_langs: list[str] | None = None,
    *,
    include_parser_langs: bool = False,
    existing_decoys: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, list[tuple[str, str, str]]]]:
    """Run SOP-001-v1 decoy tests across target languages. Returns `(results, leaks_by_gate)`."""
    families, languages, defined = fvc.engine_grid()
    cells = fvc.load_baseline()
    existing_decoys = existing_decoys or {}
    family_keys = {f.key for f in families} - NON_DECOY_FAMILIES

    if target_langs:
        langs = [lang for lang in target_langs if lang in defined]
    elif include_parser_langs:
        langs = languages
    else:
        langs = [lang for lang in languages if lang not in cells]

    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    results: dict[str, dict[str, dict[str, Any]]] = {}
    leaks: dict[str, list[tuple[str, str, str]]] = {
        "comment": [],
        "block_comment": [],
        "inline_comment": [],
        "ident_boundary": [],
        "string_comment_boundary": [],
    }

    for lang in sorted(langs):
        syntax = LANG_SYNTAX.get(lang)
        if syntax is None:
            continue
        rules = LANGUAGE_DEFINITIONS[lang].get("rules", {}) or {}
        target_fams = sorted(defined.get(lang, set()) & family_keys)
        if not target_fams:
            continue
        extractor = StructuralExtractor(lang, LANGUAGE_DEFINITIONS)
        lang_out: dict[str, dict[str, Any]] = {}
        for fam in target_fams:
            pat = rules.get(fam)
            if pat is None or not hasattr(pat, "search"):
                continue
            prev = existing_decoys.get(lang, {}).get(fam)
            preferred = prev.get("keyword") if isinstance(prev, dict) else None
            entry = test_cell(prism, extractor, lang, fam, pat, syntax, preferred_keyword=preferred)
            if entry is not None:
                lang_out[fam] = entry
                for gate in leaks:
                    if entry.get(gate) == "leak":
                        leaks[gate].append((lang, fam, entry["keyword"]))
        if lang_out:
            results[lang] = lang_out

    return results, leaks


def audit_superficial(baseline_path: Path = BASELINE) -> dict[str, Any]:
    """Classify every decoy entry and untested code-stream cell across SOP-002-v1 / SOP-001-v1 / superficial."""
    families, languages, defined = fvc.engine_grid()
    cells = fvc.load_baseline(baseline_path)
    decoys = fvc.load_decoys(baseline_path)
    code_fams = {f.key for f in families} - NON_DECOY_FAMILIES

    sop2_current: collections.Counter[str] = collections.Counter()
    sop1_current: collections.Counter[str] = collections.Counter()
    superficial: collections.Counter[str] = collections.Counter()
    untested: collections.Counter[str] = collections.Counter()

    for lang in languages:
        for fam in defined.get(lang, set()) & code_fams:
            if fam in cells.get(lang, {}):
                continue
            dec = decoys.get(lang, {}).get(fam)
            if dec is None:
                untested[lang] += 1
            elif dec.get("protocol") == "SOP-002-v1":
                sop2_current[lang] += 1
            elif dec.get("protocol") == PROTOCOL_VERSION:
                sop1_current[lang] += 1
            else:
                superficial[lang] += 1

    return {
        "protocol": PROTOCOL_VERSION,
        "sop2_total": sum(sop2_current.values()),
        "sop_current_total": sum(sop1_current.values()) + sum(sop2_current.values()),
        "sop1_only_total": sum(sop1_current.values()),
        "superficial_total": sum(superficial.values()),
        "untested_total": sum(untested.values()),
        "sop2_by_lang": dict(sorted(sop2_current.items())),
        "superficial_by_lang": dict(sorted(superficial.items())),
        "untested_by_lang": dict(sorted(untested.items())),
    }


def merge_baseline(
    new_decoys: dict[str, dict[str, dict[str, Any]]],
    baseline_path: Path = BASELINE,
) -> dict[str, Any]:
    """Merge `new_decoys` into `baseline_path`'s `decoys` section and write it back."""
    data = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.exists() else {"cells": {}}
    decoys = data.setdefault("decoys", {})
    for lang, fams in new_decoys.items():
        bucket = decoys.setdefault(lang, {})
        for fam, entry in fams.items():
            bucket[fam] = entry
    data["decoys"] = {lang: dict(sorted(fams.items())) for lang, fams in sorted(decoys.items())}
    baseline_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", nargs="*", help="specific language(s) to run (default: all parserless languages)")
    ap.add_argument("--all-langs", action="store_true", help="include parser-scored languages too")
    ap.add_argument("--write", action="store_true", help="merge results into tests/family_validity_baseline.json")
    ap.add_argument("--audit-superficial", action="store_true", help="report cells lacking SOP-001-v1 coverage")
    ap.add_argument("--baseline", default=str(BASELINE), help="baseline JSON path")
    args = ap.parse_args(argv)

    baseline_path = Path(args.baseline)
    if args.audit_superficial:
        rep = audit_superficial(baseline_path)
        print(
            f"SOP audit: "
            f"{rep['sop2_total']} SOP-002-v1 (spec-grade), "
            f"{rep['sop1_only_total']} SOP-001-v1 (first-pass), "
            f"{rep['superficial_total']} superficial (pre-SOP), "
            f"{rep['untested_total']} untested code-stream cells."
        )
        if rep["superficial_by_lang"]:
            print("Superficial by language:", rep["superficial_by_lang"])
        return 0

    existing = fvc.load_decoys(baseline_path)
    results, leaks = run_decoys(
        args.lang or None,
        include_parser_langs=args.all_langs,
        existing_decoys=existing,
    )

    total_cells = sum(len(v) for v in results.values())
    new_cells = sum(1 for lang, fams in results.items() for fam in fams if fam not in existing.get(lang, {}))
    print(
        f"Decoy run complete ({PROTOCOL_VERSION}): "
        f"{len(results)} languages, {total_cells} cells tested ({new_cells} newly covered)."
    )
    for gate, items in leaks.items():
        if items:
            by_lang = collections.Counter(lang for lang, _, _ in items)
            print(f"  LEAKS [{gate:23s}]: {len(items):3d} total -> {dict(by_lang.most_common(10))}")

    if args.write:
        merge_baseline(results, baseline_path)
        print(f"\nMerged into {baseline_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
