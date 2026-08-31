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
    "_meta": {"target_version": "Comma Separated Values", "status": "production"},
    # COMPREHENSIVE SURFACE AREA: Comma, tab, and pipe-separated value formats.
    "extensions": [".csv", ".tsv", ".psv"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Delimited data relies strictly on extensions.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Sibling datasets and data-science logic files acting as disambiguation anchors.
    "discriminators": [".csv", ".tsv", ".py", ".ipynb", ".R", ".m"],
    # EXECUTION SIGNATURES: CSV is purely static data; no shebangs exist.
    "shebangs": [],
    # UPGRADED: Maps to Family 3 (Pure Hash)
    # Rationale: While strictly data, when CSVs *do* contain comments (supported by
    # parsers like Pandas or DuckDB), they almost exclusively use the '#' symbol at the start of a line.
    "lexical_family": "line_exclusive",
    "rules": {},
}
