---
description: "You are operating within `diff-so-fancy`, a highly focused CLI utility designed to parse and format `git diff` output. The execution logic of the..."
---
# AGENTS.md: diff-so-fancy Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `diff-so-fancy`, a highly focused CLI utility designed to parse and format `git diff` output. The execution logic of the repository is almost entirely centralized within a single Perl script (representing the vast majority of the executable code mass).
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species. Its network topology is completely flat (Modularity 0.0, Assortativity 0.0), which is highly characteristic of a monolithic, single-file script architecture. The primary script acts as the absolute orchestrator, consuming standard input, applying string transformations, and emitting formatted standard output. Do NOT attempt to enforce multi-file object-oriented decoupling; the system's design explicitly favors a single, easily distributable artifact.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core formatting routines (`file_change_string` and `do_dsf_stuff`) manage dense string processing and ANSI code manipulation. Furthermore, the `git_config` memoization function operates with O(2^N) recursive time complexity in static analysis. You MUST NOT introduce deeply nested loops or backtracking regular expressions (Regex) in the hot path of the text parsing, as this will severely degrade terminal performance when processing large git diffs.
* **Orchestrator Fragility:** The `diff-so-fancy` executable is highly fragile. Any changes to the state flux (which sits at 29.6% volatility) or the regular expressions used to identify diff headers (`parse_hunk_header`) require immediate, comprehensive verification against a diverse set of git output formats.
* **Avoid Dead Code Pruning:** The `diff-so-fancy.plugin.zsh` shell integration carries 100% technical debt exposure. DO NOT autonomously attempt to prune or "modernize" this file without understanding the specific shell compatibilities it provides for Zsh environments.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream terminal output testing before modifying the structural signatures, regex patterns, or public APIs of these files:
* `diff-so-fancy` (Perl script) - Extreme Cumulative Risk (599.49), Massive Structural Mass (1451.84), 100% Churn, and 100% isolated Key Person ownership by Scott Baker. This file is the entire application logic.
* `diff-so-fancy.plugin.zsh` (Shell script) - High Technical Debt (100%) and acts as a strict dependency for shell integrations.

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Input Sanitization Surface:** Because the tool processes arbitrary repository data, file paths, and git metadata via standard input, you MUST ensure that text bleaching (`bleach_text`) and line parsing (`strip_leading_indicators`) do not inadvertently evaluate shell commands or fail insecurely when encountering malicious or obfuscated ANSI escape sequences.
2. **Configuration Parsing:** The `git_config` function reads external configuration. Modifications to how this configuration is invoked or parsed must never allow arbitrary code execution or unescaped parameter expansion.

## 5. Environmental Tooling (The Oracle)
Do not guess Perl regex behaviors, hallucinate terminal color code outputs, or rely on generalized text parsing knowledge to determine blast radius within this highly concentrated script. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
