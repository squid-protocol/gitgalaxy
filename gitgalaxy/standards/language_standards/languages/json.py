# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

from typing import Any

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "Modern JSON & Configuration Ecosystem",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard, commented, line-delimited, and geospatial JSON.
    "extensions": [
        ".json",
        ".arb",
        ".jsonc",
        ".json5",
        ".jsonl",
        ".ndjson",
        ".geojson",
        ".topojson",
    ],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Extended modern web/node tooling.
    "exact_matches": [
        ".prettierrc",
        ".eslintrc",
        ".babelrc",
        ".stylelintrc",
        ".bowerrc",
        ".hintrc",
        ".nycrc",
        ".lintstagedrc",
        ".swcrc",
    ],
    "discriminators": [".json", ".jsonc", ".json5", ".arb"],
    "shebangs": [],
    # THE FIX: JSON with comments relies on C-style comment structures, not Python/Ruby hashes.
    "lexical_family": "standard_block",
    "rules": {},
}
