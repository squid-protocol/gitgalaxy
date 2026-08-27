#!/usr/bin/env python3
"""
tri_comparison_chart.py

The unified entry point: runs the tri-comparison pipeline (gather -> reconcile -> ledger merge)
across GitGalaxy's languages and renders ONE SVG -- docs/self_scan/tri_comparison_chart.svg --
covering all three tools (GitGalaxy, tree-sitter, ctags), unlike tree_sitter_accuracy_audit.py's
chart which only ever had two bars to draw.

USAGE
    python tests/tools/tri_comparison_chart.py --languages python,rust,csharp --write
    python tests/tools/tri_comparison_chart.py --all --write   # every language with a corpus

PANELS: FIVE, BUT ONLY TWO ARE RANKED
    Functions Found, Function Precision, Classes Found, Class Precision, Args Found.

    RECALL AND ARGS-MATCH WERE REMOVED AS RATIOS -- THEIR DENOMINATORS AREN'T TRUSTWORTHY
    ENOUGH TO RANK ON YET
        An earlier version of this chart rendered "Func/Class Recall" as matched/union (every
        slot ANY available tool reported) and "Args Match" as matched-the-cross-tool-majority /
        comparable. Both sounded principled but share the same flaw: BOTH require trusting an
        unverified cross-tool agreement as if it were correctness, and both are exactly as
        unreliable as any one tool's own noise -- confirmed twice on real data, not
        theoretically: ctags' Haskell parser double/triple-tags multi-clause functions (one tag
        per pattern-match equation), and tree-sitter's own raw walk had the identical bug for the
        same language before it was fixed earlier in this effort. Either bug inflates a SHARED
        denominator (recall's union) or corrupts a "majority" (args' 2-vs-1 credit), silently
        distorting every OTHER tool's score too -- a ranking built on unverified cross-tool
        agreement isn't a ranking worth showing yet. Reporting the bare found-count instead (no
        ratio, no implied "of how many" or "how many matched") sidesteps the problem entirely:
        it's just what each tool actually claimed, full stop, not scored against anything
        uncertain. Once a language/metric's ledger shapes are validated (see
        docs/self_scan/how_to_investigate_a_discrepancy.md), a real denominator can come back for
        that language specifically -- this is a deliberate, temporary state, not a permanent
        downgrade.
    PRECISION SURVIVES BECAUSE ITS DENOMINATOR IS DIFFERENT IN KIND, NOT DEGREE
        precision_t = (slots tool t reported that at least one OTHER tool corroborated) / (slots
        tool t reported, period) -- the denominator is that SAME tool's own claim count, never a
        cross-tool union or majority vote. A tool can't inflate its own precision denominator by
        being noisy elsewhere the way it can inflate everyone's shared recall denominator or skew
        an args majority. This is exactly the "of what we found, how many are real" framing --
        confirmed differentiated on rust: GitGalaxy's ~92% precision there (some GitGalaxy-only
        claims uncorroborated) is a genuine signal a bare found-count alone wouldn't show.

    Found-count panels never render a winner badge and never enter the bottom summary tally --
    "found more" isn't a claim that tool is more correct (more found is what a hallucinating
    tool does too), so there's no ranking to declare. Only the two genuinely ranked panels
    (Func/Class Precision) produce a badge and count toward the summary.

CSS/HTML CLASS PANELS: OUT OF SCOPE, NOT JUST LOW-SCORING
    GitGalaxy's own `class_start` for css/html targets selector/tag-shaped entities (`.foo {`),
    not OOP-shaped classes -- the bi-comparison chart already treats this as permanently out of
    scope by design (epic #1295), not an unmeasured gap. This chart matches that: css and html
    are excluded from class_recall/class_precision reconciliation entirely (see
    _CLASS_SCOPE_EXCLUDED_LANGS below), not scored and hidden, so a discrepancy ledger entry
    never gets manufactured for a comparison that was never a fair one to begin with.

BAR GROUPS: VARIABLE, NOT ALWAYS THREE
    Every language with real data gets a GitGalaxy bar. Only 24 of GitGalaxy's 45 languages get
    all three (both tree-sitter and ctags available); 7 more get GitGalaxy+tree-sitter only
    (ctags has no parser for them); 9 get GitGalaxy+ctags only (tree-sitter has no grammar for
    them -- ada, agc_assembly, assembly, cobol, embedded_python, m4, scheme, sqlite, yacc); the
    rest render GitGalaxy alone. Bars are drawn compactly -- a 2-bar group is never padded with
    an empty slot for the missing tool -- but ALWAYS in the fixed order GitGalaxy, tree-sitter,
    ctags, so a given vertical position in the stack means the same tool in every row.

    "Real data" is stricter than "the corpus directory exists", in two distinct ways, each
    confirmed by hand rather than assumed:
      - lua and groovy have a language-crucible directory with files in it, but GitGalaxy's own
        language routing finds ZERO files that are actually lua/groovy source (Redis's C
        Lua-embedding code; Groovy tooling written in Java) -- gather_language() returns an empty
        result list, treated identically to a missing corpus directory (embedded_python, sqlite,
        ada): an "awaiting language-crucible corpus" row.
      - jcl and livecode have real, CORRECTLY-routed files (3 real .jcl files; 2 real livecode
        files) but every tool finds zero functions/classes in all of them -- every score is an
        undefined 0/0, not a low one. Same visual "awaiting" treatment, honest wording
        (`LanguageChartData.awaiting_note`) since the corpus genuinely isn't missing here, just
        empty of anything comparable in this small a sample.

EVERY TOOL'S BAR IS ALWAYS ITS OWN COLOR; ASTERISK MEANS "NOT YET VERIFIED", NOT "LOST"
    An earlier version of this chart turned GitGalaxy's bar gray when it lost to another
    available tool and that gap hadn't been investigated, then later moved to asterisking only
    GitGalaxy's own label. Both versions singled GitGalaxy out, which was backwards: the open
    question in a disputed cell is "has anyone actually read the source and confirmed who's
    right", and that question applies to EVERY tool shown there, not just GitGalaxy. Every
    tool's bar is always its normal categorical color; `*` now appends to EVERY tool's value
    label in a cell with any currently-reproducing, unvalidated ledger entry for that
    (language, symbol_type, metric) -- see `ledger_mod.has_open_question()` and
    docs/self_scan/how_to_investigate_a_discrepancy.md for what an asterisk is asking for.

VALUE LABELS: CENTERED ON EACH BAR, NOT STACKED TO THE SIDE
    Each bar carries its own value label (a ranked panel's `matched/total`, or a found-count
    panel's bare count) centered horizontally within the bar-track (the fixed-width background,
    not the variable-length fill -- so a short bar's label doesn't end up crammed against its own
    left edge), in white for contrast against the saturated fill.

WINNER BADGE: REQUIRES VERIFICATION, NOT JUST THE HIGHER NUMBER
    A badge implies "we know who's actually right" -- a raw percentage comparison alone isn't
    enough to earn that claim. Confirmed necessary by a real case, not a hypothetical: under a
    pure highest-rate_pct rule, a 2-sample cell at 100% (2/2) outranked an 80-sample cell at
    98.75% (79/80) with a badge exactly as confident-looking as any other, an artifact of sample
    size nobody had verified, not evidence that tool was more correct there. A cell only gets a
    badge now if `has_open_question()` is False for it (no ledger entry currently reproduces
    unvalidated) AND one available tool scored strictly highest, OR won a tie-break among tools
    sharing the top rate (see `_winner_or_tie`'s own docstring -- a rate-only tie is broken by
    each tied tool's absolute count of validated-correct occurrences, so a tool that's simply
    never wrong but narrower in scope doesn't erase the badge a tool with a larger validated
    claim count has earned) -- a colored letter (G/T/C) in that tool's own categorical color, in
    the space a stacked column of raw numbers used to occupy. No badge on a disputed cell
    (regardless of how lopsided the raw numbers look), or a tie the count tie-break also can't
    resolve.

    A 1-bar group (GitGalaxy alone -- no tree-sitter, no ctags) CAN earn a badge, via a
    different path than a cross-tool win: `_manual_verification_winner()` awards GitGalaxy's own
    badge when a fully-current manual-verification record (`MANUAL_VERIFICATION_PATH`) confirms
    100% of that tool's own claims by hand. This isn't a weaker substitute for the real
    verification bar above -- the whole point of gating it on `verified == total` (not partial
    credit) is that it clears the SAME "we know who's actually right" confidence a cross-tool
    win clears, just established by a different, equally rigorous method. Deliberately NOT
    restricted to languages that already have tree-sitter/ctags coverage: GitGalaxy is going
    after tree-sitter-blind, ctags-blind "frontier" languages on purpose, and a language
    shouldn't be structurally locked out of a badge forever just because no comparison tool
    exists for it yet -- that would make the badge a proxy for "how mainstream is this
    language's tooling ecosystem," not "how correct is GitGalaxy here," which was never the
    intent. See `_manual_verification_winner()`'s own docstring for the exact gating.

COLOR SOURCE
    Categorical slots 1-3 of the validated reference palette (see the `dataviz` skill's
    references/palette.md) -- GitGalaxy=blue, tree-sitter=orange, ctags=aqua. Those three slots
    are the ones documented as clearing the ALL-PAIRS CVD/contrast gates in both light and dark
    mode, the relevant gate for a small-multiples chart with this many rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ctags_reader  # noqa: E402
import tri_comparison_ledger as ledger_mod  # noqa: E402
from tri_comparison_reconcile import ALL_TOOLS, MetricScore, reconcile_symbols  # noqa: E402

CHART_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "self_scan" / "tri_comparison_chart.svg"

# For a language with only ONE available tool (no tree-sitter, no ctags -- e.g. abap), precision
# is structurally always 0/N: reconcile_symbols' matched_consensus requires a SECOND tool to
# corroborate a slot, and there isn't one to ask. That's an honest number, not a wrong one -- but
# it silently discards real evidence when a slower, manual pass (direct source cross-check, an
# independent grep, an LLM read of the actual corpus) has already confirmed some or all of a
# tool's claims by a different method than tool-vs-tool agreement. This file is that record,
# reviewed and committed by hand -- never machine-generated, never auto-updated by a gather run --
# so precision can show `verified/total**` instead of a bare `0/N` where a human (or an LLM,
# reviewed by a human) has actually done the checking. `**` is deliberately distinct from `*`
# (ledger_mod's "unvalidated cross-tool disagreement") -- this is a different evidentiary category
# (single-source manual review, not multi-tool corroboration), not a stronger or weaker version of
# the same claim, and the chart must never blur the two together.
MANUAL_VERIFICATION_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "self_scan" / "manual_verification.json"


def _load_manual_verification() -> dict:
    if not MANUAL_VERIFICATION_PATH.exists():
        return {}
    return json.loads(MANUAL_VERIFICATION_PATH.read_text()).get("languages", {})


def _manual_verification_entry(manual_verification: dict, lang: str, symbol_type: str) -> dict | None:
    """Returns the (verified, total) record for (lang, symbol_type) only if it's still current --
    `total` must equal the tool's OWN present found-count, not just exist. A stale record (the
    engine's count moved since the record was written, e.g. a later fix or regression) must fall
    back to the plain, honest `0/N` rather than silently keep claiming a verification that no
    longer matches what the tool actually reports today. Never inferred/auto-refreshed here --
    staleness is a signal to go re-verify and update the file by hand, not to guess."""
    return manual_verification.get(lang, {}).get(symbol_type)

# The 45 languages with real structural signatures (see docs/language_status/README.md) --
# NODE_MAPS's 31 tree-sitter-baselined languages plus the 14 GitGalaxy extracts from but
# tree-sitter has no grammar for.
_GG_ONLY_LANGS = (
    "abap",
    "ada",
    "agc_assembly",
    "assembly",
    "cobol",
    "dockerfile",
    "embedded_python",
    "jcl",
    "livecode",
    "m4",
    "scheme",
    "sqlite",
    "yacc",
    "yaml",
)

# See module docstring's CSS/HTML CLASS PANELS section -- class_start there targets
# selector/tag-shaped entities, not OOP classes; excluded from class reconciliation entirely
# (epic #1295 precedent), not scored and hidden.
_CLASS_SCOPE_EXCLUDED_LANGS = frozenset({"css", "html"})

# ARGS GRANULARITY: "args" doesn't mean the same unit across every language, even when a real
# comparison tool exists for existence. See .claude/skills/tri-comparison-ledger-sweep/SKILL.md's
# "Args granularity" section for the full methodology this was built from (2026-08-20) -- summary
# here, don't duplicate the reasoning. Three non-default categories, each rendered with its own
# superscript-style marker appended to the Args Found bar label (same convention as `*`/`**`
# already use), plus its own legend line:
#   - "program_level": exactly ONE real signature per compilation unit, not one per callable --
#     a per-function args count reading ~0 is CORRECT, not a recall gap. cobol: PROCEDURE
#     DIVISION USING/RETURNING is a whole-program header; paragraphs don't take individual
#     arguments at all (confirmed: 124/126 real cobol paragraphs genuinely take zero
#     paragraph-scoped arguments).
#   - "none": func_start matches a document-structural marker as a pseudo-callable (same "one
#     comparable schema across every language" reason non-function-shaped languages get a
#     func_start rule at all) -- there is no parameter-list concept to measure, ever. Confirmed
#     via direct regex inspection: dockerfile's func_start matches RUN/CMD/ENTRYPOINT/
#     HEALTHCHECK instruction keywords; yaml's matches CI run:/script: step keys; jcl's matches
#     EXEC job steps.
#   - "proxy": a real, non-trivial per-function measurement exists, just derived from something
#     other than a parenthesized parameter list -- same spirit as the bash/Perl $1/$2/$3
#     precedent in docs/why_gitgalaxy_beats_ast_here.md. assembly/agc_assembly: args counts
#     calling-convention register mentions (rdi/rsi/rdx/xmm0-7/etc.) inside the function body as
#     an argument-count proxy -- real data (67%/42% zero, not 100%), but structurally
#     unverifiable against ctags either way, since ctags emits no signature: field for these
#     languages at all.
# Default (absent from this dict): "per_function", the ordinary per-callable parameter-list
# count -- no marker needed. Before adding a language here, rule out a real recall bug first
# (check the ledger for an unvalidated existence shape on that language) -- a near-zero args
# count is a question, never an assumed answer; scheme and m4 both looked like granularity
# candidates at first glance and turned out to be ordinary recall bugs instead.
ARGS_GRANULARITY: dict[str, str] = {
    "cobol": "program_level",
    "dockerfile": "none",
    "yaml": "none",
    "jcl": "none",
    "assembly": "proxy",
    "agc_assembly": "proxy",
}

_ARGS_GRANULARITY_MARKER: dict[str, str] = {
    "program_level": "†",  # †
    "none": "‡",  # ‡
    "proxy": "§",  # §
}

_ARGS_GRANULARITY_LEGEND: dict[str, str] = {
    "program_level": "program-level signature, not per-function",
    "none": "no parameter-list concept exists for this language",
    "proxy": "derived from a non-parenthetical proxy, not a parameter list",
}

_TOOL_LABEL = {"gitgalaxy": "GitGalaxy", "tree_sitter": "tree-sitter", "ctags": "ctags"}
_TOOL_BADGE_LETTER = {"gitgalaxy": "G", "tree_sitter": "T", "ctags": "C"}

# Categorical palette slots 1-3 (validated all-pairs, both modes -- see dataviz skill's
# references/palette.md). Light-mode values; this is a static, light-surface-only SVG, matching
# tree_sitter_accuracy_chart.svg's own precedent.
_COLOR_GITGALAXY = "#2a78d6"
_COLOR_TREE_SITTER = "#eb6834"
_COLOR_CTAGS = "#1baf7a"
_COLOR_TOOL = {"gitgalaxy": _COLOR_GITGALAXY, "tree_sitter": _COLOR_TREE_SITTER, "ctags": _COLOR_CTAGS}


def all_languages() -> list[str]:
    import tree_sitter_accuracy_audit as tsaa

    return sorted(set(tsaa.NODE_MAPS.keys()) | set(_GG_ONLY_LANGS))


def _available_tools(lang: str) -> tuple[str, ...]:
    import tree_sitter_accuracy_audit as tsaa

    tools = ["gitgalaxy"]
    if lang in tsaa.NODE_MAPS:
        tools.append("tree_sitter")
    if ctags_reader.ctags_available(lang):
        tools.append("ctags")
    return tuple(tools)


def _corpus_exists(lang: str) -> bool:
    import os

    root = Path(
        os.environ.get(
            "LANGUAGE_CRUCIBLE_PATH", Path(__file__).resolve().parent.parent.parent.parent / "language-crucible"
        )
    )
    return (root / "data" / lang).exists()


class LanguageChartData:
    def __init__(self, lang: str):
        self.lang = lang
        self.available_tools = _available_tools(lang)
        self.has_data = _corpus_exists(lang)  # refined in run_pipeline once gather actually runs
        self.awaiting_note = "awaiting language-crucible corpus"
        self.func_recall: dict[str, MetricScore] = {}
        self.func_precision: dict[str, MetricScore] = {}
        self.class_recall: dict[str, MetricScore] = {}
        self.class_precision: dict[str, MetricScore] = {}
        self.args: dict[str, MetricScore] = {}
        # #1918: args_scores' own total_slots is structurally always 0 for a 1-tool
        # language (reconcile_symbols only increments it when 2+ tools are comparable at a
        # slot) -- so unlike func/class Found (whose found_field, matched_consensus, IS a
        # real per-tool raw count regardless of tool count), there's no live ground-truth
        # signal already on this object to check a manual-verification record's staleness
        # against for the args panel. Populated in run_pipeline from GitGalaxy's own raw
        # Occurrence.args values, independent of any cross-tool comparison.
        self.gg_args_found: int = 0


def run_pipeline(languages: list[str], verbose: bool = True) -> dict[str, LanguageChartData]:
    from tri_comparison_gatherer import gather_language

    out: dict[str, LanguageChartData] = {}
    for lang in languages:
        data = LanguageChartData(lang)
        out[lang] = data
        if not data.has_data:
            if verbose:
                print(f"tri_comparison_chart: {lang} -- no language-crucible corpus, skipping (awaiting data)")
            continue
        if verbose:
            print(f"tri_comparison_chart: {lang} -- gathering ({', '.join(data.available_tools)})...")
        try:
            results = gather_language(lang)
        except SystemExit as e:
            if verbose:
                print(f"tri_comparison_chart: {lang} -- gather failed ({e}), skipping")
            data.has_data = False
            continue

        if not results:
            # Corpus directory exists but GitGalaxy's own language routing found zero files
            # actually written in this language (confirmed cases: lua, groovy -- see module
            # docstring). Functionally identical to no corpus at all for chart purposes.
            if verbose:
                print(f"tri_comparison_chart: {lang} -- corpus has no real {lang} files, treating as awaiting data")
            data.has_data = False
            continue

        func_recall, func_precision, args_scores, func_groups = reconcile_symbols(
            results, "function", data.available_tools, lang
        )
        data.func_recall = func_recall
        data.func_precision = func_precision
        data.args = args_scores
        data.gg_args_found = sum(o.args for r in results for o in r.gg_funcs if o.args is not None)

        class_groups: list = []
        if lang not in _CLASS_SCOPE_EXCLUDED_LANGS:
            class_recall, class_precision, _, class_groups = reconcile_symbols(
                results, "class", data.available_tools, lang
            )
            data.class_recall = class_recall
            data.class_precision = class_precision

        # Different case from the empty-results one above: real, correctly-routed files exist
        # (confirmed cases: jcl -- 3 real .jcl files; livecode -- 2 real files) but EVERY tool
        # found zero functions/classes in all of them, so every score is an undefined 0/0
        # (MetricScore.rate_pct is None). Rendering three empty bar-tracks with no bars at all
        # reads as a broken row, not a "nothing to compare" one -- same visual "awaiting" note,
        # honest wording since the corpus genuinely isn't missing here.
        any_real_score = any(
            s.rate_pct is not None for d in (data.func_recall, data.class_recall, data.args) for s in d.values()
        )
        if not any_real_score:
            if verbose:
                print(
                    f"tri_comparison_chart: {lang} -- {len(results)} real file(s) but 0 functions/classes found by any tool"
                )
            data.has_data = False
            data.awaiting_note = "no functions/classes found in this corpus by any tool"

        ledger_mod.merge_and_save(lang, func_groups + class_groups, path=ledger_mod.LEDGER_PATH)

        # A validated verdict that cleanly confirms one tool correct (or two tools jointly wrong)
        # on an otherwise-agreement-scored claim should actually move that tool's precision
        # number, not just suppress its asterisk -- see tri_comparison_ledger.py's own VERIFIED
        # ADJUSTMENTS docstring section for the full reasoning and why this is precision-only
        # (never recall/found-count, which was never a ranked claim to begin with).
        ledger_mod.apply_verified_adjustments(data.func_precision, func_groups, path=ledger_mod.LEDGER_PATH)
        if class_groups:
            ledger_mod.apply_verified_adjustments(data.class_precision, class_groups, path=ledger_mod.LEDGER_PATH)
    return out


def _disputed(lang: str, symbol_type: str, ledger_metric: str) -> bool:
    return ledger_mod.has_open_question(lang, symbol_type, ledger_metric, path=ledger_mod.LEDGER_PATH)


def _winner_or_tie(scores: dict[str, MetricScore], available_tools: tuple[str, ...]) -> str | None:
    """Tool name with the strictly-highest score among available tools with real data; the
    literal string "tie" if 2+ tools share the top score AND the tie can't be broken (see below);
    None if fewer than 2 tools have real data at all (a 1-bar group, or an empty panel) -- that
    last case isn't a comparison, so it's kept distinct from a real tie rather than folded into
    it. The badge renderer only cares about the winner case (see _winner below); the
    bottom-of-chart tally (render_chart's summary block) needs all three states to count "how
    many of the 5x45 possible comparisons actually happened, and how did each one resolve"
    without silently inflating the tie count with cells that were never a real comparison to
    begin with.

    A tie at the top rate_pct is broken by each tied tool's own matched_consensus (its absolute
    count of validated-correct occurrences) -- confirmed necessary by rust's func/class existence
    panels: GitGalaxy, tree-sitter, and ctags all land on 100% precision once GitGalaxy's
    macro-body-only claims are ledger-validated (each tool is simply never WRONG about what it
    claims, at very different claim counts -- 1927 vs. 1775 vs. 1774), so a rate-only comparison
    ties 3 ways and nobody gets a badge despite GitGalaxy having demonstrably found MORE of the
    validated-real total. This is the inverse of the sample-size bug the rate-only rule was
    already fixed for (see this module's WINNER BADGE docstring): there, a smaller sample's
    identical rate got an unearned edge; here, a larger validated sample at an identical rate was
    getting NO edge at all. Both are the same principle -- more evidence should count for
    something -- pointing opposite directions. Only ever reached once the caller has already
    confirmed the cell isn't disputed (`_disputed`/`has_open_question` is checked before this is
    called), so every matched_consensus value used here is already either unquestioned or
    ledger-validated -- this breaks ties with verified evidence, not a bare unverified count."""
    vals = [(t, scores[t].rate_pct) for t in available_tools if t in scores and scores[t].rate_pct is not None]
    if len(vals) < 2:
        return None
    vals.sort(key=lambda tv: -tv[1])
    top_rate = vals[0][1]
    tied = [t for t, rate in vals if rate == top_rate]
    if len(tied) < 2:
        return tied[0]
    counts = sorted(((t, scores[t].matched_consensus) for t in tied), key=lambda tc: -tc[1])
    if counts[0][1] == counts[1][1]:
        return "tie"
    return counts[0][0]


def _winner(scores: dict[str, MetricScore], available_tools: tuple[str, ...]) -> str | None:
    """Tool name with the strictly-highest score, or None on a tie OR no real comparison --
    the coarser two-way split the badge renderer actually needs (draw a badge, or don't)."""
    result = _winner_or_tie(scores, available_tools)
    return result if result != "tie" else None


def _manual_verification_winner(
    manual_verification: dict,
    lang: str,
    mv_key: str,
    live_total: int | None,
    available_tools: tuple[str, ...],
) -> str | None:
    """A badge for a genuine cross-tool win means "we know who's actually right" -- but for a
    language with only ONE available tool at all (no tree-sitter, no ctags), that's structurally
    never possible via _winner/_winner_or_tie (they need 2+ tools to even have a comparison), so
    every such language was permanently badge-less no matter how solid its own numbers were. That
    stopped being the right call once GitGalaxy started deliberately going after more
    tree-sitter/ctags-blind "frontier" languages: a manually-verified 1-tool language has earned
    the SAME confidence claim a real cross-tool win makes, just via a different verification
    method (see MANUAL_VERIFICATION_PATH's own comment) -- it shouldn't be structurally locked
    out of the badge just because it's on the frontier. Returns "gitgalaxy" (the only tool that
    can ever hold this position) only when: exactly one tool is available, a manual-verification
    record exists at manual_verification[lang][mv_key] (`mv_key` is "function"/"class" for the
    precision panels, "args" for Args Found -- args uses a DIFFERENT key than symbol_type would
    give, since symbol_type is "function" for both func precision AND args and the two must not
    collide), that record's `total` still matches `live_total` -- the same staleness guard the
    `**` label uses, and deliberately a CALLER-SUPPLIED value rather than always reading
    score.total_slots here, since args_scores' own total_slots is structurally always 0 for a
    1-tool language (see gg_args_found's own comment) and needs a different live anchor than the
    precision panels do -- AND the record is a FULL verification (`verified == total`) -- a
    partial one (some slots checked, some not) earns the `**` label's honest partial credit but
    not the full confidence claim a badge makes. Never called when _winner already found a real
    2+-tool winner -- this is a fallback for the "structurally couldn't have one" case only, not
    a replacement for real corroboration.

    A second, narrower qualifying path exists ONLY for `mv_key == "args"`: a language can have a
    real second tool for func/class (agc_assembly has ctags) while that same tool is structurally
    incapable of reporting args at all (ctags emits no `signature:` field for Asm-parsed files --
    see ARGS_GRANULARITY's own comment). That's not "we didn't get around to comparing," it's "no
    comparison could ever exist here," the identical justification the whole-language 1-tool case
    already rests on, just scoped to one metric instead of the whole language. Gated on
    `ARGS_GRANULARITY.get(lang) in ("proxy", "program_level")` specifically -- NOT "none", since a
    `none`-granularity language's true args count is 0 by construction (nothing to verify, no
    manual_verification.json entry ever needed for it), and NOT the default `per_function` case,
    where a second tool's absence really would just mean "not yet compared." func/class precision
    (`mv_key in ("function", "class")`) never gets this path -- see the `len(available_tools) == 1`
    comment at this function's ranked-panel call site for why a 2-3 tool language's real 0/N must
    stay visible, not be quietly replaced by a manual record."""
    is_whole_language_gg_only = len(available_tools) == 1 and available_tools[0] == "gitgalaxy"
    is_args_structurally_uncomparable = mv_key == "args" and ARGS_GRANULARITY.get(lang) in ("proxy", "program_level")
    if not is_whole_language_gg_only and not is_args_structurally_uncomparable:
        return None
    if live_total is None:
        return None
    mv = _manual_verification_entry(manual_verification, lang, mv_key)
    if mv is None or mv["total"] != live_total:
        return None
    if mv["verified"] != mv["total"]:
        return None
    return "gitgalaxy"


_CHART_STYLE = """<style>
  .surface { fill: #fcfcfb; }
  .title { font-size: 15px; font-weight: 600; fill: #0b0b0b; }
  .subtitle { font-size: 11px; fill: #52514e; }
  .scope-note { font-size: 10px; fill: #706f6a; }
  .panel-title { font-size: 10.5px; font-weight: 600; fill: #0b0b0b; text-anchor: middle; }
  .summary-title { font-size: 10.5px; font-weight: 600; fill: #0b0b0b; text-anchor: start; }
  .lang-label { font-size: 13px; font-weight: 700; fill: #0b0b0b; }
  .bar-value-label { font-size: 8px; fill: #ffffff; text-anchor: middle; font-weight: 600; }
  .legend-label { font-size: 10px; fill: #0b0b0b; }
  .stripe { fill: #f0efec; }
  .awaiting { font-size: 9.5px; fill: #9a9a95; font-style: italic; }
  .bar-track { fill: #eeede9; }
  .badge-label { font-size: 8.5px; font-weight: 700; fill: #ffffff; text-anchor: middle; }
</style>"""


def render_chart(data_by_lang: dict[str, LanguageChartData]) -> str:
    from datetime import datetime, timezone

    manual_verification = _load_manual_verification()

    langs = sorted(data_by_lang.keys())
    n = len(langs)

    label_col_w = 138  # room for "embedded_python" (longest name) bold at 13px
    bar_max_w = 88
    badge_col_w = 20
    inner_gap = 6
    panel_w = bar_max_w + inner_gap + badge_col_w
    panel_gap = 18
    left_margin, right_margin = 16, 16
    top_margin = 142  # +14 vs. the old 128 -- room for the args-granularity legend line below
    header_h = 20
    bottom_margin = 44
    bar_h = 10
    sub_gap = 2
    row_pad = 5
    row_h = row_pad * 2 + 3 * bar_h + 2 * sub_gap  # room for up to 3 stacked bars, always

    # (data attr, symbol_type, ledger metric, panel title, ranked, found_field -- see
    # ledger_mod.has_open_question's own docstring for the asterisk/badge gating this drives,
    # symmetric across all three tools now regardless of panel. `ranked` False means "found
    # count, no bar-width ratio, no winner badge, doesn't enter the summary tally" -- see module
    # docstring's PANELS section for why the two existence panels AND args dropped their ratio.
    # `found_field` is which MetricScore attribute IS the found-count on an unranked panel:
    # func/class use matched_consensus (this tool's own raw claim count, gate-free); args uses
    # total_slots instead, since args_scores' matched_consensus already means "matched the
    # cross-tool majority" -- exactly the pre-verification correctness claim this panel is
    # deliberately NOT making yet, so it can't be reused as a neutral "found" count the way
    # func/class's can.)
    panels = [
        ("func_recall", "function", "existence", "Functions Found", False, "matched_consensus"),
        ("func_precision", "function", "existence", "Func Precision", True, None),
        ("class_recall", "class", "existence", "Classes Found", False, "matched_consensus"),
        ("class_precision", "class", "existence", "Class Precision", True, None),
        ("args", "function", "args", "Args Found", False, "total_slots"),
    ]

    panels_x_start = left_margin + label_col_w
    width = panels_x_start + len(panels) * panel_w + (len(panels) - 1) * panel_gap + right_margin

    # Tally: one vote per (language, panel) cell that's an actual comparison (2+ tools with real
    # data) AND not disputed (see WINNER BADGE module docstring -- a badge/vote requires
    # has_open_question() to be False, not just a highest score) -- up to 2 ranked panels x 45
    # languages, but a 1-bar group, an empty panel (css/html class), or a still-disputed cell
    # contributes no vote at all, per _winner_or_tie's own docstring on why "no comparison
    # happened" has to stay distinct from "it was a tie".
    tally: Counter[str] = Counter()
    for lang, data in data_by_lang.items():
        if not data.has_data:
            continue
        for attr, symbol_type, ledger_metric, _, ranked, _ in panels:
            if not ranked:
                continue
            scores = getattr(data, attr)
            if not scores:
                continue
            if _disputed(lang, symbol_type, ledger_metric):
                continue
            result = _winner_or_tie(scores, data.available_tools)
            if result is None:
                gg_score = scores.get("gitgalaxy")
                result = _manual_verification_winner(
                    manual_verification,
                    lang,
                    symbol_type,
                    gg_score.total_slots if gg_score is not None else None,
                    data.available_tools,
                )
            if result is not None:
                tally[result] += 1
    total_votes = sum(tally.values())

    summary_h = 76
    height = top_margin + header_h + n * row_h + bottom_margin + summary_h
    rows_top = top_margin + header_h

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        + f'width="{width}" height="{height}" font-family="system-ui, -apple-system, Segoe UI, sans-serif">',
        _CHART_STYLE,
        f'<rect class="surface" x="0" y="0" width="{width}" height="{height}"/>',
        f'<text class="title" x="{left_margin}" y="20">GitGalaxy Structural Extraction: Tri-Comparison '
        + f"vs. Tree-sitter and ctags</text>",
        f'<text class="subtitle" x="{left_margin}" y="36">{datetime.now(timezone.utc).strftime("%Y-%m-%d")} '
        + f"&#183; source: tests/tools/tri_comparison_chart.py &#183; "
        + f"ledger: docs/self_scan/tri_comparison_ledger.json</text>",
        f'<text class="scope-note" x="{left_margin}" y="52">No tool is ground truth. Found-count panels '
        + f'are unranked raw counts (no badge) -- a shared "how many are real" denominator turned out '
        + f"as corruptible as any one tool's own noise. Precision is each tool's own claims vs. what "
        + f"another tool corroborated.</text>",
        f'<text class="scope-note" x="{left_margin}" y="64">Bar groups vary 1-3 by language\'s tool coverage '
        + f"-- order is always GitGalaxy, tree-sitter, ctags. css/html class panels are out of "
        + f"scope by design (selectors, not OOP classes).</text>",
        f'<text class="scope-note" x="{left_margin}" y="76">`*` marks EVERY tool\'s label in a cell with '
        + f"any unvalidated disagreement, not just GitGalaxy's -- not a verdict either way. Badge = "
        + f"the tool that scored strictly highest on a RANKED, UN-disputed panel (blank on a tie, a "
        + f"disputed cell, or a found-count panel).</text>",
        f'<text class="scope-note" x="{left_margin}" y="88">See docs/self_scan/how_to_investigate_a_discrepancy.md '
        + f"for what `*` is asking for.</text>",
    ]

    legend_y = 108
    lx = left_margin
    for tool in ALL_TOOLS:
        parts.append(f'<rect x="{lx}" y="{legend_y - 8}" width="14" height="8" rx="2" fill="{_COLOR_TOOL[tool]}"/>')
        parts.append(f'<text class="legend-label" x="{lx + 18}" y="{legend_y}">{_TOOL_LABEL[tool]}</text>')
        lx += 18 + 9 * len(_TOOL_LABEL[tool]) + 20
    parts.append(f'<text class="legend-label" x="{lx}" y="{legend_y}">* = unvalidated disagreement here</text>')
    parts.append(
        f'<text class="legend-label" x="{left_margin}" y="{legend_y + 14}">** = validated by human/LLM '
        + "inspection in lieu of another function-finding tool</text>"
    )
    parts.append(
        f'<text class="legend-label" x="{left_margin}" y="{legend_y + 28}">Args Found markers -- '
        + " &#183; ".join(f"{_ARGS_GRANULARITY_MARKER[k]} = {v}" for k, v in _ARGS_GRANULARITY_LEGEND.items())
        + "</text>"
    )

    for i, (_, _, _, title, _, _) in enumerate(panels):
        px = panels_x_start + i * (panel_w + panel_gap)
        parts.append(
            f'<text class="panel-title" x="{px + (bar_max_w + inner_gap + badge_col_w) / 2}" '
            f'y="{top_margin + header_h - 4}">{title}</text>'
        )

    for row_i, lang in enumerate(langs):
        y = rows_top + row_i * row_h
        data = data_by_lang[lang]
        if row_i % 2 == 0:
            parts.append(
                f'<rect class="stripe" x="{left_margin}" y="{y}" width="{width - left_margin - right_margin}" height="{row_h}"/>'
            )
        parts.append(f'<text class="lang-label" x="{left_margin + 4}" y="{y + row_h / 2 + 3.5}">{lang}</text>')

        if not data.has_data:
            parts.append(
                f'<text class="awaiting" x="{panels_x_start}" y="{y + row_h / 2 + 3.5}">{data.awaiting_note}</text>'
            )
            continue

        for panel_i, (attr, symbol_type, ledger_metric, _, ranked, found_field) in enumerate(panels):
            px = panels_x_start + panel_i * (panel_w + panel_gap)
            scores: dict[str, MetricScore] = getattr(data, attr)
            if not scores:
                continue  # class panel on a css/html row, or a metric with no comparable data
            bar_y = y + row_pad
            track_h = 3 * bar_h + 2 * sub_gap
            parts.append(
                f'<rect class="bar-track" x="{px}" y="{bar_y}" width="{bar_max_w}" height="{track_h}" rx="2"/>'
            )

            # Symmetric across all three tools now -- see EVERY TOOL'S BAR / WINNER BADGE module
            # docstring sections. Computed once per panel, not per tool: it's a property of the
            # (language, symbol_type, metric) cell, not of any one tool's reading within it.
            disputed = _disputed(lang, symbol_type, ledger_metric)

            # Found-count panels have no privileged denominator to scale against (see module
            # docstring) -- bar width is relative to this ROW's own highest found-count instead,
            # purely a visual "who claimed more" cue, never a percentage of anything.
            row_max_found = (
                max(
                    (
                        getattr(scores[t], found_field)
                        for t in data.available_tools
                        if t in scores and scores[t].rate_pct is not None
                    ),
                    default=0,
                )
                if not ranked
                else 0
            )
            for tool in data.available_tools:
                if tool not in scores or scores[tool].rate_pct is None:
                    # Args Found's own found_field (total_slots) is structurally always 0
                    # for a 1-tool language -- reconcile_symbols only increments args'
                    # total_slots when 2+ tools are comparable at a slot, unlike func/class
                    # Found's found_field (matched_consensus), which IS a real per-tool raw
                    # count regardless of tool count. That's why this panel alone needs its
                    # OWN staleness anchor (data.gg_args_found, a live raw sum independent of
                    # any cross-tool comparison) instead of reusing score.total_slots the way
                    # the ranked precision panels' override does below. The SAME structural-0
                    # shape also happens for a 2-tool language whose second tool just can't
                    # report args at all (cobol/assembly/agc_assembly: ctags has no signature
                    # field for these) -- ARGS_GRANULARITY's marker path below therefore checks
                    # `lang in ARGS_GRANULARITY` directly, not tool count, unlike the plain
                    # manual-verification fallback further down which really is gg-only-specific.
                    if attr == "args" and tool == "gitgalaxy":
                        color = _COLOR_TOOL[tool]
                        label = None
                        granularity = ARGS_GRANULARITY.get(lang)
                        if granularity == "none":
                            # No parameter-list concept exists at all -- the true count is 0 BY
                            # CONSTRUCTION, not an unverified claim, so no manual_verification.json
                            # entry is needed the way the generic mv path below requires.
                            label = f"{data.gg_args_found}{_ARGS_GRANULARITY_MARKER['none']}"
                        elif granularity in ("program_level", "proxy"):
                            # A verified proxy/program-level metric earns the SAME "**"-style
                            # verified/total upgrade the whole-language 1-tool path gets below,
                            # combined with (not replacing) its granularity marker -- "**" and
                            # a granularity superscript are deliberately distinct evidentiary
                            # claims (multi-source corroboration vs. a real-but-differently-
                            # measured signal) and both stay visible together once verified,
                            # never blurred into one marker.
                            mv = _manual_verification_entry(manual_verification, lang, "args")
                            if mv is not None and mv["total"] == data.gg_args_found and mv["verified"] == mv["total"]:
                                label = f"{mv['verified']}/{mv['total']}{_ARGS_GRANULARITY_MARKER[granularity]}"
                            else:
                                label = f"{data.gg_args_found}{_ARGS_GRANULARITY_MARKER[granularity]}"
                        elif len(data.available_tools) == 1:
                            mv = _manual_verification_entry(manual_verification, lang, "args")
                            if mv is not None and mv["total"] == data.gg_args_found:
                                label = f"{mv['verified']}/{mv['total']}**"
                        if label is not None:
                            if disputed:
                                label += "*"
                            parts.append(
                                f'<rect x="{px}" y="{bar_y}" width="{bar_max_w}" height="{bar_h}" rx="2" fill="{color}"/>'
                            )
                            parts.append(
                                f'<text class="bar-value-label" x="{px + bar_max_w / 2}" '
                                f'y="{bar_y + bar_h - 2}">{label}</text>'
                            )
                            bar_y += bar_h + sub_gap
                    continue
                score = scores[tool]
                color = _COLOR_TOOL[tool]
                if ranked:
                    w = max(2, bar_max_w * score.rate_pct / 100.0)
                    label = f"{score.matched_consensus}/{score.total_slots}"
                    # A manual-verification override only makes sense for a genuine 1-tool
                    # group -- GitGalaxy alone, nothing to corroborate against at all. A 2-3
                    # tool language's 0/N is a REAL precision problem worth seeing plainly;
                    # papering over that with a manual record would hide the exact signal this
                    # chart exists to surface. See MANUAL_VERIFICATION_PATH's own comment.
                    if len(data.available_tools) == 1:
                        mv = _manual_verification_entry(manual_verification, lang, symbol_type)
                        if mv is not None and mv["total"] == score.total_slots:
                            w = bar_max_w
                            label = f"{mv['verified']}/{mv['total']}**"
                else:
                    found = getattr(score, found_field)
                    w = max(2, bar_max_w * found / row_max_found) if row_max_found else 2
                    label = f"{found}"
                    if attr == "args" and lang in ARGS_GRANULARITY:
                        label += _ARGS_GRANULARITY_MARKER[ARGS_GRANULARITY[lang]]
                parts.append(f'<rect x="{px}" y="{bar_y}" width="{w:.1f}" height="{bar_h}" rx="2" fill="{color}"/>')
                if disputed:
                    label += "*"
                parts.append(
                    f'<text class="bar-value-label" x="{px + bar_max_w / 2}" y="{bar_y + bar_h - 2}">{label}</text>'
                )
                bar_y += bar_h + sub_gap

            # Args Found is unranked (see module docstring's PANELS section -- found-count
            # panels have no cross-tool "winner" concept, more-found isn't more-correct), so
            # it's included here ONLY for the manual-verification fallback path, never for a
            # real _winner() cross-tool comparison -- there's no such thing to compute for it.
            if (ranked or attr == "args") and not disputed:
                winner = _winner(scores, data.available_tools) if ranked else None
                if winner is None:
                    gg_score = scores.get("gitgalaxy")
                    mv_key = symbol_type if ranked else "args"
                    live_total = (
                        (gg_score.total_slots if gg_score is not None else None) if ranked else data.gg_args_found
                    )
                    winner = _manual_verification_winner(manual_verification, lang, mv_key, live_total, data.available_tools)
                if winner:
                    bx = px + bar_max_w + inner_gap + badge_col_w / 2
                    by = y + row_h / 2
                    parts.append(f'<circle cx="{bx}" cy="{by}" r="8" fill="{_COLOR_TOOL[winner]}"/>')
                    parts.append(f'<text class="badge-label" x="{bx}" y="{by + 3}">{_TOOL_BADGE_LETTER[winner]}</text>')

    summary_top = rows_top + n * row_h + 20
    parts.append(
        f'<line x1="{left_margin}" y1="{summary_top - 10}" x2="{width - right_margin}" y2="{summary_top - 10}" stroke="#dedcd6" stroke-width="1"/>'
    )
    parts.append(
        f'<text class="summary-title" x="{left_margin}" y="{summary_top + 4}">'
        f"Summary -- best tool per (language, metric), ranked panels only "
        f"(Func/Class Precision), {total_votes} real comparisons "
        f"(1-bar groups and empty panels don't count)</text>"
    )
    stat_y = summary_top + 26
    sx = left_margin
    for tool in ALL_TOOLS:
        count = tally.get(tool, 0)
        pct = 100.0 * count / total_votes if total_votes else 0.0
        parts.append(f'<circle cx="{sx + 7}" cy="{stat_y - 4}" r="7" fill="{_COLOR_TOOL[tool]}"/>')
        parts.append(f'<text class="badge-label" x="{sx + 7}" y="{stat_y - 1}">{_TOOL_BADGE_LETTER[tool]}</text>')
        stat_text = f"{_TOOL_LABEL[tool]} best: {count} ({pct:.0f}%)"
        parts.append(f'<text class="legend-label" x="{sx + 20}" y="{stat_y}">{stat_text}</text>')
        sx += 20 + 6.2 * len(stat_text) + 24
    tie_count = tally.get("tie", 0)
    tie_pct = 100.0 * tie_count / total_votes if total_votes else 0.0
    parts.append(f'<circle cx="{sx + 7}" cy="{stat_y - 4}" r="7" fill="#9a9a95"/>')
    parts.append(f'<text class="legend-label" x="{sx + 20}" y="{stat_y}">Ties: {tie_count} ({tie_pct:.0f}%)</text>')

    footer_y = summary_top + 46
    parts.append(
        f'<text class="scope-note" x="{left_margin}" y="{footer_y}">Ranked-panel labels are '
        f"matched/total; found-count panels are a single raw count, no denominator. "
        f"Regenerate: tri_comparison_chart.py --all --write</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts)


# ----------------------------------------------------------------------------
# --ci / --regenerate: baseline-gated regression check on GitGalaxy's own
# precision, same shape as tree_sitter_accuracy_audit.py's load_baseline/
# _regressions/run_ci_check, kept intentionally separate (not a shared helper)
# rather than retrofitting that file's internals -- it's large, heavily tested,
# and not otherwise part of this change.
#
# PRECISION ONLY, DELIBERATELY -- not recall/found-count. This module's own
# docstring (PANELS section) already explains why recall was dropped as a
# RANKED ratio on this chart: its denominator is a cross-tool union, which one
# tool's own bug can corrupt without GitGalaxy doing anything wrong (confirmed
# case: ctags and tree-sitter both independently double-tagged Haskell
# multi-clause functions before that was fixed). Precision's denominator is a
# tool's own claim count -- self-referential, not corruptible the same way --
# which is exactly why the chart still ranks/badges precision but not recall.
# Gating CI on recall would reintroduce the same untrusted-denominator problem
# the chart already designed around.
#
# Gated numbers are read AFTER run_pipeline() calls
# ledger_mod.apply_verified_adjustments() -- i.e. this is GitGalaxy's
# ledger-VALIDATED precision, never a raw unvalidated disagreement count, per
# CLAUDE.md's "Comparative-correctness claims require verification" rule.
# ----------------------------------------------------------------------------

_GATED_METRICS = ("func_precision", "class_precision")


def _get_baseline_path(lang: str) -> Path:
    return Path(__file__).resolve().parent.parent.parent / "tests" / f"tri_comparison_baseline_{lang}.json"


def _extract_precision(data: LanguageChartData) -> dict[str, float]:
    """GitGalaxy's own rate_pct for each ranked precision panel. A metric is omitted (not stored
    as null) when there's no GitGalaxy score or its rate is undefined (0 slots) -- an absent key
    means _regressions has nothing to compare for that language/metric on this run, same
    convention tree_sitter_accuracy_audit.py's baseline-key-presence check uses."""
    out: dict[str, float] = {}
    gg_func = data.func_precision.get("gitgalaxy")
    if gg_func is not None and gg_func.rate_pct is not None:
        out["func_precision"] = gg_func.rate_pct
    gg_class = data.class_precision.get("gitgalaxy")
    if gg_class is not None and gg_class.rate_pct is not None:
        out["class_precision"] = gg_class.rate_pct
    return out


def load_baseline(lang: str) -> dict:
    path = _get_baseline_path(lang)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _regressions(current: dict, baseline: dict) -> list[str]:
    regressions = []
    for key in _GATED_METRICS:
        if key not in baseline or key not in current:
            continue
        cur, base = current[key], baseline[key]
        if cur < base:
            regressions.append(f"{key}: {base:.2f}% -> {cur:.2f}% (validated precision got worse)")
    return regressions


def run_ci_check(lang: str, verbose: bool = True) -> int:
    data = run_pipeline([lang], verbose=verbose)[lang]
    if not data.has_data:
        print(f"tri_comparison_chart: {lang} -- no corpus data available, skipping.")
        return 0

    current = _extract_precision(data)
    baseline = load_baseline(lang)
    if not baseline:
        print(f"tri_comparison_chart: no baseline committed for {lang} -- run with --regenerate to create one, failing closed.")
        return 1

    regressions = _regressions(current, baseline)
    if regressions:
        print(f"tri_comparison_chart: {lang} -- {len(regressions)} regression(s) against the committed baseline:")
        for line in regressions:
            print(f"  {line}")
        return 1

    improved = [k for k in _GATED_METRICS if k in current and k in baseline and current[k] > baseline[k]]
    if improved:
        print(f"tri_comparison_chart: {lang} -- OK, improved on {', '.join(improved)} (consider --regenerate to lock it in).")
    else:
        print(f"tri_comparison_chart: {lang} -- OK, matches committed baseline, no regressions.")
    return 0


def run_regenerate(lang: str, verbose: bool = True) -> int:
    data = run_pipeline([lang], verbose=verbose)[lang]
    if not data.has_data:
        print(f"tri_comparison_chart: {lang} -- no corpus data available, cannot regenerate baseline.")
        return 1

    current = _extract_precision(data)
    if not current:
        print(f"tri_comparison_chart: {lang} -- no gated precision metric available (no GitGalaxy score), nothing to write.")
        return 1

    path = _get_baseline_path(lang)
    path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"tri_comparison_chart: wrote {path}")
    return 0


def _all_baseline_langs() -> list[str]:
    """Every language with a committed tests/tri_comparison_baseline_<lang>.json, sorted."""
    prefix = "tri_comparison_baseline_"
    root = Path(__file__).resolve().parent.parent.parent / "tests"
    return sorted(p.stem[len(prefix) :] for p in root.glob(f"{prefix}*.json"))


def run_all_baseline_mode(languages: list[str], mode_fn, verbose: bool = True) -> int:
    failed = []
    for lang in languages:
        print(f"\n=== {lang} ===")
        if mode_fn(lang, verbose=verbose) != 0:
            failed.append(lang)

    print(f"\ntri_comparison_chart --ci: {len(languages)} language(s) checked.")
    if failed:
        print(f"tri_comparison_chart --ci: {len(failed)} FAILED: {', '.join(failed)}")
        return 1
    print("tri_comparison_chart --ci: all OK.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--languages", help="Comma-separated language list.")
    group.add_argument("--all", action="store_true", help="Every language with a corpus available.")
    parser.add_argument("--write", action="store_true", help=f"Write SVG to {CHART_PATH}.")
    parser.add_argument("--quiet", action="store_true")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--ci",
        action="store_true",
        help="Baseline-gated regression check on GitGalaxy's own validated precision, instead of rendering the chart.",
    )
    mode_group.add_argument(
        "--regenerate",
        action="store_true",
        help="Accept current GitGalaxy precision as the new committed baseline, instead of rendering the chart.",
    )
    args = parser.parse_args()

    if args.ci or args.regenerate:
        # --all in baseline mode means "every language with a committed baseline" (glob-based),
        # not "every language with a corpus" (all_languages()) -- a language nobody has
        # baselined yet is skipped rather than failing the whole --all run closed. An explicit
        # --languages request for an un-baselined language still fails closed inside
        # run_ci_check itself, since that's a real ask for an answer that doesn't exist yet.
        languages = _all_baseline_langs() if args.all else [s.strip() for s in args.languages.split(",")]
        mode_fn = run_regenerate if args.regenerate else run_ci_check
        return run_all_baseline_mode(languages, mode_fn, verbose=not args.quiet)

    languages = all_languages() if args.all else [s.strip() for s in args.languages.split(",")]
    data = run_pipeline(languages, verbose=not args.quiet)
    svg = render_chart(data)

    if args.write:
        CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
        CHART_PATH.write_text(svg)
        print(f"tri_comparison_chart: wrote {CHART_PATH}")
    else:
        print(svg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
