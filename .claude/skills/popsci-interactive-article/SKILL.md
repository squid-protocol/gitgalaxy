---
name: popsci-interactive-article
description: >-
  Write and build a long-form, Popular Science-voice interactive data article: a magazine story with the data
  tools built in (a data-driven hero image, "play with it" sections, an evolutionary tree, side-by-side maps, a
  per-item explorer), honest controls next to every number, a "Check my work" ending, and both an interactive and a
  text edition. Covers the voice, the section template, the interactive patterns, the visual system, the honesty
  checks, a three-lens editorial review, and publishing to a claude.ai artifact and the GitGalaxy docs wiki. Use when
  the owner asks to "write it up like Popular Science / the DOOM article", "make an article out of this study",
  "make it more digestible", "publish this research", or wants a study turned into an interactive story. The
  reference implementation is "DOOM's DNA" (2026-10-31).
---

# Popular Science interactive article

The owner's chosen style for publishing GitGalaxy research (2026-10-31, "DOOM's DNA"): **one long article a curious
non-programmer can read top to bottom, with the data tools embedded where the story needs them, and every claim
checkable.** Popular Science voice, Scientific American honesty, Hackaday playfulness.

Not for release notes or engine docs: those keep the dry, evidence-first tone (`release-notes` skill,
`docs/how_to_write_release_notes.md`). This skill is for public write-ups of research.

Reference implementation (read it before starting a new one; copy its structure, not its words). The study work dir
lives on the owner's box (nyx), outside any repo; the published copies are in this repo's docs wiki:

| What | Where |
|---|---|
| Article body (text + section markup) | `~/gitgalaxy/doom-study/article/body.html` |
| Builder (merges explorer code + charts + new interactives; `--wiki DIR` writes the public edition) | `~/gitgalaxy/doom-study/article/build_article.py` |
| Interactive components (data loading, phylogram, call-graph maps, per-item cards, drift charts) | `~/gitgalaxy/doom-study/explorer/index.html` |
| Data builder (one `data.json`: identity from GitHub, sizes, fates, family edges, drift) | `~/gitgalaxy/doom-study/explorer/build_facts.py` |
| Live article (claude.ai artifact) | https://claude.ai/artifact/FQuzmAcWGWTW5fqoc6LvXa |
| Public edition + text edition (docs wiki) | `docs/wiki/museum-of-code/doom-dna/` and `museum-of-code/teardown-of-doom.md` (gitgalaxy PR #7339) |

## 1. The voice

* **Lead with a surprise, not a method.** First screen: headline, dek, a one-paragraph hook that states the
  question in plain words, then three big facts. Methods go last, in a box.
* **Headline + subhead + dek.** Short noun-phrase headline with a metaphor ("DOOM's DNA"), a plain subhead ("How code
  keeps its family resemblance"), a two-sentence dek that names the subject and the payoff.
* **Lede pattern:** a concrete image the reader can picture ("Strip a program of every name, every comment...
  That shape, it turns out, works like a fingerprint."), then one paragraph of setup (who, what, how many).
* **Section heads are claims or hooks:** "Names lie", "A fingerprint you can't read", "The blind test", "Translations
  that kept the blueprint". Never "Results" or "Section 3".
* **Every number has a comparison next to it:** 60% *vs 20% by guessing*; 31% *vs 0 to 0.6% for unrelated programs*.
  A number without its control is not shown.
* **Big facts as three tiles:** the number in display type, one sentence under it that says what it means.
* **Pull quotes:** one per major section, the most quotable sentence, restating a number.
* **Plain words.** Replace jargon on sight (keep the technical term only in the methods box):

  | Jargon | Write |
  |---|---|
  | structural twin | look-alike function |
  | call graph / cross-subsystem wiring | map of which parts call which / wiring |
  | subsystem | part of the program (renderer, monsters, sound) |
  | κ / Cohen's kappa | points above guessing ("+40 pts") |
  | cosine similarity | match from 0 (nothing in common) to 1 (identical) |
  | Spearman ρ | rank correlation, "the two methods agree closely" |
  | complexity | decision points |
  | divergence | how far it drifted / less code in common |
  | port | descendant (first use: explain the term) |
  | engine hash, tool names (lineage.py, ctags) | methods box or footer only |

* **Honesty lines in the text, not only in captions.** Say where a result comes from when it switches source ("First,
  the old-fashioned way: we compared the source text... Then we throw the text away."). Say what a metaphor does not
  mean ("a biologist infers who descends from whom; here the links are what each project says; only the branch lengths
  are measured").
* **Name the limits:** a short "What it can't tell you" section (three bullets) before the methods.
* **Methods box "How we know it's not luck":** against the text (ground truth), against chance (shuffled controls),
  against outsiders (unrelated programs), against other tools, one engine version.
* **Byline at the top, credit and "Check my work" at the end:** "Written by Joe Esquibel, using the GitGalaxy
  code-scanning engine", the repo link, then every source a reader needs to rebuild the numbers (full study, the input
  list with pinned commits, the engine at the exact commit, the analysis tool, method notes, the page's own data file).

## 2. Section template

1. Kicker · headline · subhead · dek · byline ("Everything on this page is interactive: tap, hover, pick.")
2. **Hero data-image** (full width): see 3a.
3. Lede (drop cap) + setup paragraph.
4. Three big-fact tiles.
5. **Jump strip**: "Jump to the toys:" + pill links to each interactive section.
6. Story section 1 (the intuitive approach, and why it misleads) + static chart + pull quote.
7. **Play with it #1** (the per-item playground).
8. Story section 2 (the real method) + a sidebar box with the best anecdote ("Borrowed sideways").
9. **The family tree / overview interactive.**
10. Story section 3 (the hard case) + chart + pull quote.
11. Story section 4 + chart, ending "Don't take our word for it: draw the maps yourself."
12. **Play with it #2** (side-by-side comparison).
13. **Explore all N** (the full per-item explorer, list + detail cards; records folded below it).
14. What it can't tell you · How we know it's not luck · credit + Check my work · licence/affiliation footer.

Text sits in a ~44rem reading column; interactives and the hero run full width ("bands").

## 3. Interactive patterns (the level of interactivity to match)

Every interactive gets: a "PLAY WITH IT" kicker, a heading, one sentence saying what to do, its legend ABOVE the
visual (owner: never make readers scroll down to decode and back up), and a click-through to the item's detail card
(set `location.hash = "#" + name`; a hashchange handler opens the item and scrolls to the explorer).

a. **Hero data-image**: every item's name drawn in themed display fonts, **sized by a real measure** (function count),
   the root item centred and glowing, packed on an Archimedean spiral from measured `getBBox()` (wait for
   `document.fonts.load`), ~20% of small names vertical, each name clickable with a `<title>` tooltip. Use open-licence
   Google Fonts with the subject's feel; never imitate a trademarked logo. **Set font/colour as inline style**: a
   page-wide `svg text {}` rule overrides presentation attributes. Caption states what size encodes, with the real range.
b. **"Follow a ___" playground**: chips for the famous items + a type-ahead over all of them; result = one-line summary
   ("Kept identical or nearly so by 6 of 43, reworked in 11, gone from 26"), a stacked bar, and one tile per
   descendant grouped by kind, coloured by outcome, ordered best to worst. Add two rankings ("Survivors", "First to
   go") and explain what dominates them (here: 1997 Linux plumbing).
c. **Evolutionary tree (phylogram)**: right-angle branches, branch length = measured divergence, every member on its own
   row (ancestors above descendants, ladderized by clade size), unmeasured ancestors as grey italic names on short
   dashed stubs, colour by kind (fork / translation / rewrite), dot size by size, the selected item's lineage in bold
   black, axis labels top and bottom, a separate "built from scratch / no parent stated" group. Min-width + horizontal
   scroll on phones with a "swipe sideways" hint, never shrunk text.
d. **Side-by-side maps**: one-click picks spanning the range (best, middle, worst, control) + "any item" select; the
   item's map next to the reference's, both labelled, and a verdict line under them in plain words.
e. **Explorer**: searchable sorted list with a mini dumbbell (measured vs chance), detail cards (identity from GitHub,
   size vs the reference, famous-item fates, standout items, family chain, drift over time, "More detail" fold for the
   lab equipment), compare-two view with a shareable `#a&vs=b` link, records folded at the end.
f. **Static charts**: each with an over-line, a **takeaway title** (a sentence that states the finding), the legend
   above, a plain caption saying what is measured, and a "Show as a table" toggle.

## 4. Visual system

* Tokens on `:root` with dark-mode overrides (both `prefers-color-scheme` and `[data-theme="dark"]`).
* Fonts: Archivo (display/labels), Source Serif 4 (body), JetBrains Mono **only for code names and numbers**.
* Colour has one meaning everywhere: blue = measured / forks, grey = chance / unrelated, orange = translations only,
  green = rewrites, dark blue = "unchanged code". The hero image may use its own palette (fire colours for DOOM).
* Cards with 1px rule borders; story text never inside cards; sidebars on a tint background.
* Check at 1300px and 390px (headless Chrome screenshots), plus dark mode if anything is drawn on a dark band.

## 5. Honesty checks (each one bit us on DOOM's DNA)

* **Denominators:** "44 programs" included the reference; descendants were 43. Count from the data, then grep the text.
* **Metric artifacts before narrative:** an odd dip (Chocolate Doom 2010) was a one-direction score failing on
  duplicated code; switch to the robust measure the tool documents, and say why in the caption.
* **Never cap a measurement to fit an assumption;** if a measurement exceeds a limit, suspect the counting (rerun
  copies, items that never really existed) before the limit.
* **Source of each number:** label whether it came from reading the text or from shape alone.
* **Stated vs inferred:** relationships taken from the projects' own claims are labelled as such.
* **Small samples:** say "some translations", not "translations", when the strong case is one or two items.
* **Links:** verify every outbound link resolves (`gh api repos/.../contents/...?ref=main`), point at `main`, not
  merged-and-deleted branches; no claude.ai or private links in a public edition.
* **Ranges in captions come from the data** (smallest 45, largest 25,482), never from memory.

## 6. Three-lens review (before publishing)

Take section screenshots (desktop + phone) and launch three parallel review agents (Hackaday, Scientific American,
Popular Science) with the prompts in `lens-review.md`; give them the page and the screenshots, never your own opinion.
Apply what at least two lenses agree on; treat a single lens's point on its merits. Their consensus on DOOM's DNA (the
baseline to beat): story first, the tree as hero, plain-language numbers, lab equipment folded, one meaning per colour,
legends above visuals.

## 7. Build and publish

1. **Data:** one builder script writes one `data.json` (measurements and names only, never source text). Cache
   network lookups (GitHub) in a file.
2. **Page:** reuse the component code (don't fork it); the article builder swaps in the article body, adds article
   CSS scoped so it can't restyle the components (`.chart svg text`, `figure h3`), appends the charts and new
   interactives, and wires startup + hash routing.
3. **claude.ai artifact:** publish the page with `files: {"data.json": ...}` from a copy under the working dir; a data
   download needs `capabilities: {downloads: true}` and `claude.use("downloads").save({filename, data: blob})` with a
   fallback note (plain download links do nothing in the viewer).
4. **Public edition (GitGalaxy docs wiki, MkDocs Material, deployed by `deploy-docs.yml` on push to main):**
   * `build_article.py --wiki docs/wiki/museum-of-code/<slug>/` writes a complete HTML document (doctype, viewport,
     description, canonical, Open Graph incl. a 1200x600 `collage.png` screenshot of the hero, schema.org `Article`
     JSON-LD naming the author), a plain `<a download>` data link, no "draft" wording.
   * A **text edition** in Markdown (every section, number and chart table, linking into the interactive edition with
     relative links MkDocs rewrites). MkDocs' sitemap and search only list Markdown pages, and agents read text best.
     When it replaces an older page, **keep the old URL** and replace its content (keeps the search ranking, breaks no
     links); add a pointer note on superseded pages rather than deleting them.
   * `.gitignore` ignores `*.json` repo-wide: add a `!docs/wiki/.../data.json` whitelist line and confirm with
     `git check-ignore -v`.
   * No admonitions (`!!! note`): the extension is not enabled; use a blockquote.
   * Build with the pinned toolchain and compare warnings with main: `pip install --require-hashes -r
     ci/requirements/docs.txt`, `mkdocs build -d <tmp>`; same warning set as main, then serve the built site and check
     both pages and every new link. No test reads the Museum pages; the build is the gate.
   * Docs PR to main (pre-authorised); the owner merges.

## 8. Before you hand it over

- [ ] First screen: question, three facts with comparisons, hero image; no method words.
- [ ] Every chart has a takeaway title, legend above, plain caption, table toggle.
- [ ] Every interactive: one-line instruction, legend above, works at 390px, clicks through to the item.
- [ ] Honesty checks in section 5 run; counts and ranges taken from the data.
- [ ] Byline, credit, "Check my work" with working links, licence/affiliation footer, no "draft" in the public edition.
- [ ] Screenshots reviewed at desktop and phone widths; no console errors.
- [ ] Both editions published (artifact for review; wiki PR for the public), links reported to the owner.
