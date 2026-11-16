---
description: "> **Command:** `gitgalaxy libsurface SCAN_DB [SCAN_DB_AFTER] [--lib NAME]`. Which libraries a repository leans on, which files lean hardest, and how the surface changes between two scans. Read-only, no change to scan output."
---
# Library Surface

> **File Reference:** [`gitgalaxy/tools/sensors/libsurface.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/tools/sensors/libsurface.py)
>
> **Command:** `gitgalaxy libsurface SCAN_DB [SCAN_DB_AFTER] [--lib NAME] [--libs FILE] [--src ROOT] [--top N] [--json FILE]`
>
> **Metric:** For a library, the files that import or include it and call its API, counted as sites (matching imports or includes plus calls to the library's API names) and sites per line.
>
> **Summary:** Answers "what does this repository depend on, where does work on a library land, and what changed in how we use it?" from a finished scan. A list and counts, no score, and no risk claim: coupling says where work on a library tends to land, not that the file is fragile.

## Engineering Summary
A scan already stores every file's imports and includes and, since the `fcall_external` table, every call to a name the repository does not define. Together they say which libraries a file uses and which of their functions it calls. The command reads them from the scan database (opened read-only), discovers the external libraries, ranks a library's coupled files, and compares two scans to show the API names and files that came or went.

## Purpose
To scope an upgrade, a deprecation or a migration before starting it (which files absorb a change to library X, which of its functions are used), and to see afterwards what actually moved.

## Problem Being Solved
None of the existing gauges says anything about a dependency. A library's own work is spread across the repository by how it is used, not by where the library's name appears in a file name.

## Design
1. **Libraries** (`gitgalaxy libsurface DB`): every external import root is a library: the first dotted component in Python, host plus owner plus repository in Go (`github.com/o/r`), the package prefix in Java, the first `::` component in Rust, the package name in JS and TS, the include directory or header name in C and C++. Set aside first: the standard library and system headers (the engine's own lists, `standards/stdlib_modules.py` and `standards/system_headers.py`), relative imports, and the repository's own packages, modules and headers.
2. **Coupled files** (`--lib NAME`): the files that use the library, ranked by sites per line (ties by smaller size, then path), with how many distinct API names each uses.
3. **Surface change** (two scans, `--lib NAME`): API names added and dropped, files newly and no longer coupled, and the totals before and after. A renamed or moved file shows as one file leaving and one joining.
4. **API names** come from the shipped table (`library_table.py`): glob patterns per C-family library (`SSL_*`, `inflate*`), because a library reached through a wrapper header is invisible to includes alone. Without a table entry a library is counted by its imports and includes only.

## Who defines a library
Later layers win, by name; an entry with `disable = true` removes one.
1. Discovery (no list needed).
2. The shipped table, 20 C-family libraries, extendable by contribution.
3. TOML files: `$XDG_CONFIG_HOME/gitgalaxy/libraries.toml`, `ROOT/.gitgalaxy/libraries.toml` (with `--src ROOT`), then `--libs FILE`:

```toml
[[library]]
name      = "openssl"
languages = ["c", "cpp"]                 # optional: c, cpp, python, go, java, rust, js (default: any)
include   = ["openssl/*"]                # globs on an import or include string
calls     = ["SSL_*", "EVP_*"]           # globs on a called external name (optional)
```
Patterns are globs, never regexes, so a pattern a user writes cannot hang the matcher; a malformed file is refused with a message (exit 2). Keep `calls` strict: a loose pattern such as `g_*` attaches calls to the wrong library.

## Pipeline Integration
- **Inputs:** `file_data` (path, lines, `raw_imports`) and `fcall_external` (#8530) from the scan database; no source tree is needed.
- **Outputs:** a text report, and with `--json` the full result.
- **Dependencies:** scans that wrote `fcall_external` for API names; on an older scan the command still reports imports and includes and says that names were not recorded.

## Tradeoffs
- Counts, not a score: no cross-repository scale. Read lists within one repository.
- Discovery is a heuristic. It lists a repository's Rust workspace crates and platform headers it does not recognise (`in.h`) as libraries; `disable = true` removes them.

## Limitations
- API names exist only for libraries in the table (C and C++ today). In Go, Python, Java, Rust and JS the scan records external calls as bare names with no package, so name matching cannot attribute them; those languages use imports only.
- Calls the scan cannot see (macros, function pointers, names the resolver does not record) are not counted.
- The outcome measured in research is "a commit whose subject names the library touches the file in the next 180 days"; work that never names the library is missed.

## Performance Notes
One pass over `file_data` and `fcall_external`; a run takes a fraction of a second on a 1,100-file repository.

## Future Work
More table entries (contributed); the other wrapper-header languages (C++, Objective-C, Fortran) are untested; Rust needs another repository before any claim.

## Related Components
- [Reach Sensor](08-24-reach-sensor.md) (who depends on a file; `--callee` scopes a name)
- [Connectivity (API Surface)](08-14-api-exposure.md)

## Evidence and Provenance
Exploratory, from the temporal-crucible study (LIB-H1 to H3, LIB-R and the sensor-overhaul validation); no registered test of this command. Coupling to a library predicts where its work lands: with function-name patterns, +0.389 recall@20 over a size ranking on 19 (repository, library) pairs in curl, libarchive and harfbuzz (99.7% lower bound +0.344), and -0.018 against the research's regex method (non-inferior at a margin of -0.05); includes alone gave +0.253 and lost to the full measure by -0.136. The shipped glob table reproduces the research regexes exactly on all 19 pairs. Outside C, import coupling alone gave +0.241 on 11 evaluable pairs (Go +0.395 on 5, Python +0.102 on 5, Java one library; Rust not evaluable). Over the OpenSSL 3 era in curl the surface change listed 31 API names added and 15 dropped, of which 90% and 80% checked out against the source.
