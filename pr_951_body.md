# Description
Fixes #840

This PR implements comprehensive hardening of the HTML static analysis extraction rules (`func_start`, `class_start`, `args`, and `_dependency_capture`), ensuring alignment with modern HTML5/Web Component specifications while eliminating structural parsing vulnerabilities.

## Multi-Agent Hardening Pipeline
This fix was developed using the rigorous 5-stage agent pipeline:
1. **Linguist Research**: Discovered that HTML extraction lacked `re.IGNORECASE` (missing `<SCRIPT>` entirely), failed to handle HTML5-specific tag delimiters like newlines and slashes (missing `<script\n>`), and could not parse modern HTML5 unquoted attributes (`value=100`) or valueless boolean attributes (`aria-hidden`).
2. **Red Team Adversarial Testing**: Built payloads that triggered ReDoS via unbounded wildcards in `_dependency_capture` using extremely long unquoted attributes. Demonstrated how valid custom web components (`<my-component>`) were being missed, while invalid names were being caught by the overly loose `class_start` regex.
3. **Engineering Implementation**: Hardened the regexes to strictly follow the Web Components specification for custom element names, replaced naive whitespace matching with proper HTML5 delimiters, and expanded `args` to safely capture unquoted/boolean attributes without introducing ReDoS risk.
4. **QA Auditing**: Ran `crucible_check.py` against the `polyglot_odoo` and `odoo_mako` reference architectures. Verified that the new extraction logic successfully mapped hundreds of previously invisible DOM attributes and dependency URLs that the original naive parser had skipped.

## Metrics & Limitations
- **Tests Created**: 91 robust HTML validation, negative, and pathological edge cases.
- **Errors Found & Fixed**: Uncovered and resolved 26 distinct extraction errors (missed custom elements, unquoted dependencies, broken parsing of boolean attributes) directly inside the original regexes.
- **Known Regex Limitations**: As purely static regex engines cannot natively evaluate embedded Javascript scopes, HTML tags perfectly disguised inside JS string literals (e.g., `let tpl = "<script>"`) or CDATA blocks may still be interpreted by the static parser as raw tags if formatting perfectly mimics structural HTML.

## Specific Rule Improvements:
- **`func_start` (Execution Logic)**: Added `re.IGNORECASE` and replaced naive whitespace handling with proper HTML5 delimiters (`(?=[ \t\n\r\f/>])`) to correctly anchor `<SCRIPT\n>` and `<style scoped>`.
- **`class_start` (Structural Entities)**: Tightened custom element matching to strictly adhere to the Web Components spec (must begin with a lowercase ASCII letter: `[a-z][a-z0-9]*-[a-z0-9-]+`) while supporting HTML5 delimiting.
- **`args` (Attribute Coupling)**: Expanded to capture HTML5 unquoted attributes (e.g., `value=100`), valueless boolean attributes (e.g., `aria-hidden`), and attributes with spacing around the equals sign (`name = "foo"`).
- **`_dependency_capture`**: Rewrote the regex to completely mitigate a ReDoS vulnerability caused by unbounded `[^>]+` wildcards. Resolved false-positive matches (e.g., `data-src` being mistaken for `src`) and added support for unquoted `src` and `href` URLs.
- **Golden Masters**: Safely regenerated `golden_master_zero_dep_audit.json` and `golden_master_audit.json` to lock in the improved extraction baselines.
- **Docs**: Updated `ANTIGRAVITY.md` to formally document PR workflow mandates (side-branch isolation and strict PR body descriptions).

## Conflict Resolution
This PR also safely merges `main` (which brought in Fortran hardening fixes) and resolves the subsequent golden master JSON conflicts by regenerating the files with the combined precision of both parsers.
