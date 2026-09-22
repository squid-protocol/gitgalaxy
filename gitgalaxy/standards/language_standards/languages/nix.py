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

from .._shared_patterns import CALLS_OUT_UNSUPPORTED

DEFINITION: dict[str, Any] = {
    "_meta": {"target_version": "Nix Expression Language", "status": "production"},
    "extensions": [".nix"],
    "exact_matches": [],
    "discriminators": ["flake.nix", "default.nix", "shell.nix"],
    "shebangs": [],
    "lexical_family": "line_exclusive",
    "rules": {
        # Epic #3264: Explicitly declare the structural invocation paradigm
        "calls_out": CALLS_OUT_UNSUPPORTED,
    },
}
