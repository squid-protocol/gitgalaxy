# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

from typing import TypedDict


class PrismConfigSchema(TypedDict):
    # Same widening problem as LensConfig above: the mixed str/set/dict
    # values were collapsing to Collection[str] under mypy, breaking every
    # .get()/re.compile() call on PRISM_CONFIG throughout prism.py.
    SHIELD_PATTERN: str
    PYTHON_DOC_PATTERN: str
    PHP_HEREDOC_PATTERN: str
    POSITIONAL_ANCHORS: set[str]
    THRESHOLDS: dict[str, int]


PRISM_CONFIG: PrismConfigSchema = {
    "SHIELD_PATTERN": r'((?<!\\)"(?:\\.|[^"\\])*"|(?<!\\)\'(?:\\.|[^\'\\])*\'|(?<!\\)`(?:\\.|[^`\\])*`)',
    "PYTHON_DOC_PATTERN": r'(?m)^\s*(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')',
    "PHP_HEREDOC_PATTERN": r'<<<[ \t]*([\'"]?)([a-zA-Z_]\w*)\1[ \t]*\r?\n[\s\S]*?\n[ \t]*\2;?',
    "POSITIONAL_ANCHORS": {"*", "C", "c", "/", "!"},
    "THRESHOLDS": {"NESTED_PEEL_LIMIT": 500},
}
