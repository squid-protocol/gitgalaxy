#!/usr/bin/env python3
"""
tri_comparison_reconcile.py

Turns tri_comparison_gatherer.py's raw, per-tool readings into (a) an agreement-rate score per
tool per language per metric, and (b) a set of discrepancy records for anything the available
tools didn't unanimously agree on -- the raw material tri_comparison_ledger.py folds into the
persistent, human-investigated ledger.

WHY THERE IS NO "GROUND TRUTH" HERE
    tree_sitter_accuracy_audit.py treats tree-sitter's parse as ground truth and scores
    GitGalaxy against it. This module deliberately does not designate any of the three tools as
    ground truth -- multiple confirmed cases (documented in that same tool's own SCOPE &
    LIMITATIONS section, and now also directly in this corpus -- see bevy_ecs_table.rs::initialize
    below) show GitGalaxy can be right when tree-sitter's reading is wrong, and ctags can side
    with either one. What this module computes instead is each tool's AGREEMENT RATE against
    working consensus: for every symbol occurrence, if every tool available for that language
    agrees it exists (2-way when ctags doesn't cover the language, 3-way when it does), that's
    consensus; each tool that matched consensus gets credit. Where tools disagree, that specific
    occurrence contributes to a DISCREPANCY, not to any tool's score in either direction, until a
    human reads the source and the ledger records a verdict (see tri_comparison_ledger.py).

MATCHING METHODOLOGY (confirmed against real corpus data, not assumed)
    Primary match key is NAME. A probe across 153 matched-by-name Python functions in a real,
    332-decorator file (twisted/http.py) found the tree-sitter/ctags line-number offset was 0 in
    every single case -- when two tools agree a symbol is the same one, they already agree on its
    line without correction. A separate C++ probe showed the real failure mode where tools DO
    diverge is name-shape (qualified vs. bare `ClassName::method`), not a positional shift -- so
    a "detect and subtract a per-file offset" mechanism was considered and rejected; it would
    correct for a problem that essentially doesn't occur here, while doing nothing for the
    problem that does.
        A later all-language probe (2026-08-27) qualified the "offset is 0" claim: it holds for
        Python and most languages, but NOT universally, and the exceptions are naming-convention
        differences rather than the positional drift the rejected offset-correction mechanism
        would have fixed. Two systematic ones, both on name-AGREED occurrences: (1) ctags reports
        the line one PAST GitGalaxy/tree-sitter's agreed value in c/php/java/typescript (it
        anchors on the opening brace / first body token, not the declarator line); (2) GitGalaxy
        anchors at the attribute/decorator/signature line where tree-sitter starts at the keyword
        -- rust `#[proc_macro_derive]`-decorated `pub fn`, decorated TypeScript `constructor`,
        the Haskell type-signature line above the first equation. `line` is still not a match key
        and not a scored metric: these offsets don't change WHICH occurrence pairs with which
        (rank order within a name is identical), and "whose anchor convention is right" is not an
        existence disagreement worth a ledger entry. The takeaway is only that the original "0 in
        every single case" was a Python-specific measurement stated too broadly.
    Where one name occurs more than once in a file (property getter/setter pairs, method
    overloads, `build`/`constructor` across different classes), each tool's occurrences of that
    name are sorted by line, and then:
      - CLASSES, or any name whose occurrences don't all carry a line: paired by RANK (1st with
        1st, 2nd with 2nd), the same instinct tree_sitter_accuracy_audit.py's
        `_align_occurrences_by_line` already uses for two readers, generalized to however many of
        the three tools are available. GitGalaxy's own `class_data` rows carry no line number at
        all (a pre-existing schema fact), so class matching is name-multiset only -- which loses
        nothing, since classes carry no `args` value in any reader and only ever need an existence
        answer.
      - FUNCTIONS (every reader gives a real start line): paired by LINE PROXIMITY
        (`_pair_occurrences_by_line`). Rank pairing silently breaks when one tool misses an
        occurrence in the MIDDLE of a repeated name -- every pairing after the gap shifts by one,
        so tool A's reading of overload #2 gets compared against tool B's reading of overload #3,
        manufacturing a spurious args "disagreement" where each individual reading was correct for
        its own site (confirmed #2359: csharp `SetCurrentSolution`, javascript jquery
        `setup`/`trigger`). Line-proximity pairing single-linkage-clusters the occurrences in
        line order instead, so a genuinely-missed occurrence is left unpaired rather than
        shifting everything after it. The residual (occurrences that cluster alone) is still
        rank-paired, so the total slot count -- and therefore existence recall/precision -- is
        exactly what rank pairing gave; only which occurrence a discrepancy points at, and the
        args sub-comparison, change. A final belt-and-braces guard skips the args comparison for
        any slot whose paired occurrences span more than `_ARGS_LINE_SPREAD_MAX` lines (a
        residual rank-pair, or a real anchor offset too wide to trust as the same function).

EXISTENCE VS. ARGS ARE SEPARATE QUESTIONS, SCOPED SEPARATELY
    A function's EXISTENCE (does a symbol named X exist at roughly this position) and its ARG
    COUNT are reconciled independently, on purpose. Args are only ever compared for occurrences
    where existence already reached consensus across every available tool -- an args disagreement
    on an existence-agreed function affects ONLY that language's args metric, never its func
    recall/precision. Confirmed why this split matters empirically: an early, naive args
    comparison (before a signature-parsing bug fix -- see tri_comparison_gatherer.py's
    _count_ctags_signature_params docstring) showed Python at 91.3% args agreement; the same
    exact occurrences, once the parsing bug was fixed, moved to 99.9%. Existence agreement for
    that same language/run never moved at all (97.3% throughout) -- proof the two questions are
    genuinely independent, not just conceptually separable.
    Current picture (2026-08-27 all-language probe): GitGalaxy's args agreement is ~100% across
    the corpus; every language below 100% (haskell, perl, powershell, matlab, scala, swift) has a
    validated ledger verdict confirming GitGalaxy's count. The one arg-count divergence that
    reflects a real, useful difference rather than a corpus quirk is haskell -- GitGalaxy counts
    true logical arity from the type signature, tree-sitter counts only the patterns the aligned
    equation binds (undercounts eta-reduced/point-free clauses). Logged as Claim 14 in
    docs/why_gitgalaxy_beats_ast_here.md; ledger shape
    haskell/function/args/agree[none]_vs[gitgalaxy,tree_sitter].

DISCREPANCY SHAPE, NOT PER-INSTANCE LOGGING
    A language/metric pair can produce hundreds of individual disagreeing occurrences (rust
    existence: 152 cases where only GitGalaxy found the symbol; csharp existence: 271 cases where
    ctags+GitGalaxy agree and tree-sitter doesn't). Logging every one of those as its own ledger
    entry would be both unreadable and pointless to investigate one at a time -- the 271 csharp
    cases are very likely one systematic pattern (tree-sitter's C# grammar recall gap on real
    Roslyn code, already visible in the OLD bi-comparison's ts_func_recall=67% for csharp), not
    271 independent findings. This module groups raw disagreements by DISCREPANCY SHAPE --
    (language, symbol_type, metric, frozenset of which tools agreed) -- a mechanical grouping
    (no fuzzy pattern-mining, nothing that requires guessing), and emits one DiscrepancyGroup per
    shape with a capped sample of concrete (file, name, readings) examples, not an exhaustive
    enumeration. A human investigating "csharp/function/existence/{ctags,gg}-vs-{ts}-missing"
    reads the sample, not all 271.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Type-hint only (every annotation in this file is a lazy string thanks to the
    # `from __future__ import annotations` above). tri_comparison_gatherer.py hard-requires
    # tree-sitter-language-pack (an optional, verification-only download, not part of
    # GitGalaxy's zero-dependency shipped package) -- importing it eagerly here would mean
    # reconcile_symbols() couldn't even be IMPORTED, let alone run against already-gathered
    # data, without that optional package installed. Duck typing covers the runtime need: this
    # module only ever reads .name/.line/.args off objects a caller passes in.
    from tri_comparison_gatherer import FileReadings, Occurrence

ALL_TOOLS = ("gitgalaxy", "tree_sitter", "ctags")


@dataclass
class MetricScore:
    tool: str
    matched_consensus: int
    total_slots: int

    @property
    def rate_pct(self) -> float | None:
        if self.total_slots == 0:
            return None
        return 100.0 * self.matched_consensus / self.total_slots


@dataclass
class DiscrepancyExample:
    file_path: str
    name: str
    readings: dict[str, object]  # tool -> line (existence) or arg count (args), None if absent/differs


@dataclass
class DiscrepancyGroup:
    language: str
    symbol_type: str  # "function" | "class"
    metric: str  # "existence" | "args"
    agreeing_tools: frozenset[str]  # tools that agree WITH EACH OTHER in this shape
    dissenting_tools: frozenset[str]  # tools that disagree with the agreeing set
    total_occurrences: int
    examples: list[DiscrepancyExample] = field(default_factory=list)

    @property
    def shape_key(self) -> str:
        agree = ",".join(sorted(self.agreeing_tools)) or "none"
        dissent = ",".join(sorted(self.dissenting_tools)) or "none"
        return f"{self.language}/{self.symbol_type}/{self.metric}/agree[{agree}]_vs[{dissent}]"


_EXAMPLE_CAP = 10

# #2359 line-proximity function pairing. _CLUSTER_GAP_LINES: two of the SAME tool's occurrences
# of one name are always different functions, and two DIFFERENT tools' readings of the same
# function land within a handful of lines of each other (0 for most languages; a documented +1
# for ctags in c/php/java/typescript; a few more where GitGalaxy anchors at a decorator/attribute
# line and tree-sitter at the keyword -- see MATCHING METHODOLOGY above). 8 lines comfortably
# covers the real cross-tool offsets while staying below the typical gap between two adjacent
# same-name overloads. _ARGS_LINE_SPREAD_MAX: the post-pairing guard -- only compare args when the
# paired occurrences are confidently the same function; a wider spread means a residual rank-pair
# or an anchor offset too large to trust, so existence is still counted but args is skipped
# (a guessed args comparison is worse than none). Kept equal to the cluster gap on purpose.
_CLUSTER_GAP_LINES = 8
_ARGS_LINE_SPREAD_MAX = 8

# Local-label leading-dot convention: NASM/GAS scope a local label to the preceding global
# label by writing it with a leading '.' (`.loop:`, `.empty:`). Universal Ctags' Asm parser
# strips that '.' before emitting the tag (`loop`, `empty`); GitGalaxy's func_start captures
# it verbatim -- so the SAME real label at the SAME line lands in two different name buckets
# and reads as a spurious cross-tool disagreement (confirmed: bootos/os.asm's `.loop`/`.empty`/
# `.find`/`.load_vec`, ledger shapes assembly/function/existence/agree[gitgalaxy]_vs[ctags] and
# its mirror). Only these two languages use the convention; every other language pairs on the
# verbatim name, same "checked for this language, not applied blindly" discipline as
# tri_comparison_gatherer.py's javascript-only normalization.
_LEADING_DOT_LOCAL_LABEL_LANGS = frozenset({"assembly", "agc_assembly"})


def _pairing_name(name: str, language: str) -> str:
    """The name an occurrence is bucketed under for cross-tool pairing. Verbatim in the normal
    case; for assembly dialects a single leading '.' on a local label is dropped so GitGalaxy's
    `.loop` pairs with ctags' `loop` (same label, same line). A `..`-prefixed name is left
    alone (not a real local-label form)."""
    if language in _LEADING_DOT_LOCAL_LABEL_LANGS and len(name) > 1 and name[0] == "." and name[1] != ".":
        return name[1:]
    return name


def _pair_occurrences_by_rank(
    occs_by_tool: dict[str, list[Occurrence]],
) -> list[dict[str, Occurrence | None]]:
    """One name's occurrences from each available tool, already sorted by line by the caller.
    Returns one dict per rank slot, tool -> Occurrence or None if that tool had fewer occurrences
    of this name than the rank being filled."""
    max_n = max((len(v) for v in occs_by_tool.values()), default=0)
    slots = []
    for i in range(max_n):
        slots.append({tool: (occs[i] if i < len(occs) else None) for tool, occs in occs_by_tool.items()})
    return slots


def _name_wants_line_pairing(occs_by_tool: dict[str, list[Occurrence]], symbol_type: str) -> bool:
    """True only when line-proximity pairing can differ from rank pairing AND has the data to run:
    functions (classes have no gg line), some tool saw the name 2+ times (with <=1 each, the two
    strategies produce the identical single slot), and every occurrence carries a real line."""
    if symbol_type != "function":
        return False
    if max((len(v) for v in occs_by_tool.values()), default=0) < 2:
        return False
    return all(o.line is not None for occs in occs_by_tool.values() for o in occs)


def _pair_occurrences_by_line(
    occs_by_tool: dict[str, list[Occurrence]],
) -> list[dict[str, Occurrence | None]]:
    """One function name's occurrences across tools, each list already line-sorted, every
    occurrence carrying a real line (see `_name_wants_line_pairing`). Single-linkage-clusters
    them in global line order -- a new cluster starts when the line gap exceeds
    `_CLUSTER_GAP_LINES` or the current tool already occupies the open cluster (two of one tool's
    occurrences of a name ARE two different functions). Clusters holding 2+ tools are confident
    same-function slots; a tool alone in its cluster is "loose" and rank-paired against the other
    tools' equally-loose occurrences, so the total slot count matches plain rank pairing and
    existence recall/precision are unchanged -- see reconcile_symbols' caller comment and #2359.
    """
    flat = sorted(
        (o.line, tool, o) for tool, occs in occs_by_tool.items() for o in occs
    )  # (line, tool, occ), ascending by line
    clusters: list[dict[str, Occurrence]] = []
    cur: dict[str, Occurrence] = {}
    cur_last_line = 0
    for line, tool, occ in flat:
        if cur and (tool in cur or line - cur_last_line > _CLUSTER_GAP_LINES):
            clusters.append(cur)
            cur = {}
        cur[tool] = occ
        cur_last_line = line
    if cur:
        clusters.append(cur)

    slots: list[dict[str, Occurrence | None]] = []
    loose: dict[str, list[Occurrence]] = {t: [] for t in occs_by_tool}
    for c in clusters:
        if len(c) >= 2:
            slots.append({t: c.get(t) for t in occs_by_tool})
        else:
            (only_tool,) = c
            loose[only_tool].append(c[only_tool])
    slots.extend(_pair_occurrences_by_rank(loose))
    slots.sort(key=lambda s: min((o.line for o in s.values() if o is not None), default=0))
    return slots


def reconcile_symbols(
    results: list[FileReadings],
    symbol_type: str,
    available_tools: tuple[str, ...],
    language: str = "",
) -> tuple[dict[str, MetricScore], dict[str, MetricScore], dict[str, MetricScore], list[DiscrepancyGroup]]:
    """symbol_type: "function" or "class". language: the language these readings are for, used
    only for the assembly leading-dot local-label normalization (see `_pairing_name`); the
    caller knows it, this module otherwise doesn't. available_tools: whichever of ALL_TOOLS actually have
    a reading for this language -- both tree-sitter (absent for 9 of GitGalaxy's 45 languages,
    ctags-only there) and ctags (absent for 6 of the 30 tree-sitter-baselined languages) are
    independently optional per language; GitGalaxy is the only one always present.

    Returns (recall_scores, precision_scores, args_scores, discrepancy_groups). args_scores is
    only ever non-empty for symbol_type == "function" -- classes carry no args value in any
    reader. recall_scores and precision_scores are two different views of the exact same
    underlying per-slot agreement data (there's no separate "precision ground truth" to measure
    against -- see this module's own docstring for why no reader is privileged), which is also
    why both draw on the SAME "existence" discrepancy groups below rather than needing a second,
    separate discrepancy dimension:
      - recall_t = (slots tool t reported) / (every slot ANY available tool reported -- the
        union). Was this function's only "existence_scores" before recall/precision were split
        apart; unchanged in meaning, just renamed.
      - precision_t = (slots tool t reported that at least one OTHER available tool also
        reported) / (slots tool t reported, period). A tool that reports something nobody else
        agrees with pays for it here, not in recall -- confirmed meaningful on real data: rust's
        152 GitGalaxy-only occurrences (tree-sitter and ctags both independently miss them) leave
        GitGalaxy's recall at 100% (it's the superset) but its precision below 100% (some of what
        it alone reports is uncorroborated), while tree-sitter/ctags sit at ~92% recall but
        ~100% precision there -- a real, classic recall/precision tradeoff, not a coincidence of
        this specific formula.
    """
    recall_scores = {t: MetricScore(t, 0, 0) for t in available_tools}
    precision_scores = {t: MetricScore(t, 0, 0) for t in available_tools}
    args_scores = {t: MetricScore(t, 0, 0) for t in available_tools}
    existence_groups: dict[frozenset, DiscrepancyGroup] = {}
    args_groups: dict[frozenset, DiscrepancyGroup] = {}

    for r in results:
        if symbol_type == "function":
            per_tool_occs = {"gitgalaxy": r.gg_funcs, "tree_sitter": r.ts_funcs, "ctags": r.ctags_funcs}
        else:
            per_tool_occs = {"gitgalaxy": r.gg_classes, "tree_sitter": r.ts_classes, "ctags": r.ctags_classes}
        per_tool_occs = {t: per_tool_occs[t] for t in available_tools}

        by_name: dict[str, dict[str, list[Occurrence]]] = defaultdict(lambda: {t: [] for t in available_tools})
        for tool, occs in per_tool_occs.items():
            for o in occs:
                by_name[_pairing_name(o.name, language)][tool].append(o)

        for name, occs_by_tool in by_name.items():
            for tool in occs_by_tool:
                occs_by_tool[tool].sort(key=lambda o: o.line if o.line is not None else -1)

            pair_fn = (
                _pair_occurrences_by_line
                if _name_wants_line_pairing(occs_by_tool, symbol_type)
                else _pair_occurrences_by_rank
            )
            for slot in pair_fn(occs_by_tool):
                present = frozenset(t for t, o in slot.items() if o is not None)
                absent = frozenset(available_tools) - present

                # Recall: each tool's own rate against the UNION of every occurrence-slot any
                # available tool reported -- every slot counts once in every tool's denominator,
                # and a tool's numerator moves only for slots IT reported, whether or not the
                # other tools agreed. This is a real, honest number regardless of validation
                # status: "no credit for anyone until a human signs off" would silently deflate
                # every tool's rate on disputed slots and conflate two different questions (what
                # did each tool find vs. do we trust the disputed cases yet). Validation status
                # drives the ledger and the chart's asterisk decision separately, below and in
                # tri_comparison_ledger.py -- never the score itself.
                for t in available_tools:
                    recall_scores[t].total_slots += 1
                    if t in present:
                        recall_scores[t].matched_consensus += 1

                # Precision: scoped to what EACH tool itself reported, not the shared union --
                # a tool that's absent from this slot doesn't have its precision denominator
                # touched by it at all (precision is "of what you claimed, how much held up",
                # not "how much of everything did you claim"). len(present) >= 2 means at least
                # one OTHER available tool corroborates this specific slot.
                for t in present:
                    precision_scores[t].total_slots += 1
                    if len(present) >= 2:
                        precision_scores[t].matched_consensus += 1

                if present != frozenset(available_tools):
                    key = frozenset([("agree", present), ("dissent", absent)])
                    grp = existence_groups.setdefault(
                        key,
                        DiscrepancyGroup(
                            language="",
                            symbol_type=symbol_type,
                            metric="existence",
                            agreeing_tools=present,
                            dissenting_tools=absent,
                            total_occurrences=0,
                        ),
                    )
                    grp.total_occurrences += 1
                    if len(grp.examples) < _EXAMPLE_CAP:
                        grp.examples.append(
                            DiscrepancyExample(
                                file_path=r.file_path,
                                name=name,
                                readings={t: (slot[t].line if slot[t] else None) for t in available_tools},
                            )
                        )
                    continue  # no args comparison possible without existence consensus

                # existence consensus reached for this slot -- compare args (functions only;
                # classes never carry an args value in any reader)
                if symbol_type != "function":
                    continue
                # #2359 belt-and-braces: only compare args when the paired occurrences are
                # confidently the same function. Line-proximity pairing already avoids the gross
                # mis-shifts, but a residual rank-paired slot (or an anchor offset wider than
                # `_CLUSTER_GAP_LINES`) can still line up two different definitions of a repeated
                # name. A wide line spread across the present tools is the tell -- skip args
                # there (existence already counted above; a guessed args comparison is worse
                # than none). Slots with <2 lined occurrences fall through unchanged.
                slot_lines = [slot[t].line for t in present if slot[t].line is not None]
                if len(slot_lines) >= 2 and max(slot_lines) - min(slot_lines) > _ARGS_LINE_SPREAD_MAX:
                    continue
                args_vals = {t: slot[t].args for t in present}
                # None means "this tool structurally can't report args here" (e.g. ctags on
                # shell) -- exclude from the agreement question entirely rather than treating
                # None as a value that could match or mismatch another tool's real count.
                comparable = {t: v for t, v in args_vals.items() if v is not None}
                if len(comparable) < 2:
                    continue
                for t in comparable:
                    args_scores[t].total_slots += 1
                if len(set(comparable.values())) == 1:
                    for t in comparable:
                        args_scores[t].matched_consensus += 1
                else:
                    # BUG FIXED: this branch used to award matched_consensus to nobody at all --
                    # the exact same "no credit until everyone agrees" mistake already caught and
                    # fixed for recall/precision above, just never applied here too. A 2-vs-1
                    # split has two tools that genuinely agree with EACH OTHER; denying them
                    # credit because a third tool differs was silently deflating every language's
                    # args score below what the data actually supports (confirmed: no language
                    # could reach 100% even when only a small minority of occurrences had any
                    # disagreement at all, since majority-agreeing tools were being penalized for
                    # a minority outlier they had nothing to do with).
                    agree_val_counts = defaultdict(list)
                    for t, v in comparable.items():
                        agree_val_counts[v].append(t)
                    ranked = sorted(agree_val_counts.items(), key=lambda kv: -len(kv[1]))
                    top_tools = ranked[0][1]
                    second_size = len(ranked[1][1]) if len(ranked) > 1 else 0
                    if len(top_tools) > second_size:
                        # A REAL majority (strictly larger than the next-biggest group) -- e.g.
                        # 2 tools agree, 1 differs. Only the tied case (2 comparable tools that
                        # simply disagree, or a genuine 3-way split with no group larger than
                        # any other) has no real majority; nobody gets credit there, correctly,
                        # since there's no sense in which any side "won" a tie.
                        majority_tools = frozenset(top_tools)
                        for t in majority_tools:
                            args_scores[t].matched_consensus += 1
                    else:
                        majority_tools = frozenset()
                    minority_tools = frozenset(comparable) - majority_tools
                    key = frozenset([("agree", majority_tools), ("dissent", minority_tools)])
                    grp = args_groups.setdefault(
                        key,
                        DiscrepancyGroup(
                            language="",
                            symbol_type=symbol_type,
                            metric="args",
                            agreeing_tools=majority_tools,
                            dissenting_tools=minority_tools,
                            total_occurrences=0,
                        ),
                    )
                    grp.total_occurrences += 1
                    if len(grp.examples) < _EXAMPLE_CAP:
                        grp.examples.append(
                            DiscrepancyExample(file_path=r.file_path, name=name, readings=dict(args_vals))
                        )

    all_groups = list(existence_groups.values()) + list(args_groups.values())
    return recall_scores, precision_scores, args_scores, all_groups
