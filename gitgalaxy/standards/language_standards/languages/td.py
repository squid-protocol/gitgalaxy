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
        "target_version": "LLVM TableGen",
        "last_updated": "2026-03-11",
        "blueprint_version": "1.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard LLVM TableGen record definition files.
    "extensions": [".td"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: TableGen relies entirely on its extensions.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: LLVM/Clang core C++ source files, generated includes (.inc), and CMake configs anchoring the compiler backend.
    "discriminators": [
        ".td",
        ".cpp",
        ".h",
        ".inc",
        "CMakeLists.txt",
        "LLVMBuild.txt",
    ],
    # EXECUTION SIGNATURES: TableGen is processed by the llvm-tblgen backend during build time; no shebangs exist.
    "shebangs": [],
    # UPGRADED: Maps to Family 1 (Standard C-Style)
    # Rationale: TableGen was built to integrate seamlessly into LLVM's C++ codebase, natively supporting '//' and '/* */' comments.
    "lexical_family": "standard_block",
    "rules": {},
}
