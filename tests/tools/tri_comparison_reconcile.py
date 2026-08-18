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
    Where one name occurs more than once in a file (property getter/setter pairs, same method
    name on different classes), each tool's occurrences of that name are sorted by line and
    paired by RANK (1st with 1st, 2nd with 2nd), the same instinct tree_sitter_accuracy_audit.py's
    `_align_occurrences_by_line` already uses for two readers, generalized to however many of the
    three tools are available for this language. GitGalaxy's own `class_data` rows carry no line
    number at all (a pre-existing schema fact, not introduced here) -- class matching against
    GitGalaxy is therefore by name multiset only, never rank-paired by position. This doesn't
    lose anything class-specific to compare positionally anyway: classes carry no `args` value in
    any of the three readers, so class matching only ever needs to answer an existence question.

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


def reconcile_symbols(
    results: list[FileReadings],
    symbol_type: str,
    available_tools: tuple[str, ...],
) -> tuple[dict[str, MetricScore], dict[str, MetricScore], list[DiscrepancyGroup]]:
    """symbol_type: "function" or "class". available_tools: whichever of ALL_TOOLS actually have
    a reading for this language -- both tree-sitter (absent for 9 of GitGalaxy's 45 languages,
    ctags-only there) and ctags (absent for 7 of the 31 tree-sitter-baselined languages) are
    independently optional per language; GitGalaxy is the only one always present.
    Returns (existence_scores, args_scores, discrepancy_groups). args_scores is only ever
    non-empty for symbol_type == "function" -- classes carry no args value in any reader."""
    existence_scores = {t: MetricScore(t, 0, 0) for t in available_tools}
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
                by_name[o.name][tool].append(o)

        for name, occs_by_tool in by_name.items():
            for tool in occs_by_tool:
                occs_by_tool[tool].sort(key=lambda o: o.line if o.line is not None else -1)

            for slot in _pair_occurrences_by_rank(occs_by_tool):
                present = frozenset(t for t, o in slot.items() if o is not None)
                absent = frozenset(available_tools) - present

                # Score is each tool's own recall against the UNION of every occurrence-slot any
                # available tool reported -- every slot counts once in every tool's denominator,
                # and a tool's numerator moves only for slots IT reported, whether or not the
                # other tools agreed. This is a real, honest number regardless of validation
                # status: "no credit for anyone until a human signs off" would silently deflate
                # every tool's rate on disputed slots and conflate two different questions (what
                # did each tool find vs. do we trust the disputed cases yet). Validation status
                # drives the ledger and the chart's gray/colored decision separately, below and
                # in tri_comparison_ledger.py -- never the score itself.
                for t in available_tools:
                    existence_scores[t].total_slots += 1
                    if t in present:
                        existence_scores[t].matched_consensus += 1

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
                    agree_val_counts = defaultdict(list)
                    for t, v in comparable.items():
                        agree_val_counts[v].append(t)
                    majority_val, majority_tools = max(agree_val_counts.items(), key=lambda kv: len(kv[1]))
                    majority_tools = frozenset(majority_tools)
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
    return existence_scores, args_scores, all_groups
