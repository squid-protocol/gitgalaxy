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
        "target_version": "LLVM MLIR",
        "last_updated": "2026-03-11",
        "blueprint_version": "1.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: The standard dialect and transformation format for MLIR.
    "extensions": [".mlir"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: IR files strictly rely on their extensions.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: LLVM TableGen definitions, core LLVM IR, and CMake configs anchoring the compiler toolchain.
    "discriminators": [".mlir", ".td", ".ll", "CMakeLists.txt"],
    # EXECUTION SIGNATURES: MLIR is ingested by tools like mlir-opt; no shebangs exist.
    "shebangs": [],
    # UPGRADED: Maps to Family 1 (Standard C-Style)
    # Rationale: MLIR intentionally adopts standard LLVM assembly syntax conventions,
    # using '//' exclusively for line comments to maintain C++ ecosystem familiarity.
    "lexical_family": "standard_block",
    "rules": {},
}
