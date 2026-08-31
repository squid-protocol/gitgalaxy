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
        "target_version": "Protobuf Text Format",
        "last_updated": "2026-03-11",
        "blueprint_version": "6.30",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard Protobuf text and binary message formats used heavily in Google/Bazel ecosystems.
    "extensions": [".pbtxt", ".textproto", ".textpb", ".pb"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: PBTXT strictly relies on its extensions.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Standard .proto schema definitions and Bazel build files acting as disambiguation anchors.
    "discriminators": [".proto", "WORKSPACE", "BUILD.bazel", "BUILD"],
    # EXECUTION SIGNATURES: PBTXT is purely serialized message data; no shebangs exist.
    "shebangs": [],
    # UPGRADED: Maps to Family 3 (Pure Hash)
    # Rationale: While standard .proto schemas use C-style (//) comments, the instantiated
    # Text Format (.pbtxt) strictly uses '#' for comments.
    "lexical_family": "line_exclusive",
    "rules": {},
}
