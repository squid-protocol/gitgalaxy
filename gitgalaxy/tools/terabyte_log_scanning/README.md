# High-Volume Log Scanning & PII Leak Detection

This directory contains two independent, single-pass streaming scanners for large log files
and data dumps: `terabyte_log_scanner.py` (keyword search with time-series histograms) and
`pii_leak_hunter.py` (exposed-PII detection and masking). Neither depends on the core
GitGalaxy structural-signature engine — both are standalone CLI tools built for one specific
job: finding things in logs that are too large to comfortably grep, index, or load into memory.

## The Problem: Log Files Don't Fit the Usual Tooling

A production log file or a database dump can run into the tens or hundreds of gigabytes.
Loading it into memory, building a search index, or piping it through a general-purpose log
platform is often either too slow, too expensive, or simply not available — especially when
the log needs to be scanned once, on demand, as forensic evidence (e.g. "did this program
actually run last night," or "did we ever write a credit card number to this log by mistake").

## The Approach: Stream Once, Never Buffer the Whole File

Both scripts open the target file in binary mode and process it line by line in a single pass
— nothing is read into memory as a whole, and neither script builds an index before scanning.
Search patterns are pre-compiled as byte regexes (not decoded text) so the common case — a line
that matches nothing — costs a binary regex check, not a UTF-8 decode. A line is only decoded
to text once something in it actually matches. Both tools extract a timestamp from each
matching line (ISO-style or syslog-style `Mon DD HH`) and bucket hits by hour into an ASCII
time-series histogram, so a spike in volume is visible directly in the terminal without a
separate analytics step.

## `terabyte_log_scanner.py` — Keyword Search Across a Log

Streams a log file looking for one or more keywords, and reports when — not just whether —
each one showed up.

```bash
python terabyte_log_scanner.py /path/to/app.log -k PGM_BILLING PGM_SHIPPING
```

Targets can also be supplied automatically from a GitGalaxy Intermediate Representation (IR)
state file instead of typed by hand — `--input_state ir_state.json` reads the
`analysis.known_programs` array GitGalaxy's own static extraction produced, so a set of program
names identified purely from source code can be immediately searched for in a real runtime log,
without retyping them. This is the tool's actual bridge back to the rest of GitGalaxy: static
analysis says a program exists in the code, and this script checks whether it actually shows up
running.

**Output**, written next to the input file (or to `--out <dir>`):
- `<name>_results.txt` — every matching line, unmodified.
- `dynamic_telemetry.json` — a small sidecar with per-keyword hit counts.

## `pii_leak_hunter.py` — Exposed PII Detection and Masking

Streams a log file or data dump looking for a fixed set of PII patterns: Visa and Mastercard
card numbers, US Social Security numbers, and AWS API keys (`AKIA`/`ASIA`/`AGPA`/`AIDA`/`AROA`/`AIPA`
prefixes). Unlike the keyword scanner, there's nothing to configure — it always checks for all
four categories.

```bash
python pii_leak_hunter.py /path/to/dump.log
```

Every matching line is masked before it's written anywhere — the raw PII itself is never
persisted to disk, only a redacted stand-in (last 4 digits of a card or SSN, first+last 4 of an
AWS key). That's what makes the output safe to keep as evidence: you can prove a leak happened
and where, without creating a second copy of the sensitive data itself.

**Output**, written next to the input file (or to `--out <dir>`):
- `<name>_pii_leak_evidence.log` — one masked line per hit, prefixed with which category
  matched (`[VISA]`, `[SSN]`, `[AWS_KEY]`, `[MASTERCARD]`).

The summary line also reports throughput (GB/s or MB/s), since "how fast did this run" matters
more here than for a typical CLI tool — the whole point is being usable against files too large
to comfortably index first.

## Example Run

Real output from a small synthetic log containing one Visa number, one SSN, and one AWS key
(license banner and per-hit histograms trimmed for brevity — nothing here is fabricated):

```bash
$ python pii_leak_hunter.py sample_app.log
```
```text
[COMPLETE] Processed sample_app.log in 0.00 seconds.
Processing Velocity: 1.18 MB/s
Redacted Evidence Log: sample_app_pii_leak_evidence.log
```

The evidence log it wrote:

```text
[VISA] 2026-08-01T09:12:04 INFO  Payment attempt with card VISA-MASKED-1111 for order 5521
[SSN] 2026-08-01T10:03:23 INFO  User SSN on file: XXX-XX-9999 flagged for manual review
[AWS_KEY] 2026-08-01T10:15:40 INFO  AWS credential loaded: AKIA-XXXX-MNOP
```

No unmasked PII ever touches disk — the original numbers only ever existed in memory for the
single line being processed.

## The GitGalaxy Ecosystem (Powered by the blAST Engine)

These log scanners are standalone utilities within the broader **GitGalaxy Ecosystem**—an
AST-free, LLM-free heuristic knowledge graph engine built to scan repositories without a
compiler toolchain.

Explore the ecosystem:

* **[Official Documentation](https://squid-protocol.github.io/gitgalaxy/)** — Comprehensive deep dives into the engine's mathematics, pipeline architecture, and DevSecOps integration protocols.
* **[GitGalaxy Visualizer](http://gitgalaxy.io/)** — Render your codebase's topological network locally in interactive 3D using hardware-accelerated WebGPU.
* **[The blAST Paradigm](https://squid-protocol.github.io/gitgalaxy/docs/wiki/01-03-the-blast-paradigm/)** — The architectural thesis, academic research, and structural math that makes AST-free parsing possible at scale.
* **[Language Calibration Standards](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/standards/how_to_add_a_language.md)** — The definitive engineering guide to extending our comparative lexical taxonomy for custom enterprise dialects.
