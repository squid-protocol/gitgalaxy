---
name: self-scan-query
description: Query GitGalaxy's own self-scan SQLite DB (docs/self_scan/gitgalaxy_master.db) for per-file/function complexity, LOC, call graphs, and blast-radius ranking -- near-zero-token compared to grep or an Explore subagent for these questions. Use before touching a file to gauge how big/complex/depended-on it is, before a large refactor to find the real blast-radius ranking, or to answer "what does function X call" / "which functions in this file are heaviest" / "which directory has the most code". Do NOT use for finding string literals, dict/list-literal keys, exact line numbers, or any non-function symbol -- the DB has no line numbers and doesn't parse literal internals; grep or Read for those.
---

Source of truth for the DB's purpose and schema notes is the docstring at the top of
`tests/tools/self_scan.py` -- read it if anything here seems stale, since the recorder schema
evolves. This skill exists because an LLM session in this repo can burn real tokens re-deriving
basic structural facts (how big is this file, how many functions does it have, what's the
heaviest function here) via grep or an Explore subagent, when GitGalaxy's own engine already
extracted that as a Structural Signature about itself.

## Step 1 -- freshness check (do this before trusting any file-specific result)

The DB is a snapshot of the working tree at generation time, not a live view. Check it's still
current before relying on it for anything about a *specific* file you're about to edit (a stale
snapshot is fine for broad orientation like "which directory group is heaviest" -- less fine for
"how complex is this file right now"):

```bash
git rev-parse HEAD
sqlite3 docs/self_scan/gitgalaxy_master.db "SELECT DISTINCT commit_hash FROM file_data;"
git status --porcelain   # anything uncommitted touching files you care about?
```

If the DB is missing, `commit_hash` doesn't match current `HEAD`, or there are uncommitted
changes to files relevant to your question, regenerate before querying:

```bash
python tests/tools/self_scan.py
```

Takes ~6-8s. Requires `galaxyscope` on PATH (an activated venv with `pip install -e .`) and
`networkx`/`tiktoken`/`numpy`/`pandas`/`xgboost`/`pyyaml` importable -- the script itself checks
for all six and aborts loudly with an install hint if any are missing, rather than silently
producing a degraded (NULL pagerank/blast-radius) DB. Don't try to work around a failed
regeneration by querying the stale DB anyway for a file-specific question -- fall back to
grep/Read instead, and say why.

## Step 2 -- always confirm schema before querying

Column names have drifted before. Never guess:

```bash
sqlite3 docs/self_scan/gitgalaxy_master.db ".schema file_data"
sqlite3 docs/self_scan/gitgalaxy_master.db ".schema function_data"
```

## Query cookbook

Heaviest/most complex functions in a file, before editing it:

```bash
sqlite3 docs/self_scan/gitgalaxy_master.db \
  "SELECT f.func_name, f.complexity, f.loc, f.calls_out_to
   FROM function_data f JOIN file_data fd ON f.file_id = fd.id
   WHERE fd.file_path LIKE '%detector.py%' ORDER BY f.complexity DESC LIMIT 10;"
```

What does function X call (approximate call graph, no cross-file resolution -- `calls_out_to` is
a raw text list, not linked to `function_data.id`):

```bash
sqlite3 docs/self_scan/gitgalaxy_master.db \
  "SELECT func_name, calls_out_to FROM function_data WHERE func_name = 'parse_manifest';"
```

Who calls function X (grep-the-column, since `calls_out_to` is text, not a foreign key):

```bash
sqlite3 docs/self_scan/gitgalaxy_master.db \
  "SELECT fd.file_path, f.func_name FROM function_data f JOIN file_data fd ON f.file_id = fd.id
   WHERE f.calls_out_to LIKE '%parse_manifest%';"
```

File-level orientation before deciding where new code belongs, or before a refactor (blast
radius / fan-in ranking):

```bash
sqlite3 docs/self_scan/gitgalaxy_master.db \
  "SELECT file_path, function_count, class_count, total_loc, avg_func_complexity,
          pagerank_score, normalized_blast_radius
   FROM file_data ORDER BY pagerank_score DESC LIMIT 10;"

sqlite3 docs/self_scan/gitgalaxy_master.db \
  "SELECT directory_group, COUNT(*) files, SUM(total_loc) loc, SUM(function_count) funcs
   FROM file_data GROUP BY directory_group ORDER BY loc DESC LIMIT 8;"
```

If `pagerank_score`/`normalized_blast_radius` come back NULL across the board, the scan ran in
Zero-Dependency Mode (one of the six full-precision packages wasn't importable at scan time) --
rerun `python tests/tools/self_scan.py` in an environment that has all of them, don't trust
blast-radius rankings from a NULL column.

## Boundaries -- when to fall back to grep/Read/Explore instead

- Finding a string literal, comment, config key, or anything inside a dict/list literal (the DB
  explicitly can't see inside e.g. `language_standards.py`'s `LANGUAGE_DEFINITIONS` dict).
- Getting an exact line number -- the DB doesn't store one; once you know *which file* from a DB
  query, grep or Read that file for the actual location.
- Any symbol that isn't a function or class (variables, constants, types, imports by name).
- A file too new/uncommitted to be in the DB at all, or one excluded by `.galaxyscope.yaml`
  (check `excluded_artifacts` table if a file you expect is missing).
