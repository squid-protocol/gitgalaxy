# Language Standards Registry

> **File Reference:** [`gitgalaxy/standards/language_standards.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/standards/language_standards.py)

## Engineering Summary
A central dictionary maps programming languages to syntax schemas and extraction rules. It solves the challenge of cross-language static analysis by providing a unified definition layer for regular expressions, block delimiters, and comment structures. This decoupling allows engineers to add new language support without modifying the core parsing logic, known as `language_standards` in GitGalaxy.

## Purpose
To define uniform extraction rules and map disparate language syntax constructs onto a standard numerical metrics array.

## Problem Being Solved
Evaluating multi-language repositories usually requires writing bespoke parsers for each language. This registry abstracts language-specific syntax into structured regex heuristics, avoiding the overhead of maintaining distinct AST parsers.

## Design
The registry categorizes definitions into:
- Ecosystem Metadata: File extensions, false-positive filters, and matching weights.
- Function Extraction Modes: Strategies like block-scoped (C++, Java), indentation (Python), or terminator cleaving (SQL).
- Comment Handling: Standardized handlers to strip comments without corrupting strings.
- Syntax Patterns: Maps structural and security heuristics to a 51-element `UNIVERSAL_METRICS_SCHEMA`.

## Pipeline Integration
- **Inputs**: Source code files during the discovery phase.
- **Outputs**: Syntax heuristics mapped to a 51-element numerical array.
- **Dependencies**: Relies on standard regex libraries; outputs are consumed by the SignalProcessor and recording engines.
```text
Source Code -> Language Standards Registry -> 51-Element Universal Metrics Array
```

## Tradeoffs
Regex-based heuristics are less accurate than full Abstract Syntax Tree (AST) parsing, occasionally resulting in false positives for complex nested structures. This sacrifice in absolute precision was chosen to achieve high-speed, language-agnostic parsing that scales linearly with repository size.

## Limitations
- Cannot accurately parse deeply nested or obfuscated syntax that breaks regex boundaries.
- Lacks semantic understanding of variable scopes or type definitions.

## Performance Notes
By pre-compiling regular expressions on startup and using $O(1)$ dictionary lookups for extensions, file classification operates in microsecond timeframes per file.

## Future Work
- Introduce WebAssembly-based pre-compiled state machines to replace complex regex structures.
- Support dynamic addition of custom DSLs via JSON configurations instead of Python code.

## Related Components
- [Analysis Lens & Schema Registry](06-03-analysis-lens.md)
- [GitGalaxy Configuration Registry](06-01-gitgalaxy-config.md)
