# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

import re
from typing import Any

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "CommonMark / GitHub Flavored / AsciiDoc",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard modern suffixes, legacy extensions, MDX, and AsciiDoc formats.
    "extensions": [
        ".md",
        ".markdown",
        ".mdown",
        ".mkd",
        ".mdx",
        ".adoc",
        ".asciidoc",
    ],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: The universally recognized, extensionless repository documentation anchors.
    "exact_matches": ["README", "LICENSE", "CHANGELOG", "CONTRIBUTING", "SECURITY"],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Static site generators and documentation build configs acting as disambiguation anchors.
    "discriminators": [
        ".md",
        ".mdx",
        "mkdocs.yml",
        "_config.yml",
        "docusaurus.config.js",
    ],
    # EXECUTION SIGNATURES: Markdown is declarative text; no shebangs exist.
    "shebangs": [],
    # UPGRADED: Maps to Family 8 (Singular/Unique)
    # Rationale: (CORRECTION) Markdown relies entirely on HTML's SGML-style block comments ().
    # Mapping this to 'hybrid_dash' would cause the engine to miss hidden documentation mass.
    "lexical_family": "line_exclusive",
    "rules": {
        # Relative-link dependency capture (#2638): a doc that links a sibling file
        # depends on it the same way code imports a module -- the target feeds the
        # DAG (popularity / orphaned-docs detection). Scheme URLs (http:, mailto:),
        # protocol-relative (//), pure-anchor (#...) and angle-bracket-wrapped
        # (<...>, CommonMark's escape hatch for URLs with spaces/parens -- in
        # practice external) targets are excluded by the lookahead; the capture
        # stops before any #fragment, whitespace-separated title, or closing
        # paren. The bracket half reuses lit_links' vetted bounded shape (one
        # nesting level, no adjacent unbounded quantifiers).
        "_dependency_capture": re.compile(
            r"\[(?:[^\[\]]|\[[^\[\]]*\])+\]\(\s*(?!<|[a-zA-Z][a-zA-Z0-9+.-]*:|//|#)([^()\s#]+)"
        ),
        "lit_code_blocks": re.compile(r"^[ \t]{0,3}```+[^`\r\n]*$", re.M),
        "lit_diagrams": re.compile(r"^[ \t]{0,3}```+(?:mermaid|plantuml)\b", re.I | re.M),
        "lit_headers": re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+", re.M),
        "lit_links": re.compile(r"\[(?:[^\[\]]|\[[^\[\]]*\])+\]\((?:[^()]|\([^()]*\))+\)"),
    },
}
