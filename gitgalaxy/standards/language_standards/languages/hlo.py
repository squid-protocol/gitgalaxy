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
        "target_version": "XLA High-Level Optimizer IR",
        "last_updated": "2026-03-11",
        "blueprint_version": "1.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard XLA HLO intermediate representation text formats.
    "extensions": [".hlo"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: IR text files strictly rely on their extensions.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: JAX, TensorFlow, and MLIR toolchain markers acting as disambiguation anchors for ML compilers.
    "discriminators": [".hlo", ".mlir", ".pbtxt", ".py", "BUILD.bazel", "BUILD"],
    # EXECUTION SIGNATURES: HLO is compiler intermediate representation; no shebangs exist.
    "shebangs": [],
    # UPGRADED: Maps to Family 1 (Standard C-Style)
    # Rationale: HLO text format exclusively utilizes '//' for line-level comments, maintaining C++ ecosystem alignment.
    "lexical_family": "standard_block",
    "rules": {},
}
