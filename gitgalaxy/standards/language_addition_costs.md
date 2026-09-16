# Language-addition cost ledger — notes

Companion to `language_addition_costs.jsonl` (the machine-readable, graphable rows).
The JSONL is the data; this file is the *why*. Append a row with
`tests/tools/record_language_cost.py` (see `how_to_add_a_language.md` Step 6), then add a
"why" bullet here if the number is surprising.

## The value: a predictable cost envelope

The point of this ledger is **not** to watch cost fall over time — it's that the cost of adding
a language is a **known, forecastable quantity**. That is the real perk: you can quote a price
and a duration for a new language *before* starting, and add essentially any language into the
system on a budget.

The three combined Claude Code additions so far land in a tight band:

    ~$135 – $210   and   ~75 – 112 min   per language (engine + corpus, one runner)

Flat is the win here, not decreasing. And the spread inside the band isn't noise — every dollar
of it traces to a driver you can read off in advance, so you can predict *where in the band* a
given language falls:

- **Reuses an existing lexical family, no surprises** → low end (~$135, ~75 min — hlasm).
- **Pioneers a new family, or a real engine bug surfaces mid-add** → high end (~$210 — db2_sql).
- **Runs partly on Opus instead of all-Fable** → shaves cost (~2× lever — bms).

So the forecast is: pick the target's nearest family template, check whether it's the family's
anchor or a sibling, decide the model split — and you have a cost estimate before the first line
of code. `record_language_cost.py --report` prints the measured envelope to anchor that estimate.

(Different runner = different basis: an `agy`/Gemini build is priced on its own scale, not this
one. Forecast within a runner.)

## How to read the numbers (don't get fooled)

- **`est_cost_usd` and `output_tokens` are the honest comparators.** `total_tokens` on a
  Claude Code run is dominated by prompt-cache **reads** (100M+) — it is not "effort" and is
  not comparable to a context-gauge reading (~150k) you watched during the session.
- **Cost is ≈ cache-read volume × model price.** Cache reads are cheap per token (0.1× input)
  but there are ~100M+ of them, so they dominate the bill. Two levers move `est_cost_usd`:
  how long/looping the session was (more re-reads of the growing context) and which model ran
  it. **Fable 5 is 2× Opus 4.8** ($10/$50 vs $5/$25 per 1M) — a row that ran partly on Opus is
  cheaper per token than an all-Fable row.
- **`runner` gates comparability.** Claude Code totals are cache-read-inflated; an `agy`/Gemini
  run is not. Never compare token totals across runners — group by `runner` first.
- **`phase` matters.** A `corpus`-only or `engine`-only row is half an addition; only compare
  `combined` rows to each other.

## Timeline: the add-language skill vs when each language was added

All times UTC. The skill did not exist for most of these additions.

| Artifact | Created (UTC) | Note |
|---|---|---|
| `how_to_add_a_language.md` | 2026-04-19 | The source-of-truth doc — long predates the skill. |
| `add-language` SKILL.md | **2026-09-16 15:40** | #3093/#3094 — registration audit + decision tables, distilled from the bms/db2 landings. |
| SKILL.md refined | 2026-09-16 17:01 | #3098 — folded the hlasm (#2503) landing's lessons back in. |

Cross-referenced against each addition's `started_at`:

| Lang | Started (UTC) | Skill era |
|---|---|---|
| pli engine (#3057, Gemini) | 2026-09-15 ~03:2x | **pre-skill** (and pre-doc-era-irrelevant; different runner) |
| bms #2505 | 2026-09-16 01:09 | **pre-skill** (doc only) |
| pli corpus (#135) | 2026-09-16 10:13 | **pre-skill** |
| db2_sql #2511 | 2026-09-16 12:22 | **pre-skill** |
| hlasm #2503 | 2026-09-16 15:42 | **first WITH the skill** (started ~2 min after it merged) |

The story the dates tell: bms and db2 were done doc-only, and the friction they hit (the
registration surfaces #2511 paid two CI round-trips for, the decision-table questions) is
exactly what got distilled *into* the skill at 15:40. hlasm was then the first addition to run
on the skill — and it was the fastest of the three combined additions (see below). The skill's
job here is not to drive cost down forever but to **de-risk the high end** — the registration
audit and decision tables remove the surprises (mis-wired surfaces, re-litigated ownership
calls) that push an addition toward the top of the band. A tighter band is the win, not a
falling line. Watch the *spread* as more languages land, not the trend.

## Per-language: why more or less

- **hlasm #2503 — 75 min, 600k out, $175 (all Fable 5).** Cheapest *time* of the three combined
  additions despite mid-tokens. Two reasons: it reused **bms as a near-exact template** (bms IS
  HLASM macro source — same positional/comment family, comment gate already widened), and it was
  the first to run **with the skill**. Its cost is still high in dollars because it ran entirely
  on Fable 5 (2× Opus) and did a full golden-crucible pass (131M cache-read).

- **bms #2505 — 112 min, 470k out, $136 (Fable 5 + some Opus 4.8).** Longest wall-clock but
  **lowest cost of the combined rows.** It was the *first in the assembler/positional family* —
  built from `assembly.py` with no close sibling, and it had to author the positional-comment
  gate that hlasm later inherited — so it took the most exploration time. Cost stayed lowest
  because part of the work ran on Opus 4.8 (half Fable's price) and it read less context overall
  (113M cache-read, the lowest of the combined rows).

- **db2_sql #2511 — 107 min, 725k out, $210 (all Fable 5). Most expensive.** Three multipliers
  stacked: a **novel family** (SQL-dialect, the Mode E "one-statement-one-hit" shape had no
  template), a **real investigation spike** — the rosetta `--report` caught a census contract
  violation the whole engine suite couldn't see, and chasing it burned tokens — and it ran
  **entirely on Fable 5**. It has both the most generated tokens (725k) and the most cache-read
  (154M), and 154M × Fable rate is what put it at the top.

- **pli — two rows, two runners, two days.** pl-i is the one language whose halves were done at
  clearly separate times, and the merged PRs confirm both:
  - **Engine — gitgalaxy PR #3057** (issues #2502/#1142), merged 2026-09-15 09:20 UTC, **+1661
    /−5 across 12 files** (CICS/SQL/DLI parity with cobol), committed 03:25–03:41 UTC. No Claude
    session was building pl-i in that window (only the v2.7.0 speed-profiling session was live),
    which confirms this was an **`agy`/Gemini fleet build — no Claude transcript**. Recorded as a
    `runner: agy-gemini`, `phase: engine` row with tokens/cost **unmeasured** (PR size is the only
    bound we have). This is the bulk of the pl-i work and it is *not* in any dollar figure.
  - **Corpus — keyword-rosetta PR #135**, merged 2026-09-16 10:41 UTC, +245/6 files. This is the
    Claude Code row: 26 min, 325k out, $49. It maps exactly onto its session (started 10:13 UTC,
    PR opened 21 min in).

  So the `combined` pl-i cost is "$49 corpus + an unmeasured Gemini engine build of ~1661 LOC."
  Don't compare either pl-i row to the combined bms/db2/hlasm rows.

## The pattern, in one line

The cost of adding a language is bounded and predictable: a same-family sibling on Opus lands at
the bottom of the band, a new-family pioneer that hits a real bug on all-Fable at the top — and
you can tell which before you start. Template proximity buys *time*; model choice and cache-read
volume buy *dollars*. The story isn't "cost is falling," it's "cost is a number I can quote for
any language up front."
