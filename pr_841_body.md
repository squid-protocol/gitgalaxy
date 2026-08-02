Fix Extraction hardening: css #841: Harden CSS extraction rules against catastrophic backtracking and nested parens

This fix was developed using the rigorous 5-stage agent pipeline, addressing critical extraction flaws:

### What the Agents Found:
- **Catastrophic Backtracking (ReDoS) in `class_start`**: Discovered an O(n^2) ReDoS vulnerability where the lookahead's first quantifier `[ \t,>+~:]*` was a strict subset of the second's `[^{]*`, causing exponential backtracking on combinator strings missing a `{`.
- **Nested Parentheses Truncation in `args` and `scientific`**: The `args` and `scientific` regexes only supported one level of nested parentheses (`calc(var(...))`). Deeply nested math like `calc(100% - var(--sidebar, calc(var(--base) * 2px)))` truncated early.
- **Unicode Escapes Blocked**: Valid CSS escaped characters (e.g., `.\31 23-number`) were completely blocked by strict `[a-zA-Z_]` character sets.
- **Tag Masking False Positives**: Structural logic triggers like `@media` didn't catch vendor prefixes (`@-webkit-keyframes`).

### Quantitative Metrics:
- **Adversarial Tests Created**: 18 explicitly crafted payloads testing modern CSS3 nested structures, ReDoS traps, escaped unquoted URIs, and unicode identifiers.
- **Errors/Failures Fixed**: Fixed 3 critical parsing failures in the crucible (escaping mismatches, nested truncations, and lookahead vulnerability). 
- **Golden Master Updates**: Re-generated the `tests/golden_master_zero_dep_audit.json` baseline. 

### Known Regex Limitations:
- **String/Comment Masking**: Due to the declarative nature of static regex and the lack of a full CSS AST tokenizer, structural lookalikes hidden inside valid string literals (e.g., `content: "calc(100%)"`) or multiline block comments may still occasionally trigger false positive captures.
