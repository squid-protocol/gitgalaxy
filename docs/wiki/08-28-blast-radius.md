---
description: "> **Topic:** Where do later fixes land relative to an earlier change? An exploratory, replicated measurement across curl, OpenSSL and FreeBSD (and seven repositories without named causes): the fix is usually in the code that changed, and when it is elsewhere it is within one or two calls about 1.5 to 2 times as often as chance in the same file."
---
# Blast Radius of a Change

> **Status:** exploratory research, one author, not peer reviewed. The measurements are in the temporal-crucible repository (`docs/sensor-overhaul/sensors/ripple_radius.md`, with scripts and outputs). This page says what was found, how much weight it bears and how `gitgalaxy change` uses it.
>
> **Command that uses it:** [`gitgalaxy change`](08-26-change-report.md): changed signatures first, with their callers named.
>
> **Summary:** After a change, the later fix for it is most often in a function the change touched. When it is not, it is found near the change in the call graph, more often than a function of similar size in the same file. A short list of the changed functions plus their nearest neighbours covers about half of all named-cause cases we could measure, and about 80% of those we could map.

## The question
Per-function structure (branches, parameters) tells little about where fixes land once size is accounted for. The unit that does carry signal is the **change event and its neighbourhood in space and time**: functions changed together, called by, or calling the changed code, in the weeks after. This page measures that neighbourhood.

## How it was measured
1. **Named-cause pairs.** A fix commit that names the commit that caused it: curl (messages referencing the cause), OpenSSL and FreeBSD (the kernel convention `Fixes: <sha>`). For each pair: the functions each commit touched (from git hunk-header context) and the call graph of the nearest quarterly scan at or after the causing commit.
2. **A same-file baseline.** For a fixed function outside the functions the causing commit changed, the comparison is with random other functions from the same file, of similar size, outside the changed set. This removes "fixes are in the file that changed" and asks only whether the call graph adds anything.
3. **Without named causes** (seven repositories, four languages): fixes in a later quarter, or after an individual commit in the 45 days before, against functions changed earlier.
4. **Retrieval.** Rank every function in the graph for each pair and ask where the fixed function lands.

## What was found
| | finding | numbers |
|---|---|---|
| Same place | most fixes touch a function the causing commit also touched | curl 71%, FreeBSD 69%, OpenSSL 42% |
| Radius | when the fix is in another function, it is within 1 or 2 calls of the change more often than same-file functions are | within 2 calls: curl 1.54, OpenSSL 1.57, FreeBSD 2.17, pooled OpenSSL and FreeBSD **1.71** (interval 1.50 to 2.00); against random functions of the same size, about 9 times in curl and 30 times in OpenSSL |
| Without named causes | the same direction, smaller | 1.09 (interval 1.07 to 1.12) across seven repositories; 1.36 for commits in the day before the fix, about 1.2 for commits up to 45 days before |
| Time | strongest within weeks, repository-dependent after | OpenSSL: 2 times within a year, none (1.2) a year or more later; FreeBSD stays at about 2; pooled 1.41 for a year or more |
| Direction | callers against callees varies by repository | curl: callers more enriched; OpenSSL: equal; pooled OpenSSL and FreeBSD: 1.87 against 1.88 |
| **Signature changes** | when the causing commit changed a function's parameter count, the fix tends to land in a **caller** | curl 33% against 13%; OpenSSL and FreeBSD pooled 34.5% against 20.1% (3.83 times the same-file baseline, interval 1.50 to 9.12) |
| Not one person | the excess is the same when a different person writes the fix | same author 1.59, different author 1.62 (within 2 calls) |
| Callbacks | adding function-pointer and callback references found with tree-sitter changed little | curl: 1.77 to 1.87 within one call; in curl 81% of functions with no static caller are referenced as callbacks |

**A watchlist.** Rank candidates by same file, then call distance, then size. For pairs where the fix is outside the changed code, the top 20 contain the fixed function **46.5%** of the time (curl 45%, OpenSSL 47%, FreeBSD 51%; random 0.4%), from candidate sets of 3,500 to 143,000 functions. With the changed functions themselves on the list (about 23 functions in all): **79.5%** of pairs we could map and **51.8%** of all 1,208 named pairs (curl 55.8%, OpenSSL 45.6%, FreeBSD 44.8%). The neighbours matter most for fixes a year or more later (45% to 67%).

## What it does not say
- **Association, not cause.** The same-file baseline removes file location and size, not a shared feature, release or reviewer; the same-author check removes only "one person finishing their own work".
- **Modest effects.** 1.5 to 2 times a baseline, and about 1.1 times without named causes. It is a review and monitoring aid, not a score for ranking functions.
- **Caller-first is not general.** Only for a changed signature (curl, OpenSSL, FreeBSD); in the other cases the direction varies by repository, so `gitgalaxy change` lists callers for signature changes and counts, not a direction, otherwise.
- **Labels are what developers wrote.** Only fixes that name their cause are in the named-cause design (a project habit; the kernel convention, curl's messages); about half of the named pairs could not be mapped to functions in a scan and count as misses in the conservative coverage figure.
- **The static call graph** has no edge for a function reached through a pointer; the tree-sitter check suggests the effect is understated slightly, not by much, in curl; the kernel, where function-pointer tables carry much of the structure, is untested.
- **Three repositories** with named causes (curl 507 usable pairs, OpenSSL 177, FreeBSD 103) and wide intervals in the lag groups; seven repositories for the version without named causes.

## What `gitgalaxy change` does with it
For a change set it lists the touched functions with a changed signature first and names up to five callers of each; the rest follow, most-called first. See [Change Report](08-26-change-report.md). The watchlist ranking above is not in the command yet.
