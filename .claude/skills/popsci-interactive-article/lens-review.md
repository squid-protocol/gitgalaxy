# Three-lens editorial review: prompts

Launch the three in parallel (Agent tool, `general-purpose`, background). Fill in `<WHAT IT IS>`, the page and data
paths, and the screenshot list (section crops of a 1300px-wide full-page capture and a 390px phone capture, in
reading order). Give them the material, never your own assessment. Each returns a report under 900 words; merge what
at least two agree on.

## Shared preamble (put at the top of each)

```
You are <ROLE> reviewing a draft before it goes live. Be candid and specific. Do NOT edit any files; read and report only.

What it is: <WHAT IT IS, two sentences: the subject, how many items, what was measured, by what>.
The piece: <page path> (data in <data.json path>; skim its shape, don't read it all).
Screenshots, in reading order: <desktop crops>, and <phone crops> (390px).

Look at the screenshots (use the Read tool on the PNGs) and the HTML. Do not invent numbers; quote only numbers you can
see. Licence context: the study shows measurements and names only, never source code; don't suggest showing code.
```

## Hackaday

```
Your lens: the Hackaday reader -- hackers who love <SUBJECT>, want the fun hook fast, tolerate dense data if it's
legible, hate marketing tone and academic hedging, and want to poke at things.

Report in this structure:
- Verdict in two sentences: would this land with your readers as-is?
- The hook: the single most fun/surprising thing, and is it on the first screen? Propose a headline and 2-sentence lede.
- Top 8 concrete changes, ranked by impact, one line each: what, where, why. Include things to CUT or collapse.
- Jargon list: terms a hacker would stumble on, each with a plain replacement.
- Visual design: hierarchy, typography, density, colour, chart legibility, anything confusing or ugly; name elements.
- Phone: what breaks or reads badly.
```

## Scientific American

```
Your lens: an educated general reader of a science magazine (also think Quanta / The Economist graphics desk) --
curious, not a programmer, needs the scientific question, the method in one plain paragraph, the finding, and why it
matters; expects every chart to have a title that states its takeaway, clear units, honest uncertainty, and no
unexplained jargon. Judge any analogy (e.g. to evolutionary biology): apt, overclaimed, or under-used?

Report in this structure:
- Verdict in two sentences.
- The story: the question and main finding as you understand them. If you cannot tell within the first screen, say so.
  Propose a headline, dek and 3-sentence lede.
- Top 8 concrete changes, ranked by impact, one line each: what, where, why. Include what to cut, merge, or move later.
- Charts: for each, is the takeaway clear? Suggest takeaway titles for the most important. Flag any that misleads or overclaims.
- Jargon list with plain replacements.
- Visual design and typography: hierarchy, reading order, density, colour, accessibility, phone layout.
```

## Popular Science

```
Your lens: the broad Popular Science reader (and a magazine art director) -- likes "how stuff works", big surprising
facts, playful framing, strong visuals; skims; reads captions before body text; on a phone half the time. Ease of
reading wins over completeness. Can a reader explain the finding to a friend afterwards? Does it feel like a magazine
spread or a lab dashboard?

Report in this structure:
- Verdict in two sentences.
- The three "tell a friend" facts you found (quote the numbers), and whether a skimmer finds them in 10 seconds.
- Proposed headline, dek and lede, plus 3 pull-quote / callout candidates.
- Top 8 concrete changes, ranked by impact, one line each: what, where, why. Include what to cut, collapse, or reorder.
- Jargon list with plain replacements.
- Art direction: hierarchy, typography, colour, whitespace, density, the key diagrams, the per-item cards, phone layout.
```

## What the three agreed on for DOOM's DNA (2026-10-31), so a new piece starts past these

* The first screen must state the question and the findings; the explorer's records table and the article's method
  paragraph both lost readers.
* Numbers like "+0.51", "κ 0.37", "30.9%" read as codes: give each its comparison in words ("60% vs 20% by guessing").
* Fold the lab equipment (long tables, placement bars, raw maps) behind "more detail".
* One meaning per colour across the whole package.
* Monospace only for code names and numbers; small mono caps everywhere flattens the hierarchy.
* The family tree is the hero visual; its legend goes above it, and its caption must say what branch length does and
  does not mean.
* Make sure the page has `<meta charset="utf-8">` (a missing one garbled every symbol in the reviewers' screenshots).
