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
        "target_version": "Protocol Buffers 3 (proto3)",
        "last_updated": "2026-03-11",
        "blueprint_version": "1.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard Protocol Buffer schema definition files.
    "extensions": [".proto"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Schemas strictly rely on their extensions.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Buf configuration files, Bazel build files, and generated code markers acting as anchors.
    "discriminators": [
        ".proto",
        "buf.yaml",
        "buf.gen.yaml",
        "WORKSPACE",
        "BUILD.bazel",
        "BUILD",
    ],
    # EXECUTION SIGNATURES: Protobuf is a declarative schema language; no shebangs exist.
    "shebangs": [],
    # UPGRADED: Maps to Family 1 (Standard C-Style)
    # Rationale: Protobuf schemas strictly use standard '//' and '/* */' comments.
    "lexical_family": "standard_block",
    "rules": {},
}
